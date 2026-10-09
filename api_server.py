"""
FastAPI Server - Connects Frontend to Your Multi-Agent System
Provides REST API endpoints for the chatbot and product operations
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import uvicorn
import asyncio
import os
from datetime import datetime

# Initialize Firebase FIRST before importing agents
from utils.firebase_db import get_db

def init_database():
    """Initialize and verify Firebase database connection"""
    print("\n📊 Initializing Firebase database...")
    try:
        db = get_db()
        print(f"   ✅ Firebase connected (Firestore client ready)")
        return True
    except Exception as e:
        print(f"⚠️  Firebase initialization warning: {e}")
        print("   Make sure Firebase is configured correctly.\n")
        return False

# Initialize Firebase before loading agents
init_database()

# Import your agents
from agents.sales_agent import sales_agent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

# Import your tools directly for product operations
from utils.tools.recommendation_tools import search_products_tool, get_personalized_recommendations
from utils.tools.inventory_tools import check_inventory, reserve_inventory
from utils.tools.payment_tools import create_payment_link, confirm_payment, get_order_status
from utils.tools.loyalty_tools import get_loyalty_status, register_new_customer
from utils.firebase_db import get_all_products, get_product

app = FastAPI(
    title="Retail Sales Agent API",
    description="API for AI-powered retail shopping assistant",
    version="1.0.0"
)

# Get allowed origins from environment or use defaults
import os
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "").split(",") if os.getenv("ALLOWED_ORIGINS") else []
DEFAULT_ORIGINS = [
    "http://localhost:3000", 
    "http://localhost:9002",
    "https://*.vercel.app",  # Vercel preview deployments
]
ALL_ORIGINS = ALLOWED_ORIGINS + DEFAULT_ORIGINS

from config.config import DEFAULT_MODEL

# Enable CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, you may want to restrict this
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
async def health_check():
    return {"status": "ok", "model": DEFAULT_MODEL, "timestamp": datetime.now().isoformat()}

# Session management for chat
session_service = InMemorySessionService()
runner = Runner(
    agent=sales_agent,
    app_name="retail_sales_agent",
    session_service=session_service
)

# Store active sessions
active_sessions = {}

# ==================== MODELS ====================

class ChatMessage(BaseModel):
    role: str  # 'user' or 'model'
    content: str

class ChatRequest(BaseModel):
    history: List[ChatMessage]
    session_id: Optional[str] = None
    customer_id: Optional[str] = None

class ChatResponse(BaseModel):
    message: str
    session_id: str
    agent_name: str = "Sales Agent"  # Which agent responded

class ProductSearchRequest(BaseModel):
    query: str = ""
    category: str = ""
    min_price: Optional[float] = None
    max_price: Optional[float] = None
    limit: int = 20

class AddToCartRequest(BaseModel):
    sku: str
    quantity: int = 1
    customer_id: str
    location: str

class PaymentRequest(BaseModel):
    customer_id: str
    amount: float
    description: str
    items: List[dict]

# ==================== AGENT DETECTION ====================

def detect_agent_from_response(response_text: str, user_input: str) -> str:
    """Detect which agent handled the query based on response tags, content, and user input"""
    response_lower = response_text.lower()
    input_lower = user_input.lower()
    
    # Check for direct agent tags first (most accurate)
    if "[recommendation agent]" in response_lower:
        return "Recommendation Agent"
    if "[inventory agent]" in response_lower:
        return "Inventory Agent"
    if "[payment agent]" in response_lower:
        return "Payment Agent"
    if "[fulfillment agent]" in response_lower:
        return "Fulfillment Agent"
    if "[loyalty agent]" in response_lower:
        return "Loyalty Agent"
    if "[post-purchase agent]" in response_lower:
        return "Post-Purchase Agent"
    if "[sales agent]" in response_lower:
        return "Sales Agent"
    
    # Check for loyalty/promo related keywords
    loyalty_keywords = ['loyalty', 'points', 'tier', 'bronze', 'silver', 'gold', 'platinum', 
                       'promo', 'coupon', 'discount code', 'voucher', 'member', 'reward']
    if any(kw in response_lower for kw in loyalty_keywords) or any(kw in input_lower for kw in ['promo', 'coupon', 'loyalty', 'points', 'discount code']):
        return "Loyalty Agent"
    
    # Check for inventory/stock related keywords
    inventory_keywords = ['stock', 'inventory', 'available', 'out of stock', 'warehouse', 
                         'quantity available', 'in stock', 'units']
    if any(kw in response_lower for kw in inventory_keywords) or any(kw in input_lower for kw in ['stock', 'inventory', 'available']):
        return "Inventory Agent"
    
    # Check for payment related keywords
    payment_keywords = ['payment', 'razorpay', 'pay now', 'checkout', 'transaction', 
                       'payment link', 'upi', 'card payment', 'pay ₹', 'pay rs']
    if any(kw in response_lower for kw in payment_keywords) or any(kw in input_lower for kw in ['pay', 'payment', 'checkout']):
        return "Payment Agent"
    
    # Check for order/fulfillment related keywords
    fulfillment_keywords = ['order status', 'shipping', 'delivery', 'track order', 'dispatched',
                           'order #', 'order id', 'delivered', 'estimated delivery', 'shipment']
    if any(kw in response_lower for kw in fulfillment_keywords) or any(kw in input_lower for kw in ['order status', 'track', 'delivery', 'shipping']):
        return "Fulfillment Agent"
    
    # Check for return/refund related keywords
    post_purchase_keywords = ['return', 'refund', 'exchange', 'cancel order', 'warranty',
                             'return policy', 'refund status', 'return request']
    if any(kw in response_lower for kw in post_purchase_keywords) or any(kw in input_lower for kw in ['return', 'refund', 'cancel', 'exchange']):
        return "Post-Purchase Agent"
    
    # Check for recommendation related keywords
    recommendation_keywords = ['recommend', 'suggestion', 'you might like', 'similar products',
                              'based on your', 'popular', 'trending', 'best seller']
    if any(kw in response_lower for kw in recommendation_keywords) or any(kw in input_lower for kw in ['recommend', 'suggest', 'similar']):
        return "Recommendation Agent"
    
    # Default to Sales Agent
    return "Sales Agent"

# ==================== CHAT ENDPOINT ====================

@app.post("/api/chat", response_model=ChatResponse)
async def chat_with_agent(request: ChatRequest):
    """
    Main chat endpoint - connects to your multi-agent system
    """
    try:
        # Get or create session
        session_id = request.session_id or f"session_{int(datetime.now().timestamp())}_{os.urandom(4).hex()}"
        
        # Always ensure session exists in session_service (handles restarts)
        try:
            # Try to get existing session
            existing_session = await session_service.get_session(
                app_name="retail_sales_agent",
                user_id=request.customer_id or "guest",
                session_id=session_id
            )
            if not existing_session:
                raise ValueError("Session not found")
        except:
            # Create new session if not found
            session = await session_service.create_session(
                app_name="retail_sales_agent",
                user_id=request.customer_id or "guest",
                session_id=session_id
            )
            active_sessions[session_id] = session
        
        # Get the last user message
        if not request.history:
            return ChatResponse(message="Hello! How can I help you today?", session_id=session_id)
        
        last_message = request.history[-1]
        if last_message.role != 'user':
            return ChatResponse(message="I'm ready to help!", session_id=session_id)
        
        user_input = last_message.content
        original_input = user_input  # Save original for agent detection
        
        # Add customer context if available
        if request.customer_id:
            user_input = f"[Customer ID: {request.customer_id}] {user_input}"
        
        # Run the agent
        response_text = ""
        async for event in runner.run_async(
            user_id=request.customer_id or "guest",
            session_id=session_id,
            new_message=types.Content(
                role="user",
                parts=[types.Part(text=user_input)]
            )
        ):
            if hasattr(event, 'content') and event.content:
                parts = getattr(event.content, 'parts', None)
                if parts:
                    for part in parts:
                        if hasattr(part, 'text') and part.text:
                            response_text += part.text
        
        if not response_text:
            response_text = "I'm processing your request. How else can I help?"
        
        # Detect which agent responded
        agent_name = detect_agent_from_response(response_text, original_input)
        
        return ChatResponse(message=response_text, session_id=session_id, agent_name=agent_name)
    
    except Exception as e:
        print(f"Chat error: {e}")
        # Fallback to simple response
        return ChatResponse(
            message=f"I apologize, I encountered an issue. Please try again. Error: {str(e)[:100]}",
            session_id=request.session_id or "error_session"
        )

# ==================== PRODUCT ENDPOINTS ====================

@app.get("/api/products")
async def get_products(
    query: str = "",
    category: str = "",
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    limit: int = 20
):
    """Get products with optional filters"""
    try:
        if query or category or min_price or max_price:
            result = search_products_tool(
                query=query,
                category=category,
                min_price=min_price,
                max_price=max_price,
                max_results=limit
            )
            products = result.get('results', [])
        else:
            products = get_all_products(limit=limit)
        
        # Transform to frontend format
        formatted_products = []
        for p in products:
            formatted_products.append({
                "id": p.get('sku', p.get('id', '')),
                "sku": p.get('sku', ''),
                "name": p.get('name', ''),
                "description": p.get('description', ''),
                "price": p.get('current_price', p.get('price', 0)),
                "originalPrice": p.get('original_price'),
                "rating": p.get('rating', 0),
                "reviewCount": p.get('reviews_count', 0),
                "images": p.get('images', []),
                "category": p.get('category', ''),
                "brand": p.get('brand', ''),
                "stock": p.get('stock', 100),
                "inStock": p.get('stock', 100) > 0
            })
        
        return {"products": formatted_products, "count": len(formatted_products)}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/products/{product_id}")
async def get_product_detail(product_id: str):
    """Get single product by ID/SKU"""
    try:
        product = get_product(product_id)
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")
        
        # Check inventory
        inventory = check_inventory(product_id)
        total_stock = inventory.get('total_stock', 0) if inventory.get('status') == 'success' else 100
        
        return {
            "id": product.get('sku', product_id),
            "sku": product.get('sku', product_id),
            "name": product.get('name', ''),
            "description": product.get('description', ''),
            "price": product.get('current_price', product.get('price', 0)),
            "originalPrice": product.get('original_price'),
            "rating": product.get('rating', 0),
            "reviewCount": product.get('reviews_count', 0),
            "images": product.get('images', []),
            "category": product.get('category', ''),
            "brand": product.get('brand', ''),
            "stock": total_stock,
            "inStock": total_stock > 0,
            "inventory": inventory.get('inventory', [])
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/categories")
async def get_categories():
    """Get all product categories"""
    try:
        products = get_all_products(limit=1000)
        categories = set()
        for p in products:
            if p.get('category'):
                categories.add(p.get('category'))
        
        return {
            "categories": [
                {"name": cat, "slug": cat.lower().replace(' ', '-'), "image": "", "description": f"Browse {cat}"}
                for cat in sorted(categories)
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ==================== CART/INVENTORY ENDPOINTS ====================

@app.post("/api/cart/reserve")
async def reserve_product(request: AddToCartRequest):
    """Reserve inventory for cart"""
    try:
        result = reserve_inventory(
            sku=request.sku,
            quantity=request.quantity,
            location=request.location
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/inventory/{sku}")
async def check_product_inventory(sku: str):
    """Check inventory for a product"""
    try:
        result = check_inventory(sku)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ==================== PAYMENT ENDPOINTS ====================

class RazorpayOrderRequest(BaseModel):
    customer_id: str
    amount: float
    description: str
    receipt: str  # Our internal order ID

@app.post("/api/payment/create-order")
async def create_razorpay_order(request: RazorpayOrderRequest):
    """Create Razorpay order for inline checkout"""
    try:
        import os
        import razorpay
        
        RAZORPAY_KEY_ID = os.getenv('RAZORPAY_KEY_ID')
        RAZORPAY_KEY_SECRET = os.getenv('RAZORPAY_KEY_SECRET')
        
        if not RAZORPAY_KEY_ID or not RAZORPAY_KEY_SECRET:
            raise HTTPException(status_code=500, detail="Razorpay not configured")
        
        client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))
        
        # Create Razorpay order
        order_data = {
            "amount": int(request.amount * 100),  # Convert to paise
            "currency": "INR",
            "receipt": request.receipt,
            "notes": {
                "customer_id": request.customer_id,
                "description": request.description
            }
        }
        
        razorpay_order = client.order.create(order_data)
        
        return {
            "status": "success",
            "order_id": razorpay_order.get("id"),
            "amount": request.amount,
            "currency": "INR",
            "key_id": RAZORPAY_KEY_ID  # Frontend needs this to open checkout
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/payment/verify")
async def verify_razorpay_payment(
    razorpay_order_id: str,
    razorpay_payment_id: str,
    razorpay_signature: str
):
    """Verify Razorpay payment signature"""
    try:
        import os
        import razorpay
        import hmac
        import hashlib
        
        RAZORPAY_KEY_SECRET = os.getenv('RAZORPAY_KEY_SECRET')
        
        # Verify signature
        message = f"{razorpay_order_id}|{razorpay_payment_id}"
        expected_signature = hmac.new(
            RAZORPAY_KEY_SECRET.encode(),
            message.encode(),
            hashlib.sha256
        ).hexdigest()
        
        if expected_signature == razorpay_signature:
            return {"status": "success", "message": "Payment verified"}
        else:
            return {"status": "failed", "message": "Invalid signature"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/payment/create-link")
async def create_payment(request: PaymentRequest):
    """Create Razorpay payment link"""
    try:
        result = create_payment_link(
            customer_id=request.customer_id,
            amount=request.amount,
            description=request.description,
            items=request.items
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/payment/confirm/{order_id}")
async def confirm_order_payment(order_id: str):
    """Confirm payment for an order"""
    try:
        result = confirm_payment(order_id)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/orders/{order_id}")
async def get_order(order_id: str):
    """Get order status"""
    try:
        result = get_order_status(order_id)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ==================== CUSTOMER ENDPOINTS ====================

@app.get("/api/customer/{customer_id}/loyalty")
async def get_customer_loyalty(customer_id: str):
    """Get customer loyalty status"""
    try:
        result = get_loyalty_status(customer_id)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/customer/register")
async def register_customer(
    name: str,
    email: str,
    phone: str,
    location: str
):
    """Register new customer"""
    try:
        result = register_new_customer(name, email, phone, location)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ==================== HEALTH CHECK ====================

@app.get("/api/health")
async def health_check():
    return {"status": "healthy", "service": "Retail Sales Agent API"}

@app.get("/")
async def root():
    return {
        "message": "Retail Sales Agent API",
        "docs": "/docs",
        "health": "/api/health"
    }

if __name__ == "__main__":
    print("🚀 Starting Retail Sales Agent API Server...")
    print("📍 API Docs: http://localhost:8000/docs")
    print("💬 Chat Endpoint: POST http://localhost:8000/api/chat")
    uvicorn.run(app, host="0.0.0.0", port=8000)

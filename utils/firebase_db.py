"""
Firebase Database Module for Retail Sales Agent
Google Firebase Firestore - Cloud NoSQL Database
"""
import os
import sys
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# Import category filter from config
try:
    from config.config import is_allowed_category, ALLOWED_CATEGORIES
except ImportError:
    # Fallback if config not available
    ALLOWED_CATEGORIES = None
    def is_allowed_category(category):
        return True

# Firebase imports
try:
    import firebase_admin
    from firebase_admin import credentials, firestore
    FIREBASE_AVAILABLE = True
except ImportError:
    FIREBASE_AVAILABLE = False
    print("⚠️  Firebase SDK not installed. Run: pip install firebase-admin")

# Global Firestore client
db = None

def init_firebase():
    """Initialize Firebase connection"""
    global db
    
    if not FIREBASE_AVAILABLE:
        raise ImportError("firebase-admin not installed")
    
    # Check if already initialized
    if db is not None:
        return db
    
    try:
        # Try to get existing app
        app = firebase_admin.get_app()
    except ValueError:
        # Initialize new app
        # Option 1: Use service account JSON file
        service_account_path = os.getenv('FIREBASE_SERVICE_ACCOUNT_PATH')
        
        # Option 2: Use service account JSON string (for deployment)
        service_account_json = os.getenv('FIREBASE_SERVICE_ACCOUNT_JSON')
        
        if service_account_path and os.path.exists(service_account_path):
            cred = credentials.Certificate(service_account_path)
            firebase_admin.initialize_app(cred)
            print(f"✅ Firebase initialized from service account file")
        elif service_account_json:
            import json
            cred_dict = json.loads(service_account_json)
            cred = credentials.Certificate(cred_dict)
            firebase_admin.initialize_app(cred)
            print(f"✅ Firebase initialized from environment variable")
        else:
            # Try default credentials (for Google Cloud environments)
            try:
                firebase_admin.initialize_app()
                print(f"✅ Firebase initialized with default credentials")
            except Exception as e:
                raise ValueError(
                    "Firebase credentials not found. Set FIREBASE_SERVICE_ACCOUNT_PATH "
                    "or FIREBASE_SERVICE_ACCOUNT_JSON in .env file"
                )
    
    db = firestore.client()
    print("✅ Firestore database connected")
    return db


def get_db():
    """Get Firestore database client"""
    global db
    if db is None:
        db = init_firebase()
    return db


# ==================== CUSTOMER FUNCTIONS ====================

def get_customer(customer_id: str) -> dict:
    """Get customer by ID"""
    try:
        db = get_db()
        doc = db.collection('customers').document(customer_id).get()
        if doc.exists:
            data = doc.to_dict()
            data['customer_id'] = doc.id
            return data
        return None
    except Exception as e:
        print(f"Error getting customer: {e}")
        return None


def create_customer(customer_data: dict) -> dict:
    """Create a new customer"""
    try:
        db = get_db()
        customer_id = customer_data.get('customer_id')
        if not customer_id:
            # Auto-generate ID
            doc_ref = db.collection('customers').document()
            customer_id = doc_ref.id
            customer_data['customer_id'] = customer_id
        else:
            doc_ref = db.collection('customers').document(customer_id)
        
        customer_data['created_at'] = datetime.now().isoformat()
        doc_ref.set(customer_data)
        return {"status": "success", "customer_id": customer_id}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def update_customer(customer_id: str, updates: dict) -> dict:
    """Update customer data"""
    try:
        db = get_db()
        db.collection('customers').document(customer_id).update(updates)
        return {"status": "success"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def get_all_customers(limit: int = 100) -> list:
    """Get all customers"""
    try:
        db = get_db()
        docs = db.collection('customers').limit(limit).stream()
        customers = []
        for doc in docs:
            data = doc.to_dict()
            data['customer_id'] = doc.id
            customers.append(data)
        return customers
    except Exception as e:
        print(f"Error getting customers: {e}")
        return []


# ==================== PRODUCT FUNCTIONS ====================

def get_all_products(limit: int = 100, filter_categories: bool = True) -> list:
    """Get all products from Firebase
    
    Args:
        limit: Maximum number of products to return
        filter_categories: If True, only return products from allowed categories (clothing/fashion)
    """
    try:
        db = get_db()
        # Fetch more to account for filtering
        fetch_limit = limit * 3 if filter_categories and ALLOWED_CATEGORIES else limit
        docs = db.collection('products').limit(fetch_limit).stream()
        products = []
        for doc in docs:
            data = doc.to_dict()
            data['sku'] = doc.id
            data['id'] = doc.id  # Add id field for frontend compatibility
            
            # Apply category filter for fashion/clothing focus
            if filter_categories and ALLOWED_CATEGORIES:
                if not is_allowed_category(data.get('category', '')):
                    continue
            
            products.append(data)
            if len(products) >= limit:
                break
        return products
    except Exception as e:
        print(f"Error getting all products: {e}")
        return []


# In-memory cache for ultra-fast product lookups
import time
_PRODUCTS_CACHE = None
_PRODUCTS_CACHE_TIME = 0
_CACHE_TTL_SECONDS = 300  # 5 minutes

def get_cached_products_list():
    """Retrieve all products from in-memory cache, populating it if empty or expired"""
    global _PRODUCTS_CACHE, _PRODUCTS_CACHE_TIME
    now = time.time()
    if _PRODUCTS_CACHE is not None and (now - _PRODUCTS_CACHE_TIME) < _CACHE_TTL_SECONDS:
        return _PRODUCTS_CACHE
    try:
        db = get_db()
        docs = db.collection('products').stream()
        products = []
        for doc in docs:
            d = doc.to_dict()
            d['sku'] = doc.id
            d['id'] = doc.id
            products.append(d)
        _PRODUCTS_CACHE = products
        _PRODUCTS_CACHE_TIME = now
        return _PRODUCTS_CACHE
    except Exception as e:
        print(f"Error fetching products for cache: {e}")
        return _PRODUCTS_CACHE or []


def get_product(sku: str) -> dict:
    """Get product by SKU with cache acceleration"""
    try:
        # Check cache first for 0ms lookup
        cached = get_cached_products_list()
        for p in cached:
            if p.get('sku') == sku or p.get('id') == sku:
                return p
        
        # Fallback to direct DB read
        db = get_db()
        doc = db.collection('products').document(sku).get()
        if doc.exists:
            data = doc.to_dict()
            data['sku'] = doc.id
            data['id'] = doc.id
            return data
        return None
    except Exception as e:
        print(f"Error getting product: {e}")
        return None


def search_products(query: str = "", category: str = "", min_price: float = None, 
                   max_price: float = None, limit: int = 10, filter_categories: bool = True) -> list:
    """Search products by name, category, price range with in-memory acceleration"""
    try:
        docs = get_cached_products_list()
        results = []
        query_lower = query.lower().strip() if query else ""
        category_lower = category.lower().strip() if category else ""
        
        # Split query into words for better matching
        query_words = query_lower.split() if query_lower else []
        
        for data in docs:
            # Apply category filter for fashion/clothing focus
            if filter_categories and ALLOWED_CATEGORIES:
                if not is_allowed_category(data.get('category', '')):
                    continue
            
            name_lower = data.get('name', '').lower()
            cat_lower = data.get('category', '').lower()
            
            # Check if ANY query word matches in name or category
            if query_words:
                name_match = any(word in name_lower for word in query_words)
                cat_query_match = any(word in cat_lower for word in query_words)
                query_match = name_match or cat_query_match
            else:
                query_match = True
            
            # Category filter
            category_match = not category_lower or category_lower in cat_lower
            
            price = float(data.get('current_price', data.get('price', 0)))
            min_match = min_price is None or price >= min_price
            max_match = max_price is None or price <= max_price
            
            if query_match and category_match and min_match and max_match:
                results.append({
                    "sku": data['sku'],
                    "name": data.get('name', ''),
                    "category": data.get('category', ''),
                    "price": price,
                    "rating": float(data.get('rating', 0)),
                    "reviews": data.get('reviews_count', 0)
                })
        
        # Sort by rating then reviews
        results.sort(key=lambda x: (x['rating'], x['reviews']), reverse=True)
        return results[:limit]
    except Exception as e:
        print(f"Error searching products: {e}")
        return []


def create_product(product_data: dict) -> dict:
    """Create a new product"""
    try:
        db = get_db()
        sku = product_data.get('sku')
        if not sku:
            return {"status": "error", "message": "SKU required"}
        
        product_data['created_at'] = datetime.now().isoformat()
        db.collection('products').document(sku).set(product_data)
        return {"status": "success", "sku": sku}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def get_products_count() -> int:
    """Get total products count"""
    try:
        db = get_db()
        # Firestore doesn't have direct count, so we use aggregation
        docs = db.collection('products').stream()
        return sum(1 for _ in docs)
    except Exception as e:
        return 0


# ==================== INVENTORY FUNCTIONS ====================

def get_inventory(sku: str, location: str = None) -> list:
    """Get inventory for a product"""
    try:
        from google.cloud.firestore_v1.base_query import FieldFilter
        db = get_db()
        query = db.collection('inventory').where(filter=FieldFilter('sku', '==', sku))
        
        if location:
            query = query.where(filter=FieldFilter('location', '==', location))
        
        docs = query.stream()
        results = []
        for doc in docs:
            data = doc.to_dict()
            results.append({
                "location": data.get('location', ''),
                "quantity": data.get('quantity', 0)
            })
        return results
    except Exception as e:
        print(f"Error getting inventory: {e}")
        return []


def update_inventory(sku: str, location: str, quantity: int) -> dict:
    """Update or create inventory record"""
    try:
        db = get_db()
        # Use composite key
        doc_id = f"{sku}_{location.replace(' ', '_')}"
        db.collection('inventory').document(doc_id).set({
            'sku': sku,
            'location': location,
            'quantity': quantity,
            'last_updated': datetime.now().isoformat()
        })
        return {"status": "success"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


# ==================== ORDER FUNCTIONS ====================

def create_order(order_data: dict) -> dict:
    """Create a new order"""
    try:
        db = get_db()
        order_id = order_data.get('order_id')
        if not order_id:
            import random
            order_id = f"ORD{random.randint(100000, 999999)}"
            order_data['order_id'] = order_id
        
        order_data['created_at'] = datetime.now().isoformat()
        order_data['status'] = order_data.get('status', 'pending')
        
        db.collection('orders').document(order_id).set(order_data)
        return {"status": "success", "order_id": order_id}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def get_order(order_id: str) -> dict:
    """Get order by ID"""
    try:
        db = get_db()
        doc = db.collection('orders').document(order_id).get()
        if doc.exists:
            data = doc.to_dict()
            data['order_id'] = doc.id
            return data
        return None
    except Exception as e:
        print(f"Error getting order: {e}")
        return None


def update_order(order_id: str, updates: dict) -> dict:
    """Update order"""
    try:
        db = get_db()
        db.collection('orders').document(order_id).update(updates)
        return {"status": "success"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def get_customer_orders(customer_id: str, limit: int = 10) -> list:
    """Get orders for a customer"""
    try:
        db = get_db()
        docs = db.collection('orders')\
            .where('customer_id', '==', customer_id)\
            .order_by('created_at', direction=firestore.Query.DESCENDING)\
            .limit(limit)\
            .stream()
        
        orders = []
        for doc in docs:
            data = doc.to_dict()
            data['order_id'] = doc.id
            orders.append(data)
        return orders
    except Exception as e:
        print(f"Error getting customer orders: {e}")
        return []


def get_recent_orders(limit: int = 10) -> list:
    """Get recent orders"""
    try:
        db = get_db()
        docs = db.collection('orders')\
            .order_by('created_at', direction=firestore.Query.DESCENDING)\
            .limit(limit)\
            .stream()
        
        orders = []
        for doc in docs:
            data = doc.to_dict()
            data['order_id'] = doc.id
            orders.append(data)
        return orders
    except Exception as e:
        print(f"Error getting recent orders: {e}")
        return []


# ==================== PROMOTIONS FUNCTIONS ====================

def get_promotion(promo_code: str) -> dict:
    """Get promotion by code"""
    try:
        db = get_db()
        doc = db.collection('promotions').document(promo_code.upper()).get()
        if doc.exists:
            data = doc.to_dict()
            data['promo_code'] = doc.id
            return data
        return None
    except Exception as e:
        print(f"Error getting promotion: {e}")
        return None


def create_promotion(promo_data: dict) -> dict:
    """Create a promotion"""
    try:
        db = get_db()
        promo_code = promo_data.get('promo_code', '').upper()
        if not promo_code:
            return {"status": "error", "message": "Promo code required"}
        
        db.collection('promotions').document(promo_code).set(promo_data)
        return {"status": "success", "promo_code": promo_code}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def get_promotions() -> list:
    """Get all active promotions"""
    try:
        db = get_db()
        docs = db.collection('promotions').stream()
        promos = []
        for doc in docs:
            data = doc.to_dict()
            data['promo_code'] = doc.id
            promos.append(data)
        return promos
    except Exception as e:
        return []


# ==================== TRANSACTION FUNCTIONS ====================

def create_transaction(transaction_data: dict) -> dict:
    """Create a transaction record"""
    try:
        db = get_db()
        transaction_id = transaction_data.get('transaction_id')
        if not transaction_id:
            import random
            transaction_id = f"TXN{random.randint(100000000, 999999999)}"
            transaction_data['transaction_id'] = transaction_id
        
        transaction_data['created_at'] = datetime.now().isoformat()
        db.collection('transactions').document(transaction_id).set(transaction_data)
        return {"status": "success", "transaction_id": transaction_id}
    except Exception as e:
        return {"status": "error", "message": str(e)}


# ==================== HELPER FUNCTIONS ====================

def execute_query(query_func, *args, **kwargs):
    """Execute a query function (compatibility wrapper)"""
    return query_func(*args, **kwargs)


# Initialize on import
print("✅ Firebase database module loaded")

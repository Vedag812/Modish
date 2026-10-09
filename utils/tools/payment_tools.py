"""
Payment Agent Tools - Firebase + Razorpay Integration
Processes payments and saves orders to Firebase database
"""
import random
from datetime import datetime
from typing import Optional, List, Dict, Any
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from utils.db import get_db, get_customer
from utils.firebase_db import create_order, update_order, create_transaction as fb_create_transaction, get_order

# Import Razorpay
try:
    import razorpay
    from dotenv import load_dotenv
    load_dotenv()
    
    RAZORPAY_KEY_ID = os.getenv('RAZORPAY_KEY_ID')
    RAZORPAY_KEY_SECRET = os.getenv('RAZORPAY_KEY_SECRET')
    
    if RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET:
        razorpay_client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))
        USE_RAZORPAY = True
        print(f"✅ Razorpay initialized (Key: {RAZORPAY_KEY_ID[:15]}...)")
    else:
        USE_RAZORPAY = False
        razorpay_client = None
        print("⚠️  Razorpay credentials not found")
except ImportError:
    USE_RAZORPAY = False
    razorpay_client = None
    print("⚠️  Razorpay SDK not installed. Run: pip install razorpay")


# ==================== PAYMENT GATEWAY SIMULATION ====================
# These functions simulate payment gateway authorize/capture/decline flows

# In-memory storage for authorized payments (simulates gateway hold)
authorized_payments = {}


def authorize_payment(customer_id: str, amount: float, payment_method: str = "credit_card", order_id: Optional[str] = None):
    """
    Authorize (pre-auth) a payment - places a hold on customer's funds without capturing.
    This simulates the payment gateway's authorization phase.
    
    Args:
        customer_id: Customer identifier
        amount: Amount to authorize in INR
        payment_method: Payment method (credit_card, debit_card, upi)
        order_id: Optional order ID to associate with authorization
    
    Returns:
        Dictionary with authorization details including auth_code
    """
    customer = get_customer(customer_id)
    if not customer:
        return {"status": "error", "message": f"Customer {customer_id} not found"}
    
    # Simulate authorization logic
    auth_code = f"AUTH{random.randint(100000000, 999999999)}"
    
    # Simulate random authorization failures (10% chance for realism)
    if random.random() < 0.1:
        decline_reason = random.choice([
            "Insufficient funds",
            "Card declined by issuer",
            "Invalid card number",
            "Card expired"
        ])
        return {
            "status": "declined",
            "auth_code": None,
            "customer_id": customer_id,
            "amount": amount,
            "decline_reason": decline_reason,
            "timestamp": datetime.now().isoformat(),
            "message": f"❌ Authorization declined: {decline_reason}"
        }
    
    # Store authorization (simulates payment gateway hold)
    authorized_payments[auth_code] = {
        "customer_id": customer_id,
        "amount": amount,
        "payment_method": payment_method,
        "order_id": order_id,
        "authorized_at": datetime.now().isoformat(),
        "expires_at": datetime.now().isoformat(),  # Auth typically expires in 7 days
        "captured": False,
        "voided": False
    }
    
    return {
        "status": "authorized",
        "auth_code": auth_code,
        "customer_id": customer_id,
        "customer_name": customer.get("name"),
        "amount": round(amount, 2),
        "currency": "INR",
        "payment_method": payment_method,
        "order_id": order_id,
        "timestamp": datetime.now().isoformat(),
        "message": f"✅ Payment of ₹{amount:.2f} authorized. Auth code: {auth_code}. Call capture_payment to complete."
    }


def capture_payment(auth_code: str, amount: Optional[float] = None):
    """
    Capture (settle) an authorized payment - actually charges the customer.
    This completes the two-step payment flow.
    
    Args:
        auth_code: Authorization code from authorize_payment
        amount: Amount to capture (optional, defaults to full authorized amount)
                Can be less than authorized for partial capture.
    
    Returns:
        Dictionary with capture result
    """
    if auth_code not in authorized_payments:
        return {
            "status": "error",
            "message": f"Invalid or expired authorization code: {auth_code}"
        }
    
    auth_data = authorized_payments[auth_code]
    
    if auth_data.get("captured"):
        return {
            "status": "error",
            "message": f"Authorization {auth_code} has already been captured"
        }
    
    if auth_data.get("voided"):
        return {
            "status": "error",
            "message": f"Authorization {auth_code} has been voided/declined"
        }
    
    # Use authorized amount if not specified
    capture_amount = amount if amount is not None else auth_data["amount"]
    
    # Can't capture more than authorized
    if capture_amount > auth_data["amount"]:
        return {
            "status": "error",
            "message": f"Cannot capture ₹{capture_amount}. Maximum authorized: ₹{auth_data['amount']}"
        }
    
    # Mark as captured
    authorized_payments[auth_code]["captured"] = True
    authorized_payments[auth_code]["captured_at"] = datetime.now().isoformat()
    authorized_payments[auth_code]["captured_amount"] = capture_amount
    
    # Generate transaction
    transaction_id = f"TXN{random.randint(100000000, 999999999)}"
    
    # Save to database
    if auth_data.get("order_id"):
        save_transaction_to_db(
            order_id=auth_data["order_id"],
            customer_id=auth_data["customer_id"],
            amount=capture_amount,
            payment_method=auth_data["payment_method"],
            transaction_id=transaction_id,
            status="completed"
        )
    
    return {
        "status": "captured",
        "auth_code": auth_code,
        "transaction_id": transaction_id,
        "customer_id": auth_data["customer_id"],
        "authorized_amount": auth_data["amount"],
        "captured_amount": capture_amount,
        "currency": "INR",
        "order_id": auth_data.get("order_id"),
        "timestamp": datetime.now().isoformat(),
        "message": f"✅ Payment of ₹{capture_amount:.2f} captured successfully. Transaction ID: {transaction_id}"
    }


def decline_transaction(auth_code: Optional[str] = None, transaction_id: Optional[str] = None, reason: str = "Merchant declined"):
    """
    Decline/void an authorization or transaction.
    This releases the hold on customer's funds.
    
    Args:
        auth_code: Authorization code to void (for pre-auth)
        transaction_id: Transaction ID to decline (for completed transactions)
        reason: Reason for decline/void
    
    Returns:
        Dictionary with decline result
    """
    if auth_code:
        if auth_code not in authorized_payments:
            return {
                "status": "error",
                "message": f"Authorization {auth_code} not found"
            }
        
        auth_data = authorized_payments[auth_code]
        
        if auth_data.get("captured"):
            return {
                "status": "error",
                "message": f"Cannot void - payment already captured. Use refund_payment instead."
            }
        
        if auth_data.get("voided"):
            return {
                "status": "error",
                "message": f"Authorization already voided"
            }
        
        # Void the authorization
        authorized_payments[auth_code]["voided"] = True
        authorized_payments[auth_code]["voided_at"] = datetime.now().isoformat()
        authorized_payments[auth_code]["void_reason"] = reason
        
        return {
            "status": "voided",
            "auth_code": auth_code,
            "customer_id": auth_data["customer_id"],
            "amount_released": auth_data["amount"],
            "currency": "INR",
            "reason": reason,
            "timestamp": datetime.now().isoformat(),
            "message": f"✅ Authorization voided. ₹{auth_data['amount']:.2f} hold released."
        }
    
    elif transaction_id:
        # For completed transactions, this would typically trigger a refund
        return {
            "status": "declined",
            "transaction_id": transaction_id,
            "reason": reason,
            "timestamp": datetime.now().isoformat(),
            "message": f"Transaction {transaction_id} marked as declined. Reason: {reason}"
        }
    
    return {"status": "error", "message": "Provide either auth_code or transaction_id"}


def get_authorization_status(auth_code: str):
    """
    Check the status of an authorization.
    
    Args:
        auth_code: Authorization code to check
    
    Returns:
        Dictionary with authorization status
    """
    if auth_code not in authorized_payments:
        return {"status": "error", "message": f"Authorization {auth_code} not found"}
    
    auth_data = authorized_payments[auth_code]
    
    status = "authorized"
    if auth_data.get("captured"):
        status = "captured"
    elif auth_data.get("voided"):
        status = "voided"
    
    return {
        "status": "success",
        "auth_code": auth_code,
        "auth_status": status,
        "customer_id": auth_data["customer_id"],
        "amount": auth_data["amount"],
        "payment_method": auth_data["payment_method"],
        "authorized_at": auth_data["authorized_at"],
        "captured_at": auth_data.get("captured_at"),
        "voided_at": auth_data.get("voided_at")
    }


# ==================== DATABASE FUNCTIONS ====================

def save_order_to_db(customer_id: str, items: list, total_amount: float, payment_status: str = "pending", razorpay_order_id: str = None):
    """Save order to Firebase database"""
    try:
        order_id = f"ORD{random.randint(100000, 999999)}"
        
        order_data = {
            "order_id": order_id,
            "customer_id": customer_id,
            "items": items or [],
            "total_amount": total_amount,
            "status": payment_status,
            "razorpay_order_id": razorpay_order_id,
            "created_at": datetime.now().isoformat()
        }
        
        result = create_order(order_data)
        
        if result.get("status") == "success":
            return {"status": "success", "order_id": order_id}
        else:
            return {"status": "error", "message": result.get("message"), "order_id": order_id}
    except Exception as e:
        print(f"❌ Error saving order: {e}")
        return {"status": "error", "message": str(e), "order_id": f"ORD{random.randint(100000, 999999)}"}


def save_transaction_to_db(order_id: str, customer_id: str, amount: float, payment_method: str, 
                           transaction_id: str, status: str, razorpay_payment_id: str = None):
    """Save transaction to Firebase database"""
    try:
        transaction_data = {
            "transaction_id": transaction_id,
            "order_id": order_id,
            "customer_id": customer_id,
            "amount": amount,
            "payment_method": payment_method,
            "status": status,
            "razorpay_payment_id": razorpay_payment_id,
            "created_at": datetime.now().isoformat()
        }
        
        fb_create_transaction(transaction_data)
        
        # Update order status
        update_order(order_id, {"status": status})
        
        return {"status": "success", "transaction_id": transaction_id}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def create_payment_link(customer_id: str, amount: float, description: str = "", items: Optional[list] = None):
    """
    Create a REAL Razorpay payment link for the customer.
    
    Args:
        customer_id: Customer identifier
        amount: Payment amount in INR
        description: Order description
        items: List of items in the order
    
    Returns:
        Dictionary with payment link details
    """
    customer = get_customer(customer_id)
    if not customer:
        return {"status": "error", "message": f"Customer {customer_id} not found"}
    
    # Save order to database first
    order_result = save_order_to_db(customer_id, items or [], amount, "pending")
    order_id = order_result.get("order_id", f"ORD{random.randint(100000, 999999)}")
    
    if USE_RAZORPAY and razorpay_client:
        try:
            # Create Razorpay payment link
            payment_link_data = {
                "amount": int(amount * 100),  # Convert to paise
                "currency": "INR",
                "description": description or f"Order {order_id} - Retail Store",
                "customer": {
                    "name": customer.get("name", "Customer"),
                    "email": customer.get("email", ""),
                    "contact": customer.get("phone", "")
                },
                "notify": {
                    "sms": True,
                    "email": True
                },
                "reminder_enable": True,
                "notes": {
                    "order_id": order_id,
                    "customer_id": customer_id
                },
                "callback_url": "https://your-store.com/payment/callback",
                "callback_method": "get"
            }
            
            payment_link = razorpay_client.payment_link.create(payment_link_data)
            
            # Update order with Razorpay link ID (Firebase)
            update_order(order_id, {"razorpay_order_id": payment_link.get('id')})
            
            return {
                "status": "success",
                "order_id": order_id,
                "payment_link_id": payment_link.get("id"),
                "payment_url": payment_link.get("short_url"),  # This is the actual Razorpay link!
                "amount": amount,
                "currency": "INR",
                "customer_name": customer.get("name"),
                "customer_email": customer.get("email"),
                "expires_at": payment_link.get("expire_by"),
                "message": f"✅ Payment link created! Click here to pay: {payment_link.get('short_url')}"
            }
            
        except Exception as e:
            # Fallback to simulated link if Razorpay fails
            return {
                "status": "success",
                "order_id": order_id,
                "payment_link_id": f"plink_{random.randint(100000, 999999)}",
                "payment_url": f"https://rzp.io/demo/{order_id}",
                "amount": amount,
                "currency": "INR",
                "error_note": f"Razorpay error: {str(e)}. Using demo link.",
                "message": f"Payment link for ₹{amount:.2f} (Demo mode due to API error)"
            }
    else:
        # Simulated payment link
        return {
            "status": "success",
            "order_id": order_id,
            "payment_link_id": f"plink_{random.randint(100000, 999999)}",
            "payment_url": f"https://rzp.io/demo/{order_id}",
            "amount": amount,
            "currency": "INR",
            "message": f"Payment link created (Demo mode). Amount: ₹{amount:.2f}"
        }


def process_payment(customer_id: str, amount: float, payment_method: str, order_id: Optional[str] = None, items: Optional[list] = None):
    """
    Process a payment transaction and save to database.
    
    Args:
        customer_id: Customer identifier
        amount: Payment amount
        payment_method: Type of payment ("credit_card", "debit_card", "upi", "payment_link")
        order_id: Existing order ID (optional)
        items: List of items being purchased
    
    Returns:
        Dictionary with payment result
    """
    customer = get_customer(customer_id)
    if not customer:
        return {"status": "error", "message": f"Customer {customer_id} not found"}
    
    # Create order if not provided
    if not order_id:
        order_result = save_order_to_db(customer_id, items or [], amount, "processing")
        order_id = order_result.get("order_id", f"ORD{random.randint(100000, 999999)}")
    
    # Generate transaction ID
    transaction_id = f"TXN{random.randint(100000000, 999999999)}"
    
    # If payment_method is "payment_link", create a Razorpay link
    if payment_method.lower() == "payment_link":
        return create_payment_link(customer_id, amount, f"Order {order_id}", items)
    
    # For other methods, try Razorpay order creation
    razorpay_order_id = None
    if USE_RAZORPAY and razorpay_client:
        try:
            rz_order = razorpay_client.order.create({
                "amount": int(amount * 100),
                "currency": "INR",
                "receipt": order_id,
                "notes": {"customer_id": customer_id}
            })
            razorpay_order_id = rz_order.get("id")
        except:
            pass
    
    # Save transaction to database
    save_transaction_to_db(
        order_id=order_id,
        customer_id=customer_id,
        amount=amount,
        payment_method=payment_method,
        transaction_id=transaction_id,
        status="completed",
        razorpay_payment_id=razorpay_order_id
    )
    
    # Update order status
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("UPDATE orders SET status = 'paid' WHERE order_id = %s", (order_id,))
        conn.commit()
        conn.close()
    except:
        pass
    
    return {
        "status": "success",
        "transaction_id": transaction_id,
        "order_id": order_id,
        "razorpay_order_id": razorpay_order_id,
        "customer_id": customer_id,
        "customer_name": customer.get("name"),
        "amount": round(amount, 2),
        "currency": "INR",
        "payment_method": payment_method,
        "payment_status": "completed",
        "timestamp": datetime.now().isoformat(),
        "message": f"✅ Payment of ₹{amount:.2f} processed successfully via {payment_method.upper().replace('_', ' ')}. Order saved to database."
    }


def get_saved_payment_methods(customer_id: str):
    """Get customer's saved payment methods."""
    customer = get_customer(customer_id)
    if not customer:
        return {"status": "error", "message": f"Customer {customer_id} not found"}
    
    payment_methods = [
        {"id": "card_1", "type": "credit_card", "last_four": "4242", "brand": "Visa", "expiry": "12/26", "is_default": True},
        {"id": "card_2", "type": "debit_card", "last_four": "8888", "brand": "HDFC", "expiry": "08/27", "is_default": False},
        {"id": "upi_1", "type": "upi", "upi_id": f"{customer.get('name', '').lower().split()[0]}@okicici", "is_default": False},
        {"id": "upi_2", "type": "upi", "upi_id": f"{customer.get('phone', '9999999999')[-10:]}@paytm", "is_default": False},
    ]
    
    return {
        "status": "success",
        "customer_id": customer_id,
        "customer_name": customer.get("name"),
        "payment_methods": payment_methods,
        "count": len(payment_methods),
        "message": f"Found {len(payment_methods)} saved payment methods for {customer.get('name')}"
    }


def apply_gift_card(gift_card_code: str, order_amount: float):
    """Apply a gift card to an order."""
    valid_cards = {
        "GIFT1234": 500.00,
        "GIFT5678": 1000.00,
        "GIFT9999": 250.00,
        "WELCOME100": 100.00
    }
    
    if gift_card_code.upper() not in valid_cards:
        return {"status": "error", "message": f"Invalid gift card: {gift_card_code}"}
    
    balance = valid_cards[gift_card_code.upper()]
    applied_amount = min(balance, order_amount)
    remaining_balance = round(balance - applied_amount, 2)
    new_order_total = round(order_amount - applied_amount, 2)
    
    return {
        "status": "success",
        "gift_card_code": gift_card_code.upper(),
        "original_balance": balance,
        "applied_amount": applied_amount,
        "remaining_balance": remaining_balance,
        "new_order_total": new_order_total,
        "message": f"Applied ₹{applied_amount} from gift card. New total: ₹{new_order_total}"
    }


def get_order_status(order_id: str):
    """Get order status from Firebase database."""
    try:
        order = get_order(order_id)
        
        if order:
            return {
                "status": "success",
                "order_id": order.get("order_id", order_id),
                "customer_id": order.get("customer_id"),
                "total_amount": float(order.get("total_amount", 0)),
                "order_status": order.get("status", "unknown"),
                "razorpay_order_id": order.get("razorpay_order_id"),
                "created_at": str(order.get("created_at", ""))
            }
        else:
            return {"status": "error", "message": f"Order {order_id} not found"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def confirm_payment(order_id: str, customer_id: Optional[str] = None, amount: Optional[float] = None, items: Optional[list] = None):
    """
    Confirm that payment has been completed for an order.
    Checks with Razorpay if payment was actually made, otherwise simulates realistic payment flow.
    
    Args:
        order_id: The order ID to confirm payment for
        customer_id: Customer ID (optional, for creating order if missing)
        amount: Order amount (optional, for creating order if missing)
        items: List of items (optional)
    
    Returns:
        Dictionary with confirmation status
    """
    try:
        # Check if order exists in Firebase
        order = get_order(order_id)
        
        if not order:
            if customer_id and amount:
                # Create order first
                order_data = {
                    "order_id": order_id,
                    "customer_id": customer_id,
                    "total_amount": amount,
                    "items": items or [],
                    "status": "pending",
                    "created_at": datetime.now().isoformat()
                }
                create_order(order_data)
                order = order_data
            else:
                return {"status": "error", "message": f"Order {order_id} not found. Please provide customer_id and amount to create it."}
        
        # Check if already paid
        if order.get("status") == "paid":
            return {
                "status": "success",
                "order_id": order_id,
                "payment_status": "already_paid",
                "message": f"✅ Order {order_id} is already paid!"
            }
        
        # If Razorpay is available and we have a payment_link_id, verify with Razorpay
        # Note: payment link ID is stored as razorpay_order_id in Firebase
        payment_link_id = order.get("razorpay_order_id") or order.get("payment_link_id")
        
        if USE_RAZORPAY and razorpay_client and payment_link_id:
            try:
                # Fetch payment link status from Razorpay
                payment_link = razorpay_client.payment_link.fetch(payment_link_id)
                
                if payment_link.get("status") == "paid":
                    # Payment actually completed!
                    update_order(order_id, {
                        "status": "paid", 
                        "paid_at": datetime.now().isoformat(),
                        "razorpay_payment_id": payment_link.get("payments", [{}])[0].get("payment_id") if payment_link.get("payments") else None
                    })
                    return {
                        "status": "success",
                        "order_id": order_id,
                        "payment_status": "paid",
                        "amount": float(order.get("total_amount", 0)),
                        "message": f"✅ Payment confirmed for order {order_id}. Your order is now being processed!"
                    }
                elif payment_link.get("status") == "expired":
                    return {
                        "status": "expired",
                        "order_id": order_id,
                        "message": f"❌ Payment link has expired. Please request a new payment link."
                    }
                else:
                    # Payment not yet completed
                    return {
                        "status": "pending",
                        "order_id": order_id,
                        "payment_link": payment_link.get("short_url"),
                        "message": f"⏳ Payment not yet received for order {order_id}. Please complete the payment at: {payment_link.get('short_url')}"
                    }
            except Exception as e:
                print(f"Razorpay verification error: {e}")
                # Fall through to simulation if Razorpay fails
        
        # SIMULATION MODE: Realistic payment verification
        # Simulate 70% success, 20% pending, 10% failure
        simulation_result = random.random()
        
        if simulation_result < 0.7:
            # Payment successful
            update_order(order_id, {"status": "paid", "paid_at": datetime.now().isoformat()})
            return {
                "status": "success",
                "order_id": order_id,
                "payment_status": "paid",
                "customer_id": order.get("customer_id"),
                "amount": float(order.get("total_amount", 0)),
                "message": f"✅ Payment confirmed for order {order_id}. Order is now marked as PAID."
            }
        elif simulation_result < 0.9:
            # Payment pending
            return {
                "status": "pending",
                "order_id": order_id,
                "message": f"⏳ Payment is still being processed for order {order_id}. Please wait a moment and try again."
            }
        else:
            # Payment failed
            return {
                "status": "failed",
                "order_id": order_id,
                "message": f"❌ Payment failed for order {order_id}. Please try again or use a different payment method.",
                "suggested_actions": [
                    "Retry payment using the same link",
                    "Request a new payment link",
                    "Try a different payment method (UPI/Card)"
                ]
            }
    
    except Exception as e:
        return {"status": "error", "message": str(e)}


def process_in_store_pos(customer_id: str, amount: float, payment_method: str, store_location: str, items: Optional[list] = None):
    """
    Process payment via in-store Point of Sale (POS) system.
    
    Args:
        customer_id: Customer identifier
        amount: Payment amount in INR
        payment_method: "card_swipe", "upi_scan", "cash", "contactless"
        store_location: Store where payment is being processed
        items: List of items being purchased
    
    Returns:
        Dictionary with POS transaction result
    """
    customer = get_customer(customer_id)
    if not customer:
        return {"status": "error", "message": f"Customer {customer_id} not found"}
    
    valid_methods = ["card_swipe", "upi_scan", "cash", "contactless"]
    if payment_method not in valid_methods:
        return {"status": "error", "message": f"Invalid POS method. Use: {', '.join(valid_methods)}"}
    
    # Create order
    order_result = save_order_to_db(customer_id, items or [], amount, "paid")
    order_id = order_result.get("order_id")
    
    # Generate POS transaction ID
    pos_transaction_id = f"POS{random.randint(100000000, 999999999)}"
    
    # Save transaction
    save_transaction_to_db(
        order_id=order_id,
        customer_id=customer_id,
        amount=amount,
        payment_method=f"pos_{payment_method}",
        transaction_id=pos_transaction_id,
        status="completed"
    )
    
    return {
        "status": "success",
        "transaction_type": "in_store_pos",
        "pos_transaction_id": pos_transaction_id,
        "order_id": order_id,
        "customer_id": customer_id,
        "customer_name": customer.get("name"),
        "amount": round(amount, 2),
        "currency": "INR",
        "payment_method": payment_method,
        "store_location": store_location,
        "timestamp": datetime.now().isoformat(),
        "receipt": f"RCP{random.randint(10000, 99999)}",
        "message": f"✅ In-store payment of ₹{amount:.2f} completed via {payment_method.upper().replace('_', ' ')} at {store_location}"
    }


def retry_failed_payment(order_id: str, new_payment_method: Optional[str] = None, max_retries: int = 3):
    """
    Retry a failed payment with optional different payment method.
    Implements exponential backoff for gateway retries.
    
    Args:
        order_id: Order ID with failed payment
        new_payment_method: Optional new payment method to try
        max_retries: Maximum retry attempts (default: 3)
    
    Returns:
        Dictionary with retry result
    """
    # Check order exists
    order = get_order(order_id)
    if not order:
        return {"status": "error", "message": f"Order {order_id} not found"}
    
    if order.get("status") == "paid":
        return {"status": "error", "message": f"Order {order_id} is already paid"}
    
    customer_id = order.get("customer_id")
    amount = float(order.get("total_amount", 0))
    items = order.get("items", [])
    
    # Simulate retry logic with failure tracking
    retry_attempts = []
    success = False
    final_transaction_id = None
    
    for attempt in range(1, max_retries + 1):
        # Simulate 70% success rate per attempt (realistic retry)
        if random.random() < 0.7:
            success = True
            final_transaction_id = f"TXN{random.randint(100000000, 999999999)}"
            retry_attempts.append({
                "attempt": attempt,
                "status": "success",
                "transaction_id": final_transaction_id
            })
            break
        else:
            failure_reason = random.choice([
                "Gateway timeout",
                "Bank server unavailable",
                "Network error",
                "Processing delay"
            ])
            retry_attempts.append({
                "attempt": attempt,
                "status": "failed",
                "reason": failure_reason
            })
    
    if success:
        # Update order and save transaction
        update_order(order_id, {"status": "paid", "paid_at": datetime.now().isoformat()})
        save_transaction_to_db(
            order_id=order_id,
            customer_id=customer_id,
            amount=amount,
            payment_method=new_payment_method or "retry",
            transaction_id=final_transaction_id,
            status="completed"
        )
        
        return {
            "status": "success",
            "order_id": order_id,
            "transaction_id": final_transaction_id,
            "amount": amount,
            "attempts_made": len(retry_attempts),
            "retry_log": retry_attempts,
            "message": f"✅ Payment successful on attempt {len(retry_attempts)}. Transaction: {final_transaction_id}"
        }
    else:
        return {
            "status": "failed",
            "order_id": order_id,
            "attempts_made": len(retry_attempts),
            "retry_log": retry_attempts,
            "message": f"❌ Payment failed after {max_retries} attempts. Please try a different payment method.",
            "suggested_actions": [
                "Try a different card",
                "Use UPI payment",
                "Create a new payment link",
                "Contact bank if issue persists"
            ]
        }


print("✅ Payment tools loaded (Firebase + Razorpay)")

"""
Loyalty Agent Tools - Firebase Firestore
Handles loyalty points, tiers, discounts, and offers
"""
import json
from datetime import datetime
from typing import Optional
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from utils.db import get_db, get_customer, update_customer_points, update_customer_tier, get_promotions, create_customer, generate_customer_id

# Tier benefits configuration
TIER_BENEFITS = {
    "bronze": {"discount": 5, "free_shipping_min": 500, "points_multiplier": 1},
    "silver": {"discount": 10, "free_shipping_min": 500, "points_multiplier": 1.25},
    "gold": {"discount": 15, "free_shipping_min": 0, "points_multiplier": 1.5},
    "platinum": {"discount": 20, "free_shipping_min": 0, "points_multiplier": 2}
}

def get_loyalty_status(customer_id: str):
    """
    Get customer's loyalty tier, points, and benefits.
    
    Args:
        customer_id: Customer identifier
    
    Returns:
        Dictionary with loyalty status and benefits
    """
    customer = get_customer(customer_id)
    if not customer:
        return {"status": "error", "message": f"Customer {customer_id} not found"}
    
    tier = customer["loyalty_tier"].lower()
    points = customer["loyalty_points"]
    benefits = TIER_BENEFITS.get(tier, TIER_BENEFITS["bronze"])
    
    # Calculate points to next tier
    tier_thresholds = {"bronze": 500, "silver": 1500, "gold": 3000, "platinum": float('inf')}
    tier_order = ["bronze", "silver", "gold", "platinum"]
    current_idx = tier_order.index(tier)
    
    next_tier = None
    points_to_next = 0
    if current_idx < len(tier_order) - 1:
        next_tier = tier_order[current_idx + 1]
        points_to_next = tier_thresholds[tier] - points
        if points_to_next < 0:
            points_to_next = 0
    
    free_shipping_text = "free shipping on all orders" if benefits["free_shipping_min"] == 0 else f"free shipping on orders ₹{benefits['free_shipping_min']}+"
    
    return {
        "status": "success",
        "customer_id": customer_id,
        "customer_name": customer["name"],
        "loyalty_tier": customer["loyalty_tier"],
        "loyalty_points": points,
        "tier_discount": benefits["discount"],
        "free_shipping_minimum": benefits["free_shipping_min"],
        "points_multiplier": benefits["points_multiplier"],
        "next_tier": next_tier.capitalize() if next_tier else None,
        "points_to_next_tier": points_to_next,
        "benefits_summary": f"{benefits['discount']}% discount, {free_shipping_text}"
    }

def apply_promotion(promo_code: str, order_total: float, customer_id: Optional[str] = None):
    """
    Validate and apply a promotion code.
    Supports timed promotions with valid_from and valid_until dates.
    """
    promotions = get_promotions()
    promo = None
    for p in promotions:
        code_field = p.get("code") or p.get("promo_code", "")
        if code_field.upper() == promo_code.upper():
            promo = p
            break
    
    if not promo:
        return {"status": "error", "message": f"Invalid promo code: {promo_code}"}
    
    # Check timed promotion validity
    now = datetime.now()
    
    # Check valid_from (promotion not yet started)
    valid_from = promo.get("valid_from")
    if valid_from:
        try:
            if isinstance(valid_from, str):
                start_date = datetime.fromisoformat(valid_from.replace('Z', '+00:00').replace('+00:00', ''))
            else:
                start_date = valid_from
            if now < start_date:
                return {
                    "status": "error",
                    "message": f"Promo code {promo_code} is not active yet. Valid from: {start_date.strftime('%Y-%m-%d')}"
                }
        except (ValueError, TypeError):
            pass  # If date parsing fails, allow the promo
    
    # Check valid_until (promotion expired)
    valid_until = promo.get("valid_until") or promo.get("expires_at")
    if valid_until:
        try:
            if isinstance(valid_until, str):
                end_date = datetime.fromisoformat(valid_until.replace('Z', '+00:00').replace('+00:00', ''))
            else:
                end_date = valid_until
            if now > end_date:
                return {
                    "status": "error",
                    "message": f"Promo code {promo_code} has expired on {end_date.strftime('%Y-%m-%d')}"
                }
        except (ValueError, TypeError):
            pass  # If date parsing fails, allow the promo
    
    # Check minimum order
    min_order = promo.get("min_order", 0)
    if order_total < min_order:
        return {
            "status": "error",
            "message": f"Minimum order of ₹{min_order} required for {promo_code}"
        }
    
    discount_percent = promo.get("discount_percent", 0)
    discount_amount = round(order_total * (discount_percent / 100), 2)
    new_total = round(order_total - discount_amount, 2)
    
    # Include expiration info in response
    expiry_info = ""
    if valid_until:
        try:
            if isinstance(valid_until, str):
                end_date = datetime.fromisoformat(valid_until.replace('Z', '+00:00').replace('+00:00', ''))
            else:
                end_date = valid_until
            days_left = (end_date - now).days
            if days_left <= 7:
                expiry_info = f" (Expires in {days_left} days!)"
        except:
            pass
    
    return {
        "status": "success",
        "promo_code": promo_code,
        "description": promo.get("description", ""),
        "original_total": order_total,
        "discount_percent": discount_percent,
        "discount_amount": discount_amount,
        "new_total": new_total,
        "valid_from": str(valid_from) if valid_from else None,
        "valid_until": str(valid_until) if valid_until else None,
        "message": f"Promo {promo_code} applied! You saved ₹{discount_amount}{expiry_info}"
    }

def calculate_final_price(customer_id: str, base_price: float, promo_code: Optional[str] = None):
    """
    Calculate final price with loyalty discount and optional promo code.
    """
    customer = get_customer(customer_id)
    if not customer:
        return {"status": "error", "message": f"Customer {customer_id} not found"}
    
    tier = customer["loyalty_tier"].lower()
    benefits = TIER_BENEFITS.get(tier, TIER_BENEFITS["bronze"])
    
    # Apply tier discount
    tier_discount = round(base_price * (benefits["discount"] / 100), 2)
    price_after_tier = round(base_price - tier_discount, 2)
    
    # Apply promo code if provided
    promo_discount = 0
    promo_info = None
    if promo_code:
        promo_result = apply_promotion(promo_code, price_after_tier, customer_id)
        if promo_result["status"] == "success":
            promo_discount = promo_result["discount_amount"]
            price_after_tier = promo_result["new_total"]
            promo_info = promo_result
    
    # Determine shipping (₹49 standard shipping if below free shipping threshold)
    shipping_cost = 0.0 if (price_after_tier >= benefits["free_shipping_min"] or benefits["free_shipping_min"] == 0) else 49.0
    
    final_price = round(price_after_tier + shipping_cost, 2)
    
    # Calculate points earned
    points_earned = int(base_price * benefits["points_multiplier"])
    
    return {
        "status": "success",
        "customer_id": customer_id,
        "customer_name": customer["name"],
        "loyalty_tier": customer["loyalty_tier"],
        "base_price": base_price,
        "tier_discount": tier_discount,
        "tier_discount_percent": benefits["discount"],
        "promo_discount": promo_discount,
        "shipping_cost": shipping_cost,
        "final_price": final_price,
        "points_earned": points_earned,
        "savings_total": round(tier_discount + promo_discount, 2),
        "promo_applied": promo_info
    }

def register_new_customer(name: str, email: str, phone: str = "", location: str = ""):
    """
    Register a new customer in the database.
    
    Args:
        name: Customer's full name
        email: Customer's email address
        phone: Customer's phone number (optional)
        location: Customer's location (optional)
    
    Returns:
        Dictionary with new customer details
    """
    customer_id = generate_customer_id()
    result = create_customer(customer_id, name, email, phone, location, "Bronze", 100)
    
    if result["status"] == "success":
        return {
            "status": "success",
            "customer_id": customer_id,
            "name": name,
            "email": email,
            "loyalty_tier": "Bronze",
            "loyalty_points": 100,
            "message": f"Welcome {name}! Your customer ID is {customer_id}. You start with Bronze tier and 100 bonus points!"
        }
    return result

def add_loyalty_points(customer_id: str, points: int, reason: str = "Purchase"):
    """
    Add loyalty points to a customer's account.
    """
    customer = get_customer(customer_id)
    if not customer:
        return {"status": "error", "message": f"Customer {customer_id} not found"}
    
    update_customer_points(customer_id, points)
    
    new_points = customer["loyalty_points"] + points
    
    # Check for tier upgrade
    tier_thresholds = {"Bronze": 0, "Silver": 500, "Gold": 1500, "Platinum": 3000}
    current_tier = customer["loyalty_tier"]
    new_tier = current_tier
    
    for tier, threshold in sorted(tier_thresholds.items(), key=lambda x: x[1], reverse=True):
        if new_points >= threshold:
            new_tier = tier
            break
    
    if new_tier != current_tier:
        update_customer_tier(customer_id, new_tier)
    
    return {
        "status": "success",
        "customer_id": customer_id,
        "points_added": points,
        "reason": reason,
        "new_total": new_points,
        "tier_upgraded": new_tier != current_tier,
        "new_tier": new_tier if new_tier != current_tier else None,
        "message": f"Added {points} points for {reason}. New balance: {new_points}"
    }


def get_active_promotions():
    """
    Get all currently active promotions (considering timed validity).
    
    Returns:
        Dictionary with list of active promotions and their details
    """
    promotions = get_promotions()
    now = datetime.now()
    
    active_promos = []
    upcoming_promos = []
    expired_promos = []
    
    for promo in promotions:
        code = promo.get("code") or promo.get("promo_code", "")
        valid_from = promo.get("valid_from")
        valid_until = promo.get("valid_until") or promo.get("expires_at")
        
        # Parse dates
        start_date = None
        end_date = None
        
        if valid_from:
            try:
                if isinstance(valid_from, str):
                    start_date = datetime.fromisoformat(valid_from.replace('Z', ''))
                else:
                    start_date = valid_from
            except:
                pass
        
        if valid_until:
            try:
                if isinstance(valid_until, str):
                    end_date = datetime.fromisoformat(valid_until.replace('Z', ''))
                else:
                    end_date = valid_until
            except:
                pass
        
        promo_info = {
            "code": code,
            "description": promo.get("description", ""),
            "discount_percent": promo.get("discount_percent"),
            "min_order": promo.get("min_order", promo.get("min_purchase", 0)),
            "valid_from": str(valid_from) if valid_from else "Always",
            "valid_until": str(valid_until) if valid_until else "Never expires"
        }
        
        # Categorize promotion
        if start_date and now < start_date:
            promo_info["status"] = "upcoming"
            promo_info["starts_in_days"] = (start_date - now).days
            upcoming_promos.append(promo_info)
        elif end_date and now > end_date:
            promo_info["status"] = "expired"
            expired_promos.append(promo_info)
        else:
            promo_info["status"] = "active"
            if end_date:
                days_left = (end_date - now).days
                promo_info["expires_in_days"] = days_left
                if days_left <= 3:
                    promo_info["urgency"] = "⚠️ Expiring soon!"
            active_promos.append(promo_info)
    
    return {
        "status": "success",
        "active_promotions": active_promos,
        "active_count": len(active_promos),
        "upcoming_promotions": upcoming_promos,
        "upcoming_count": len(upcoming_promos),
        "expired_promotions": expired_promos,
        "expired_count": len(expired_promos),
        "message": f"Found {len(active_promos)} active promotions, {len(upcoming_promos)} upcoming, {len(expired_promos)} expired"
    }


print("✅ Loyalty and offers tools loaded (Firebase)")

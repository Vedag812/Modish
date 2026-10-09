"""
Inventory Agent Tools - Firebase Firestore
Real-time stock checking and fulfillment options
"""
import json
import random
from datetime import datetime, timedelta
from typing import Optional
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from utils.db import get_db, get_product, get_inventory

# Import real inventory API if available
try:
    from utils.external_apis.inventory_api import inventory_api
    USE_REAL_INVENTORY_API = True
    print("✅ Using REAL Inventory API integration")
except:
    USE_REAL_INVENTORY_API = False
    print("⚠️  Inventory API not available, using database")

def check_inventory(sku: str, location: Optional[str] = None):
    """
    Check inventory levels for a product across locations.
    
    Args:
        sku: Product SKU to check
        location: Optional specific location to check
    
    Returns:
        Dictionary with inventory status
    """
    product = get_product(sku)
    if not product:
        return {"status": "error", "message": f"Product {sku} not found"}
    
    inventory = get_inventory(sku, location)
    
    if not inventory:
        return {
            "status": "success",
            "sku": sku,
            "product_name": product["name"],
            "inventory": [],
            "message": "Product not available at any location"
        }
    
    total_stock = sum(item["quantity"] for item in inventory)
    
    return {
        "status": "success",
        "sku": sku,
        "product_name": product["name"],
        "total_stock": total_stock,
        "inventory": inventory,
        "in_stock": total_stock > 0
    }

def get_fulfillment_options(sku: str, customer_location: str = ""):
    """
    Get available fulfillment options for a product.
    
    Args:
        sku: Product SKU
        customer_location: Customer's location for shipping estimates
    
    Returns:
        Dictionary with fulfillment options
    """
    product = get_product(sku)
    if not product:
        return {"status": "error", "message": f"Product {sku} not found"}
    
    inventory = get_inventory(sku)
    available_locations = [item for item in inventory if item["quantity"] > 0]
    
    fulfillment_options = []
    
    # Standard shipping (free above ₹500)
    price = product.get("current_price", product.get("price", 0))
    fulfillment_options.append({
        "type": "standard_shipping",
        "name": "Standard Shipping",
        "cost": 49 if price < 500 else 0,
        "cost_display": "₹49" if price < 500 else "FREE",
        "estimated_days": "5-7 business days",
        "available": len(available_locations) > 0
    })
    
    # Express shipping
    fulfillment_options.append({
        "type": "express_shipping",
        "name": "Express Shipping",
        "cost": 99,
        "cost_display": "₹99",
        "estimated_days": "2-3 business days",
        "available": len(available_locations) > 0
    })
    
    # Same day delivery
    fulfillment_options.append({
        "type": "same_day",
        "name": "Same Day Delivery",
        "cost": 149,
        "cost_display": "₹149",
        "estimated_days": "Today (order before 2 PM)",
        "available": len(available_locations) > 0
    })
    
    # Store pickup
    for loc in available_locations[:3]:
        fulfillment_options.append({
            "type": "store_pickup",
            "name": f"Store Pickup - {loc['location']}",
            "cost": 0,
            "estimated_days": "Same day",
            "available": True,
            "location": loc["location"],
            "stock": loc["quantity"]
        })
    
    return {
        "status": "success",
        "sku": sku,
        "product_name": product["name"],
        "fulfillment_options": fulfillment_options,
        "total_available_stock": sum(item["quantity"] for item in available_locations)
    }

def check_in_store_availability(sku: str, store_location: Optional[str] = None):
    """
    Check product availability for in-store pickup or purchase.
    
    Args:
        sku: Product SKU
        store_location: Specific store to check (optional)
    
    Returns:
        Dictionary with in-store availability across all stores
    """
    product = get_product(sku)
    if not product:
        return {"status": "error", "message": f"Product {sku} not found"}
    
    inventory = get_inventory(sku, store_location)
    
    stores_with_stock = []
    for item in inventory:
        if item["quantity"] > 0:
            stores_with_stock.append({
                "store": item["location"],
                "quantity": item["quantity"],
                "ready_for_pickup": True,
                "pickup_time": "Ready in 2 hours"
            })
    
    return {
        "status": "success",
        "sku": sku,
        "product_name": product["name"],
        "in_store_availability": stores_with_stock,
        "available_stores_count": len(stores_with_stock),
        "message": f"Available at {len(stores_with_stock)} store(s) for in-store pickup"
    }


def reserve_click_and_collect(sku: str, quantity: int, store_location: str, customer_id: str):
    """
    Reserve product for Click & Collect (buy online, pickup in store).
    
    Args:
        sku: Product SKU
        quantity: Number of units
        store_location: Store for pickup
        customer_id: Customer ID
    
    Returns:
        Dictionary with pickup reservation details
    """
    product = get_product(sku)
    if not product:
        return {"status": "error", "message": f"Product {sku} not found"}
    
    inventory = get_inventory(sku, store_location)
    if not inventory or inventory[0]["quantity"] < quantity:
        return {"status": "error", "message": f"Product not available at {store_location} for pickup"}
    
    reservation_id = f"CC{random.randint(100000, 999999)}"
    pickup_code = f"PU{random.randint(1000, 9999)}"
    ready_time = datetime.now() + timedelta(hours=2)
    
    return {
        "status": "success",
        "reservation_type": "click_and_collect",
        "reservation_id": reservation_id,
        "pickup_code": pickup_code,
        "sku": sku,
        "product_name": product["name"],
        "quantity": quantity,
        "store_location": store_location,
        "customer_id": customer_id,
        "ready_by": ready_time.strftime("%I:%M %p"),
        "expires_at": (ready_time + timedelta(hours=48)).isoformat(),
        "message": f"Reserved for pickup! Your code: {pickup_code}. Ready by {ready_time.strftime('%I:%M %p')} at {store_location}"
    }


def reserve_inventory(sku: str, quantity: int, location: Optional[str] = None):
    """
    Reserve inventory for a customer.
    If location is a warehouse, check stock there.
    If location is a customer city (like Kolkata), find nearest warehouse with stock.
    
    Args:
        sku: Product SKU
        quantity: Number of units to reserve
        location: Warehouse location OR customer's city for shipping
    """
    product = get_product(sku)
    if not product:
        return {"status": "error", "message": f"Product {sku} not found"}
    
    # Known warehouse locations
    warehouses = ["Mumbai Warehouse", "Delhi Warehouse", "Bengaluru Warehouse", 
                  "Chennai Warehouse", "Hyderabad Warehouse"]
    
    # Normalize location - map city names to warehouse names
    warehouse_city_map = {
        "mumbai": "Mumbai Warehouse",
        "delhi": "Delhi Warehouse",
        "bengaluru": "Bengaluru Warehouse",
        "bangalore": "Bengaluru Warehouse",
        "chennai": "Chennai Warehouse",
        "hyderabad": "Hyderabad Warehouse"
    }
    
    # Check if location matches a warehouse city
    normalized_location = location.lower().strip() if location else ""
    matched_warehouse = None
    
    # Direct warehouse name match
    for w in warehouses:
        if w.lower() == normalized_location or normalized_location == w.lower():
            matched_warehouse = w
            break
    
    # City name to warehouse match
    if not matched_warehouse:
        for city, warehouse in warehouse_city_map.items():
            if city in normalized_location or normalized_location in city:
                matched_warehouse = warehouse
                break
    
    # If location is a warehouse, check stock there
    if matched_warehouse:
        inventory = get_inventory(sku, matched_warehouse)
        if not inventory or inventory[0]["quantity"] < quantity:
            # Try finding another warehouse
            all_inventory = get_inventory(sku)
            available = [inv for inv in all_inventory if inv["quantity"] >= quantity]
            if available:
                best = max(available, key=lambda x: x["quantity"])
                return {
                    "status": "success",
                    "reservation_id": f"RES{random.randint(100000, 999999)}",
                    "sku": sku,
                    "product_name": product.get("name", sku),
                    "quantity": quantity,
                    "source_warehouse": best["location"],
                    "ship_to": location,
                    "available_stock": best["quantity"],
                    "expires_at": (datetime.now() + timedelta(hours=24)).isoformat(),
                    "message": f"Reserved {quantity} unit(s) from {best['location']} (shipping to {location})"
                }
            return {
                "status": "error",
                "message": f"Insufficient stock at {matched_warehouse}. Try another warehouse."
            }
        
        reservation_id = f"RES{random.randint(100000, 999999)}"
        return {
            "status": "success",
            "reservation_id": reservation_id,
            "sku": sku,
            "product_name": product.get("name", sku),
            "quantity": quantity,
            "source_warehouse": matched_warehouse,
            "ship_to": location,
            "available_stock": inventory[0]["quantity"],
            "expires_at": (datetime.now() + timedelta(hours=24)).isoformat(),
            "message": f"Reserved {quantity} unit(s) of {product.get('name', sku)} from {matched_warehouse}"
        }
    
    # Customer city (not a warehouse) - find best warehouse with stock
    all_inventory = get_inventory(sku)
    if not all_inventory:
        return {"status": "error", "message": f"Product {sku} not available at any location"}
    
    # Find warehouse with sufficient stock
    available_warehouses = [inv for inv in all_inventory if inv["quantity"] >= quantity]
    if not available_warehouses:
        max_available = max(inv['quantity'] for inv in all_inventory)
        return {
            "status": "error",
            "message": f"Insufficient stock. Max available: {max_available} units"
        }
    
    # Select warehouse with most stock for shipping
    best_warehouse = max(available_warehouses, key=lambda x: x["quantity"])
    selected_warehouse = best_warehouse["location"]
    available_qty = best_warehouse["quantity"]
    
    # Generate reservation
    reservation_id = f"RES{random.randint(100000, 999999)}"
    
    return {
        "status": "success",
        "reservation_id": reservation_id,
        "sku": sku,
        "product_name": product.get("name", sku),
        "quantity": quantity,
        "source_warehouse": selected_warehouse,
        "ship_to": location,
        "available_stock": available_qty,
        "expires_at": (datetime.now() + timedelta(hours=24)).isoformat(),
        "message": f"Reserved {quantity} unit(s) of {product.get('name', sku)} from {selected_warehouse}. Shipping to {location}."
    }

print("✅ Inventory tools loaded (Firebase)")

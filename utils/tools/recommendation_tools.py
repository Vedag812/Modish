"""
Recommendation Agent Tools
Analyzes customer profile, browsing history, and seasonal trends to suggest products
Uses Firebase Firestore
"""
import json
import random
from datetime import datetime
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from utils.db import get_customer, search_products
from utils.firebase_db import get_all_products, get_product, get_promotions

def get_personalized_recommendations(customer_id: str, max_recommendations: int = 5):
    """
    Get personalized product recommendations based on customer profile and history.
    
    Args:
        customer_id: The unique customer identifier (e.g., "CUST1001")
        max_recommendations: Maximum number of products to recommend (default: 5)
    
    Returns:
        Dictionary with status and recommendations
    """
    customer = get_customer(customer_id)
    if not customer:
        return {"status": "error", "message": f"Customer {customer_id} not found"}
    
    name = customer.get("name", "Customer")
    browsing_history = customer.get("browsing_history", [])
    purchase_history = customer.get("purchase_history", [])
    preferences = customer.get("preferences", {})
    
    # Get previously purchased SKUs
    purchased_skus = [item.get('sku', '') for item in purchase_history] if purchase_history else []
    
    # Get products from favorite categories
    favorite_categories = preferences.get('favorite_categories', [])
    
    recommendations = []
    
    # Get all products from Firebase
    all_products = get_all_products(limit=100)
    
    # Sort by rating
    all_products.sort(key=lambda x: (x.get('rating', 0), x.get('reviews_count', 0)), reverse=True)
    
    # Recommend from favorite categories first
    if favorite_categories:
        for product in all_products:
            if product.get('category') in favorite_categories and product.get('sku') not in purchased_skus:
                if len(recommendations) >= max_recommendations:
                    break
                recommendations.append({
                    "sku": product.get('sku'),
                    "name": product.get('name'),
                    "category": product.get('category'),
                    "price": float(product.get('current_price', product.get('price', 0))),
                    "rating": float(product.get('rating', 0)),
                    "reason": f"Recommended based on your interest in {product.get('category')}"
                })
    
    # Add trending products if we need more
    if len(recommendations) < max_recommendations:
        existing_skus = [r['sku'] for r in recommendations] + purchased_skus
        for product in all_products:
            if product.get('sku') not in existing_skus:
                if len(recommendations) >= max_recommendations:
                    break
                recommendations.append({
                    "sku": product.get('sku'),
                    "name": product.get('name'),
                    "category": product.get('category'),
                    "price": float(product.get('current_price', product.get('price', 0))),
                    "rating": float(product.get('rating', 0)),
                    "reason": "Trending item with high ratings"
                })
    
    return {
        "status": "success",
        "customer_name": name,
        "recommendations": recommendations[:max_recommendations]
    }

def suggest_bundle_deals(sku: str):
    """
    Suggest complementary products that go well together as a bundle.
    """
    # Get main product
    main_product = get_product(sku)
    if not main_product:
        return {"status": "error", "message": f"Product {sku} not found"}
    
    main_sku = main_product.get('sku', sku)
    main_name = main_product.get('name', '')
    main_category = main_product.get('category', '')
    main_price = main_product.get('current_price', main_product.get('price', 0))
    
    # Get complementary products from same category
    all_products = get_all_products(limit=100)
    same_category = [p for p in all_products if p.get('category') == main_category and p.get('sku') != sku]
    
    # Sort by rating and take top 3
    same_category.sort(key=lambda x: x.get('rating', 0), reverse=True)
    
    bundle_items = []
    total_discount = 0
    
    for product in same_category[:3]:
        price = float(product.get('current_price', product.get('price', 0)))
        discount_amount = round(price * 0.10, 2)
        bundle_items.append({
            "sku": product.get('sku'),
            "name": product.get('name'),
            "original_price": price,
            "bundle_price": round(price - discount_amount, 2),
            "discount": "10%"
        })
        total_discount += discount_amount
    
    return {
        "status": "success",
        "main_product": {
            "sku": main_sku,
            "name": main_name,
            "price": float(main_price)
        },
        "bundle_items": bundle_items,
        "bundle_savings": round(total_discount, 2),
        "message": f"Save ₹{round(total_discount, 2)} when you buy these items together!"
    }

def get_seasonal_promotions(category: str = None):
    """
    Get current seasonal promotions and deals.
    """
    promotions = get_promotions()
    if category:
        promotions = [p for p in promotions if p.get('category') == category or not p.get('category')]
    return {
        "status": "success",
        "promotions": promotions,
        "count": len(promotions)
    }

def search_products_tool(query: str = "", category: str = "", max_price: float = None, min_price: float = None, max_results: int = 10):
    """
    Search for products by name, category, and price range.
    Includes smart fallback when no direct matches are found.
    """
    results = search_products(query=query, category=category, min_price=min_price, max_price=max_price, limit=max_results)
    
    # Fallback 1: If no results with category or price filters, broaden the search to match query across all categories/prices
    if not results and query and (category or min_price is not None or max_price is not None):
        broader_results = search_products(query=query, limit=max_results)
        if broader_results:
            return {
                "status": "success",
                "results": broader_results,
                "count": len(broader_results),
                "query": query,
                "note": f"No items matched the specific category/price filter, but found {len(broader_results)} items matching '{query}' across the store.",
                "filters_relaxed": True,
                "filters": {"category": category, "max_price": max_price, "min_price": min_price}
            }
    
    # Fallback 2: If still no results, provide top trending fashion items as smart alternatives
    if not results:
        popular_results = search_products(query="", limit=min(5, max_results))
        return {
            "status": "no_direct_match",
            "results": [],
            "suggested_alternatives": popular_results,
            "count": 0,
            "query": query,
            "message": f"No direct matches found for '{query}'. Here are our top trending fashion picks to suggest instead.",
            "filters": {"category": category, "max_price": max_price, "min_price": min_price}
        }
    
    return {
        "status": "success",
        "results": results,
        "count": len(results),
        "query": query,
        "filters": {"category": category, "max_price": max_price, "min_price": min_price}
    }

print("✅ Recommendation tools loaded (Firebase)")

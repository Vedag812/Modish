"""
Product search and recommendation utilities.

Helper functions for the recommendation agent including search ranking,
category filtering, price range matching, and relevance scoring.
"""

from typing import List, Dict, Optional


def filter_by_price_range(
    products: List[Dict],
    min_price: float = 0,
    max_price: float = float("inf"),
) -> List[Dict]:
    """
    Filter products within a specified price range.

    Args:
        products: List of product dictionaries with 'price' field.
        min_price: Minimum price (inclusive). Defaults to 0.
        max_price: Maximum price (inclusive). Defaults to infinity.

    Returns:
        Filtered list of products within the price range.
    """
    return [
        p for p in products
        if min_price <= p.get("price", 0) <= max_price
    ]


def filter_by_category(
    products: List[Dict],
    category: str,
) -> List[Dict]:
    """
    Filter products by category name (case-insensitive partial match).

    Args:
        products: List of product dictionaries with 'category' field.
        category: Category name or partial name to filter by.

    Returns:
        Products matching the specified category.
    """
    category_lower = category.lower()
    return [
        p for p in products
        if category_lower in p.get("category", "").lower()
    ]


def compute_relevance_score(
    product: Dict,
    query: str,
    price_weight: float = 0.3,
    name_weight: float = 0.5,
    rating_weight: float = 0.2,
) -> float:
    """
    Compute a relevance score for a product against a search query.

    Uses a weighted combination of:
    - Name similarity (keyword overlap)
    - Price competitiveness within category
    - Customer rating

    Args:
        product: Product dictionary.
        query: User's search query string.
        price_weight: Weight for price factor (0-1).
        name_weight: Weight for name matching (0-1).
        rating_weight: Weight for rating factor (0-1).

    Returns:
        Relevance score between 0.0 and 1.0.
    """
    score = 0.0

    # Name similarity (keyword overlap)
    query_words = set(query.lower().split())
    name_words = set(product.get("name", "").lower().split())
    desc_words = set(product.get("description", "").lower().split())
    all_product_words = name_words | desc_words

    if query_words:
        overlap = len(query_words & all_product_words) / len(query_words)
        score += overlap * name_weight

    # Rating factor (normalized to 0-1, assuming 5-star scale)
    rating = product.get("rating", 3.0)
    score += (rating / 5.0) * rating_weight

    # Price competitiveness (lower price = higher score, normalized)
    price = product.get("price", 0)
    if price > 0:
        # Sigmoid-like normalization: prices around ₹1000 score ~0.5
        price_score = 1.0 / (1.0 + (price / 2000.0))
        score += price_score * price_weight

    return round(min(score, 1.0), 3)


def sort_by_relevance(
    products: List[Dict],
    query: str,
    top_k: int = 10,
) -> List[Dict]:
    """
    Sort products by relevance to the user's query.

    Computes relevance score for each product and returns
    the top-k most relevant results.

    Args:
        products: List of product dictionaries.
        query: User's search query.
        top_k: Number of top results to return.

    Returns:
        Top-k products sorted by descending relevance score.
    """
    scored = []
    for product in products:
        score = compute_relevance_score(product, query)
        product_with_score = {**product, "_relevance": score}
        scored.append(product_with_score)

    scored.sort(key=lambda x: x["_relevance"], reverse=True)
    return scored[:top_k]


def format_price_inr(amount: float) -> str:
    """
    Format a price amount in Indian Rupee notation.

    Args:
        amount: Price as a float.

    Returns:
        Formatted string like '₹1,299.00'.
    """
    return f"₹{amount:,.2f}"


def get_warehouse_availability(
    inventory: List[Dict],
    product_id: str,
) -> Dict[str, int]:
    """
    Get stock availability across all warehouses for a product.

    Args:
        inventory: List of inventory records with warehouse and quantity.
        product_id: The product identifier to check.

    Returns:
        Dictionary mapping warehouse names to available quantities.
    """
    availability = {}
    for record in inventory:
        if record.get("product_id") == product_id:
            warehouse = record.get("warehouse", "Unknown")
            quantity = record.get("quantity", 0)
            availability[warehouse] = quantity

    return availability

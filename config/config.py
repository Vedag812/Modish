"""
Configuration file for Retail Sales Agent System
Manages API keys and system settings
"""
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Gemini API Configuration
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

if not GEMINI_API_KEY:
    print("⚠️  Warning: GEMINI_API_KEY not found in environment variables.")
    print("Please set it using: $env:GEMINI_API_KEY='your-api-key-here' (PowerShell)")
    print("Or add it to a .env file")

# System Configuration
APP_NAME = "Retail_Sales_Agent_System"
USER_ID = "customer_user"

# Database Configuration - Firebase Firestore
FIREBASE_SERVICE_ACCOUNT_PATH = os.environ.get("FIREBASE_SERVICE_ACCOUNT_PATH", "./firebase-service-account.json")
print("✅ Using Firebase Firestore")

# Recommended update in config/config.py:
DEFAULT_MODEL = os.environ.get("DEFAULT_MODEL", "gemini-2.5-flash-lite")
FALLBACK_MODEL = os.environ.get("FALLBACK_MODEL", "gemini-2.5-flash-lite")

# Agent Configuration
MAX_RETRIES = 2
RETRY_DELAY = 1

# Channel Types
CHANNELS = ["web_chat", "mobile_app", "whatsapp", "telegram", "in_store_kiosk", "voice_assistant"]

# Product Categories - All available
PRODUCT_CATEGORIES = [
    "Electronics",
    "Clothing",
    "Home & Kitchen",
    "Sports & Outdoors",
    "Books",
    "Beauty & Personal Care",
    "Toys & Games",
    "Automotive"
]

# ==================== FASHION/CLOTHING FILTER ====================
# Only these categories will be displayed on the website and used by agents
# Set to None or empty list to show all categories
ALLOWED_CATEGORIES = [
    "Clothing - Men",
    "Clothing - Women",
    "Footwear",
]

# Helper function to check if a category is allowed
def is_allowed_category(category: str) -> bool:
    """Check if a category is in the allowed list for fashion/clothing focus"""
    if not ALLOWED_CATEGORIES:
        return True  # If no filter, allow all
    if not category:
        return False
    # Case-insensitive partial matching for flexibility
    category_lower = category.lower()
    for allowed in ALLOWED_CATEGORIES:
        if allowed.lower() in category_lower or category_lower in allowed.lower():
            return True
    return False

# Loyalty Tiers
LOYALTY_TIERS = {
    "bronze": {"min_points": 0, "discount": 0.05},
    "silver": {"min_points": 500, "discount": 0.10},
    "gold": {"min_points": 1500, "discount": 0.15},
    "platinum": {"min_points": 3000, "discount": 0.20}
}

# Store Locations
STORE_LOCATIONS = [
    "New York - 5th Avenue",
    "Los Angeles - Beverly Hills",
    "Chicago - Michigan Ave",
    "Miami - Brickell",
    "Seattle - Downtown"
]

print("✅ Configuration loaded successfully")

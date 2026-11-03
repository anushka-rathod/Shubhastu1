"""
Configuration settings for Shubhashtu Fashion.
Reads from .env file or environment variables with intelligent defaults.
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

# Simple .env loader if python-dotenv is not installed
def load_dotenv(dotenv_path=None):
    if dotenv_path is None:
        dotenv_path = BASE_DIR / '.env'
    if os.path.exists(dotenv_path):
        with open(dotenv_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#') or '=' not in line:
                    continue
                k, v = line.split('=', 1)
                k = k.strip()
                v = v.strip().strip('"').strip("'")
                if k not in os.environ:
                    os.environ[k] = v

load_dotenv()

class Config:
    PORT = int(os.environ.get('PORT', 8000))
    DEBUG = os.environ.get('DEBUG', 'False').lower() in ('true', '1', 'yes')
    SECRET_KEY = os.environ.get('SECRET_KEY', 'shubhashtu-super-secret-key-2026-luxury-fashion-store')
    COOKIE_SECRET = os.environ.get('COOKIE_SECRET', 'shubhashtu-cookie-secret-token-gold-blush-98432')
    DATABASE_PATH = os.environ.get('DATABASE_PATH', str(BASE_DIR / 'database.sqlite'))
    
    # Brand details
    BRAND_NAME = os.environ.get('BRAND_NAME', 'Shubhashtu Fashion')
    BRAND_TAGLINE = os.environ.get('BRAND_TAGLINE', 'Style That Speaks for You.')
    SUPPORT_PHONE = os.environ.get('SUPPORT_PHONE', '+91 98765 43210')
    SUPPORT_WHATSAPP = os.environ.get('SUPPORT_WHATSAPP', '919876543210')
    SUPPORT_EMAIL = os.environ.get('SUPPORT_EMAIL', 'care@shubhashtufashion.com')
    STORE_ADDRESS = os.environ.get('STORE_ADDRESS', 'Shubhashtu Studio, 402 Heritage Galleria, M.G. Road, Bengaluru, Karnataka - 560001')
    
    # Razorpay Payment Gateway
    RAZORPAY_KEY_ID = os.environ.get('RAZORPAY_KEY_ID', '')
    RAZORPAY_KEY_SECRET = os.environ.get('RAZORPAY_KEY_SECRET', '')
    RAZORPAY_WEBHOOK_SECRET = os.environ.get('RAZORPAY_WEBHOOK_SECRET', '')
    RAZORPAY_TEST_MODE = os.environ.get('RAZORPAY_TEST_MODE', 'True').lower() in ('true', '1', 'yes')
    
    # Shiprocket Logistics Integration
    SHIPROCKET_EMAIL = os.environ.get('SHIPROCKET_EMAIL', '')
    SHIPROCKET_PASSWORD = os.environ.get('SHIPROCKET_PASSWORD', '')
    SHIPROCKET_PICKUP_PINCODE = os.environ.get('SHIPROCKET_PICKUP_PINCODE', '560001')
    
    # Admin Credentials for Initial Setup
    ADMIN_EMAIL = os.environ.get('ADMIN_EMAIL', 'admin@shubhashtu.com')
    ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'ShubhashtuAdmin@2026')
    
    # SMTP Email
    SMTP_HOST = os.environ.get('SMTP_HOST', 'smtp.gmail.com')
    SMTP_PORT = int(os.environ.get('SMTP_PORT', 587))
    SMTP_USER = os.environ.get('SMTP_USER', '')
    SMTP_PASSWORD = os.environ.get('SMTP_PASSWORD', '')
    SMTP_FROM = os.environ.get('SMTP_FROM', 'Shubhashtu Fashion <orders@shubhashtufashion.com>')


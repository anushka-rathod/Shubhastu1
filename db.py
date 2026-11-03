"""
Database connection and schema initialization for Shubhashtu Fashion.
Uses SQLite with WAL mode and foreign key constraints enabled.
"""
import sqlite3
import os
import contextlib
from config import Config

def get_connection():
    conn = sqlite3.connect(Config.DATABASE_PATH, timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    return conn

@contextlib.contextmanager
def get_db():
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def init_db():
    """Create all necessary tables and indexes if they do not exist."""
    with get_db() as conn:
        cursor = conn.cursor()
        
        # 1. Users Table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            salt TEXT NOT NULL,
            full_name TEXT NOT NULL,
            phone TEXT,
            role TEXT DEFAULT 'customer', -- 'customer' or 'admin'
            reset_token TEXT,
            reset_expires TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)
        
        # 2. Saved Addresses
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_addresses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            label TEXT DEFAULT 'Home', -- 'Home', 'Work', 'Other'
            full_name TEXT NOT NULL,
            phone TEXT NOT NULL,
            address_line1 TEXT NOT NULL,
            address_line2 TEXT,
            landmark TEXT,
            city TEXT NOT NULL,
            state TEXT NOT NULL,
            pincode TEXT NOT NULL,
            is_default INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        );
        """)
        
        # 3. Categories
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            slug TEXT UNIQUE NOT NULL,
            description TEXT,
            image_url TEXT,
            sort_order INTEGER DEFAULT 0,
            is_active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)
        
        # 4. Products
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            slug TEXT UNIQUE NOT NULL,
            sku TEXT UNIQUE NOT NULL,
            category_id INTEGER NOT NULL,
            short_description TEXT,
            description TEXT,
            care_instructions TEXT,
            mrp REAL NOT NULL,
            price REAL NOT NULL,
            stock INTEGER DEFAULT 10,
            weight_grams INTEGER DEFAULT 350,
            badge TEXT, -- 'New', 'Bestseller', 'Trending', 'Sale', etc.
            is_featured INTEGER DEFAULT 0,
            is_active INTEGER DEFAULT 1,
            sizes TEXT DEFAULT 'Free Size', -- Comma separated e.g. "XS,S,M,L,XL,XXL" or "Free Size"
            colors TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(category_id) REFERENCES categories(id) ON DELETE RESTRICT
        );
        """)
        
        # 5. Product Images
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS product_images (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER NOT NULL,
            image_url TEXT NOT NULL,
            is_primary INTEGER DEFAULT 0,
            sort_order INTEGER DEFAULT 0,
            FOREIGN KEY(product_id) REFERENCES products(id) ON DELETE CASCADE
        );
        """)
        
        # 6. Cart Items
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS cart_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            user_id INTEGER,
            product_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL DEFAULT 1,
            selected_size TEXT DEFAULT 'Free Size',
            selected_color TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY(product_id) REFERENCES products(id) ON DELETE CASCADE
        );
        """)
        
        # 7. Orders
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_number TEXT UNIQUE NOT NULL,
            user_id INTEGER,
            customer_name TEXT NOT NULL,
            customer_email TEXT NOT NULL,
            customer_phone TEXT NOT NULL,
            shipping_address_line1 TEXT NOT NULL,
            shipping_address_line2 TEXT,
            shipping_landmark TEXT,
            shipping_city TEXT NOT NULL,
            shipping_state TEXT NOT NULL,
            shipping_pincode TEXT NOT NULL,
            subtotal REAL NOT NULL,
            coupon_code TEXT,
            discount_amount REAL DEFAULT 0.0,
            shipping_fee REAL DEFAULT 0.0,
            total_amount REAL NOT NULL,
            payment_method TEXT NOT NULL, -- 'razorpay' or 'cod'
            payment_status TEXT DEFAULT 'pending', -- 'pending', 'paid', 'failed', 'refunded'
            razorpay_order_id TEXT,
            razorpay_payment_id TEXT,
            razorpay_signature TEXT,
            order_status TEXT DEFAULT 'Order Placed', -- 'Order Placed', 'Confirmed', 'Processing', 'Shipped', 'Out for Delivery', 'Delivered', 'Cancelled', 'Refunded'
            courier_name TEXT,
            tracking_number TEXT,
            tracking_url TEXT,
            estimated_delivery TEXT,
            customer_notes TEXT,
            admin_notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE SET NULL
        );
        """)
        
        # 8. Order Items
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS order_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL,
            product_id INTEGER,
            product_name TEXT NOT NULL,
            product_image TEXT,
            sku TEXT,
            selected_size TEXT,
            selected_color TEXT,
            mrp REAL NOT NULL,
            price REAL NOT NULL,
            quantity INTEGER NOT NULL,
            total_price REAL NOT NULL,
            FOREIGN KEY(order_id) REFERENCES orders(id) ON DELETE CASCADE,
            FOREIGN KEY(product_id) REFERENCES products(id) ON DELETE SET NULL
        );
        """)
        
        # 9. Order Status History Timeline
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS order_status_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL,
            status TEXT NOT NULL,
            comment TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(order_id) REFERENCES orders(id) ON DELETE CASCADE
        );
        """)
        
        # 10. Coupons
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS coupons (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE NOT NULL,
            description TEXT,
            discount_type TEXT NOT NULL, -- 'percentage' or 'fixed'
            discount_value REAL NOT NULL,
            min_order_value REAL DEFAULT 0.0,
            max_discount REAL, -- cap for percentage discounts
            usage_limit INTEGER,
            usage_count INTEGER DEFAULT 0,
            is_active INTEGER DEFAULT 1,
            expires_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)
        
        # 11. Customer Reviews
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER NOT NULL,
            user_id INTEGER,
            customer_name TEXT NOT NULL,
            customer_email TEXT,
            rating INTEGER NOT NULL CHECK(rating >= 1 AND rating <= 5),
            title TEXT,
            comment TEXT NOT NULL,
            is_verified_buyer INTEGER DEFAULT 1,
            is_approved INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(product_id) REFERENCES products(id) ON DELETE CASCADE,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE SET NULL
        );
        """)
        
        # 12. Wishlist
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS wishlist (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            session_id TEXT,
            product_id INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, product_id),
            UNIQUE(session_id, product_id),
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY(product_id) REFERENCES products(id) ON DELETE CASCADE
        );
        """)
        
        # 13. Settings (Key-Value)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            description TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)
        
        # 14. Contact & Inquiries
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS contact_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            phone TEXT,
            subject TEXT,
            message TEXT NOT NULL,
            is_read INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)
        
        # Indexes for query speed
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_products_category ON products(category_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_products_slug ON products(slug);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_products_featured ON products(is_featured);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_cart_session ON cart_items(session_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_cart_user ON cart_items(user_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_orders_user ON orders(user_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_orders_number ON orders(order_number);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(order_status);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_reviews_product ON reviews(product_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_wishlist_session ON wishlist(session_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_wishlist_user ON wishlist(user_id);")

if __name__ == '__main__':
    init_db()
    print("Database tables initialized successfully.")


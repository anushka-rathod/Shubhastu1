"""
Database connection and schema initialization for Shubhashtu Fashion.
Supports:
1. Cloud PostgreSQL (Supabase / Neon / Railway / AWS RDS) via Config.DATABASE_URL
   - Solves Vercel serverless ephemeral storage & total data loss.
   - All serverless instances share the persistent database safely.
2. Local SQLite with WAL mode & foreign keys via Config.DATABASE_PATH
   - Zero-configuration local offline development fallback.
"""
import os
import re
import ssl
import sqlite3
import contextlib
import urllib.parse
from config import Config

def is_postgres() -> bool:
    """Returns True if a cloud PostgreSQL connection string is configured."""
    return bool(getattr(Config, 'DATABASE_URL', '') and str(Config.DATABASE_URL).strip())

# ==================== POSTGRESQL ROW & CURSOR ADAPTER ====================

class PostgresRow:
    """Provides sqlite3.Row-like dictionary & index access for PostgreSQL result tuples."""
    def __init__(self, col_names, values):
        self._col_names = col_names
        self._values = values
        self._dict = {col: values[i] for i, col in enumerate(col_names)}

    def __getitem__(self, key):
        if isinstance(key, int):
            return self._values[key]
        return self._dict.get(key)

    def get(self, key, default=None):
        return self._dict.get(key, default)

    def keys(self):
        return self._col_names

    def values(self):
        return self._values

    def items(self):
        return self._dict.items()

    def __iter__(self):
        return iter(self._col_names)

    def __contains__(self, key):
        return key in self._dict

    def __repr__(self):
        return repr(self._dict)

class PostgresCursorWrapper:
    """
    Wraps PostgreSQL cursor to provide:
    - Auto-translation of '?' parameter placeholders to '%s'
    - Auto-capture of lastrowid via 'RETURNING id' on INSERT statements
    - Conversion of result tuples to dict-accessible PostgresRow objects
    """
    TABLES_WITH_ID = {
        'users', 'user_addresses', 'categories', 'products', 'product_images',
        'cart_items', 'orders', 'order_items', 'order_status_history',
        'coupons', 'reviews', 'wishlist', 'contact_messages'
    }

    def __init__(self, raw_cursor):
        self._cur = raw_cursor
        self.lastrowid = None
        self._col_names = []

    def execute(self, sql, params=None):
        # Ignore SQLite-specific PRAGMA statements on PostgreSQL
        if sql.strip().upper().startswith("PRAGMA"):
            return self

        # Convert '?' placeholders to '%s'
        pg_sql = sql
        if '?' in pg_sql:
            pg_sql = pg_sql.replace('?', '%s')

        # Check for INSERT to capture lastrowid
        is_insert = pg_sql.strip().upper().startswith("INSERT INTO")
        has_returning = "RETURNING" in pg_sql.upper()
        appended_returning = False

        if is_insert and not has_returning:
            # Check if target table has an 'id' column
            match = re.search(r'INSERT\s+INTO\s+([a-zA-Z_0-9]+)', pg_sql, re.IGNORECASE)
            if match:
                table_name = match.group(1).lower()
                if table_name in self.TABLES_WITH_ID:
                    pg_sql = pg_sql.rstrip('; \t\n') + " RETURNING id;"
                    appended_returning = True

        if params:
            # Convert list params to tuple for pg8000/psycopg2
            exec_params = tuple(params) if isinstance(params, list) else params
            self._cur.execute(pg_sql, exec_params)
        else:
            self._cur.execute(pg_sql)

        if appended_returning:
            try:
                row = self._cur.fetchone()
                if row:
                    self.lastrowid = row[0]
            except Exception:
                self.lastrowid = None

        if hasattr(self._cur, 'description') and self._cur.description:
            self._col_names = [col[0].lower() for col in self._cur.description]
        else:
            self._col_names = []

        return self

    def fetchone(self):
        row = self._cur.fetchone()
        if not row:
            return None
        return PostgresRow(self._col_names, row)

    def fetchall(self):
        rows = self._cur.fetchall()
        if not rows:
            return []
        return [PostgresRow(self._col_names, r) for r in rows]

    def close(self):
        try:
            self._cur.close()
        except Exception:
            pass

class PostgresConnectionWrapper:
    """Wraps PostgreSQL connection to provide execute() convenience and context manager support."""
    def __init__(self, raw_conn):
        self._conn = raw_conn

    def cursor(self):
        return PostgresCursorWrapper(self._conn.cursor())

    def execute(self, sql, params=None):
        cur = self.cursor()
        return cur.execute(sql, params)

    def commit(self):
        self._conn.commit()

    def rollback(self):
        try:
            self._conn.rollback()
        except Exception:
            pass

    def close(self):
        try:
            self._conn.close()
        except Exception:
            pass

# ==================== CONNECTION FACTORIES ====================

def get_postgres_connection():
    """Connects to cloud PostgreSQL using pg8000 or psycopg2."""
    database_url = Config.DATABASE_URL.strip()
    parsed = urllib.parse.urlparse(database_url)

    # 1. Try pure-Python pg8000 first (runs without any C compiler on Vercel)
    try:
        import pg8000.dbapi as pgdb
        query_params = urllib.parse.parse_qs(parsed.query)
        need_ssl = (
            'sslmode' in query_params or 
            'supabase' in (parsed.hostname or '') or 
            'neon' in (parsed.hostname or '') or
            'aws' in (parsed.hostname or '') or
            parsed.port == 6543
        )
        ssl_ctx = None
        if need_ssl:
            ssl_ctx = ssl.create_default_context()
            ssl_ctx.check_hostname = False
            ssl_ctx.verify_mode = ssl.CERT_NONE

        raw_conn = pgdb.connect(
            user=urllib.parse.unquote(parsed.username or 'postgres'),
            password=urllib.parse.unquote(parsed.password or ''),
            host=parsed.hostname,
            port=parsed.port or 5432,
            database=parsed.path.lstrip('/'),
            ssl_context=ssl_ctx
        )
        return PostgresConnectionWrapper(raw_conn)
    except ImportError:
        pass

    # 2. Try psycopg2 if installed
    try:
        import psycopg2
        raw_conn = psycopg2.connect(database_url)
        return PostgresConnectionWrapper(raw_conn)
    except ImportError:
        pass

    raise RuntimeError(
        "PostgreSQL connection requested via DATABASE_URL, but neither 'pg8000' nor 'psycopg2' is installed. "
        "Please run 'pip install pg8000' or add it to requirements.txt."
    )

def get_sqlite_connection():
    """Connects to local SQLite with WAL mode & foreign keys."""
    conn = sqlite3.connect(Config.DATABASE_PATH, timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    return conn

def get_connection():
    """Unified connection dispatcher."""
    if is_postgres():
        return get_postgres_connection()
    return get_sqlite_connection()

@contextlib.contextmanager
def get_db():
    """Context manager for automatic commit and rollback."""
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

# ==================== SCHEMA INITIALIZATION ====================

def init_postgres_db(cursor):
    """Creates all required tables and indexes in PostgreSQL."""
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id SERIAL PRIMARY KEY,
        email VARCHAR(255) UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        salt TEXT NOT NULL,
        full_name VARCHAR(255) NOT NULL,
        phone VARCHAR(50),
        role VARCHAR(50) DEFAULT 'customer',
        reset_token TEXT,
        reset_expires TIMESTAMP,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS user_addresses (
        id SERIAL PRIMARY KEY,
        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        label VARCHAR(50) DEFAULT 'Home',
        full_name VARCHAR(255) NOT NULL,
        phone VARCHAR(50) NOT NULL,
        address_line1 TEXT NOT NULL,
        address_line2 TEXT,
        landmark TEXT,
        city VARCHAR(100) NOT NULL,
        state VARCHAR(100) NOT NULL,
        pincode VARCHAR(20) NOT NULL,
        is_default INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS categories (
        id SERIAL PRIMARY KEY,
        name VARCHAR(255) NOT NULL,
        slug VARCHAR(255) UNIQUE NOT NULL,
        description TEXT,
        image_url TEXT,
        sort_order INTEGER DEFAULT 0,
        is_active INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS products (
        id SERIAL PRIMARY KEY,
        name VARCHAR(255) NOT NULL,
        slug VARCHAR(255) UNIQUE NOT NULL,
        sku VARCHAR(100) UNIQUE NOT NULL,
        category_id INTEGER NOT NULL REFERENCES categories(id) ON DELETE RESTRICT,
        short_description TEXT,
        description TEXT,
        care_instructions TEXT,
        mrp NUMERIC(10, 2) NOT NULL,
        price NUMERIC(10, 2) NOT NULL,
        stock INTEGER DEFAULT 10,
        weight_grams INTEGER DEFAULT 350,
        badge VARCHAR(50),
        is_featured INTEGER DEFAULT 0,
        is_active INTEGER DEFAULT 1,
        sizes VARCHAR(255) DEFAULT 'Free Size',
        colors VARCHAR(255),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS product_images (
        id SERIAL PRIMARY KEY,
        product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
        image_url TEXT NOT NULL,
        is_primary INTEGER DEFAULT 0,
        sort_order INTEGER DEFAULT 0
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS cart_items (
        id SERIAL PRIMARY KEY,
        session_id VARCHAR(255) NOT NULL,
        user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
        product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
        quantity INTEGER NOT NULL DEFAULT 1,
        selected_size VARCHAR(100) DEFAULT 'Free Size',
        selected_color VARCHAR(100),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS orders (
        id SERIAL PRIMARY KEY,
        order_number VARCHAR(100) UNIQUE NOT NULL,
        user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
        customer_name VARCHAR(255) NOT NULL,
        customer_email VARCHAR(255) NOT NULL,
        customer_phone VARCHAR(50) NOT NULL,
        shipping_address_line1 TEXT NOT NULL,
        shipping_address_line2 TEXT,
        shipping_landmark TEXT,
        shipping_city VARCHAR(100) NOT NULL,
        shipping_state VARCHAR(100) NOT NULL,
        shipping_pincode VARCHAR(20) NOT NULL,
        subtotal NUMERIC(10, 2) NOT NULL,
        coupon_code VARCHAR(100),
        discount_amount NUMERIC(10, 2) DEFAULT 0.0,
        shipping_fee NUMERIC(10, 2) DEFAULT 0.0,
        total_amount NUMERIC(10, 2) NOT NULL,
        payment_method VARCHAR(50) NOT NULL,
        payment_status VARCHAR(50) DEFAULT 'pending',
        razorpay_order_id VARCHAR(255),
        razorpay_payment_id VARCHAR(255),
        razorpay_signature TEXT,
        order_status VARCHAR(100) DEFAULT 'Order Placed',
        courier_name VARCHAR(100),
        tracking_number VARCHAR(100),
        tracking_url TEXT,
        estimated_delivery VARCHAR(100),
        customer_notes TEXT,
        admin_notes TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS order_items (
        id SERIAL PRIMARY KEY,
        order_id INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
        product_id INTEGER REFERENCES products(id) ON DELETE SET NULL,
        product_name VARCHAR(255) NOT NULL,
        product_image TEXT,
        sku VARCHAR(100),
        selected_size VARCHAR(100),
        selected_color VARCHAR(100),
        mrp NUMERIC(10, 2) NOT NULL,
        price NUMERIC(10, 2) NOT NULL,
        quantity INTEGER NOT NULL,
        total_price NUMERIC(10, 2) NOT NULL
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS order_status_history (
        id SERIAL PRIMARY KEY,
        order_id INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
        status VARCHAR(100) NOT NULL,
        comment TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS coupons (
        id SERIAL PRIMARY KEY,
        code VARCHAR(100) UNIQUE NOT NULL,
        description TEXT,
        discount_type VARCHAR(50) NOT NULL,
        discount_value NUMERIC(10, 2) NOT NULL,
        min_order_value NUMERIC(10, 2) DEFAULT 0.0,
        max_discount NUMERIC(10, 2),
        usage_limit INTEGER,
        usage_count INTEGER DEFAULT 0,
        is_active INTEGER DEFAULT 1,
        expires_at TIMESTAMP,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS reviews (
        id SERIAL PRIMARY KEY,
        product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
        user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
        customer_name VARCHAR(255) NOT NULL,
        customer_email VARCHAR(255),
        rating INTEGER NOT NULL CHECK(rating >= 1 AND rating <= 5),
        title VARCHAR(255),
        comment TEXT NOT NULL,
        review_image_url TEXT,
        is_verified_buyer INTEGER DEFAULT 1,
        is_approved INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS wishlist (
        id SERIAL PRIMARY KEY,
        user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
        session_id VARCHAR(255),
        product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(user_id, product_id)
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS settings (
        key VARCHAR(255) PRIMARY KEY,
        value TEXT NOT NULL,
        description TEXT,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS contact_messages (
        id SERIAL PRIMARY KEY,
        name VARCHAR(255) NOT NULL,
        email VARCHAR(255) NOT NULL,
        phone VARCHAR(50),
        subject VARCHAR(255),
        message TEXT NOT NULL,
        is_read INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # Indexes
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

def init_sqlite_db(cursor):
    """Creates all required tables and indexes in SQLite."""
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        salt TEXT NOT NULL,
        full_name TEXT NOT NULL,
        phone TEXT,
        role TEXT DEFAULT 'customer',
        reset_token TEXT,
        reset_expires TIMESTAMP,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS user_addresses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        label TEXT DEFAULT 'Home',
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
        badge TEXT,
        is_featured INTEGER DEFAULT 0,
        is_active INTEGER DEFAULT 1,
        sizes TEXT DEFAULT 'Free Size',
        colors TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(category_id) REFERENCES categories(id) ON DELETE RESTRICT
    );
    """)

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
        payment_method TEXT NOT NULL,
        payment_status TEXT DEFAULT 'pending',
        razorpay_order_id TEXT,
        razorpay_payment_id TEXT,
        razorpay_signature TEXT,
        order_status TEXT DEFAULT 'Order Placed',
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

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS coupons (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT UNIQUE NOT NULL,
        description TEXT,
        discount_type TEXT NOT NULL,
        discount_value REAL NOT NULL,
        min_order_value REAL DEFAULT 0.0,
        max_discount REAL,
        usage_limit INTEGER,
        usage_count INTEGER DEFAULT 0,
        is_active INTEGER DEFAULT 1,
        expires_at TIMESTAMP,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

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
        review_image_url TEXT,
        is_verified_buyer INTEGER DEFAULT 1,
        is_approved INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(product_id) REFERENCES products(id) ON DELETE CASCADE,
        FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE SET NULL
    );
    """)

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

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL,
        description TEXT,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

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

    # Indexes
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

def init_db():
    """Initializes tables for either PostgreSQL or SQLite based on configuration."""
    with get_db() as conn:
        cursor = conn.cursor()
        if is_postgres():
            init_postgres_db(cursor)
        else:
            init_sqlite_db(cursor)

if __name__ == '__main__':
    init_db()
    db_type = "PostgreSQL" if is_postgres() else "SQLite"
    print(f"Database ({db_type}) initialized successfully.")

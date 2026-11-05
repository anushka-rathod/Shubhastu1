"""
Data Access Layer (DAL) for Shubhashtu Fashion.
Encapsulates all database operations with clean Python functions.
"""
import random
import string
from datetime import datetime
from db import get_db

def generate_order_number() -> str:
    """Generates unique brand order number like SHB-2026-8942."""
    year = datetime.now().year
    rand_chars = ''.join(random.choices(string.digits, k=5))
    return f"SHB-{year}-{rand_chars}"

# ----------------- Settings -----------------
def get_store_settings() -> dict:
    """Returns all settings as a key-value dictionary."""
    with get_db() as conn:
        rows = conn.execute("SELECT key, value FROM settings").fetchall()
        return {r['key']: r['value'] for r in rows}

def get_setting(key: str, default: str = "") -> str:
    with get_db() as conn:
        row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        return row['value'] if row else default

def update_setting(key: str, value: str, description: str = ""):
    with get_db() as conn:
        conn.execute(
            """INSERT INTO settings (key, value, description, updated_at) 
               VALUES (?, ?, ?, CURRENT_TIMESTAMP)
               ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=CURRENT_TIMESTAMP""",
            (key, str(value), description)
        )

# ----------------- Categories -----------------
def get_categories(only_active: bool = True) -> list[dict]:
    with get_db() as conn:
        sql = "SELECT * FROM categories"
        if only_active:
            sql += " WHERE is_active = 1"
        sql += " ORDER BY sort_order ASC, name ASC"
        return [dict(r) for r in conn.execute(sql).fetchall()]

def get_category_by_id(cat_id: int) -> dict | None:
    with get_db() as conn:
        row = conn.execute("SELECT * FROM categories WHERE id = ?", (cat_id,)).fetchone()
        return dict(row) if row else None

def get_category_by_slug(slug: str) -> dict | None:
    with get_db() as conn:
        row = conn.execute("SELECT * FROM categories WHERE slug = ?", (slug,)).fetchone()
        return dict(row) if row else None

def create_category(name: str, slug: str, description: str, image_url: str, sort_order: int = 0) -> int:
    with get_db() as conn:
        cursor = conn.execute(
            "INSERT INTO categories (name, slug, description, image_url, sort_order) VALUES (?, ?, ?, ?, ?)",
            (name, slug, description, image_url, sort_order)
        )
        return cursor.lastrowid

def update_category(cat_id: int, name: str, slug: str, description: str, image_url: str, sort_order: int, is_active: int):
    with get_db() as conn:
        conn.execute(
            "UPDATE categories SET name=?, slug=?, description=?, image_url=?, sort_order=?, is_active=? WHERE id=?",
            (name, slug, description, image_url, sort_order, is_active, cat_id)
        )

def delete_category(cat_id: int) -> bool:
    with get_db() as conn:
        # Check if products exist in category
        count = conn.execute("SELECT COUNT(*) FROM products WHERE category_id = ?", (cat_id,)).fetchone()[0]
        if count > 0:
            return False
        conn.execute("DELETE FROM categories WHERE id = ?", (cat_id,))
        return True

# ----------------- Products -----------------
def get_products(category_slug: str = None, search: str = None, sort_by: str = None, 
                 badge: str = None, is_featured: bool = None, only_active: bool = True,
                 min_price: float = None, max_price: float = None, limit: int = None, offset: int = None) -> list[dict]:
    with get_db() as conn:
        sql = """
        SELECT p.*, c.name as category_name, c.slug as category_slug,
               (SELECT image_url FROM product_images WHERE product_id = p.id ORDER BY is_primary DESC, sort_order ASC LIMIT 1) as primary_image,
               (SELECT image_url FROM product_images WHERE product_id = p.id AND is_primary = 0 ORDER BY sort_order ASC LIMIT 1) as secondary_image,
               (SELECT AVG(rating) FROM reviews WHERE product_id = p.id AND is_approved = 1) as avg_rating,
               (SELECT COUNT(*) FROM reviews WHERE product_id = p.id AND is_approved = 1) as review_count
        FROM products p
        JOIN categories c ON p.category_id = c.id
        WHERE 1=1
        """
        params = []

        if only_active:
            sql += " AND p.is_active = 1"

        if category_slug and category_slug != 'all':
            sql += " AND c.slug = ?"
            params.append(category_slug)

        if badge:
            sql += " AND p.badge = ?"
            params.append(badge)

        if is_featured:
            sql += " AND p.is_featured = 1"

        if min_price is not None:
            sql += " AND p.price >= ?"
            params.append(min_price)

        if max_price is not None:
            sql += " AND p.price <= ?"
            params.append(max_price)

        if search:
            search_query = f"%{search.strip()}%"
            sql += " AND (p.name LIKE ? OR p.description LIKE ? OR p.short_description LIKE ? OR c.name LIKE ?)"
            params.extend([search_query, search_query, search_query, search_query])

        if sort_by == 'price_low_high':
            sql += " ORDER BY p.price ASC"
        elif sort_by == 'price_high_low':
            sql += " ORDER BY p.price DESC"
        elif sort_by == 'popular':
            sql += " ORDER BY avg_rating DESC NULLS LAST, review_count DESC"
        elif sort_by == 'discount':
            sql += " ORDER BY ((p.mrp - p.price) / p.mrp) DESC"
        elif sort_by == 'oldest':
            sql += " ORDER BY p.id ASC"
        else: # 'newest' default
            sql += " ORDER BY p.created_at DESC, p.id DESC"

        if limit is not None:
            sql += " LIMIT ?"
            params.append(limit)
            if offset is not None:
                sql += " OFFSET ?"
                params.append(offset)

        rows = conn.execute(sql, params).fetchall()
        products = []
        for r in rows:
            p = dict(r)
            p['discount_pct'] = round(((p['mrp'] - p['price']) / p['mrp'] * 100)) if p['mrp'] > p['price'] else 0
            p['avg_rating'] = round(p['avg_rating'], 1) if p['avg_rating'] else 5.0
            p['sizes_list'] = [s.strip() for s in (p.get('sizes') or 'Free Size').split(',') if s.strip()]
            p['colors_list'] = [c.strip() for c in (p.get('colors') or '').split(',') if c.strip()]
            products.append(p)
        return products

def get_product_by_id(product_id: int) -> dict | None:
    with get_db() as conn:
        sql = """
        SELECT p.*, c.name as category_name, c.slug as category_slug,
               (SELECT image_url FROM product_images WHERE product_id = p.id ORDER BY is_primary DESC, sort_order ASC LIMIT 1) as primary_image,
               (SELECT image_url FROM product_images WHERE product_id = p.id AND is_primary = 0 ORDER BY sort_order ASC LIMIT 1) as secondary_image,
               (SELECT AVG(rating) FROM reviews WHERE product_id = p.id AND is_approved = 1) as avg_rating,
               (SELECT COUNT(*) FROM reviews WHERE product_id = p.id AND is_approved = 1) as review_count
        FROM products p
        JOIN categories c ON p.category_id = c.id
        WHERE p.id = ?
        """
        row = conn.execute(sql, (product_id,)).fetchone()
        if not row:
            return None
        p = dict(row)
        p['discount_pct'] = round(((p['mrp'] - p['price']) / p['mrp'] * 100)) if p['mrp'] > p['price'] else 0
        p['avg_rating'] = round(p['avg_rating'], 1) if p['avg_rating'] else 5.0
        p['sizes_list'] = [s.strip() for s in (p.get('sizes') or 'Free Size').split(',') if s.strip()]
        p['colors_list'] = [c.strip() for c in (p.get('colors') or '').split(',') if c.strip()]
        
        # Fetch all images
        img_rows = conn.execute("SELECT * FROM product_images WHERE product_id = ? ORDER BY is_primary DESC, sort_order ASC", (product_id,)).fetchall()
        p['images'] = [dict(img) for img in img_rows]
        return p

def get_product_by_slug(slug: str) -> dict | None:
    with get_db() as conn:
        row = conn.execute("SELECT id FROM products WHERE slug = ?", (slug,)).fetchone()
        if not row:
            return None
        return get_product_by_id(row['id'])

def get_related_products(category_id: int, exclude_id: int, limit: int = 4) -> list[dict]:
    with get_db() as conn:
        sql = """
        SELECT p.*, c.name as category_name, c.slug as category_slug,
               (SELECT image_url FROM product_images WHERE product_id = p.id ORDER BY is_primary DESC, sort_order ASC LIMIT 1) as primary_image,
               (SELECT image_url FROM product_images WHERE product_id = p.id AND is_primary = 0 ORDER BY sort_order ASC LIMIT 1) as secondary_image,
               (SELECT AVG(rating) FROM reviews WHERE product_id = p.id AND is_approved = 1) as avg_rating,
               (SELECT COUNT(*) FROM reviews WHERE product_id = p.id AND is_approved = 1) as review_count
        FROM products p
        JOIN categories c ON p.category_id = c.id
        WHERE p.category_id = ? AND p.id != ? AND p.is_active = 1
        ORDER BY RANDOM() LIMIT ?
        """
        rows = conn.execute(sql, (category_id, exclude_id, limit)).fetchall()
        items = []
        for r in rows:
            p = dict(r)
            p['discount_pct'] = round(((p['mrp'] - p['price']) / p['mrp'] * 100)) if p['mrp'] > p['price'] else 0
            p['avg_rating'] = round(p['avg_rating'], 1) if p['avg_rating'] else 5.0
            items.append(p)
        return items

def create_product(data: dict) -> int:
    with get_db() as conn:
        cursor = conn.execute("""
            INSERT INTO products (
                name, slug, sku, category_id, short_description, description, 
                care_instructions, mrp, price, stock, weight_grams, badge, 
                is_featured, is_active, sizes, colors
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            data['name'], data['slug'], data['sku'], data['category_id'],
            data.get('short_description', ''), data.get('description', ''),
            data.get('care_instructions', ''), data['mrp'], data['price'],
            data.get('stock', 10), data.get('weight_grams', 350), data.get('badge', ''),
            data.get('is_featured', 0), data.get('is_active', 1),
            data.get('sizes', 'Free Size'), data.get('colors', '')
        ))
        product_id = cursor.lastrowid

        # Insert images
        images = data.get('images', [])
        for i, img_url in enumerate(images):
            if img_url:
                conn.execute(
                    "INSERT INTO product_images (product_id, image_url, is_primary, sort_order) VALUES (?, ?, ?, ?)",
                    (product_id, img_url, 1 if i == 0 else 0, i)
                )

        return product_id

def update_product(product_id: int, data: dict):
    existing = get_product_by_id(product_id)
    if not existing:
        return
    merged = {**existing, **data}
    with get_db() as conn:
        conn.execute("""
            UPDATE products SET
                name=?, slug=?, sku=?, category_id=?, short_description=?, description=?,
                care_instructions=?, mrp=?, price=?, stock=?, weight_grams=?, badge=?,
                is_featured=?, is_active=?, sizes=?, colors=?, updated_at=CURRENT_TIMESTAMP
            WHERE id=?
        """, (
            merged['name'], merged['slug'], merged['sku'], merged['category_id'],
            merged.get('short_description', ''), merged.get('description', ''),
            merged.get('care_instructions', ''), merged['mrp'], merged['price'],
            merged.get('stock', 10), merged.get('weight_grams', 350), merged.get('badge', ''),
            merged.get('is_featured', 0), merged.get('is_active', 1),
            merged.get('sizes', 'Free Size'), merged.get('colors', ''),
            product_id
        ))

        # Update images if provided
        if 'images' in data and data['images']:
            conn.execute("DELETE FROM product_images WHERE product_id = ?", (product_id,))
            for i, img_url in enumerate(data['images']):
                if img_url:
                    conn.execute(
                        "INSERT INTO product_images (product_id, image_url, is_primary, sort_order) VALUES (?, ?, ?, ?)",
                        (product_id, img_url, 1 if i == 0 else 0, i)
                    )

def delete_product(product_id: int):
    with get_db() as conn:
        conn.execute("DELETE FROM products WHERE id = ?", (product_id,))

# ----------------- Cart -----------------
def get_cart_item_count(session_id: str, user_id: int = None) -> int:
    with get_db() as conn:
        if user_id:
            row = conn.execute("SELECT SUM(quantity) FROM cart_items WHERE user_id = ? OR session_id = ?", (user_id, session_id)).fetchone()
        else:
            row = conn.execute("SELECT SUM(quantity) FROM cart_items WHERE session_id = ?", (session_id,)).fetchone()
        return row[0] if (row and row[0]) else 0

def get_cart(session_id: str, user_id: int = None) -> dict:
    with get_db() as conn:
        if user_id:
            sql = """
            SELECT c.*, p.name, p.slug, p.mrp, p.price, p.stock, p.weight_grams,
                   (SELECT image_url FROM product_images WHERE product_id = p.id ORDER BY is_primary DESC, sort_order ASC LIMIT 1) as primary_image
            FROM cart_items c
            JOIN products p ON c.product_id = p.id
            WHERE c.user_id = ? OR c.session_id = ?
            ORDER BY c.created_at DESC
            """
            rows = conn.execute(sql, (user_id, session_id)).fetchall()
        else:
            sql = """
            SELECT c.*, p.name, p.slug, p.mrp, p.price, p.stock, p.weight_grams,
                   (SELECT image_url FROM product_images WHERE product_id = p.id ORDER BY is_primary DESC, sort_order ASC LIMIT 1) as primary_image
            FROM cart_items c
            JOIN products p ON c.product_id = p.id
            WHERE c.session_id = ?
            ORDER BY c.created_at DESC
            """
            rows = conn.execute(sql, (session_id,)).fetchall()

        items = []
        subtotal = 0.0
        mrp_total = 0.0
        total_weight_grams = 0

        for r in rows:
            item = dict(r)
            item['item_total'] = round(item['price'] * item['quantity'], 2)
            item['mrp_total'] = round(item['mrp'] * item['quantity'], 2)
            subtotal += item['item_total']
            mrp_total += item['mrp_total']
            total_weight_grams += item.get('weight_grams', 350) * item['quantity']
            items.append(item)

        total_savings = round(mrp_total - subtotal, 2) if mrp_total > subtotal else 0.0

        return {
            'items': items,
            'item_count': sum(i['quantity'] for i in items),
            'subtotal': round(subtotal, 2),
            'mrp_total': round(mrp_total, 2),
            'total_savings': total_savings,
            'total_weight_grams': total_weight_grams
        }

def add_to_cart(session_id: str, product_id: int, quantity: int = 1, size: str = 'Free Size', color: str = '', user_id: int = None) -> dict:
    with get_db() as conn:
        # Check product stock
        prod = conn.execute("SELECT stock, is_active FROM products WHERE id = ?", (product_id,)).fetchone()
        if not prod or not prod['is_active']:
            return {'success': False, 'message': 'Product is currently unavailable.'}
        if prod['stock'] < 1:
            return {'success': False, 'message': 'Product is out of stock.'}

        # Check if already in cart
        if user_id:
            existing = conn.execute(
                "SELECT id, quantity FROM cart_items WHERE (user_id = ? OR session_id = ?) AND product_id = ? AND selected_size = ?",
                (user_id, session_id, product_id, size)
            ).fetchone()
        else:
            existing = conn.execute(
                "SELECT id, quantity FROM cart_items WHERE session_id = ? AND product_id = ? AND selected_size = ?",
                (session_id, product_id, size)
            ).fetchone()

        if existing:
            new_qty = min(prod['stock'], existing['quantity'] + quantity)
            conn.execute("UPDATE cart_items SET quantity = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (new_qty, existing['id']))
        else:
            conn.execute("""
                INSERT INTO cart_items (session_id, user_id, product_id, quantity, selected_size, selected_color)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (session_id, user_id, product_id, min(prod['stock'], quantity), size, color))

        return {'success': True}

def update_cart_quantity(cart_item_id: int, quantity: int, session_id: str, user_id: int = None) -> bool:
    with get_db() as conn:
        if quantity <= 0:
            return remove_from_cart(cart_item_id, session_id, user_id)

        # Verify ownership & stock
        row = conn.execute("""
            SELECT c.id, p.stock 
            FROM cart_items c 
            JOIN products p ON c.product_id = p.id 
            WHERE c.id = ? AND (c.session_id = ? OR c.user_id = ?)
        """, (cart_item_id, session_id, user_id)).fetchone()

        if not row:
            return False

        allowed_qty = min(row['stock'], quantity)
        conn.execute("UPDATE cart_items SET quantity = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (allowed_qty, cart_item_id))
        return True

def remove_from_cart(cart_item_id: int, session_id: str, user_id: int = None) -> bool:
    with get_db() as conn:
        conn.execute("DELETE FROM cart_items WHERE id = ? AND (session_id = ? OR user_id = ?)", (cart_item_id, session_id, user_id))
        return True

def clear_cart(session_id: str, user_id: int = None):
    with get_db() as conn:
        if user_id:
            conn.execute("DELETE FROM cart_items WHERE user_id = ? OR session_id = ?", (user_id, session_id))
        else:
            conn.execute("DELETE FROM cart_items WHERE session_id = ?", (session_id,))

def merge_guest_cart(session_id: str, user_id: int):
    with get_db() as conn:
        conn.execute("UPDATE cart_items SET user_id = ? WHERE session_id = ?", (user_id, session_id))

# ----------------- Coupons -----------------
def get_coupons(only_active: bool = False) -> list[dict]:
    with get_db() as conn:
        sql = "SELECT * FROM coupons"
        if only_active:
            sql += " WHERE is_active = 1"
        sql += " ORDER BY created_at DESC"
        return [dict(r) for r in conn.execute(sql).fetchall()]

def get_coupon_by_code(code: str) -> dict | None:
    with get_db() as conn:
        row = conn.execute("SELECT * FROM coupons WHERE UPPER(code) = UPPER(?)", (code.strip(),)).fetchone()
        return dict(row) if row else None

def validate_coupon(code: str, subtotal: float) -> dict:
    coupon = get_coupon_by_code(code)
    if not coupon:
        return {'valid': False, 'message': 'Invalid coupon code.'}

    if not coupon['is_active']:
        return {'valid': False, 'message': 'This coupon code has expired or is inactive.'}

    if coupon['min_order_value'] > subtotal:
        return {
            'valid': False, 
            'message': f"Minimum order value for coupon {coupon['code']} is ₹{coupon['min_order_value']:.2f}."
        }

    if coupon['usage_limit'] and coupon['usage_count'] >= coupon['usage_limit']:
        return {'valid': False, 'message': 'Coupon usage limit has been reached.'}

    # Calculate discount
    if coupon['discount_type'] == 'percentage':
        discount = (subtotal * coupon['discount_value']) / 100.0
        if coupon['max_discount']:
            discount = min(discount, coupon['max_discount'])
    else: # fixed amount
        discount = min(subtotal, coupon['discount_value'])

    discount = round(discount, 2)

    return {
        'valid': True,
        'code': coupon['code'],
        'discount': discount,
        'description': coupon.get('description', ''),
        'message': f"Coupon applied! You saved ₹{discount:.2f}."
    }

def create_coupon(data: dict) -> int:
    with get_db() as conn:
        cursor = conn.execute("""
            INSERT INTO coupons (code, description, discount_type, discount_value, min_order_value, max_discount, usage_limit, is_active)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            data['code'].upper().strip(), data.get('description', ''),
            data['discount_type'], data['discount_value'],
            data.get('min_order_value', 0.0), data.get('max_discount'),
            data.get('usage_limit'), data.get('is_active', 1)
        ))
        return cursor.lastrowid

def toggle_coupon_active(coupon_id: int):
    with get_db() as conn:
        conn.execute("UPDATE coupons SET is_active = CASE WHEN is_active = 1 THEN 0 ELSE 1 END WHERE id = ?", (coupon_id,))

def delete_coupon(coupon_id: int):
    with get_db() as conn:
        conn.execute("DELETE FROM coupons WHERE id = ?", (coupon_id,))

# ----------------- Orders -----------------
def create_order(order_data: dict, items: list[dict]) -> dict:
    """
    Creates an order, associated order items, updates inventory stock,
    and logs status history in a single atomic transaction.
    """
    with get_db() as conn:
        order_number = generate_order_number()

        cursor = conn.execute("""
            INSERT INTO orders (
                order_number, user_id, customer_name, customer_email, customer_phone,
                shipping_address_line1, shipping_address_line2, shipping_landmark,
                shipping_city, shipping_state, shipping_pincode,
                subtotal, coupon_code, discount_amount, shipping_fee, total_amount,
                payment_method, payment_status, razorpay_order_id, razorpay_payment_id, razorpay_signature,
                order_status, courier_name, tracking_number, tracking_url, estimated_delivery, customer_notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            order_number, order_data.get('user_id'), order_data['customer_name'],
            order_data['customer_email'], order_data['customer_phone'],
            order_data['shipping_address_line1'], order_data.get('shipping_address_line2', ''),
            order_data.get('shipping_landmark', ''), order_data['shipping_city'],
            order_data['shipping_state'], order_data['shipping_pincode'],
            order_data['subtotal'], order_data.get('coupon_code', ''),
            order_data.get('discount_amount', 0.0), order_data.get('shipping_fee', 0.0),
            order_data['total_amount'], order_data['payment_method'],
            order_data.get('payment_status', 'pending'),
            order_data.get('razorpay_order_id', ''), order_data.get('razorpay_payment_id', ''),
            order_data.get('razorpay_signature', ''),
            order_data.get('order_status', 'Order Placed'),
            order_data.get('courier_name', 'Shubhashtu Courier Partner'),
            order_data.get('tracking_number', ''), order_data.get('tracking_url', ''),
            order_data.get('estimated_delivery', '3-5 Business Days'),
            order_data.get('customer_notes', '')
        ))
        order_id = cursor.lastrowid

        # Insert items and decrement stock
        for it in items:
            conn.execute("""
                INSERT INTO order_items (
                    order_id, product_id, product_name, product_image, sku,
                    selected_size, selected_color, mrp, price, quantity, total_price
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                order_id, it.get('product_id'), it['product_name'],
                it.get('product_image', ''), it.get('sku', ''),
                it.get('selected_size', 'Free Size'), it.get('selected_color', ''),
                it.get('mrp', it['price']), it['price'], it['quantity'],
                round(it['price'] * it['quantity'], 2)
            ))

            if it.get('product_id'):
                conn.execute(
                    "UPDATE products SET stock = MAX(0, stock - ?) WHERE id = ?",
                    (it['quantity'], it['product_id'])
                )

        # Log initial status history
        conn.execute("""
            INSERT INTO order_status_history (order_id, status, comment)
            VALUES (?, ?, ?)
        """, (order_id, 'Order Placed', 'Order placed successfully.'))

        # Increment coupon usage count if used
        if order_data.get('coupon_code'):
            conn.execute(
                "UPDATE coupons SET usage_count = usage_count + 1 WHERE UPPER(code) = UPPER(?)",
                (order_data['coupon_code'],)
            )

    return get_order_by_id(order_id)

def get_order_items(order_id: int) -> list[dict]:
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM order_items WHERE order_id = ?", (order_id,)).fetchall()
        return [dict(r) for r in rows]

def get_order_by_id(order_id: int) -> dict | None:
    with get_db() as conn:
        row = conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
        if not row:
            return None
        order = dict(row)
        item_rows = conn.execute("SELECT * FROM order_items WHERE order_id = ?", (order_id,)).fetchall()
        order['items'] = [dict(it) for it in item_rows]
        history_rows = conn.execute("SELECT * FROM order_status_history WHERE order_id = ? ORDER BY created_at ASC", (order_id,)).fetchall()
        order['history'] = [dict(h) for h in history_rows]
        return order

def get_order_by_number(order_number: str) -> dict | None:
    with get_db() as conn:
        row = conn.execute("SELECT id FROM orders WHERE UPPER(order_number) = UPPER(?)", (order_number.strip(),)).fetchone()
        if not row:
            return None
        return get_order_by_id(row['id'])

def get_order_tracking(order_number: str, phone_or_email: str = None) -> dict | None:
    with get_db() as conn:
        sql = "SELECT id, customer_phone, customer_email FROM orders WHERE UPPER(order_number) = UPPER(?)"
        row = conn.execute(sql, (order_number.strip(),)).fetchone()
        if not row:
            return None

        if phone_or_email:
            check = phone_or_email.strip().lower()
            stored_phone = str(row['customer_phone']).strip().lower()
            stored_email = str(row['customer_email']).strip().lower()
            if check not in stored_phone and check != stored_email:
                return None

        return get_order_by_id(row['id'])

def get_orders_for_user(user_id: int) -> list[dict]:
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM orders WHERE user_id = ? ORDER BY created_at DESC", (user_id,)).fetchall()
        orders = []
        for r in rows:
            ord_dict = dict(r)
            item_rows = conn.execute("SELECT * FROM order_items WHERE order_id = ?", (ord_dict['id'],)).fetchall()
            ord_dict['items'] = [dict(it) for it in item_rows]
            orders.append(ord_dict)
        return orders

# Compatibility alias
get_user_orders = get_orders_for_user

def get_all_orders(status_filter: str = None, search: str = None, limit: int = 100) -> list[dict]:
    with get_db() as conn:
        sql = "SELECT * FROM orders WHERE 1=1"
        params = []
        if status_filter and status_filter != 'all':
            sql += " AND order_status = ?"
            params.append(status_filter)
        if search:
            q = f"%{search.strip()}%"
            sql += " AND (order_number LIKE ? OR customer_name LIKE ? OR customer_email LIKE ? OR customer_phone LIKE ?)"
            params.extend([q, q, q, q])
        sql += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        rows = conn.execute(sql, params).fetchall()
        orders = []
        for r in rows:
            ord_dict = dict(r)
            count = conn.execute("SELECT COUNT(*) FROM order_items WHERE order_id = ?", (ord_dict['id'],)).fetchone()[0]
            ord_dict['item_count'] = count
            orders.append(ord_dict)
        return orders

def update_order_status(order_id: int, new_status: str, comment: str = "", courier_name: str = None, tracking_number: str = None, tracking_url: str = None):
    with get_db() as conn:
        updates = ["order_status = ?", "updated_at = CURRENT_TIMESTAMP"]
        params = [new_status]

        if courier_name is not None:
            updates.append("courier_name = ?")
            params.append(courier_name)
        if tracking_number is not None:
            updates.append("tracking_number = ?")
            params.append(tracking_number)
        if tracking_url is not None:
            updates.append("tracking_url = ?")
            params.append(tracking_url)

        params.append(order_id)
        sql = f"UPDATE orders SET {', '.join(updates)} WHERE id = ?"
        conn.execute(sql, params)

        # Append timeline
        conn.execute(
            "INSERT INTO order_status_history (order_id, status, comment) VALUES (?, ?, ?)",
            (order_id, new_status, comment or f"Status changed to {new_status}")
        )

def update_payment_status(order_id: int, payment_status: str, razorpay_order_id: str = None, razorpay_payment_id: str = None, razorpay_signature: str = None):
    with get_db() as conn:
        conn.execute("""
            UPDATE orders SET 
                payment_status = ?,
                razorpay_order_id = COALESCE(?, razorpay_order_id),
                razorpay_payment_id = COALESCE(?, razorpay_payment_id),
                razorpay_signature = COALESCE(?, razorpay_signature),
                order_status = CASE WHEN ? = 'paid' AND order_status = 'Order Placed' THEN 'Confirmed' ELSE order_status END,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (payment_status, razorpay_order_id, razorpay_payment_id, razorpay_signature, payment_status, order_id))

        if payment_status == 'paid':
            conn.execute(
                "INSERT INTO order_status_history (order_id, status, comment) VALUES (?, 'Confirmed', 'Payment received via Razorpay.')",
                (order_id,)
            )

def delete_order(order_id: int) -> tuple[bool, str]:
    """Permanently deletes an order and associated items and status logs."""
    with get_db() as conn:
        order = conn.execute("SELECT id, order_number FROM orders WHERE id = ?", (order_id,)).fetchone()
        if not order:
            return False, "Order not found."
        conn.execute("DELETE FROM order_items WHERE order_id = ?", (order_id,))
        conn.execute("DELETE FROM order_status_history WHERE order_id = ?", (order_id,))
        conn.execute("DELETE FROM orders WHERE id = ?", (order_id,))
        return True, f"Order #{order['order_number']} deleted successfully."

def get_dashboard_metrics() -> dict:
    with get_db() as conn:
        total_sales = conn.execute("SELECT SUM(total_amount) FROM orders WHERE payment_status = 'paid' OR payment_method = 'cod'").fetchone()[0] or 0.0
        total_orders = conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0] or 0
        pending_orders = conn.execute("SELECT COUNT(*) FROM orders WHERE order_status IN ('Order Placed', 'Confirmed', 'Processing')").fetchone()[0] or 0
        delivered_orders = conn.execute("SELECT COUNT(*) FROM orders WHERE order_status = 'Delivered'").fetchone()[0] or 0
        total_customers = conn.execute("SELECT COUNT(*) FROM users WHERE role = 'customer'").fetchone()[0] or 0
        low_stock_products = conn.execute("SELECT COUNT(*) FROM products WHERE stock <= 3 AND is_active = 1").fetchone()[0] or 0

        # Recent 7 orders
        recent_rows = conn.execute("SELECT * FROM orders ORDER BY created_at DESC LIMIT 7").fetchall()
        recent_orders = [dict(r) for r in recent_rows]

        return {
            'total_sales': round(total_sales, 2),
            'total_orders': total_orders,
            'pending_orders': pending_orders,
            'delivered_orders': delivered_orders,
            'total_customers': total_customers,
            'low_stock_products': low_stock_products,
            'recent_orders': recent_orders
        }

# ----------------- Users -----------------
def get_user_by_email(email: str) -> dict | None:
    with get_db() as conn:
        row = conn.execute("SELECT * FROM users WHERE LOWER(email) = LOWER(?)", (email.strip(),)).fetchone()
        return dict(row) if row else None

def get_user_by_id(user_id: int) -> dict | None:
    with get_db() as conn:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return dict(row) if row else None

def create_user(email: str, password_hash: str, salt: str, full_name: str, phone: str = '', role: str = 'customer') -> int:
    with get_db() as conn:
        cursor = conn.execute("""
            INSERT INTO users (email, password_hash, salt, full_name, phone, role)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (email.strip().lower(), password_hash, salt, full_name.strip(), phone.strip(), role))
        return cursor.lastrowid

def update_user_profile(user_id: int, full_name: str, phone: str):
    with get_db() as conn:
        conn.execute("UPDATE users SET full_name = ?, phone = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (full_name, phone, user_id))

def update_user_password(user_id: int, password_hash: str, salt: str):
    with get_db() as conn:
        conn.execute("UPDATE users SET password_hash = ?, salt = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (password_hash, salt, user_id))

def get_all_customers() -> list[dict]:
    with get_db() as conn:
        sql = """
        SELECT u.id, u.email, u.full_name, u.phone, u.created_at,
               COUNT(o.id) as order_count,
               COALESCE(SUM(o.total_amount), 0) as total_spent
        FROM users u
        LEFT JOIN orders o ON u.id = o.user_id
        WHERE u.role = 'customer'
        GROUP BY u.id
        ORDER BY u.created_at DESC
        """
        rows = conn.execute(sql).fetchall()
        return [dict(r) for r in rows]

def delete_customer(customer_id: int) -> tuple[bool, str]:
    """Deletes a customer account and cleans up associated shopping state."""
    with get_db() as conn:
        user = conn.execute("SELECT id, role, full_name, email FROM users WHERE id = ?", (customer_id,)).fetchone()
        if not user:
            return False, "Customer not found."
        if user['role'] == 'admin':
            return False, "Cannot delete an administrator account."
        
        # Clean up related customer records
        conn.execute("DELETE FROM user_addresses WHERE user_id = ?", (customer_id,))
        conn.execute("DELETE FROM cart_items WHERE user_id = ?", (customer_id,))
        conn.execute("DELETE FROM wishlist WHERE user_id = ?", (customer_id,))
        # Disassociate from historical orders so ledger data is not lost
        conn.execute("UPDATE orders SET user_id = NULL WHERE user_id = ?", (customer_id,))
        conn.execute("UPDATE reviews SET user_id = NULL WHERE user_id = ?", (customer_id,))
        conn.execute("DELETE FROM users WHERE id = ?", (customer_id,))
        return True, f"Customer account {user['email']} deleted successfully."

# ----------------- User Addresses -----------------
def get_user_addresses(user_id: int) -> list[dict]:
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM user_addresses WHERE user_id = ? ORDER BY is_default DESC, id DESC", (user_id,)).fetchall()
        return [dict(r) for r in rows]

def add_user_address(user_id: int, data: dict) -> int:
    with get_db() as conn:
        if data.get('is_default'):
            conn.execute("UPDATE user_addresses SET is_default = 0 WHERE user_id = ?", (user_id,))
        cursor = conn.execute("""
            INSERT INTO user_addresses (
                user_id, label, full_name, phone, address_line1, address_line2, landmark, city, state, pincode, is_default
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            user_id, data.get('label', 'Home'), data['full_name'], data['phone'],
            data['address_line1'], data.get('address_line2', ''), data.get('landmark', ''),
            data['city'], data['state'], data['pincode'], 1 if data.get('is_default') else 0
        ))
        return cursor.lastrowid

def delete_user_address(address_id: int, user_id: int):
    with get_db() as conn:
        conn.execute("DELETE FROM user_addresses WHERE id = ? AND user_id = ?", (address_id, user_id))

def set_default_address(address_id: int, user_id: int):
    with get_db() as conn:
        conn.execute("UPDATE user_addresses SET is_default = 0 WHERE user_id = ?", (user_id,))
        conn.execute("UPDATE user_addresses SET is_default = 1 WHERE id = ? AND user_id = ?", (address_id, user_id))

# ----------------- Reviews -----------------
def get_product_reviews(product_id: int, approved_only: bool = True) -> list[dict]:
    with get_db() as conn:
        sql = "SELECT * FROM reviews WHERE product_id = ?"
        if approved_only:
            sql += " AND is_approved = 1"
        sql += " ORDER BY created_at DESC"
        rows = conn.execute(sql, (product_id,)).fetchall()
        return [dict(r) for r in rows]

def add_review(product_id: int, name: str, email: str, rating: int, comment: str, title: str = "", user_id: int = None) -> int:
    with get_db() as conn:
        cursor = conn.execute("""
            INSERT INTO reviews (product_id, user_id, customer_name, customer_email, rating, title, comment, is_approved)
            VALUES (?, ?, ?, ?, ?, ?, ?, 1)
        """, (product_id, user_id, name.strip(), email.strip(), rating, title.strip(), comment.strip()))
        return cursor.lastrowid

def get_all_reviews() -> list[dict]:
    with get_db() as conn:
        sql = """
        SELECT r.*, p.name as product_name, p.slug as product_slug
        FROM reviews r
        JOIN products p ON r.product_id = p.id
        ORDER BY r.created_at DESC
        """
        rows = conn.execute(sql).fetchall()
        return [dict(r) for r in rows]

def toggle_review_approval(review_id: int):
    with get_db() as conn:
        conn.execute("UPDATE reviews SET is_approved = CASE WHEN is_approved = 1 THEN 0 ELSE 1 END WHERE id = ?", (review_id,))

def delete_review(review_id: int):
    with get_db() as conn:
        conn.execute("DELETE FROM reviews WHERE id = ?", (review_id,))

# ----------------- Wishlist -----------------
def get_wishlist(session_id: str, user_id: int = None) -> list[dict]:
    with get_db() as conn:
        if user_id:
            sql = """
            SELECT p.*, c.name as category_name, c.slug as category_slug,
                   (SELECT image_url FROM product_images WHERE product_id = p.id ORDER BY is_primary DESC, sort_order ASC LIMIT 1) as primary_image
            FROM wishlist w
            JOIN products p ON w.product_id = p.id
            JOIN categories c ON p.category_id = c.id
            WHERE w.user_id = ? OR w.session_id = ?
            ORDER BY w.created_at DESC
            """
            rows = conn.execute(sql, (user_id, session_id)).fetchall()
        else:
            sql = """
            SELECT p.*, c.name as category_name, c.slug as category_slug,
                   (SELECT image_url FROM product_images WHERE product_id = p.id ORDER BY is_primary DESC, sort_order ASC LIMIT 1) as primary_image
            FROM wishlist w
            JOIN products p ON w.product_id = p.id
            JOIN categories c ON p.category_id = c.id
            WHERE w.session_id = ?
            ORDER BY w.created_at DESC
            """
            rows = conn.execute(sql, (session_id,)).fetchall()

        items = []
        for r in rows:
            p = dict(r)
            p['discount_pct'] = round(((p['mrp'] - p['price']) / p['mrp'] * 100)) if p['mrp'] > p['price'] else 0
            items.append(p)
        return items

def toggle_wishlist(session_id: str, product_id: int, user_id: int = None) -> bool:
    """Toggles wishlist status. Returns True if added, False if removed."""
    with get_db() as conn:
        if user_id:
            existing = conn.execute("SELECT id FROM wishlist WHERE (user_id = ? OR session_id = ?) AND product_id = ?", (user_id, session_id, product_id)).fetchone()
        else:
            existing = conn.execute("SELECT id FROM wishlist WHERE session_id = ? AND product_id = ?", (session_id, product_id)).fetchone()

        if existing:
            conn.execute("DELETE FROM wishlist WHERE id = ?", (existing['id'],))
            return False
        else:
            conn.execute("INSERT INTO wishlist (user_id, session_id, product_id) VALUES (?, ?, ?)", (user_id, session_id, product_id))
            return True

def is_in_wishlist(session_id: str, product_id: int, user_id: int = None) -> bool:
    with get_db() as conn:
        if user_id:
            row = conn.execute("SELECT id FROM wishlist WHERE (user_id = ? OR session_id = ?) AND product_id = ?", (user_id, session_id, product_id)).fetchone()
        else:
            row = conn.execute("SELECT id FROM wishlist WHERE session_id = ? AND product_id = ?", (session_id, product_id)).fetchone()
        return bool(row)

# ----------------- Contact Messages -----------------
def save_contact_message(name: str, email: str, phone: str, subject: str, message: str) -> int:
    with get_db() as conn:
        cursor = conn.execute("""
            INSERT INTO contact_messages (name, email, phone, subject, message)
            VALUES (?, ?, ?, ?, ?)
        """, (name.strip(), email.strip(), phone.strip(), subject.strip(), message.strip()))
        return cursor.lastrowid

def get_contact_messages() -> list[dict]:
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM contact_messages ORDER BY created_at DESC").fetchall()
        return [dict(r) for r in rows]

"""
Vercel Serverless Function entrypoint for Shubhashtu Fashion.
Exports WSGI application `app` compatible with Vercel's Python runtime (@vercel/python).
Full feature parity with local Tornado app (Storefront, Cart, Checkout, Razorpay, Admin Panel, AI Stylist).
"""
import sys
import os
import shutil
import json
import re
import io
import csv
import urllib.parse
from pathlib import Path
from datetime import datetime

# Set paths
CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import config
from config import Config

# Detect serverless / read-only filesystem environment (e.g. Vercel / AWS Lambda)
is_serverless = os.environ.get('VERCEL') == '1' or os.environ.get('AWS_LAMBDA_FUNCTION_NAME') is not None or not os.access(PROJECT_ROOT, os.W_OK)
if is_serverless:
    Config.DATABASE_PATH = '/tmp/database.sqlite'
    tmp_db = Path('/tmp/database.sqlite')
    src_db = PROJECT_ROOT / 'database.sqlite'
    if not tmp_db.exists() and src_db.exists() and src_db.stat().st_size > 0:
        try:
            shutil.copy(src_db, tmp_db)
        except Exception as e:
            print(f"Notice: database copy to /tmp: {e}")

import db
import dal
from services.auth_service import hash_password, verify_password, generate_session_id
from services.shipping_service import ShippingService
from services.payment_service import PaymentService
from services.invoice_service import build_invoice_context, format_inr
from services.email_service import EmailService
import jinja2

# Jinja2 environment setup
TEMPLATES_DIR = PROJECT_ROOT / 'templates'
jinja_env = jinja2.Environment(
    loader=jinja2.FileSystemLoader(str(TEMPLATES_DIR)),
    autoescape=jinja2.select_autoescape(['html', 'xml'])
)
jinja_env.filters['format_inr'] = format_inr

# Ensure database tables, catalogue, and Admin account are 100% ready
def ensure_database_ready():
    try:
        db.init_db()
        import seed
        seed.seed_database()

        # Guarantee admin user exists with current Config credentials
        admin_email = Config.ADMIN_EMAIL.strip().lower()
        admin_pwd = Config.ADMIN_PASSWORD
        h, s = hash_password(admin_pwd)
        with db.get_db() as conn:
            admin_row = conn.execute("SELECT id FROM users WHERE LOWER(email) = ?", (admin_email,)).fetchone()
            if not admin_row:
                conn.execute("""
                    INSERT INTO users (email, password_hash, salt, full_name, phone, role)
                    VALUES (?, ?, ?, ?, ?, 'admin')
                """, (admin_email, h, s, "Shubhashtu Administrator", Config.SUPPORT_PHONE))
            else:
                conn.execute("""
                    UPDATE users SET password_hash = ?, salt = ?, role = 'admin' WHERE id = ?
                """, (h, s, admin_row['id']))
    except Exception as e:
        print(f"Database readiness initialization notice: {e}")

ensure_database_ready()

# Robust cookie parser
def parse_cookies(cookie_header):
    cookies_map = {}
    if not cookie_header:
        return cookies_map
    for item in cookie_header.split(';'):
        item = item.strip()
        if not item:
            continue
        if '=' in item:
            name, val = item.split('=', 1)
            cookies_map[name.strip()] = val.strip().strip('"\'')
    return cookies_map

def get_session_id(cookie_header):
    c_map = parse_cookies(cookie_header)
    if 'shubhashtu_session' in c_map and c_map['shubhashtu_session']:
        return c_map['shubhashtu_session']
    return generate_session_id()

def get_current_user(cookie_header):
    if not cookie_header:
        return None
    c_map = parse_cookies(cookie_header)
    if 'shubhashtu_user' in c_map:
        try:
            user_id = int(c_map['shubhashtu_user'])
            return dal.get_user_by_id(user_id)
        except Exception:
            return None
    return None

def app(environ, start_response):
    """WSGI application callable for Vercel."""
    method = environ.get('REQUEST_METHOD', 'GET').upper()
    path = environ.get('PATH_INFO', '/')
    query_string = environ.get('QUERY_STRING', '')
    query_params = urllib.parse.parse_qs(query_string)

    def q(name, default=''):
        val = query_params.get(name)
        return val[0] if val else default

    cookie_header = environ.get('HTTP_COOKIE', '')
    session_id = get_session_id(cookie_header)
    current_user = get_current_user(cookie_header)
    user_id = current_user['id'] if current_user else None

    # Read body for POST / PUT
    body_bytes = b''
    try:
        content_length = int(environ.get('CONTENT_LENGTH', 0) or 0)
        if content_length > 0:
            body_bytes = environ['wsgi.input'].read(content_length)
    except Exception:
        body_bytes = b''

    post_params = {}
    json_data = {}
    content_type = environ.get('CONTENT_TYPE', '')
    if 'application/json' in content_type and body_bytes:
        try:
            json_data = json.loads(body_bytes.decode('utf-8'))
        except Exception:
            json_data = {}
    elif ('application/x-www-form-urlencoded' in content_type or 'multipart/form-data' in content_type) and body_bytes:
        try:
            post_params = urllib.parse.parse_qs(body_bytes.decode('utf-8', 'ignore'))
        except Exception:
            post_params = {}

    def p(name, default=''):
        val = post_params.get(name)
        return val[0] if val else default

    # Base response headers
    res_headers = [
        ('Content-Type', 'text/html; charset=utf-8'),
        ('Set-Cookie', f'shubhashtu_session={session_id}; Path=/; HttpOnly; SameSite=Lax; Max-Age=2592000')
    ]

    def render(template_name, **ctx):
        tmpl = jinja_env.get_template(template_name)
        store_settings = dal.get_store_settings()
        cart_count = dal.get_cart_item_count(session_id, user_id)
        wishlist = dal.get_wishlist(session_id, user_id)
        full_ctx = {
            'store_settings': store_settings,
            'current_user': current_user,
            'cart_count': cart_count,
            'wishlist_count': len(wishlist),
            'active_nav': '',
            'request': type('Req', (), {'path': path})(),
            **ctx
        }
        output = tmpl.render(**full_ctx)
        start_response('200 OK', res_headers)
        return [output.encode('utf-8')]

    def json_resp(data, status='200 OK'):
        resp_headers = [
            ('Content-Type', 'application/json; charset=utf-8'),
            ('Set-Cookie', f'shubhashtu_session={session_id}; Path=/; HttpOnly; SameSite=Lax; Max-Age=2592000')
        ]
        start_response(status, resp_headers)
        return [json.dumps(data).encode('utf-8')]

    def redirect(location, extra_cookies=None):
        r_headers = [('Location', location)]
        # Keep session cookie
        r_headers.append(('Set-Cookie', f'shubhashtu_session={session_id}; Path=/; HttpOnly; SameSite=Lax; Max-Age=2592000'))
        if extra_cookies:
            for c in extra_cookies:
                r_headers.append(('Set-Cookie', c))
        start_response('302 Found', r_headers)
        return [b'']

    # ==================== ROUTING ====================

    # 0. Static Files (CSS, JS, Images, Fonts)
    if path.startswith('/static/'):
        rel_path = path[len('/static/'):].lstrip('/')
        static_dir = (PROJECT_ROOT / 'static').resolve()
        file_path = (static_dir / rel_path).resolve()
        if str(file_path).startswith(str(static_dir)) and file_path.is_file():
            import mimetypes
            ctype, _ = mimetypes.guess_type(str(file_path))
            if not ctype:
                ctype = 'application/octet-stream'
            with open(file_path, 'rb') as f:
                content = f.read()
            start_response('200 OK', [
                ('Content-Type', ctype),
                ('Cache-Control', 'public, max-age=86400')
            ])
            return [content]
        start_response('404 Not Found', [('Content-Type', 'text/plain')])
        return [b'Static asset not found']

    # 1. Homepage
    if path == '' or path == '/':
        cats = dal.get_categories(only_active=True)
        featured = dal.get_products(is_featured=True, limit=8)
        bestsellers = dal.get_products(badge='Bestseller', limit=6)
        new_arrivals = dal.get_products(badge='New', limit=6)
        return render('index.html', categories=cats, featured_products=featured, bestsellers=bestsellers, new_arrivals=new_arrivals, active_nav='home')

    # 2. Shop & Categories
    if path == '/shop' or path.startswith('/shop/'):
        cat_slug = None
        if path.startswith('/shop/'):
            cat_slug = path[len('/shop/'):].strip('/')
        all_cats = dal.get_categories(only_active=True)
        current_cat = dal.get_category_by_slug(cat_slug) if (cat_slug and cat_slug != 'all') else None

        badge = q('badge') or None
        sort_by = q('sort', 'newest')
        search = q('q') or None
        min_p = float(q('min_price')) if q('min_price') else None
        max_p = float(q('max_price')) if q('max_price') else None

        products = dal.get_products(
            category_slug=cat_slug,
            search=search,
            sort_by=sort_by,
            badge=badge,
            min_price=min_p,
            max_price=max_p
        )
        return render(
            'shop.html',
            products=products,
            all_categories=all_cats,
            current_category=current_cat,
            current_category_slug=cat_slug or 'all',
            current_search=search,
            current_sort=sort_by,
            current_badge=badge,
            min_price=min_p,
            max_price=max_p,
            active_nav='shop'
        )

    # 3. Product Detail
    if path.startswith('/product/'):
        slug = path[len('/product/'):].strip('/')
        product = dal.get_product_by_slug(slug)
        if not product:
            start_response('404 Not Found', [('Content-Type', 'text/html; charset=utf-8')])
            return [b'<h1>Product Not Found</h1><p><a href="/shop">Back to Shop</a></p>']
        reviews = dal.get_product_reviews(product['id'], approved_only=True)
        related = dal.get_related_products(product['category_id'], product['id'], limit=4)
        return render('product_detail.html', product=product, reviews=reviews, related_products=related)

    # 4. Cart Page
    if path == '/cart':
        cart = dal.get_cart(session_id, user_id)
        return render('cart.html', cart=cart, active_nav='cart')

    # 5. Checkout Page
    if path == '/checkout':
        cart = dal.get_cart(session_id, user_id)
        if not cart['items']:
            return redirect('/cart')
        addresses = dal.get_user_addresses(user_id) if user_id else []
        return render('checkout.html', cart=cart, addresses=addresses)

    # 6. Wishlist Page
    if path == '/wishlist':
        items = dal.get_wishlist(session_id, user_id)
        return render('wishlist.html', items=items)

    # 7. Information Pages
    if path == '/about':
        return render('about.html', active_nav='about')

    if path == '/contact':
        if method == 'POST':
            name = p('name').strip()
            email = p('email').strip()
            phone = p('phone').strip()
            subject = p('subject').strip()
            msg = p('message').strip()
            if name and email and msg:
                dal.save_contact_message(name, email, phone, subject, msg)
                return render('contact.html', success=True, active_nav='contact')
            return render('contact.html', success=False, error="Please complete all required fields.", active_nav='contact')
        return render('contact.html', success=False, active_nav='contact')

    if path == '/policies':
        return render('policies.html')

    # 8. Order Tracking & Invoice
    if path == '/track-order':
        order_number = q('order_number').strip()
        phone = q('phone').strip()
        tracked = None
        if order_number:
            tracked = dal.get_order_tracking(order_number, phone if phone else None)
        return render('order_track.html', order=tracked, searched=bool(order_number))

    if path.startswith('/invoice/'):
        order_number = path[len('/invoice/'):].strip('/')
        order = dal.get_order_by_number(order_number)
        if not order:
            start_response('404 Not Found', [('Content-Type', 'text/plain')])
            return [b'Order invoice not found.']
        settings = dal.get_store_settings()
        items = dal.get_order_items(order['id'])
        ctx = build_invoice_context(order, items, settings)
        return render('invoice.html', **ctx)

    if path.startswith('/order-success/'):
        order_number = path[len('/order-success/'):].strip('/')
        order = dal.get_order_by_number(order_number)
        if not order:
            return redirect('/')
        items = dal.get_order_items(order['id'])
        return render('order_success.html', order=order, items=items)

    # 9. Authentication Routes (LOGIN, REGISTER, FORGOT PASSWORD, LOGOUT)
    if path == '/login':
        redirect_url = q('redirect')
        if current_user:
            if current_user.get('role') == 'admin':
                target = redirect_url if redirect_url and redirect_url.startswith('/') else '/admin'
            else:
                target = redirect_url if redirect_url and redirect_url.startswith('/') else '/profile'
            return redirect(target)

        if method == 'POST':
            email = p('email').strip().lower()
            pwd = p('password').strip()
            redirect_url = p('redirect').strip() or q('redirect').strip()

            user = dal.get_user_by_email(email)
            if user and verify_password(pwd, user['password_hash'], user['salt']):
                # Merge guest cart into user account
                dal.merge_guest_cart(session_id, user['id'])
                cookie_val = f'shubhashtu_user={user["id"]}; Path=/; HttpOnly; SameSite=Lax; Max-Age=1209600'
                if redirect_url and redirect_url.startswith('/'):
                    target = redirect_url
                elif user.get('role') == 'admin':
                    target = '/admin'
                else:
                    target = '/profile'
                return redirect(target, [cookie_val])
            return render('login.html', error="Invalid email address or password.", redirect_url=redirect_url)
        return render('login.html', redirect_url=redirect_url)

    if path == '/register':
        redirect_url = q('redirect')
        if current_user:
            return redirect('/profile')
        if method == 'POST':
            name = p('full_name').strip()
            email = p('email').strip().lower()
            phone = p('phone').strip()
            pwd = p('password').strip()
            redirect_url = p('redirect').strip() or q('redirect').strip()

            if not name or not email or not pwd or len(pwd) < 6:
                return render('login.html', error="Please provide a valid name, email, and password (at least 6 characters).", is_register=True, redirect_url=redirect_url)
            if dal.get_user_by_email(email):
                return render('login.html', error="An account with this email address already exists.", is_register=True, redirect_url=redirect_url)

            h, s = hash_password(pwd)
            uid = dal.create_user(email, h, s, name, phone, role='customer')
            dal.merge_guest_cart(session_id, uid)
            cookie_val = f'shubhashtu_user={uid}; Path=/; HttpOnly; SameSite=Lax; Max-Age=1209600'
            target = redirect_url if redirect_url and redirect_url.startswith('/') else '/profile'
            return redirect(target, [cookie_val])
        return render('login.html', is_register=True, redirect_url=redirect_url)

    if path == '/forgot-password':
        if method == 'POST':
            email = p('email').strip().lower()
            new_pwd = p('new_password').strip()
            u = dal.get_user_by_email(email)
            if u and len(new_pwd) >= 6:
                ph, ps = hash_password(new_pwd)
                dal.update_user_password(u['id'], ph, ps)
                return render('forgot_password.html', message="Your password has been successfully reset! You can now sign in.")
            elif not u:
                return render('forgot_password.html', error="No account found matching that email address.")
            else:
                return render('forgot_password.html', error="Password must be at least 6 characters.")
        return render('forgot_password.html')

    if path == '/logout':
        return redirect('/', ['shubhashtu_user=; Path=/; Expires=Thu, 01 Jan 1970 00:00:00 GMT; Max-Age=0'])

    # 10. Customer Profile & Addresses
    if path == '/profile':
        if not current_user:
            return redirect('/login?redirect=/profile')
        orders = dal.get_orders_for_user(user_id)
        addresses = dal.get_user_addresses(user_id)
        return render('profile.html', orders=orders, addresses=addresses)

    if path == '/profile/update' and method == 'POST':
        if not current_user:
            return redirect('/login')
        fname = p('full_name').strip()
        ph = p('phone').strip()
        if fname:
            dal.update_user_profile(user_id, fname, ph)
        return redirect('/profile')

    if path == '/profile/password' and method == 'POST':
        if not current_user:
            return redirect('/login')
        curr = p('current_password').strip()
        newp = p('new_password').strip()
        if verify_password(curr, current_user['password_hash'], current_user['salt']) and len(newp) >= 6:
            h, s = hash_password(newp)
            dal.update_user_password(user_id, h, s)
            return render('profile.html', orders=dal.get_orders_for_user(user_id), addresses=dal.get_user_addresses(user_id), message="Password updated successfully!")
        return redirect('/profile')

    if path == '/profile/address/add' and method == 'POST':
        if not current_user:
            return redirect('/login')
        data = {
            'label': 'Home',
            'full_name': p('full_name'),
            'phone': p('phone'),
            'address_line1': p('address_line1'),
            'address_line2': p('address_line2'),
            'landmark': p('landmark'),
            'city': p('city'),
            'state': p('state'),
            'pincode': p('pincode'),
            'is_default': bool(p('is_default'))
        }
        dal.add_user_address(user_id, data)
        return redirect('/profile')

    if path == '/profile/address/delete' and method == 'POST':
        if not current_user:
            return redirect('/login')
        aid = int(p('address_id', 0))
        dal.delete_user_address(aid, user_id)
        return redirect('/profile')

    if path == '/profile/address/default' and method == 'POST':
        if not current_user:
            return redirect('/login')
        aid = int(p('address_id', 0))
        dal.set_default_address(aid, user_id)
        return redirect('/profile')

    # 11. Client-Side APIs
    if path == '/api/cart':
        cart = dal.get_cart(session_id, user_id)
        cart['free_shipping_threshold'] = float(dal.get_setting('free_shipping_threshold', '999'))
        return json_resp(cart)

    if path == '/api/cart/add' and method == 'POST':
        pid = int(json_data.get('product_id', 0))
        qty = int(json_data.get('quantity', 1))
        size = json_data.get('size', 'Free Size')
        color = json_data.get('color', '')
        res = dal.add_to_cart(session_id, pid, qty, size, color, user_id)
        return json_resp(res)

    if path == '/api/cart/update' and method == 'POST':
        cid = int(json_data.get('cart_item_id', 0))
        qty = int(json_data.get('quantity', 1))
        res = dal.update_cart_quantity(cid, qty, session_id, user_id)
        return json_resp({'success': res, 'cart': dal.get_cart(session_id, user_id)})

    if path == '/api/cart/remove' and method == 'POST':
        cid = int(json_data.get('cart_item_id', 0))
        dal.remove_from_cart(cid, session_id, user_id)
        return json_resp({'success': True, 'cart': dal.get_cart(session_id, user_id)})

    if path == '/api/wishlist/toggle' and method == 'POST':
        pid = int(json_data.get('product_id', 0))
        is_added = dal.toggle_wishlist(session_id, pid, user_id)
        count = len(dal.get_wishlist(session_id, user_id))
        return json_resp({'success': True, 'added': is_added, 'count': count})

    if path == '/api/search':
        sq = q('q').strip()
        results = dal.get_products(search=sq, limit=8) if sq else []
        clean = [{
            'id': p['id'],
            'name': p['name'],
            'slug': p['slug'],
            'price': p['price'],
            'mrp': p['mrp'],
            'category_name': p.get('category_name', ''),
            'primary_image': p.get('primary_image', '')
        } for p in results]
        return json_resp(clean)

    if path == '/api/shipping/calculate':
        pincode = q('pincode').strip() or str(json_data.get('pincode', '')).strip()
        subtotal = float(q('subtotal', 0) or json_data.get('subtotal', 0))
        is_express = (q('express') in ('1', 'true')) or bool(json_data.get('is_express'))
        is_cod = (q('cod') in ('1', 'true')) or bool(json_data.get('is_cod'))

        shipping_svc = ShippingService(db.get_connection())
        calc = shipping_svc.calculate_delivery(pincode=pincode, subtotal=subtotal, is_express=is_express, is_cod=is_cod)
        return json_resp(calc)

    if path == '/api/coupon/apply' and method == 'POST':
        code = str(json_data.get('code', '')).strip().upper()
        subtotal = float(json_data.get('subtotal', 0))
        if not subtotal:
            cart = dal.get_cart(session_id, user_id)
            subtotal = cart['subtotal']
        res = dal.validate_coupon(code, subtotal)
        return json_resp(res)

    if path == '/api/coupons':
        coupons = dal.get_coupons(only_active=True)
        return json_resp([{
            'code': c['code'],
            'description': c['description'],
            'type': c['discount_type'],
            'value': f"{c['discount_value']}% OFF" if c['discount_type'] == 'percentage' else f"Flat ₹{c['discount_value']} OFF",
            'min_order': c['min_order_value']
        } for c in coupons])

    if path == '/api/track':
        order_number = q('order_number').strip() or str(json_data.get('order_number', '')).strip()
        phone = q('phone').strip() or str(json_data.get('phone', '')).strip()
        if not order_number:
            return json_resp({'found': False, 'message': 'Please provide an order number.'}, status='400 Bad Request')
        tracked = dal.get_order_tracking(order_number, phone if phone else None)
        if not tracked:
            return json_resp({'found': False, 'message': f'Order #{order_number} not found.'}, status='404 Not Found')
        return json_resp({'found': True, 'order': tracked})

    if path in ('/api/reviews/add', '/api/review/submit') and method == 'POST':
        pid = int(p('product_id', 0))
        cname = p('customer_name')
        cemail = p('customer_email')
        rating = int(p('rating', 5))
        title = p('title')
        comment = p('comment')
        if pid and cname and comment:
            dal.add_review(pid, cname, cemail, rating, comment, title, user_id)
        prod = dal.get_product_by_id(pid)
        return redirect(f"/product/{prod['slug']}#reviews-section" if prod else "/shop")

    # AI Stylist Concierge API
    if path == '/api/ai/chat' and method == 'POST':
        from services.ai_agent_service import AIAgentService
        ai_svc = AIAgentService()
        msg = json_data.get('message', '')
        history = json_data.get('history', [])
        result = ai_svc.process_message(msg, history)
        return json_resp(result)

    # 12. Checkout & Payment APIs
    if path == '/api/checkout/place-cod-order' and method == 'POST':
        cart = dal.get_cart(session_id, user_id)
        if not cart['items']:
            return json_resp({'success': False, 'message': 'Your bag is empty.'})

        d = json_data
        shipping_svc = ShippingService(db.get_connection())
        ship_calc = shipping_svc.calculate_delivery(
            pincode=d.get('shipping_pincode', d.get('pincode', '')),
            subtotal=cart['subtotal'],
            is_express=bool(d.get('is_express')),
            is_cod=True
        )
        shipping_fee = ship_calc.get('shipping_fee', 70.0)
        cod_fee = ship_calc.get('cod_fee', 0.0)

        coupon_code = d.get('coupon_code', '').strip().upper()
        discount_amount = 0.0
        if coupon_code:
            c_res = dal.validate_coupon(coupon_code, cart['subtotal'])
            if c_res['valid']:
                discount_amount = c_res['discount']

        total = round(max(0.0, cart['subtotal'] - discount_amount + shipping_fee + cod_fee), 2)
        order_data = {
            'user_id': user_id,
            'customer_name': d.get('customer_name', d.get('full_name', '')),
            'customer_email': d.get('customer_email', d.get('email', '')),
            'customer_phone': d.get('customer_phone', d.get('phone', '')),
            'shipping_address_line1': d.get('shipping_address_line1', d.get('address_line1', '')),
            'shipping_address_line2': d.get('shipping_address_line2', d.get('address_line2', '')),
            'shipping_landmark': d.get('shipping_landmark', d.get('landmark', '')),
            'shipping_city': d.get('shipping_city', d.get('city', '')),
            'shipping_state': d.get('shipping_state', d.get('state', '')),
            'shipping_pincode': d.get('shipping_pincode', d.get('pincode', '')),
            'subtotal': cart['subtotal'],
            'coupon_code': coupon_code,
            'discount_amount': discount_amount,
            'shipping_fee': shipping_fee + cod_fee,
            'total_amount': total,
            'payment_method': 'cod',
            'payment_status': 'pending',
            'order_status': 'Order Placed',
            'estimated_delivery': ship_calc.get('estimated_date', '3-5 Business Days'),
            'customer_notes': d.get('customer_notes', d.get('order_notes', ''))
        }
        order_items = [{
            'product_id': item['product_id'],
            'product_name': item['name'],
            'sku': item.get('slug', ''),
            'mrp': item['mrp'],
            'price': item['price'],
            'quantity': item['quantity'],
            'selected_size': item.get('selected_size', 'Free Size'),
            'selected_color': item.get('selected_color', ''),
            'product_image': item.get('primary_image', ''),
            'total_price': round(item['price'] * item['quantity'], 2)
        } for item in cart['items']]

        created = dal.create_order(order_data, order_items)
        dal.clear_cart(session_id, user_id)
        EmailService.send_order_confirmation(order_data['customer_email'], created, order_items)
        return json_resp({'success': True, 'order_number': created['order_number'], 'redirect_url': f'/order-success/{created["order_number"]}'})

    if path in ('/api/checkout/create-razorpay-order', '/api/checkout/razorpay/create-order') and method == 'POST':
        cart = dal.get_cart(session_id, user_id)
        if not cart['items']:
            return json_resp({'success': False, 'message': 'Shopping bag is empty.'})

        payment_svc = PaymentService(dal.get_setting('razorpay_key_id'), dal.get_setting('razorpay_key_secret'))
        if not payment_svc.is_razorpay_configured():
            return json_resp({
                'success': False,
                'configured': False,
                'error': 'Razorpay keys are not yet configured. Please choose Cash on Delivery.'
            })

        d = json_data
        shipping_svc = ShippingService(db.get_connection())
        ship_calc = shipping_svc.calculate_delivery(
            pincode=d.get('shipping_pincode', d.get('pincode', '')),
            subtotal=cart['subtotal'],
            is_express=bool(d.get('is_express')),
            is_cod=False
        )
        shipping_fee = ship_calc.get('shipping_fee', 70.0)

        coupon_code = d.get('coupon_code', '').strip().upper()
        discount_amount = 0.0
        if coupon_code:
            c_res = dal.validate_coupon(coupon_code, cart['subtotal'])
            if c_res['valid']:
                discount_amount = c_res['discount']

        total = round(max(0.0, cart['subtotal'] - discount_amount + shipping_fee), 2)
        order_data = {
            'user_id': user_id,
            'customer_name': d.get('customer_name', d.get('full_name', '')),
            'customer_email': d.get('customer_email', d.get('email', '')),
            'customer_phone': d.get('customer_phone', d.get('phone', '')),
            'shipping_address_line1': d.get('shipping_address_line1', d.get('address_line1', '')),
            'shipping_address_line2': d.get('shipping_address_line2', d.get('address_line2', '')),
            'shipping_landmark': d.get('shipping_landmark', d.get('landmark', '')),
            'shipping_city': d.get('shipping_city', d.get('city', '')),
            'shipping_state': d.get('shipping_state', d.get('state', '')),
            'shipping_pincode': d.get('shipping_pincode', d.get('pincode', '')),
            'subtotal': cart['subtotal'],
            'coupon_code': coupon_code,
            'discount_amount': discount_amount,
            'shipping_fee': shipping_fee,
            'total_amount': total,
            'payment_method': 'razorpay',
            'payment_status': 'pending',
            'order_status': 'Order Placed',
            'estimated_delivery': ship_calc.get('estimated_date', '3-5 Business Days'),
            'customer_notes': d.get('customer_notes', d.get('order_notes', ''))
        }
        order_items = [{
            'product_id': item['product_id'],
            'product_name': item['name'],
            'sku': item.get('slug', ''),
            'mrp': item['mrp'],
            'price': item['price'],
            'quantity': item['quantity'],
            'selected_size': item.get('selected_size', 'Free Size'),
            'selected_color': item.get('selected_color', ''),
            'product_image': item.get('primary_image', ''),
            'total_price': round(item['price'] * item['quantity'], 2)
        } for item in cart['items']]

        created = dal.create_order(order_data, order_items)
        rzp_res = payment_svc.create_order(
            amount_inr=total,
            receipt_id=created['order_number'],
            notes={'internal_order_id': str(created['id'])}
        )
        if not rzp_res['success']:
            return json_resp({'success': False, 'error': rzp_res.get('error', 'Unable to initiate Razorpay order.')})

        return json_resp({
            'success': True,
            'configured': True,
            'internal_order_id': created['id'],
            'order_number': created['order_number'],
            'razorpay_order_id': rzp_res['order_id'],
            'amount_paise': rzp_res['amount_paise'],
            'currency': rzp_res['currency'],
            'key_id': rzp_res['key_id']
        })

    if path in ('/api/checkout/verify-razorpay-payment', '/api/checkout/razorpay/verify') and method == 'POST':
        d = json_data
        oid = int(d.get('order_id', 0))
        rzp_oid = d.get('razorpay_order_id', '')
        rzp_pid = d.get('razorpay_payment_id', '')
        rzp_sig = d.get('razorpay_signature', '')

        payment_svc = PaymentService(dal.get_setting('razorpay_key_id'), dal.get_setting('razorpay_key_secret'))
        if not payment_svc.verify_signature(rzp_oid, rzp_pid, rzp_sig):
            return json_resp({'success': False, 'error': 'Payment verification failed.'}, status='400 Bad Request')

        dal.update_payment_status(oid, payment_status='paid', razorpay_order_id=rzp_oid, razorpay_payment_id=rzp_pid, razorpay_signature=rzp_sig)
        dal.clear_cart(session_id, user_id)
        order = dal.get_order_by_id(oid)
        if order:
            EmailService.send_order_confirmation(order['customer_email'], order, dal.get_order_items(oid))
        return json_resp({'success': True})

    # ==================== 13. ADMIN PANEL (Protected) ====================
    if path.startswith('/admin'):
        if not current_user or current_user.get('role') != 'admin':
            return redirect('/login?redirect=' + urllib.parse.quote(path))

        # Admin Dashboard
        if path == '/admin' or path == '/admin/dashboard':
            metrics = dal.get_dashboard_metrics()
            return render('admin/dashboard.html', active_page='dashboard', metrics=metrics)

        # Products Management
        if path == '/admin/products':
            prods = dal.get_products(only_active=False)
            return render('admin/products.html', active_page='products', products=prods)

        if path == '/admin/products/new':
            if method == 'POST':
                name = p('name').strip()
                cid = int(p('category_id', 1))
                sku = p('sku').strip().upper()
                slug = re.sub(r'[^a-zA-Z0-9]+', '-', name).strip('-').lower()
                mrp = float(p('mrp', 0))
                price = float(p('price', 0))
                stock = int(p('stock', 10))
                weight = int(p('weight_grams', 350))
                badge = p('badge').strip()
                short_desc = p('short_description').strip()
                desc = p('description').strip()
                care = p('care_instructions').strip()
                sizes = p('sizes', 'Free Size').strip()
                colors = p('colors').strip()
                is_feat = 1 if p('is_featured') else 0
                is_act = 1 if p('is_active') else 0

                images = []
                urls_text = p('image_urls').strip()
                if urls_text:
                    for url in urls_text.splitlines():
                        if url.strip():
                            images.append(url.strip())

                pdata = {
                    'name': name, 'slug': slug, 'sku': sku, 'category_id': cid,
                    'short_description': short_desc, 'description': desc,
                    'care_instructions': care, 'mrp': mrp, 'price': price,
                    'stock': stock, 'weight_grams': weight, 'badge': badge,
                    'sizes': sizes, 'colors': colors, 'is_featured': is_feat,
                    'is_active': is_act, 'images': images
                }
                dal.create_product(pdata)
                return redirect('/admin/products')
            cats = dal.get_categories(only_active=False)
            return render('admin/product_form.html', active_page='products', product=None, categories=cats)

        prod_edit_match = re.match(r'^/admin/products/(?:edit/(\d+)|(\d+)/edit)$', path)
        if prod_edit_match:
            pid = int(prod_edit_match.group(1) or prod_edit_match.group(2))
            if method == 'POST':
                name = p('name').strip()
                cid = int(p('category_id', 1))
                sku = p('sku').strip().upper()
                slug = re.sub(r'[^a-zA-Z0-9]+', '-', name).strip('-').lower()
                mrp = float(p('mrp', 0))
                price = float(p('price', 0))
                stock = int(p('stock', 10))
                weight = int(p('weight_grams', 350))
                badge = p('badge').strip()
                short_desc = p('short_description').strip()
                desc = p('description').strip()
                care = p('care_instructions').strip()
                sizes = p('sizes', 'Free Size').strip()
                colors = p('colors').strip()
                is_feat = 1 if p('is_featured') else 0
                is_act = 1 if p('is_active') else 0

                images = []
                urls_text = p('image_urls').strip()
                if urls_text:
                    for url in urls_text.splitlines():
                        if url.strip():
                            images.append(url.strip())

                pdata = {
                    'name': name, 'slug': slug, 'sku': sku, 'category_id': cid,
                    'short_description': short_desc, 'description': desc,
                    'care_instructions': care, 'mrp': mrp, 'price': price,
                    'stock': stock, 'weight_grams': weight, 'badge': badge,
                    'sizes': sizes, 'colors': colors, 'is_featured': is_feat,
                    'is_active': is_act
                }
                if images:
                    pdata['images'] = images
                dal.update_product(pid, pdata)
                return redirect('/admin/products')

            prod = dal.get_product_by_id(pid)
            cats = dal.get_categories(only_active=False)
            return render('admin/product_form.html', active_page='products', product=prod, categories=cats)

        if path == '/admin/products/delete' and method == 'POST':
            pid = int(json_data.get('product_id', 0) or p('product_id', 0))
            dal.delete_product(pid)
            return json_resp({'success': True})

        # Categories
        if path == '/admin/categories':
            cats = dal.get_categories(only_active=False)
            return render('admin/categories.html', active_page='categories', categories=cats)

        if path == '/admin/categories/new' and method == 'POST':
            name = p('name').strip()
            slug = p('slug').strip() or re.sub(r'[^a-zA-Z0-9]+', '-', name).strip('-').lower()
            desc = p('description').strip()
            img = p('image_url').strip()
            so = int(p('sort_order', 0))
            dal.create_category(name, slug, desc, img, so)
            return redirect('/admin/categories')

        if path == '/admin/categories/delete' and method == 'POST':
            cid = int(p('category_id', 0) or json_data.get('category_id', 0))
            dal.delete_category(cid)
            return redirect('/admin/categories')

        # Orders Management
        if path == '/admin/orders':
            st = q('status', 'all')
            orders = dal.get_all_orders(status_filter=st if st != 'all' else None)
            return render('admin/orders.html', active_page='orders', orders=orders, current_status=st)

        if re.match(r'^/admin/orders/\d+$', path):
            oid = int(path.split('/')[-1])
            order = dal.get_order_by_id(oid)
            if not order:
                return redirect('/admin/orders')
            return render('admin/order_detail.html', active_page='orders', order=order)

        if path in ('/admin/orders/status', '/admin/orders/update-status') and method == 'POST':
            if json_data:
                oid = int(json_data.get('order_id', 0))
                status = json_data.get('status', '')
                comment = json_data.get('comment', '')
                courier = json_data.get('courier_name')
                tracking = json_data.get('tracking_number')
                url = json_data.get('tracking_url')
                dal.update_order_status(oid, status, comment, courier, tracking, url)
                return json_resp({'success': True})
            else:
                oid = int(p('order_id', 0))
                status = p('status')
                courier = p('courier_name', '')
                tracking = p('tracking_number', '')
                url = p('tracking_url', '')
                comment = p('comment', '')
                dal.update_order_status(oid, status, comment, courier, tracking, url)
                return redirect(f"/admin/orders/{oid}")

        if path == '/admin/orders/delete' and method == 'POST':
            oid = int(json_data.get('order_id', 0) or p('order_id', 0))
            ok, msg = dal.delete_order(oid)
            return json_resp({'success': ok, 'message': msg})

        if path == '/admin/orders/export-csv':
            orders = dal.get_all_orders(limit=1000)
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow([
                "Order Number", "Date", "Customer Name", "Phone", "Email",
                "Address", "City", "State", "PIN Code", "Subtotal", "Discount",
                "Delivery Charges", "Total Amount", "Payment Method", "Payment Status",
                "Order Status", "Courier", "Tracking Number"
            ])
            for o in orders:
                writer.writerow([
                    o['order_number'], o['created_at'], o['customer_name'],
                    o['customer_phone'], o['customer_email'],
                    o['shipping_address_line1'], o['shipping_city'],
                    o['shipping_state'], o['shipping_pincode'],
                    o['subtotal'], o['discount_amount'], o['shipping_fee'],
                    o['total_amount'], o['payment_method'], o['payment_status'],
                    o['order_status'], o.get('courier_name', ''), o.get('tracking_number', '')
                ])
            csv_bytes = output.getvalue().encode('utf-8-sig')
            start_response('200 OK', [
                ('Content-Type', 'text/csv; charset=utf-8'),
                ('Content-Disposition', f'attachment; filename=Shubhashtu_Orders_{datetime.now().strftime("%Y%m%d")}.csv')
            ])
            return [csv_bytes]

        # Customers Management
        if path == '/admin/customers':
            customers = dal.get_all_customers()
            return render('admin/customers.html', active_page='customers', customers=customers)

        if path == '/admin/customers/delete' and method == 'POST':
            cid = int(json_data.get('customer_id', 0) or p('customer_id', 0))
            ok, msg = dal.delete_customer(cid)
            return json_resp({'success': ok, 'message': msg})

        # Coupons Management
        if path == '/admin/coupons':
            coupons = dal.get_coupons(only_active=False)
            return render('admin/coupons.html', active_page='coupons', coupons=coupons)

        if path == '/admin/coupons/new' and method == 'POST':
            code = p('code').strip().upper()
            desc = p('description').strip()
            dtype = p('discount_type', 'percentage')
            dval = float(p('discount_value', 0))
            min_val = float(p('min_order_value', 0))
            max_d = float(p('max_discount')) if p('max_discount') else None
            limit = int(p('usage_limit')) if p('usage_limit') else None
            dal.create_coupon({
                'code': code, 'description': desc, 'discount_type': dtype,
                'discount_value': dval, 'min_order_value': min_val,
                'max_discount': max_d, 'usage_limit': limit
            })
            return redirect('/admin/coupons')

        if path == '/admin/coupons/toggle' and method == 'POST':
            cid = int(json_data.get('coupon_id', 0) or p('coupon_id', 0))
            dal.toggle_coupon_active(cid)
            return json_resp({'success': True})

        if path == '/admin/coupons/delete' and method == 'POST':
            cid = int(json_data.get('coupon_id', 0) or p('coupon_id', 0))
            dal.delete_coupon(cid)
            return json_resp({'success': True})

        # Shipping Rules & Courier
        if path == '/admin/shipping':
            return render('admin/shipping.html', active_page='shipping', settings=dal.get_store_settings())

        if path in ('/admin/shipping/save', '/admin/shipping') and method == 'POST':
            keys = [
                'standard_shipping_fee', 'free_shipping_threshold', 'express_shipping_fee',
                'cod_fee', 'remote_zone_surcharge', 'shiprocket_email', 'shiprocket_password',
                'shiprocket_pickup_pincode'
            ]
            for k in keys:
                dal.update_setting(k, p(k))
            return render('admin/shipping.html', active_page='shipping', settings=dal.get_store_settings(), success_msg="Shipping rules and courier settings saved successfully.")

        # Payment Settings
        if path == '/admin/payments':
            settings = dal.get_store_settings()
            has_keys = bool(settings.get('razorpay_key_id') and settings.get('razorpay_key_secret'))
            return render('admin/payments.html', active_page='payments', settings=settings, has_keys=has_keys)

        if path in ('/admin/payments/save', '/admin/payments') and method == 'POST':
            dal.update_setting('razorpay_key_id', p('razorpay_key_id').strip())
            dal.update_setting('razorpay_key_secret', p('razorpay_key_secret').strip())
            dal.update_setting('razorpay_webhook_secret', p('razorpay_webhook_secret').strip())
            dal.update_setting('razorpay_test_mode', '1' if p('razorpay_test_mode') else '0')
            dal.update_setting('cod_enabled', '1' if p('cod_enabled') else '0')
            settings = dal.get_store_settings()
            has_keys = bool(settings.get('razorpay_key_id') and settings.get('razorpay_key_secret'))
            return render('admin/payments.html', active_page='payments', settings=settings, has_keys=has_keys, success_msg="Payment credentials and options updated.")

        # Reviews Moderation
        if path == '/admin/reviews':
            reviews = dal.get_all_reviews()
            return render('admin/reviews.html', active_page='reviews', reviews=reviews)

        if path == '/admin/reviews/toggle' and method == 'POST':
            rid = int(json_data.get('review_id', 0) or p('review_id', 0))
            dal.toggle_review_approval(rid)
            return json_resp({'success': True})

        if path == '/admin/reviews/delete' and method == 'POST':
            rid = int(json_data.get('review_id', 0) or p('review_id', 0))
            dal.delete_review(rid)
            return json_resp({'success': True})

        # Store Settings
        if path == '/admin/settings':
            return render('admin/settings.html', active_page='settings', settings=dal.get_store_settings())

        if path in ('/admin/settings/save', '/admin/settings') and method == 'POST':
            keys = ['store_name', 'tagline', 'support_phone', 'support_whatsapp', 'support_email', 'store_address', 'announcement_bar', 'instagram_handle']
            for k in keys:
                dal.update_setting(k, p(k))
            return render('admin/settings.html', active_page='settings', settings=dal.get_store_settings(), success_msg="Store information saved.")

    # Fallback 404
    start_response('404 Not Found', [('Content-Type', 'text/html; charset=utf-8')])
    return [b'<h1>404 Not Found</h1><p><a href="/">Return to Shubhashtu Fashion</a></p>']

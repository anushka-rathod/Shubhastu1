"""
Comprehensive End-to-End Test Suite for Shubhashtu Fashion.
Tests:
- Database & Seeding
- Catalog & Products (Earrings, T-Shirts, Kurtis, Accessories)
- Cart & Checkout Calculations
- Indian Pincode Shipping Engine
- Coupon Validation System
- Customer Auth & Profiles
- Admin Auth & Security Protection
- Admin Dashboard & Store Management CRUD
- Order Status Lifecycle & Deletion
- AI Stylist Agent Tool-Calling
- WSGI Vercel Entrypoint compatibility
"""
import sys
import io
import json
import urllib.parse
from datetime import datetime

import db
import dal
import seed
import config
from config import Config
from services.auth_service import hash_password, verify_password, generate_session_id
from services.shipping_service import ShippingService
from services.payment_service import PaymentService
from services.ai_agent_service import AIAgentService
from services.invoice_service import build_invoice_context, format_inr
from api.index import app as wsgi_app

def run_tests():
    print("=" * 70)
    print("  SHUBHASHTU FASHION - COMPREHENSIVE SYSTEM VERIFICATION")
    print("=" * 70)
    passed = 0
    total = 0

    def assert_test(cond, msg):
        nonlocal passed, total
        total += 1
        if cond:
            passed += 1
            print(f"  [PASS] {msg}")
        else:
            print(f"  [FAIL] {msg}")
            raise AssertionError(f"Test Failed: {msg}")

    # ---------------- 1. Database & Seeding ----------------
    print("\n--- 1. Database & Seeding Verification ---")
    seed.seed_database()
    cats = dal.get_categories(only_active=False)
    assert_test(len(cats) >= 4, f"Found {len(cats)} categories (expected >= 4)")

    prods = dal.get_products(only_active=False)
    assert_test(len(prods) >= 12, f"Found {len(prods)} products in catalog (expected >= 12)")

    earrings = [p for p in prods if p.get('category_slug') == 'earrings']
    assert_test(len(earrings) >= 6, f"Found {len(earrings)} royal handcrafted earrings")

    tshirts = [p for p in prods if p.get('category_slug') == 'hand-painted-t-shirts']
    assert_test(len(tshirts) >= 6, f"Found {len(tshirts)} wearable art hand-painted t-shirts")

    settings = dal.get_store_settings()
    assert_test(settings.get('store_name') == Config.BRAND_NAME, "Store name matches configuration")
    assert_test('standard_shipping_fee' in settings, "Shipping settings populated")

    # ---------------- 2. Shipping Service ----------------
    print("\n--- 2. Shipping & Delivery Rate Engine ---")
    conn = db.get_connection()
    ship_svc = ShippingService(conn)

    # Metro Free shipping (Subtotal >= 999)
    res_metro_free = ship_svc.calculate_delivery(pincode="560001", subtotal=1499.0)
    assert_test(res_metro_free['serviceable'] and res_metro_free['shipping_fee'] == 0.0, "Metro pin 560001: Free shipping above 999")

    # Metro Standard shipping (Subtotal < 999)
    res_metro_std = ship_svc.calculate_delivery(pincode="110001", subtotal=499.0)
    assert_test(res_metro_std['serviceable'] and res_metro_std['shipping_fee'] == 70.0, "Metro pin 110001: Standard delivery fee 70 INR")

    # Remote pincode (Northeast)
    res_remote = ship_svc.calculate_delivery(pincode="795001", subtotal=500.0)
    assert_test(res_remote['serviceable'] and res_remote['shipping_fee'] == 110.0, "Remote pin 795001: Standard 70 + Remote surcharge 40 = 110 INR")

    # Invalid pincode
    res_invalid = ship_svc.calculate_delivery(pincode="99999", subtotal=500.0)
    assert_test(not res_invalid['serviceable'], "Invalid pin code 99999 correctly marked non-serviceable")

    # ---------------- 3. Coupons & Discounts ----------------
    print("\n--- 3. Coupon Validation Engine ---")
    c_w10 = dal.validate_coupon("WELCOME10", subtotal=2000.0)
    assert_test(c_w10['valid'] and c_w10['discount'] == 200.0, "Coupon WELCOME10: 10% off of 2000 = 200 INR")

    c_s500_fail = dal.validate_coupon("SHUBH500", subtotal=1500.0)
    assert_test(not c_s500_fail['valid'], "Coupon SHUBH500: Rejects subtotal below minimum 2499 INR")

    c_s500_ok = dal.validate_coupon("SHUBH500", subtotal=3000.0)
    assert_test(c_s500_ok['valid'] and c_s500_ok['discount'] == 500.0, "Coupon SHUBH500: Applies 500 INR discount for order >= 2499")

    # ---------------- 4. Cart & Wishlist Operations ----------------
    print("\n--- 4. Shopping Cart & Wishlist Lifecycle ---")
    test_session = f"test_session_{int(datetime.now().timestamp())}"
    sample_prod = prods[0]

    # Add to cart
    add_res = dal.add_to_cart(test_session, sample_prod['id'], quantity=2, size="M")
    assert_test(add_res['success'], "Product added to cart successfully")

    cart = dal.get_cart(test_session)
    assert_test(cart['item_count'] == 2, f"Cart item count is 2 (got {cart['item_count']})")
    assert_test(cart['subtotal'] == sample_prod['price'] * 2, "Cart subtotal calculated accurately")

    # Wishlist toggle
    w_add = dal.toggle_wishlist(test_session, sample_prod['id'])
    assert_test(w_add is True, "Product added to wishlist")
    wishlist = dal.get_wishlist(test_session)
    assert_test(len(wishlist) == 1, "Wishlist contains 1 item")

    w_remove = dal.toggle_wishlist(test_session, sample_prod['id'])
    assert_test(w_remove is False, "Product toggled off wishlist")
    assert_test(len(dal.get_wishlist(test_session)) == 0, "Wishlist is now empty")

    # ---------------- 5. Order Placement Lifecycle ----------------
    print("\n--- 5. Order Placement & Status Tracking ---")
    order_data = {
        'user_id': None,
        'customer_name': 'Meera Kapoor',
        'customer_email': 'meera.kapoor@example.com',
        'customer_phone': '+91 98111 22334',
        'shipping_address_line1': 'Villa 14, Lotus Boulevard',
        'shipping_city': 'Bengaluru',
        'shipping_state': 'Karnataka',
        'shipping_pincode': '560001',
        'subtotal': cart['subtotal'],
        'coupon_code': 'WELCOME10',
        'discount_amount': round(cart['subtotal'] * 0.1, 2),
        'shipping_fee': 0.0,
        'total_amount': round(cart['subtotal'] * 0.9, 2),
        'payment_method': 'cod',
        'payment_status': 'pending',
        'order_status': 'Order Placed',
        'estimated_delivery': '3-5 Business Days'
    }
    order_items = [{
        'product_id': sample_prod['id'],
        'product_name': sample_prod['name'],
        'sku': sample_prod.get('slug', 'sku'),
        'mrp': sample_prod['mrp'],
        'price': sample_prod['price'],
        'quantity': 2,
        'selected_size': 'M',
        'product_image': sample_prod.get('primary_image', ''),
        'total_price': sample_prod['price'] * 2
    }]

    initial_stock = dal.get_product_by_id(sample_prod['id'])['stock']
    created_order = dal.create_order(order_data, order_items)
    assert_test(created_order['order_number'].startswith('SHB-'), f"Generated brand order ID: {created_order['order_number']}")

    new_stock = dal.get_product_by_id(sample_prod['id'])['stock']
    assert_test(new_stock == initial_stock - 2, f"Inventory stock automatically reduced from {initial_stock} to {new_stock}")

    # Track order
    tracked = dal.get_order_tracking(created_order['order_number'], '+91 98111 22334')
    assert_test(tracked is not None and tracked['order_status'] == 'Order Placed', "Order tracking query verified successfully")

    # ---------------- 6. Admin Authentication & Role Protection ----------------
    print("\n--- 6. Admin Authentication & Security Protection ---")
    admin_user = dal.get_user_by_email('admin@shubhashtu.com')
    assert_test(admin_user is not None, "Admin account admin@shubhashtu.com exists")
    assert_test(admin_user['role'] == 'admin', "Admin account has role='admin'")
    assert_test(verify_password('ShubhashtuAdmin@2026', admin_user['password_hash'], admin_user['salt']), "Admin password verification succeeds")

    # ---------------- 7. Admin Dashboard & Store Management CRUD ----------------
    print("\n--- 7. Admin Dashboard Metrics & Management CRUD ---")
    metrics = dal.get_dashboard_metrics()
    assert_test('total_sales' in metrics and 'total_orders' in metrics, "Dashboard sales and order metrics calculated")

    # Update order status to Confirmed -> Shipped
    dal.update_order_status(created_order['id'], 'Shipped', courier_name='BlueDart Express', tracking_number='BD987654321IN')
    updated_order = dal.get_order_by_id(created_order['id'])
    assert_test(updated_order['order_status'] == 'Shipped', "Admin order status updated to 'Shipped'")
    assert_test(updated_order['tracking_number'] == 'BD987654321IN', "Admin courier tracking details stored")

    # Product update
    dal.update_product(sample_prod['id'], {'badge': 'Exclusive'})
    refreshed_p = dal.get_product_by_id(sample_prod['id'])
    assert_test(refreshed_p['badge'] == 'Exclusive', "Admin product details update verified")

    # Order deletion
    del_ok, del_msg = dal.delete_order(created_order['id'])
    assert_test(del_ok, f"Admin order deletion verified: {del_msg}")
    assert_test(dal.get_order_by_id(created_order['id']) is None, "Order purged from database")

    # ---------------- 8. AI Stylist Agent Tool Calling ----------------
    print("\n--- 8. AI Stylist Agent & Tool Calling ---")
    ai_svc = AIAgentService()
    search_tool_res = ai_svc.tool_search_products('earrings', max_price=3000)
    assert_test(len(search_tool_res) > 0, "AI Stylist tool_search_products returned relevant items")

    shipping_tool_res = ai_svc.tool_calculate_shipping('560001', 1200.0)
    assert_test(shipping_tool_res['is_free_shipping'] is True, "AI Stylist tool_calculate_shipping calculated free shipping")

    ai_chat = ai_svc.process_message("Suggest me some hand painted t-shirts for casual wear")
    assert_test('products' in ai_chat and len(ai_chat['products']) > 0, "AI Stylist conversational agent returns aesthetic product recommendations")

    # ---------------- 9. WSGI Entrypoint (Vercel Compatibility) ----------------
    print("\n--- 9. Vercel WSGI Serverless Function Compatibility ---")
    def wsgi_req(method, path, body='', cookie='', content_type='application/x-www-form-urlencoded'):
        body_bytes = body.encode('utf-8') if isinstance(body, str) else body
        env = {
            'REQUEST_METHOD': method,
            'PATH_INFO': path,
            'QUERY_STRING': '',
            'CONTENT_LENGTH': str(len(body_bytes)),
            'CONTENT_TYPE': content_type,
            'wsgi.input': io.BytesIO(body_bytes),
            'HTTP_COOKIE': cookie
        }
        res_status = []
        res_headers = []
        def start_response(status, headers):
            res_status.append(status)
            res_headers.extend(headers)
        body_out = b''.join(wsgi_app(env, start_response)).decode('utf-8', 'ignore')
        return res_status[0], dict(res_headers), body_out

    # Storefront routes
    for route in ['/', '/shop', '/shop/earrings', '/shop/hand-painted-t-shirts', '/cart', '/about', '/contact', '/policies']:
        st, hd, _ = wsgi_req('GET', route)
        assert_test(st.startswith('200'), f"WSGI route {route} -> 200 OK")

    # Unauthenticated /admin -> Redirects to /login?redirect=/admin
    st, hd, _ = wsgi_req('GET', '/admin')
    assert_test(st.startswith('302') and '/login?redirect=' in hd.get('Location', ''), "Unauthenticated /admin redirects to login with redirect param")

    # Admin Login POST -> Redirects to /admin
    login_data = urllib.parse.urlencode({'email': 'admin@shubhashtu.com', 'password': 'ShubhashtuAdmin@2026'})
    st, hd, _ = wsgi_req('POST', '/login', body=login_data)
    assert_test(st.startswith('302') and hd.get('Location') == '/admin', "Admin login POST redirects directly to /admin")
    admin_cookie = [c.strip() for c in hd.get('Set-Cookie', '').split(';') if 'shubhashtu_user=' in c][0]

    # Access all Admin subpages with admin cookie
    admin_routes = [
        '/admin', '/admin/dashboard', '/admin/products', '/admin/products/new',
        '/admin/categories', '/admin/orders', '/admin/customers',
        '/admin/coupons', '/admin/shipping', '/admin/payments',
        '/admin/reviews', '/admin/settings'
    ]
    for r in admin_routes:
        st, hd, body = wsgi_req('GET', r, cookie=admin_cookie)
        assert_test(st.startswith('200'), f"Admin page {r} accessible with admin cookie -> 200 OK")

    # Customer Login POST -> Redirects to /profile
    cust_data = urllib.parse.urlencode({'email': 'ananya.sharma@example.com', 'password': 'Customer@123'})
    st, hd, _ = wsgi_req('POST', '/login', body=cust_data)
    assert_test(st.startswith('302') and hd.get('Location') == '/profile', "Customer login POST redirects to /profile")

    conn.close()
    print("\n" + "=" * 70)
    print(f"  ALL {passed}/{total} VERIFICATION CHECKS PASSED PERFECTLY (100% SUCCESS)!")
    print("=" * 70)

if __name__ == '__main__':
    run_tests()


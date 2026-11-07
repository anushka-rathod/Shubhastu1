"""
Automated End-to-End Verification Test Suite for Shubhashtu Fashion.
Verifies all core services, DAL, cart, checkout, delivery calculations, and Tornado HTTP endpoints.
"""
import unittest
import json
import dal
import db
from services.auth_service import hash_password, verify_password
from services.shipping_service import ShippingService
from services.payment_service import PaymentService
from services.invoice_service import format_inr
import config

class TestShubhashtu(unittest.TestCase):

    def setUp(self):
        self.conn = db.get_connection()
        self.shipping_svc = ShippingService(self.conn)
        self.payment_svc = PaymentService("rzp_test_sampleKey", "sampleSecret123456789")

    def tearDown(self):
        self.conn.close()

    def test_01_categories_and_products(self):
        """Verify initial catalogue seeding."""
        cats = dal.get_categories(only_active=True)
        self.assertGreaterEqual(len(cats), 4, "Should have at least 4 categories")
        
        # Verify specific categories
        slugs = [c['slug'] for c in cats]
        self.assertIn("earrings", slugs)
        self.assertIn("hand-painted-t-shirts", slugs)
        self.assertIn("ethnic-and-kurtis", slugs)
        self.assertIn("accessories", slugs)

        # Verify products
        prods = dal.get_products()
        self.assertGreaterEqual(len(prods), 12, "Should have at least 12 products")
        for p in prods:
            self.assertGreater(p['price'], 0)
            self.assertGreater(p['mrp'], 0)
            self.assertIsNotNone(p['primary_image'])

    def test_02_shipping_calculation_engine(self):
        """Test Indian pincode lookup and dynamic delivery fees."""
        # 1. Metro Pincode with subtotal >= 999 (should be FREE)
        calc1 = self.shipping_svc.calculate_delivery(pincode="560001", subtotal=1499.0)
        self.assertTrue(calc1['serviceable'])
        self.assertTrue(calc1['is_free_shipping'])
        self.assertEqual(calc1['shipping_fee'], 0.0)
        self.assertEqual(calc1['city'], "Bengaluru")
        self.assertEqual(calc1['state'], "Karnataka")

        # 2. Metro Pincode below free shipping threshold (< 999)
        calc2 = self.shipping_svc.calculate_delivery(pincode="110001", subtotal=499.0)
        self.assertTrue(calc2['serviceable'])
        self.assertFalse(calc2['is_free_shipping'])
        self.assertEqual(calc2['shipping_fee'], 70.0)
        self.assertEqual(calc2['city'], "New Delhi")

        # 3. Special Remote Northeast Pincode
        calc3 = self.shipping_svc.calculate_delivery(pincode="795001", subtotal=500.0)
        self.assertTrue(calc3['serviceable'])
        # standard 70 + remote 40 = 110
        self.assertEqual(calc3['shipping_fee'], 110.0)

        # 4. Invalid Pincode
        calc4 = self.shipping_svc.calculate_delivery(pincode="123", subtotal=500.0)
        self.assertFalse(calc4['serviceable'])

    def test_03_coupons_validation(self):
        """Test coupon discounts and limits."""
        # WELCOME10: 10% off
        res1 = dal.validate_coupon("WELCOME10", subtotal=1000.0)
        self.assertTrue(res1['valid'])
        self.assertEqual(res1['discount'], 100.0)

        # Min order requirement check
        res2 = dal.validate_coupon("SHUBH500", subtotal=1500.0) # min order 2499
        self.assertFalse(res2['valid'])

        res3 = dal.validate_coupon("SHUBH500", subtotal=3000.0)
        self.assertTrue(res3['valid'])
        self.assertEqual(res3['discount'], 500.0)

    def test_04_cart_operations(self):
        """Test guest & customer cart workflow."""
        test_session = "test_sess_999"
        prod = dal.get_products()[0]
        
        # Add to cart
        res = dal.add_to_cart(test_session, prod['id'], quantity=2, size="M")
        self.assertTrue(res['success'])

        cart = dal.get_cart(test_session)
        self.assertEqual(cart['item_count'], 2)
        self.assertEqual(cart['subtotal'], prod['price'] * 2)

        # Update quantity
        item_id = cart['items'][0]['id']
        dal.update_cart_quantity(item_id, 3, test_session)
        cart = dal.get_cart(test_session)
        self.assertEqual(cart['item_count'], 3)

        # Clear cart
        dal.clear_cart(test_session)
        cart_empty = dal.get_cart(test_session)
        self.assertEqual(cart_empty['item_count'], 0)

    def test_05_auth_password_hashing(self):
        """Verify secure PBKDF2 salt and hash verification."""
        pwd = "SecretFashion@2026"
        pwd_hash, salt = hash_password(pwd)
        self.assertTrue(verify_password(pwd, pwd_hash, salt))
        self.assertFalse(verify_password("WrongPassword", pwd_hash, salt))

    def test_06_razorpay_cryptographic_verification(self):
        """Verify HMAC-SHA256 signature verification."""
        # Pre-calculated test signature
        import hmac, hashlib
        order_id = "order_test_123"
        payment_id = "pay_test_456"
        secret = "sampleSecret123456789"
        msg = f"{order_id}|{payment_id}".encode('utf-8')
        valid_sig = hmac.new(secret.encode('utf-8'), msg, hashlib.sha256).hexdigest()

        # Should verify valid signature
        self.assertTrue(self.payment_svc.verify_signature(order_id, payment_id, valid_sig))
        # Should reject tampered signature
        self.assertFalse(self.payment_svc.verify_signature(order_id, payment_id, "tampered_fake_signature"))

    def test_07_order_placement_and_inventory(self):
        """Verify atomic order placement, stock decrement, and order tracking."""
        prod = dal.get_products()[0]
        initial_stock = prod['stock']

        order_data = {
            'customer_name': 'Test Buyer',
            'customer_email': 'buyer@example.com',
            'customer_phone': '9876543210',
            'shipping_address_line1': '123 Fashion Street',
            'shipping_city': 'Bengaluru',
            'shipping_state': 'Karnataka',
            'shipping_pincode': '560001',
            'subtotal': prod['price'],
            'discount_amount': 0.0,
            'shipping_fee': 0.0,
            'total_amount': prod['price'],
            'payment_method': 'cod',
            'payment_status': 'pending'
        }
        items = [{
            'product_id': prod['id'],
            'product_name': prod['name'],
            'price': prod['price'],
            'mrp': prod['mrp'],
            'quantity': 1,
            'selected_size': 'M'
        }]

        created = dal.create_order(order_data, items)
        self.assertIsNotNone(created['order_number'])
        self.assertTrue(created['order_number'].startswith("SHB-"))

        # Verify stock decrement
        updated_prod = dal.get_product_by_id(prod['id'])
        self.assertEqual(updated_prod['stock'], initial_stock - 1)

        # Verify tracking
        tracked = dal.get_order_tracking(created['order_number'], '9876543210')
        self.assertIsNotNone(tracked)
        self.assertEqual(tracked['customer_name'], 'Test Buyer')

    def test_08_currency_formatting(self):
        """Verify Indian Rupee number grouping."""
        self.assertEqual(format_inr(1299), "₹1,299.00")
        self.assertEqual(format_inr(125000), "₹1,25,000.00")
        self.assertEqual(format_inr(99), "₹99.00")

    def test_09_customer_and_order_deletion(self):
        """Verify customer deletion and order deletion."""
        # 1. Create a test customer
        pwd_hash, salt = hash_password("TestCust123!")
        cust_id = dal.create_user("temp.del.cust@example.com", pwd_hash, salt, "Temp Customer", "9998887770")
        self.assertIsNotNone(cust_id)

        # Ensure admin cannot be deleted
        admin = dal.get_user_by_email(config.Config.ADMIN_EMAIL)
        success, msg = dal.delete_customer(admin['id'])
        self.assertFalse(success, "Admin account must not be deletable")

        # Delete customer
        success, msg = dal.delete_customer(cust_id)
        self.assertTrue(success, "Customer should be deleted successfully")
        self.assertIsNone(dal.get_user_by_id(cust_id))

        # 2. Test order deletion
        prod = dal.get_products()[0]
        temp_order = dal.create_order({
            'customer_name': 'Delete Test Order',
            'customer_email': 'del@example.com',
            'customer_phone': '9876500000',
            'shipping_address_line1': 'Delete Test Road',
            'shipping_city': 'Bengaluru',
            'shipping_state': 'Karnataka',
            'shipping_pincode': '560001',
            'subtotal': prod['price'],
            'discount_amount': 0.0,
            'shipping_fee': 0.0,
            'total_amount': prod['price'],
            'payment_method': 'cod',
            'payment_status': 'pending'
        }, [{
            'product_id': prod['id'],
            'product_name': prod['name'],
            'price': prod['price'],
            'mrp': prod['mrp'],
            'quantity': 1,
            'selected_size': 'Free Size'
        }])
        
        order_id = temp_order['id']
        self.assertIsNotNone(dal.get_order_by_id(order_id))

        # Delete order
        del_success, del_msg = dal.delete_order(order_id)
        self.assertTrue(del_success)
        self.assertIsNone(dal.get_order_by_id(order_id))

    def test_10_ai_agent_service(self):
        """Verify AI Agent tool calling, catalog search, order tracking, and coupons."""
        from services.ai_agent_service import AIAgentService
        agent = AIAgentService()

        # 1. Product Search Tool
        earrings = agent.tool_search_products(category_slug='earrings')
        self.assertGreater(len(earrings), 0)
        self.assertIn('price', earrings[0])

        # 2. Shipping Calculation Tool
        ship = agent.tool_calculate_shipping('560001', 1500.0)
        self.assertTrue(ship['serviceable'])
        self.assertTrue(ship['is_free_shipping'])

        # 3. Coupons Tool
        coupons = agent.tool_list_coupons()
        self.assertGreaterEqual(len(coupons), 4)

        # 4. Agent Intent Processing
        resp = agent.process_message('I am looking for hand painted t-shirts')
        self.assertIn('products', resp)
        self.assertGreater(len(resp['products']), 0)
        self.assertIn('Wearable Art', resp['response'])

    def test_11_wsgi_admin_authentication(self):
        """Verify Vercel WSGI entrypoint admin login, cookie handling, and access protection."""
        import io
        import urllib.parse
        from api.index import app

        def wsgi_req(method, path, body='', cookie=''):
            body_bytes = body.encode('utf-8') if isinstance(body, str) else body
            env = {
                'REQUEST_METHOD': method,
                'PATH_INFO': path,
                'QUERY_STRING': '',
                'CONTENT_LENGTH': str(len(body_bytes)),
                'CONTENT_TYPE': 'application/x-www-form-urlencoded',
                'wsgi.input': io.BytesIO(body_bytes),
                'HTTP_COOKIE': cookie
            }
            res_status = []
            res_headers = []
            def start_response(status, headers):
                res_status.append(status)
                res_headers.extend(headers)
            body_out = b''.join(app(env, start_response)).decode('utf-8', 'ignore')
            return res_status[0], dict(res_headers), body_out

        # 1. Unauthenticated /admin -> 302 to /login?redirect=/admin
        st, hd, _ = wsgi_req('GET', '/admin')
        self.assertTrue(st.startswith('302'))
        self.assertIn('/login?redirect=', hd.get('Location', ''))

        # 2. Admin Login POST -> 302 to /admin with shubhashtu_user cookie
        login_data = urllib.parse.urlencode({'email': 'admin@shubhashtu.com', 'password': 'ShubhashtuAdmin@2026'})
        st, hd, _ = wsgi_req('POST', '/login', body=login_data)
        self.assertTrue(st.startswith('302'))
        self.assertEqual(hd.get('Location'), '/admin')
        cookie = hd.get('Set-Cookie', '')
        self.assertIn('shubhashtu_user=', cookie)

        # 3. Access /admin with cookie -> 200 OK
        user_c = [c.strip() for c in cookie.split(';') if 'shubhashtu_user=' in c][0]
        st, hd, body = wsgi_req('GET', '/admin', cookie=user_c)
        self.assertTrue(st.startswith('200'))
        self.assertIn('Dashboard', body)

if __name__ == '__main__':
    unittest.main()


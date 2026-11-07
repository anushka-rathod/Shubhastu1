"""
Shubhashtu Fashion - Main Application Server
Full-stack production-ready e-commerce web platform.
Built with Python, Tornado asynchronous server, Jinja2, SQLite, and Razorpay.
"""
import os
import sys
import json
import csv
import io
import re
import logging
from pathlib import Path
from datetime import datetime

try:
    import tornado.ioloop
    import tornado.web
    import tornado.httpserver
    import jinja2
    HAS_TORNADO = True
except ImportError:
    HAS_TORNADO = False
    class _MockRequestHandler: pass
    tornado = type('MockTornado', (), {
        'web': type('MockWeb', (), {'RequestHandler': _MockRequestHandler, 'Application': object, 'StaticFileHandler': object}),
        'httpserver': object,
        'ioloop': object
    })()
    jinja2 = None

import config
from config import Config
import db
import dal
from services.auth_service import hash_password, verify_password, generate_session_id
from services.shipping_service import ShippingService
from services.payment_service import PaymentService
from services.invoice_service import build_invoice_context, format_inr
from services.email_service import EmailService
from services.image_service import ImageService

# Logging Setup
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("shubhashtu")

# Jinja2 Environment Setup
TEMPLATES_DIR = config.BASE_DIR / 'templates'
STATIC_DIR = config.BASE_DIR / 'static'
if jinja2:
    jinja_env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=jinja2.select_autoescape(['html', 'xml'])
    )
    jinja_env.filters['format_inr'] = format_inr
else:
    jinja_env = None

# ----------------- Base Request Handler -----------------
class BaseHandler(tornado.web.RequestHandler):
    def initialize(self):
        self.shipping_svc = ShippingService(db.get_connection())
        # Check Razorpay credentials
        key_id = dal.get_setting('razorpay_key_id', Config.RAZORPAY_KEY_ID)
        key_secret = dal.get_setting('razorpay_key_secret', Config.RAZORPAY_KEY_SECRET)
        self.payment_svc = PaymentService(key_id, key_secret)

    def get_current_user(self):
        user_id = self.get_secure_cookie("shubhashtu_user")
        if user_id:
            try:
                return dal.get_user_by_id(int(user_id.decode('utf-8')))
            except Exception:
                return None
        return None

    def get_session_id(self) -> str:
        session_id = self.get_secure_cookie("shubhashtu_session")
        if session_id:
            return session_id.decode('utf-8')
        new_sid = generate_session_id()
        self.set_secure_cookie("shubhashtu_session", new_sid, expires_days=30, httponly=True)
        return new_sid

    def get_cart_count(self) -> int:
        user = self.get_current_user()
        user_id = user['id'] if user else None
        return dal.get_cart_item_count(self.get_session_id(), user_id)

    def render_template(self, template_name: str, **context):
        user = self.get_current_user()
        store_settings = dal.get_store_settings()
        cart_count = self.get_cart_count()
        has_razorpay_keys = bool(store_settings.get('razorpay_key_id') and store_settings.get('razorpay_key_secret'))

        default_context = {
            'current_user': user,
            'store_settings': store_settings,
            'cart_count': cart_count,
            'has_razorpay_keys': has_razorpay_keys,
            'request': self.request,
            'format_inr': format_inr
        }
        default_context.update(context)
        template = jinja_env.get_template(template_name)
        self.set_header("Content-Type", "text/html; charset=UTF-8")
        self.write(template.render(**default_context))

    def get_json_body(self) -> dict:
        try:
            return json.loads(self.request.body.decode('utf-8'))
        except Exception:
            return {}

    def require_admin(self):
        user = self.get_current_user()
        if not user or user.get('role') != 'admin':
            self.redirect(f"/login?redirect={self.request.uri}")
            raise tornado.web.Finish()

# ----------------- Storefront Handlers -----------------
class IndexHandler(BaseHandler):
    def get(self):
        categories = dal.get_categories(only_active=True)
        featured = dal.get_products(is_featured=True, limit=8)
        new_arrivals = dal.get_products(badge='New', limit=4)
        self.render_template(
            "index.html",
            categories=categories,
            featured_products=featured,
            new_arrivals=new_arrivals
        )

class ShopHandler(BaseHandler):
    def get(self, category_slug=None):
        search = self.get_argument("q", "").strip()
        sort_by = self.get_argument("sort", "newest")
        badge = self.get_argument("badge", "").strip()
        min_p = self.get_argument("min_price", None)
        max_p = self.get_argument("max_price", None)

        try:
            min_price = float(min_p) if min_p else None
            max_price = float(max_p) if max_p else None
        except ValueError:
            min_price, max_price = None, None

        all_cats = dal.get_categories(only_active=True)
        current_cat = None
        if category_slug and category_slug != 'all':
            current_cat = dal.get_category_by_slug(category_slug)

        products = dal.get_products(
            category_slug=category_slug,
            search=search if search else None,
            sort_by=sort_by,
            badge=badge if badge else None,
            min_price=min_price,
            max_price=max_price
        )

        self.render_template(
            "shop.html",
            products=products,
            all_categories=all_cats,
            current_category=current_cat,
            current_category_slug=category_slug or 'all',
            current_search=search,
            current_sort=sort_by,
            current_badge=badge,
            min_price=min_p,
            max_price=max_p
        )

class ProductDetailHandler(BaseHandler):
    def get(self, slug):
        product = dal.get_product_by_slug(slug)
        if not product:
            self.set_status(404)
            self.write("Product not found. <a href='/shop'>Return to Shop</a>")
            return

        reviews = dal.get_product_reviews(product['id'], approved_only=True)
        related = dal.get_related_products(product['category_id'], product['id'], limit=4)

        self.render_template(
            "product_detail.html",
            product=product,
            reviews=reviews,
            related_products=related
        )

class CartPageHandler(BaseHandler):
    def get(self):
        user = self.get_current_user()
        user_id = user['id'] if user else None
        cart = dal.get_cart(self.get_session_id(), user_id)
        self.render_template("cart.html", cart=cart)

class CheckoutPageHandler(BaseHandler):
    def get(self):
        # 1-Click WhatsApp Storefront: Orders are finalized seamlessly via WhatsApp
        self.redirect("/cart")

class OrderSuccessHandler(BaseHandler):
    def get(self, order_number):
        order = dal.get_order_by_number(order_number)
        if not order:
            self.redirect("/")
            return
        self.render_template("order_success.html", order=order)

class OrderTrackHandler(BaseHandler):
    def get(self):
        order_number = self.get_argument("order_number", "").strip()
        phone_or_email = self.get_argument("phone_or_email", "").strip()

        order = None
        searched = False
        if order_number:
            searched = True
            order = dal.get_order_tracking(order_number, phone_or_email if phone_or_email else None)

        self.render_template(
            "order_track.html",
            order=order,
            order_number=order_number,
            phone_or_email=phone_or_email,
            searched=searched
        )

class InvoiceHandler(BaseHandler):
    def get(self, order_number):
        order = dal.get_order_by_number(order_number)
        if not order:
            self.set_status(404)
            self.write("Order not found.")
            return

        store_settings = dal.get_store_settings()
        items = dal.get_order_items(order['id'])
        ctx = build_invoice_context(order, items, store_settings)
        self.render_template("invoice.html", **ctx)

class WishlistPageHandler(BaseHandler):
    def get(self):
        user = self.get_current_user()
        user_id = user['id'] if user else None
        items = dal.get_wishlist(self.get_session_id(), user_id)
        self.render_template("wishlist.html", items=items)

class AboutHandler(BaseHandler):
    def get(self):
        self.render_template("about.html")

class ContactHandler(BaseHandler):
    def get(self):
        self.render_template("contact.html", success=False)

    def post(self):
        name = self.get_argument("name", "")
        email = self.get_argument("email", "")
        phone = self.get_argument("phone", "")
        subject = self.get_argument("subject", "")
        message = self.get_argument("message", "")

        if name and email and message:
            dal.save_contact_message(name, email, phone, subject, message)
            self.render_template("contact.html", success=True)
        else:
            self.render_template("contact.html", success=False, error="Please complete all required fields.")

class PoliciesHandler(BaseHandler):
    def get(self):
        self.render_template("policies.html")

# ----------------- Customer Authentication Handlers -----------------
class LoginHandler(BaseHandler):
    def get(self):
        if self.get_current_user():
            self.redirect("/profile")
            return
        redirect_url = self.get_argument("redirect", "")
        self.render_template("login.html", redirect_url=redirect_url)

    def post(self):
        email = self.get_argument("email", "").strip()
        password = self.get_argument("password", "").strip()
        redirect_url = self.get_argument("redirect", "").strip()

        user = dal.get_user_by_email(email)
        if user and verify_password(password, user['password_hash'], user['salt']):
            self.set_secure_cookie("shubhashtu_user", str(user['id']), expires_days=14, httponly=True)
            # Merge guest cart into user account
            dal.merge_guest_cart(self.get_session_id(), user['id'])

            if redirect_url and redirect_url.startswith('/'):
                self.redirect(redirect_url)
            elif user['role'] == 'admin':
                self.redirect("/admin")
            else:
                self.redirect("/profile")
        else:
            self.render_template("login.html", error="Invalid email address or password.", redirect_url=redirect_url)

class RegisterHandler(BaseHandler):
    def post(self):
        full_name = self.get_argument("full_name", "").strip()
        email = self.get_argument("email", "").strip()
        phone = self.get_argument("phone", "").strip()
        password = self.get_argument("password", "").strip()
        redirect_url = self.get_argument("redirect", "").strip()

        if not full_name or not email or not password or len(password) < 6:
            self.render_template("login.html", error="Please provide a valid name, email, and password (at least 6 characters).")
            return

        existing = dal.get_user_by_email(email)
        if existing:
            self.render_template("login.html", error="An account with this email address already exists.")
            return

        pwd_hash, salt = hash_password(password)
        user_id = dal.create_user(email, pwd_hash, salt, full_name, phone, role='customer')
        self.set_secure_cookie("shubhashtu_user", str(user_id), expires_days=14, httponly=True)
        dal.merge_guest_cart(self.get_session_id(), user_id)

        if redirect_url and redirect_url.startswith('/'):
            self.redirect(redirect_url)
        else:
            self.redirect("/profile")

class LogoutHandler(BaseHandler):
    def get(self):
        self.clear_cookie("shubhashtu_user")
        self.redirect("/")

class ForgotPasswordHandler(BaseHandler):
    def get(self):
        self.render_template("forgot_password.html")

    def post(self):
        email = self.get_argument("email", "").strip()
        new_password = self.get_argument("new_password", "").strip()

        user = dal.get_user_by_email(email)
        if user and len(new_password) >= 6:
            pwd_hash, salt = hash_password(new_password)
            dal.update_user_password(user['id'], pwd_hash, salt)
            self.render_template("forgot_password.html", message="Your password has been successfully reset! You can now sign in.")
        elif not user:
            self.render_template("forgot_password.html", error="No account found matching that email address.")
        else:
            self.render_template("forgot_password.html", error="Password must be at least 6 characters.")

class ProfileHandler(BaseHandler):
    def get(self):
        user = self.get_current_user()
        if not user:
            self.redirect("/login?redirect=/profile")
            return
        orders = dal.get_orders_for_user(user['id'])
        addresses = dal.get_user_addresses(user['id'])
        self.render_template("profile.html", orders=orders, addresses=addresses)

class ProfileUpdateHandler(BaseHandler):
    def post(self):
        user = self.get_current_user()
        if not user:
            self.redirect("/login")
            return
        full_name = self.get_argument("full_name", "").strip()
        phone = self.get_argument("phone", "").strip()
        if full_name:
            dal.update_user_profile(user['id'], full_name, phone)
        self.redirect("/profile")

class ProfilePasswordHandler(BaseHandler):
    def post(self):
        user = self.get_current_user()
        if not user:
            self.redirect("/login")
            return
        current_pwd = self.get_argument("current_password", "").strip()
        new_pwd = self.get_argument("new_password", "").strip()

        if verify_password(current_pwd, user['password_hash'], user['salt']) and len(new_pwd) >= 6:
            pwd_hash, salt = hash_password(new_pwd)
            dal.update_user_password(user['id'], pwd_hash, salt)
            self.render_template("profile.html", orders=dal.get_orders_for_user(user['id']), addresses=dal.get_user_addresses(user['id']), message="Password updated successfully!")
        else:
            self.redirect("/profile")

class ProfileAddressAddHandler(BaseHandler):
    def post(self):
        user = self.get_current_user()
        if not user:
            self.redirect("/login")
            return
        data = {
            'label': 'Home',
            'full_name': self.get_argument("full_name", ""),
            'phone': self.get_argument("phone", ""),
            'address_line1': self.get_argument("address_line1", ""),
            'address_line2': self.get_argument("address_line2", ""),
            'landmark': self.get_argument("landmark", ""),
            'city': self.get_argument("city", ""),
            'state': self.get_argument("state", ""),
            'pincode': self.get_argument("pincode", ""),
            'is_default': bool(self.get_argument("is_default", 0))
        }
        dal.add_user_address(user['id'], data)
        self.redirect("/profile")

class ProfileAddressDeleteHandler(BaseHandler):
    def post(self):
        user = self.get_current_user()
        if not user:
            self.redirect("/login")
            return
        addr_id = int(self.get_argument("address_id"))
        dal.delete_user_address(addr_id, user['id'])
        self.redirect("/profile")

class ProfileAddressDefaultHandler(BaseHandler):
    def post(self):
        user = self.get_current_user()
        if not user:
            self.redirect("/login")
            return
        addr_id = int(self.get_argument("address_id"))
        dal.set_default_address(addr_id, user['id'])
        self.redirect("/profile")

# ----------------- Cart & Client-Side APIs -----------------
class CartApiHandler(BaseHandler):
    def get(self):
        user = self.get_current_user()
        user_id = user['id'] if user else None
        cart = dal.get_cart(self.get_session_id(), user_id)
        # Include free shipping threshold
        free_thresh = float(dal.get_setting('free_shipping_threshold', '999'))
        cart['free_shipping_threshold'] = free_thresh
        self.write(cart)

class CartAddApiHandler(BaseHandler):
    def post(self):
        data = self.get_json_body()
        prod_id = int(data.get('product_id', 0))
        qty = int(data.get('quantity', 1))
        size = data.get('size', 'Free Size')
        color = data.get('color', '')

        user = self.get_current_user()
        user_id = user['id'] if user else None
        result = dal.add_to_cart(self.get_session_id(), prod_id, qty, size, color, user_id)
        self.write(result)

class CartUpdateApiHandler(BaseHandler):
    def post(self):
        data = self.get_json_body()
        cart_item_id = int(data.get('cart_item_id', 0))
        qty = int(data.get('quantity', 1))

        user = self.get_current_user()
        user_id = user['id'] if user else None
        success = dal.update_cart_quantity(cart_item_id, qty, self.get_session_id(), user_id)
        self.write({'success': success})

class CartRemoveApiHandler(BaseHandler):
    def post(self):
        data = self.get_json_body()
        cart_item_id = int(data.get('cart_item_id', 0))
        user = self.get_current_user()
        user_id = user['id'] if user else None
        dal.remove_from_cart(cart_item_id, self.get_session_id(), user_id)
        self.write({'success': True})

class WishlistToggleApiHandler(BaseHandler):
    def post(self):
        data = self.get_json_body()
        prod_id = int(data.get('product_id', 0))
        user = self.get_current_user()
        user_id = user['id'] if user else None
        is_added = dal.toggle_wishlist(self.get_session_id(), prod_id, user_id)
        count = len(dal.get_wishlist(self.get_session_id(), user_id))
        self.write({'success': True, 'added': is_added, 'count': count})

class SearchApiHandler(BaseHandler):
    def get(self):
        q = self.get_argument("q", "").strip()
        if len(q) < 2:
            self.write([])
            return
        results = dal.get_products(search=q, limit=6)
        clean_res = [
            {
                'id': p['id'],
                'name': p['name'],
                'slug': p['slug'],
                'category_name': p['category_name'],
                'price': p['price'],
                'primary_image': p['primary_image']
            } for p in results
        ]
        self.write(clean_res)

class ShippingCalculateApiHandler(BaseHandler):
    def get(self):
        pincode = self.get_argument("pincode", "").strip()
        subtotal = float(self.get_argument("subtotal", 0.0))
        is_express = self.get_argument("express", "0") in ('1', 'true', 'yes')
        is_cod = self.get_argument("cod", "0") in ('1', 'true', 'yes')

        result = self.shipping_svc.calculate_delivery(
            pincode=pincode,
            subtotal=subtotal,
            is_express=is_express,
            is_cod=is_cod
        )
        self.write(result)

class CouponApplyApiHandler(BaseHandler):
    def post(self):
        data = self.get_json_body()
        code = data.get('code', '')
        subtotal = float(data.get('subtotal', 0.0))
        result = dal.validate_coupon(code, subtotal)
        self.write(result)

class ReviewSubmitApiHandler(BaseHandler):
    def post(self):
        prod_id = int(self.get_argument("product_id"))
        name = self.get_argument("customer_name", "")
        email = self.get_argument("customer_email", "")
        rating = int(self.get_argument("rating", 5))
        title = self.get_argument("title", "")
        comment = self.get_argument("comment", "")

        user = self.get_current_user()
        user_id = user['id'] if user else None

        if prod_id and name and comment:
            dal.add_review(prod_id, name, email, rating, comment, title, user_id)
        
        prod = dal.get_product_by_id(prod_id)
        if prod:
            self.redirect(f"/product/{prod['slug']}#reviews-section")
        else:
            self.redirect("/shop")

# ----------------- AI Stylist & Concierge Agent API -----------------
class AiAgentChatHandler(BaseHandler):
    def initialize(self):
        super().initialize()
        from services.ai_agent_service import AIAgentService
        self.ai_svc = AIAgentService()

    def post(self):
        data = self.get_json_body()
        user_message = data.get("message", "")
        history = data.get("history", [])
        result = self.ai_svc.process_message(user_message, history)
        self.write(result)

# ----------------- Checkout & Payment APIs -----------------
class CheckoutPlaceCodOrderApiHandler(BaseHandler):
    def post(self):
        data = self.get_json_body()
        user = self.get_current_user()
        user_id = user['id'] if user else None
        session_id = self.get_session_id()

        cart = dal.get_cart(session_id, user_id)
        if not cart['items']:
            self.write({'success': False, 'message': 'Your shopping bag is empty.'})
            return

        # Delivery fee calculation
        pincode = data.get('shipping_pincode', '')
        ship_calc = self.shipping_svc.calculate_delivery(
            pincode=pincode,
            subtotal=cart['subtotal'],
            is_express=bool(data.get('is_express')),
            is_cod=True
        )

        shipping_fee = ship_calc.get('shipping_fee', 70.0)
        cod_fee = ship_calc.get('cod_fee', 0.0)

        # Coupon validation
        discount = 0.0
        coupon_code = data.get('coupon_code', '').strip().upper()
        if coupon_code:
            coupon_res = dal.validate_coupon(coupon_code, cart['subtotal'])
            if coupon_res['valid']:
                discount = coupon_res['discount']

        total_amount = max(0.0, cart['subtotal'] - discount + shipping_fee + cod_fee)

        order_data = {
            'user_id': user_id,
            'customer_name': data['customer_name'],
            'customer_email': data['customer_email'],
            'customer_phone': data['customer_phone'],
            'shipping_address_line1': data['shipping_address_line1'],
            'shipping_address_line2': data.get('shipping_address_line2', ''),
            'shipping_landmark': data.get('shipping_landmark', ''),
            'shipping_city': data['shipping_city'],
            'shipping_state': data['shipping_state'],
            'shipping_pincode': pincode,
            'subtotal': cart['subtotal'],
            'coupon_code': coupon_code,
            'discount_amount': discount,
            'shipping_fee': shipping_fee + cod_fee,
            'total_amount': total_amount,
            'payment_method': 'cod',
            'payment_status': 'pending',
            'order_status': 'Order Placed',
            'estimated_delivery': ship_calc.get('estimated_date', '3-5 Business Days'),
            'customer_notes': data.get('customer_notes', '')
        }

        # Transform cart items into order items
        order_items = [
            {
                'product_id': item['product_id'],
                'product_name': item['name'],
                'product_image': item.get('primary_image', ''),
                'sku': item.get('slug', ''),
                'selected_size': item.get('selected_size', 'Free Size'),
                'selected_color': item.get('selected_color', ''),
                'mrp': item['mrp'],
                'price': item['price'],
                'quantity': item['quantity'],
                'total_price': round(item['price'] * item['quantity'], 2)
            } for item in cart['items']
        ]

        order = dal.create_order(order_data, order_items)
        dal.clear_cart(session_id, user_id)

        # Send confirmation email
        EmailService.send_order_confirmation(data['customer_email'], order, order_items)

        self.write({
            'success': True,
            'order_number': order['order_number']
        })

class CheckoutRazorpayCreateOrderApiHandler(BaseHandler):
    def post(self):
        data = self.get_json_body()
        user = self.get_current_user()
        user_id = user['id'] if user else None
        session_id = self.get_session_id()

        cart = dal.get_cart(session_id, user_id)
        if not cart['items']:
            self.write({'success': False, 'message': 'Shopping bag is empty.'})
            return

        if not self.payment_svc.is_razorpay_configured():
            self.write({
                'success': False,
                'configured': False,
                'error': 'Razorpay payment gateway keys are not yet configured. Please select Cash on Delivery or configure keys in Admin.'
            })
            return

        pincode = data.get('shipping_pincode', '')
        ship_calc = self.shipping_svc.calculate_delivery(
            pincode=pincode,
            subtotal=cart['subtotal'],
            is_express=bool(data.get('is_express')),
            is_cod=False
        )

        shipping_fee = ship_calc.get('shipping_fee', 70.0)

        # Coupon
        discount = 0.0
        coupon_code = data.get('coupon_code', '').strip().upper()
        if coupon_code:
            coupon_res = dal.validate_coupon(coupon_code, cart['subtotal'])
            if coupon_res['valid']:
                discount = coupon_res['discount']

        total_amount = max(0.0, cart['subtotal'] - discount + shipping_fee)

        # Pre-create internal order in database
        order_data = {
            'user_id': user_id,
            'customer_name': data['customer_name'],
            'customer_email': data['customer_email'],
            'customer_phone': data['customer_phone'],
            'shipping_address_line1': data['shipping_address_line1'],
            'shipping_address_line2': data.get('shipping_address_line2', ''),
            'shipping_landmark': data.get('shipping_landmark', ''),
            'shipping_city': data['shipping_city'],
            'shipping_state': data['shipping_state'],
            'shipping_pincode': pincode,
            'subtotal': cart['subtotal'],
            'coupon_code': coupon_code,
            'discount_amount': discount,
            'shipping_fee': shipping_fee,
            'total_amount': total_amount,
            'payment_method': 'razorpay',
            'payment_status': 'pending',
            'order_status': 'Order Placed',
            'estimated_delivery': ship_calc.get('estimated_date', '3-5 Business Days'),
            'customer_notes': data.get('customer_notes', '')
        }

        order_items = [
            {
                'product_id': item['product_id'],
                'product_name': item['name'],
                'product_image': item.get('primary_image', ''),
                'selected_size': item.get('selected_size', 'Free Size'),
                'mrp': item['mrp'],
                'price': item['price'],
                'quantity': item['quantity'],
                'total_price': round(item['price'] * item['quantity'], 2)
            } for item in cart['items']
        ]

        internal_order = dal.create_order(order_data, order_items)

        # Create Razorpay Order
        rzp_res = self.payment_svc.create_order(
            amount_inr=total_amount,
            receipt=internal_order['order_number'],
            notes={'order_number': internal_order['order_number']}
        )

        if not rzp_res['success']:
            self.write(rzp_res)
            return

        # Update razorpay_order_id in DB
        dal.update_payment_status(internal_order['id'], 'pending', razorpay_order_id=rzp_res['order_id'])

        self.write({
            'success': True,
            'configured': True,
            'internal_order_id': internal_order['id'],
            'order_number': internal_order['order_number'],
            'razorpay_order_id': rzp_res['order_id'],
            'amount_paise': rzp_res['amount_paise'],
            'currency': rzp_res['currency'],
            'key_id': rzp_res['key_id']
        })

class CheckoutRazorpayVerifyApiHandler(BaseHandler):
    def post(self):
        data = self.get_json_body()
        order_id = int(data.get('order_id', 0))
        rzp_order_id = data.get('razorpay_order_id', '')
        rzp_pay_id = data.get('razorpay_payment_id', '')
        rzp_sig = data.get('razorpay_signature', '')

        # Real cryptographic verification
        is_valid = self.payment_svc.verify_signature(rzp_order_id, rzp_pay_id, rzp_sig)
        if not is_valid:
            self.set_status(400)
            self.write({'success': False, 'error': 'Cryptographic payment signature verification failed.'})
            return

        # Verified! Update order and clear cart
        dal.update_payment_status(
            order_id,
            payment_status='paid',
            razorpay_order_id=rzp_order_id,
            razorpay_payment_id=rzp_pay_id,
            razorpay_signature=rzp_sig
        )

        user = self.get_current_user()
        user_id = user['id'] if user else None
        dal.clear_cart(self.get_session_id(), user_id)

        order = dal.get_order_by_id(order_id)
        if order:
            items = dal.get_order_items(order_id)
            EmailService.send_order_confirmation(order['customer_email'], order, items)

        self.write({'success': True})

class RazorpayWebhookHandler(BaseHandler):
    def post(self):
        signature = self.request.headers.get('X-Razorpay-Signature', '')
        secret = dal.get_setting('razorpay_webhook_secret', Config.RAZORPAY_WEBHOOK_SECRET)

        if not self.payment_svc.verify_webhook_signature(self.request.body, signature, secret):
            self.set_status(400)
            self.write("Invalid webhook signature")
            return

        try:
            payload = json.loads(self.request.body)
            event = payload.get('event')
            if event == 'payment.captured':
                payment = payload['payload']['payment']['entity']
                order_id = payment.get('order_id')
                pay_id = payment.get('id')
                logger.info("Webhook payment captured for %s (Payment ID: %s)", order_id, pay_id)
        except Exception as e:
            logger.error("Error processing webhook: %s", e)

        self.write({'status': 'ok'})

# ----------------- Admin Handlers -----------------
class AdminDashboardHandler(BaseHandler):
    def get(self):
        self.require_admin()
        metrics = dal.get_dashboard_metrics()
        self.render_template(
            "admin/dashboard.html",
            active_page='dashboard',
            metrics=metrics
        )

class AdminProductsHandler(BaseHandler):
    def get(self):
        self.require_admin()
        q = self.get_argument("q", "").strip()
        products = dal.get_products(search=q if q else None, only_active=False)
        self.render_template(
            "admin/products.html",
            active_page='products',
            products=products,
            search_query=q
        )

class AdminProductNewHandler(BaseHandler):
    def get(self):
        self.require_admin()
        categories = dal.get_categories(only_active=False)
        default_sku = f"SHB-{datetime.now().strftime('%m%d%H%M')}"
        self.render_template(
            "admin/product_form.html",
            active_page='product_new',
            product=None,
            categories=categories,
            default_sku=default_sku
        )

    def post(self):
        self.require_admin()
        name = self.get_argument("name", "").strip()
        category_id = int(self.get_argument("category_id"))
        sku = self.get_argument("sku", "").strip().upper()
        slug = re.sub(r'[^a-zA-Z0-9]+', '-', name).strip('-').lower()
        mrp = float(self.get_argument("mrp", 0))
        price = float(self.get_argument("price", 0))
        stock = int(self.get_argument("stock", 10))
        weight_grams = int(self.get_argument("weight_grams", 350))
        badge = self.get_argument("badge", "").strip()
        short_desc = self.get_argument("short_description", "").strip()
        desc = self.get_argument("description", "").strip()
        care = self.get_argument("care_instructions", "").strip()
        sizes = self.get_argument("sizes", "Free Size").strip()
        colors = self.get_argument("colors", "").strip()
        is_featured = 1 if self.get_argument("is_featured", None) else 0
        is_active = 1 if self.get_argument("is_active", None) else 0

        # Handle uploaded images safely (never crash on read-only environments)
        images = []
        if 'product_files' in self.request.files:
            try:
                upload_dir = STATIC_DIR / 'images' / 'products'
                upload_dir.mkdir(parents=True, exist_ok=True)
                for f in self.request.files['product_files']:
                    fname = f"{int(datetime.now().timestamp())}_{f['filename'].replace(' ', '_')}"
                    fpath = upload_dir / fname
                    with open(fpath, 'wb') as up:
                        up.write(f['body'])
                    images.append(f"/static/images/products/{fname}")
            except Exception as e:
                logger.warning("Local disk upload skipped or read-only: %s", e)

        # Handle image URLs
        urls_text = self.get_argument("image_urls", "").strip()
        if urls_text:
            for url in urls_text.splitlines():
                clean_url = url.strip()
                if clean_url:
                    images.append(clean_url)

        product_data = {
            'name': name,
            'slug': slug,
            'sku': sku,
            'category_id': category_id,
            'short_description': short_desc,
            'description': desc,
            'care_instructions': care,
            'mrp': mrp,
            'price': price,
            'stock': stock,
            'weight_grams': weight_grams,
            'badge': badge,
            'sizes': sizes,
            'colors': colors,
            'is_featured': is_featured,
            'is_active': is_active,
            'images': images
        }

        dal.create_product(product_data)
        self.redirect("/admin/products")

class AdminProductEditHandler(BaseHandler):
    def get(self, product_id):
        self.require_admin()
        product = dal.get_product_by_id(int(product_id))
        categories = dal.get_categories(only_active=False)
        self.render_template(
            "admin/product_form.html",
            active_page='products',
            product=product,
            categories=categories
        )

    def post(self, product_id):
        self.require_admin()
        pid = int(product_id)
        name = self.get_argument("name", "").strip()
        category_id = int(self.get_argument("category_id"))
        sku = self.get_argument("sku", "").strip().upper()
        slug = re.sub(r'[^a-zA-Z0-9]+', '-', name).strip('-').lower()
        mrp = float(self.get_argument("mrp", 0))
        price = float(self.get_argument("price", 0))
        stock = int(self.get_argument("stock", 10))
        weight_grams = int(self.get_argument("weight_grams", 350))
        badge = self.get_argument("badge", "").strip()
        short_desc = self.get_argument("short_description", "").strip()
        desc = self.get_argument("description", "").strip()
        care = self.get_argument("care_instructions", "").strip()
        sizes = self.get_argument("sizes", "Free Size").strip()
        colors = self.get_argument("colors", "").strip()
        is_featured = 1 if self.get_argument("is_featured", None) else 0
        is_active = 1 if self.get_argument("is_active", None) else 0

        images = []
        if 'product_files' in self.request.files:
            try:
                upload_dir = STATIC_DIR / 'images' / 'products'
                upload_dir.mkdir(parents=True, exist_ok=True)
                for f in self.request.files['product_files']:
                    fname = f"{int(datetime.now().timestamp())}_{f['filename'].replace(' ', '_')}"
                    fpath = upload_dir / fname
                    with open(fpath, 'wb') as up:
                        up.write(f['body'])
                    images.append(f"/static/images/products/{fname}")
            except Exception as e:
                logger.warning("Local disk upload skipped or read-only: %s", e)

        urls_text = self.get_argument("image_urls", "").strip()
        if urls_text:
            for url in urls_text.splitlines():
                clean_url = url.strip()
                if clean_url:
                    images.append(clean_url)

        product_data = {
            'name': name,
            'slug': slug,
            'sku': sku,
            'category_id': category_id,
            'short_description': short_desc,
            'description': desc,
            'care_instructions': care,
            'mrp': mrp,
            'price': price,
            'stock': stock,
            'weight_grams': weight_grams,
            'badge': badge,
            'sizes': sizes,
            'colors': colors,
            'is_featured': is_featured,
            'is_active': is_active
        }
        if images:
            product_data['images'] = images

        dal.update_product(pid, product_data)
        self.redirect("/admin/products")

class AdminProductDeleteHandler(BaseHandler):
    def post(self):
        self.require_admin()
        data = self.get_json_body()
        pid = int(data.get('product_id', 0))
        dal.delete_product(pid)
        self.write({'success': True})

class AdminCategoriesHandler(BaseHandler):
    def get(self):
        self.require_admin()
        cats = dal.get_categories(only_active=False)
        self.render_template("admin/categories.html", active_page='categories', categories=cats)

class AdminCategoryNewHandler(BaseHandler):
    def post(self):
        self.require_admin()
        name = self.get_argument("name", "").strip()
        slug = self.get_argument("slug", "").strip() or re.sub(r'[^a-zA-Z0-9]+', '-', name).strip('-').lower()
        desc = self.get_argument("description", "").strip()
        image_url = self.get_argument("image_url", "").strip()
        sort_order = int(self.get_argument("sort_order", 0))

        dal.create_category(name, slug, desc, image_url, sort_order)
        self.redirect("/admin/categories")

class AdminCategoryDeleteHandler(BaseHandler):
    def post(self):
        self.require_admin()
        cat_id = int(self.get_argument("category_id"))
        success = dal.delete_category(cat_id)
        self.redirect("/admin/categories")

class AdminOrdersHandler(BaseHandler):
    def get(self):
        self.require_admin()
        status_filter = self.get_argument("status", "all")
        orders = dal.get_all_orders(status_filter=status_filter)
        self.render_template(
            "admin/orders.html",
            active_page='orders',
            orders=orders,
            current_status=status_filter
        )

class AdminOrderDetailHandler(BaseHandler):
    def get(self, order_id):
        self.require_admin()
        order = dal.get_order_by_id(int(order_id))
        if not order:
            self.redirect("/admin/orders")
            return
        self.render_template("admin/order_detail.html", active_page='orders', order=order)

class AdminOrderStatusUpdateHandler(BaseHandler):
    def post(self):
        self.require_admin()
        # Handle JSON or Form body
        if self.request.headers.get("Content-Type", "").startswith("application/json"):
            data = self.get_json_body()
            order_id = int(data.get('order_id', 0))
            status = data.get('status', '')
            comment = data.get('comment', '')
            courier = data.get('courier_name')
            tracking = data.get('tracking_number')
            url = data.get('tracking_url')
            dal.update_order_status(order_id, status, comment, courier, tracking, url)
            self.write({'success': True})
        else:
            order_id = int(self.get_argument("order_id"))
            status = self.get_argument("status")
            courier = self.get_argument("courier_name", "")
            tracking = self.get_argument("tracking_number", "")
            url = self.get_argument("tracking_url", "")
            comment = self.get_argument("comment", "")
            dal.update_order_status(order_id, status, comment, courier, tracking, url)
            self.redirect(f"/admin/orders/{order_id}")

class AdminOrdersExportCsvHandler(BaseHandler):
    def get(self):
        self.require_admin()
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

        csv_content = output.getvalue()
        self.set_header("Content-Type", "text/csv; charset=UTF-8")
        self.set_header("Content-Disposition", f"attachment; filename=Shubhashtu_Orders_{datetime.now().strftime('%Y%m%d')}.csv")
        self.write(csv_content)

class AdminCustomersHandler(BaseHandler):
    def get(self):
        self.require_admin()
        customers = dal.get_all_customers()
        self.render_template("admin/customers.html", active_page='customers', customers=customers)

class AdminCustomerDeleteHandler(BaseHandler):
    def post(self):
        self.require_admin()
        data = self.get_json_body()
        customer_id = int(data.get('customer_id', 0))
        success, message = dal.delete_customer(customer_id)
        self.write({'success': success, 'message': message})

class AdminOrderDeleteHandler(BaseHandler):
    def post(self):
        self.require_admin()
        data = self.get_json_body()
        order_id = int(data.get('order_id', 0))
        success, message = dal.delete_order(order_id)
        self.write({'success': success, 'message': message})

class AdminCouponsHandler(BaseHandler):
    def get(self):
        self.require_admin()
        coupons = dal.get_coupons(only_active=False)
        self.render_template("admin/coupons.html", active_page='coupons', coupons=coupons)

class AdminCouponNewHandler(BaseHandler):
    def post(self):
        self.require_admin()
        code = self.get_argument("code", "").strip().upper()
        desc = self.get_argument("description", "").strip()
        dtype = self.get_argument("discount_type", "percentage")
        dval = float(self.get_argument("discount_value", 0))
        min_val = float(self.get_argument("min_order_value", 0))
        max_d = float(self.get_argument("max_discount")) if self.get_argument("max_discount", "") else None
        limit = int(self.get_argument("usage_limit")) if self.get_argument("usage_limit", "") else None

        dal.create_coupon({
            'code': code,
            'description': desc,
            'discount_type': dtype,
            'discount_value': dval,
            'min_order_value': min_val,
            'max_discount': max_d,
            'usage_limit': limit
        })
        self.redirect("/admin/coupons")

class AdminCouponToggleHandler(BaseHandler):
    def post(self):
        self.require_admin()
        data = self.get_json_body()
        cid = int(data.get('coupon_id', 0))
        dal.toggle_coupon_active(cid)
        self.write({'success': True})

class AdminCouponDeleteHandler(BaseHandler):
    def post(self):
        self.require_admin()
        data = self.get_json_body()
        cid = int(data.get('coupon_id', 0))
        dal.delete_coupon(cid)
        self.write({'success': True})

class AdminShippingHandler(BaseHandler):
    def get(self):
        self.require_admin()
        settings = dal.get_store_settings()
        self.render_template("admin/shipping.html", active_page='shipping', settings=settings)

class AdminShippingSaveHandler(BaseHandler):
    def post(self):
        self.require_admin()
        keys = [
            'standard_shipping_fee', 'free_shipping_threshold', 'express_shipping_fee',
            'cod_fee', 'remote_zone_surcharge', 'shiprocket_email', 'shiprocket_password',
            'shiprocket_pickup_pincode'
        ]
        for k in keys:
            val = self.get_argument(k, "")
            dal.update_setting(k, val)
        self.render_template("admin/shipping.html", active_page='shipping', settings=dal.get_store_settings(), success_msg="Shipping rules and courier settings saved successfully.")

class AdminPaymentsHandler(BaseHandler):
    def get(self):
        self.require_admin()
        settings = dal.get_store_settings()
        has_keys = bool(settings.get('razorpay_key_id') and settings.get('razorpay_key_secret'))
        self.render_template("admin/payments.html", active_page='payments', settings=settings, has_keys=has_keys)

class AdminPaymentsSaveHandler(BaseHandler):
    def post(self):
        self.require_admin()
        dal.update_setting('razorpay_key_id', self.get_argument("razorpay_key_id", "").strip())
        dal.update_setting('razorpay_key_secret', self.get_argument("razorpay_key_secret", "").strip())
        dal.update_setting('razorpay_webhook_secret', self.get_argument("razorpay_webhook_secret", "").strip())
        dal.update_setting('razorpay_test_mode', '1' if self.get_argument("razorpay_test_mode", None) else '0')
        dal.update_setting('cod_enabled', '1' if self.get_argument("cod_enabled", None) else '0')

        settings = dal.get_store_settings()
        has_keys = bool(settings.get('razorpay_key_id') and settings.get('razorpay_key_secret'))
        self.render_template("admin/payments.html", active_page='payments', settings=settings, has_keys=has_keys, success_msg="Payment credentials and options updated.")

class AdminReviewsHandler(BaseHandler):
    def get(self):
        self.require_admin()
        reviews = dal.get_all_reviews()
        self.render_template("admin/reviews.html", active_page='reviews', reviews=reviews)

class AdminReviewToggleHandler(BaseHandler):
    def post(self):
        self.require_admin()
        data = self.get_json_body()
        rid = int(data.get('review_id', 0))
        dal.toggle_review_approval(rid)
        self.write({'success': True})

class AdminReviewDeleteHandler(BaseHandler):
    def post(self):
        self.require_admin()
        data = self.get_json_body()
        rid = int(data.get('review_id', 0))
        dal.delete_review(rid)
        self.write({'success': True})

class AdminSettingsHandler(BaseHandler):
    def get(self):
        self.require_admin()
        settings = dal.get_store_settings()
        self.render_template("admin/settings.html", active_page='settings', settings=settings)

class AdminSettingsSaveHandler(BaseHandler):
    def post(self):
        self.require_admin()
        keys = ['store_name', 'tagline', 'support_phone', 'support_whatsapp', 'support_email', 'store_address', 'announcement_bar', 'instagram_handle']
        for k in keys:
            dal.update_setting(k, self.get_argument(k, ""))
        self.render_template("admin/settings.html", active_page='settings', settings=dal.get_store_settings(), success_msg="Store information saved.")

class AdminUploadImageHandler(BaseHandler):
    def post(self):
        self.require_admin()
        file_bytes = b''
        filename = "product.jpg"
        if 'file' in self.request.files:
            f = self.request.files['file'][0]
            file_bytes = f['body']
            filename = f['filename']
        elif self.request.body:
            file_bytes = self.request.body

        if not file_bytes:
            self.write({'success': False, 'error': 'No file received.'})
            return

        upload_res = ImageService.upload_image_bytes(file_bytes, filename)
        self.write(upload_res)

# ----------------- Application Setup -----------------
def make_app():
    handlers = [
        # Storefront
        (r"/", IndexHandler),
        (r"/shop", ShopHandler),
        (r"/shop/([a-zA-Z0-9_-]+)", ShopHandler),
        (r"/product/([a-zA-Z0-9_-]+)", ProductDetailHandler),
        (r"/cart", CartPageHandler),
        (r"/checkout", CheckoutPageHandler),
        (r"/order-success/([a-zA-Z0-9_-]+)", OrderSuccessHandler),
        (r"/track-order", OrderTrackHandler),
        (r"/invoice/([a-zA-Z0-9_-]+)", InvoiceHandler),
        (r"/wishlist", WishlistPageHandler),
        (r"/about", AboutHandler),
        (r"/contact", ContactHandler),
        (r"/policies", PoliciesHandler),

        # Auth
        (r"/login", LoginHandler),
        (r"/register", RegisterHandler),
        (r"/logout", LogoutHandler),
        (r"/forgot-password", ForgotPasswordHandler),
        (r"/profile", ProfileHandler),
        (r"/profile/update", ProfileUpdateHandler),
        (r"/profile/password", ProfilePasswordHandler),
        (r"/profile/address/add", ProfileAddressAddHandler),
        (r"/profile/address/delete", ProfileAddressDeleteHandler),
        (r"/profile/address/default", ProfileAddressDefaultHandler),

        # Client APIs
        (r"/api/cart", CartApiHandler),
        (r"/api/cart/add", CartAddApiHandler),
        (r"/api/cart/update", CartUpdateApiHandler),
        (r"/api/cart/remove", CartRemoveApiHandler),
        (r"/api/wishlist/toggle", WishlistToggleApiHandler),
        (r"/api/search", SearchApiHandler),
        (r"/api/shipping/calculate", ShippingCalculateApiHandler),
        (r"/api/coupon/apply", CouponApplyApiHandler),
        (r"/api/review/submit", ReviewSubmitApiHandler),
        (r"/api/ai/chat", AiAgentChatHandler),

        # Checkout & Payments
        (r"/api/checkout/place-cod-order", CheckoutPlaceCodOrderApiHandler),
        (r"/api/checkout/razorpay/create-order", CheckoutRazorpayCreateOrderApiHandler),
        (r"/api/checkout/razorpay/verify", CheckoutRazorpayVerifyApiHandler),
        (r"/api/payment/razorpay/webhook", RazorpayWebhookHandler),

        # Admin Panel
        (r"/admin", AdminDashboardHandler),
        (r"/admin/products", AdminProductsHandler),
        (r"/admin/products/new", AdminProductNewHandler),
        (r"/admin/products/edit/([0-9]+)", AdminProductEditHandler),
        (r"/admin/products/delete", AdminProductDeleteHandler),
        (r"/api/admin/upload-image", AdminUploadImageHandler),
        (r"/admin/categories", AdminCategoriesHandler),
        (r"/admin/categories/new", AdminCategoryNewHandler),
        (r"/admin/categories/delete", AdminCategoryDeleteHandler),
        (r"/admin/orders", AdminOrdersHandler),
        (r"/admin/orders/([0-9]+)", AdminOrderDetailHandler),
        (r"/admin/orders/update-status", AdminOrderStatusUpdateHandler),
        (r"/admin/orders/delete", AdminOrderDeleteHandler),
        (r"/admin/orders/export-csv", AdminOrdersExportCsvHandler),
        (r"/admin/customers", AdminCustomersHandler),
        (r"/admin/customers/delete", AdminCustomerDeleteHandler),
        (r"/admin/coupons", AdminCouponsHandler),
        (r"/admin/coupons/new", AdminCouponNewHandler),
        (r"/admin/coupons/toggle", AdminCouponToggleHandler),
        (r"/admin/coupons/delete", AdminCouponDeleteHandler),
        (r"/admin/shipping", AdminShippingHandler),
        (r"/admin/shipping/save", AdminShippingSaveHandler),
        (r"/admin/payments", AdminPaymentsHandler),
        (r"/admin/payments/save", AdminPaymentsSaveHandler),
        (r"/admin/reviews", AdminReviewsHandler),
        (r"/admin/reviews/toggle", AdminReviewToggleHandler),
        (r"/admin/reviews/delete", AdminReviewDeleteHandler),
        (r"/admin/settings", AdminSettingsHandler),
        (r"/admin/settings/save", AdminSettingsSaveHandler),

        # Static assets
        (r"/static/(.*)", tornado.web.StaticFileHandler, {"path": str(STATIC_DIR)})
    ]

    settings = {
        "cookie_secret": Config.COOKIE_SECRET,
        "debug": Config.DEBUG,
        "xsrf_cookies": False
    }

    return tornado.web.Application(handlers, **settings)

def main():
    db.init_db()
    # Auto-seed if first run
    import seed
    seed.seed_database()

    port = Config.PORT
    print(f"\n" + "="*60, flush=True)
    print(f"  *** SHUBHASHTU FASHION E-COMMERCE IS LIVE! ***", flush=True)
    print(f"  Brand Tagline: \"{Config.BRAND_TAGLINE}\"", flush=True)
    print(f"  Store URL:     http://localhost:{port}", flush=True)
    print(f"  Admin Portal:  http://localhost:{port}/admin", flush=True)
    print(f"  Admin Login:   {Config.ADMIN_EMAIL} / {Config.ADMIN_PASSWORD}", flush=True)
    print(f"="*60 + "\n", flush=True)

    if not HAS_TORNADO:
        from wsgiref.simple_server import make_server
        from api.index import app as wsgi_app
        print("  Running with Python Built-in WSGI Server...")
        httpd = make_server('0.0.0.0', port, wsgi_app)
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nServer stopped.")
        return

    app = make_app()
    server = tornado.httpserver.HTTPServer(app)
    server.listen(port, address="0.0.0.0")
    tornado.ioloop.IOLoop.current().start()

if __name__ == "__main__":
    main()

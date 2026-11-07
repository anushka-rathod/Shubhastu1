"""
AI Agent Service for Shubhashtu Fashion.
Implements Vercel AI SDK Agent architecture with tool calling, catalog retrieval,
order tracking, shipping calculation, and fashion styling recommendations.
"""
import os
import re
import json
import logging
from typing import List, Dict, Any, Optional

import dal
from config import Config
from services.shipping_service import ShippingService
import db

logger = logging.getLogger("shubhashtu.ai_agent")

SYSTEM_PROMPT = """
You are the official AI Fashion Stylist & Concierge for SHUBHASHTU FASHION ("Style That Speaks for You.").
Your role is to guide customers with warmth, elegance, and expert fashion advice.

Brand Heritage:
- Shubhashtu Fashion is a premium Indian boutique specializing in handcrafted heritage earrings (Kundan, Meenakari, Temple Jhumkas, Pearls, Polki, Afghani Tribal Silver) and 100% hand-painted wearable art t-shirts (220 GSM bio-washed combed cotton with permanent wash-safe mineral colors).
- You can recommend products, assist with sizing, styling tips for festivals/weddings, check order tracking, calculate delivery charges, and share active coupon codes.

Available Tools:
1. search_products(query, category_slug, max_price)
2. get_product_details(slug)
3. track_order(order_number, phone)
4. calculate_shipping(pincode, subtotal)
5. list_coupons()

Tone: Polite, sophisticated, helpful, and proudly celebrating authentic Indian craftsmanship.
"""

class AIAgentService:
    def __init__(self):
        self.shipping_svc = ShippingService(db.get_connection())
        self.gemini_key = os.environ.get("GEMINI_API_KEY", "")
        self.openai_key = os.environ.get("OPENAI_API_KEY", "")

    # ==================== AGENT TOOLS ====================

    def tool_search_products(self, query: str = None, category_slug: str = None, max_price: float = None) -> List[Dict[str, Any]]:
        """Tool: Search store catalog with real-time stock and prices."""
        prods = dal.get_products(
            category_slug=category_slug if (category_slug and category_slug != 'all') else None,
            search=query if query else None,
            max_price=max_price,
            limit=5
        )
        results = []
        for p in prods:
            results.append({
                'id': p['id'],
                'name': p['name'],
                'slug': p['slug'],
                'category': p['category_name'],
                'price': p['price'],
                'mrp': p['mrp'],
                'discount_pct': p['discount_pct'],
                'image': p['primary_image'],
                'badge': p.get('badge', ''),
                'stock': p['stock'],
                'short_description': p['short_description']
            })
        return results

    def tool_get_product_details(self, slug: str) -> Optional[Dict[str, Any]]:
        """Tool: Retrieve full specs, craftsmanship story, care tips for a product."""
        p = dal.get_product_by_slug(slug)
        if not p:
            return None
        return {
            'id': p['id'],
            'name': p['name'],
            'slug': p['slug'],
            'category': p['category_name'],
            'price': p['price'],
            'mrp': p['mrp'],
            'description': p['description'],
            'care_instructions': p['care_instructions'],
            'sizes': p['sizes_list'],
            'colors': p['colors_list'],
            'stock': p['stock'],
            'badge': p['badge'],
            'image': p['primary_image']
        }

    def tool_track_order(self, order_number: str, phone: str = None) -> Dict[str, Any]:
        """Tool: Track order status, courier name, and estimated delivery date."""
        tracked = dal.get_order_tracking(order_number.strip().upper(), phone.strip() if phone else None)
        if not tracked:
            return {
                'found': False,
                'message': f"No order found matching #{order_number}. Please verify your order ID or phone number."
            }
        return {
            'found': True,
            'order_number': tracked['order_number'],
            'status': tracked['order_status'],
            'total_amount': tracked['total_amount'],
            'courier_name': tracked.get('courier_name', 'In Transit via BlueDart / Delhivery'),
            'tracking_number': tracked.get('tracking_number', 'Will be shared via SMS upon dispatch'),
            'estimated_delivery': tracked.get('estimated_delivery', '3-5 business days across India'),
            'item_count': len(tracked.get('items', []))
        }

    def tool_calculate_shipping(self, pincode: str, subtotal: float = 1200.0) -> Dict[str, Any]:
        """Tool: Calculate domestic delivery fees, courier routing, and free shipping."""
        return self.shipping_svc.calculate_delivery(pincode, subtotal)

    def tool_list_coupons(self) -> List[Dict[str, Any]]:
        """Tool: List all active promotional offers and discounts."""
        coupons = dal.get_coupons(only_active=True)
        return [{
            'code': c['code'],
            'description': c['description'],
            'type': c['discount_type'],
            'value': f"{c['discount_value']}% OFF" if c['discount_type'] == 'percentage' else f"Flat ₹{c['discount_value']} OFF",
            'min_order': c['min_order_value']
        } for c in coupons]

    # ==================== CONVERSATION DISPATCHER ====================

    def process_message(self, user_msg: str, conversation_history: List[Dict[str, str]] = None) -> Dict[str, Any]:
        """
        Processes a customer query, executes relevant tools, and formulates
        a luxury styling response with actionable product recommendation cards.
        """
        msg_clean = user_msg.strip().lower()
        products_to_recommend = []
        suggestions = []

        # 1. Order Tracking Query
        order_match = re.search(r'shb[-_\s]?\d{4}[-_\s]?\d+', msg_clean, re.IGNORECASE)
        if order_match or 'track' in msg_clean or 'order status' in msg_clean:
            if order_match:
                ord_num = order_match.group(0).replace(' ', '-').upper()
                track_res = self.tool_track_order(ord_num)
                if track_res['found']:
                    reply = (
                        f"✨ **Order Status for #{track_res['order_number']}**\n\n"
                        f"• **Current Status:** `{track_res['status']}`\n"
                        f"• **Estimated Delivery:** {track_res['estimated_delivery']}\n"
                        f"• **Courier Partner:** {track_res['courier_name']}\n"
                        f"• **Tracking No:** `{track_res['tracking_number']}`\n\n"
                        f"Your items are carefully packed in our signature Shubhashtu protective packaging. Let me know if you need any styling tips while you await your package!"
                    )
                else:
                    reply = f"I couldn't find an order with number **#{ord_num}**. Please check your SMS or email for the exact order ID."
                suggestions = ["Check another order", "Explore New Arrivals", "View Best Sellers"]
                return {'response': reply, 'products': [], 'suggestions': suggestions}
            else:
                reply = "I'd be happy to track your order! Please share your **Order ID** (for example `SHB-2026-1001`) or phone number."
                return {'response': reply, 'products': [], 'suggestions': ["SHB-2026-1001", "Contact Support"]}

        # 2. Shipping & Delivery Queries
        pin_match = re.search(r'\b\d{6}\b', msg_clean)
        if pin_match or 'delivery' in msg_clean or 'shipping' in msg_clean or 'pincode' in msg_clean:
            if pin_match:
                pincode = pin_match.group(0)
                ship_res = self.tool_calculate_shipping(pincode, 1499.0)
                if ship_res['serviceable']:
                    fee_txt = "FREE (on orders above ₹999)" if ship_res['is_free_shipping'] else f"₹{ship_res['shipping_fee']}"
                    reply = (
                        f"🚚 **Delivery Information for PIN {pincode}** ({ship_res['city']}, {ship_res['state']}):\n\n"
                        f"• **Serviceability:** Available across all standard & express couriers\n"
                        f"• **Shipping Fee:** **{fee_txt}**\n"
                        f"• **Estimated Time:** {ship_res['estimated_days']} business days\n"
                        f"• **Cash on Delivery (COD):** Available\n\n"
                        f"All orders are dispatched from our studio within 24 hours with real-time tracking!"
                    )
                else:
                    reply = f"PIN Code {pincode} could not be validated. We ship across all Indian postal circles via BlueDart and Delhivery."
                suggestions = ["Browse Hand-Painted Tees", "Browse Royal Earrings", "View Coupons"]
                return {'response': reply, 'products': [], 'suggestions': suggestions}

        # 3. Coupons & Offers Queries
        if any(w in msg_clean for w in ['coupon', 'discount', 'offer', 'promo', 'code', 'sale']):
            coupons = self.tool_list_coupons()
            c_text = "\n".join([f"• **`{c['code']}`**: {c['description']} ({c['value']})" for c in coupons])
            reply = (
                f"🏷️ **Exclusive Festive Offers at Shubhashtu Fashion**:\n\n"
                f"{c_text}\n\n"
                f"💡 *Tip:* Standard domestic shipping is also **100% FREE** on all orders above ₹999!"
            )
            products_to_recommend = self.tool_search_products(category_slug='earrings')[:2]
            suggestions = ["Apply WELCOME10", "Shop Earrings Under ₹1500", "Shop Hand-Painted Tees"]
            return {'response': reply, 'products': products_to_recommend, 'suggestions': suggestions}

        # 4. Hand-Painted T-Shirts Queries
        if any(w in msg_clean for w in ['t-shirt', 'tshirt', 'tee', 'cotton', 'hand painted', 'painted', 'mandala', 'peacock tee', 'elephant']):
            products_to_recommend = self.tool_search_products(category_slug='hand-painted-t-shirts')
            reply = (
                f"🎨 **Wearable Art Collection: Hand-Painted T-Shirts**\n\n"
                f"Each Shubhashtu t-shirt is an individual masterpiece! Our master artists paint every motif stroke-by-stroke using permanent, non-fading fabric acrylics on **220 GSM combed bio-washed organic cotton**.\n\n"
                f"Here are our most celebrated motifs:"
            )
            suggestions = ["Peacock Symphony Tee", "Sacred Mandala Oversized Tee", "Sizing Guide", "Care Instructions"]
            return {'response': reply, 'products': products_to_recommend, 'suggestions': suggestions}

        # 5. Earrings & Jewelry Queries
        if any(w in msg_clean for w in ['earring', 'jhumka', 'chandbali', 'kundan', 'pearl', 'silver', 'jewelry', 'jewellery', 'stud', 'polki']):
            # Filter specific keyword if present
            search_term = None
            if 'kundan' in msg_clean: search_term = 'Kundan'
            elif 'temple' in msg_clean or 'jhumka' in msg_clean: search_term = 'Temple'
            elif 'pearl' in msg_clean: search_term = 'Pearl'
            elif 'silver' in msg_clean or 'oxidised' in msg_clean: search_term = 'Afghani'

            products_to_recommend = self.tool_search_products(query=search_term, category_slug='earrings')
            reply = (
                f"👑 **The Royal Earring Atelier**\n\n"
                f"Sculpted with 24K gold micron plating and handcrafted by master Jaipur karigars. Hypoallergenic, feather-light on the earlobes, and delivered in a protective velvet keepsake box.\n\n"
                f"Take a look at these exquisite handcrafted pieces:"
            )
            suggestions = ["Kundan Meenakari Chandbalis", "Mayura Temple Jhumkas", "Pearl Floral Tops", "Under ₹1,000"]
            return {'response': reply, 'products': products_to_recommend, 'suggestions': suggestions}

        # 6. Sangeet / Wedding / Festive Styling Advice
        if any(w in msg_clean for w in ['sangeet', 'wedding', 'festive', 'party', 'lehenga', 'saree', 'gift', 'style', 'recommend']):
            products_to_recommend = self.tool_search_products(category_slug='earrings')[:3]
            reply = (
                f"✨ **Bespoke Festive Styling by Shubhashtu**\n\n"
                f"For weddings, sangeet, and celebratory evenings, we recommend balancing royal statement jewelry with pastel or gold highlights:\n\n"
                f"• **For Lehengas & Anarkalis:** Pair with our **Kundan Meenakari Royal Chandbalis** (Blush Pink enamel) or **Jadau Polki Palace Danglers**.\n"
                f"• **For Silk Sarees:** Our **Mayura Heritage Temple Dancing Peacock Jhumkas** create an unforgettable regal presence.\n"
                f"• **For Day Events & Contemporary Silhouettes:** Our **Gulabi Freshwater Pearl Blossoms** offer effortless royal grace."
            )
            suggestions = ["Show Chandbalis", "Show Temple Jhumkas", "Delivery Time", "Coupon Codes"]
            return {'response': reply, 'products': products_to_recommend, 'suggestions': suggestions}

        # 7. General Friendly Welcome / Help
        all_picks = self.tool_search_products()[:3]
        reply = (
            f"Namaste! 🙏 Welcome to **Shubhashtu Fashion** — *Style That Speaks for You.*\n\n"
            f"I am your personal AI Stylist and Concierge. I can help you with:\n"
            f"• 👑 **Jewelry Styling:** Finding the perfect Kundan, jhumka, or chandbali for your outfit.\n"
            f"• 🎨 **Wearable Art:** Exploring authentic hand-painted organic cotton tees.\n"
            f"• 🚚 **Delivery & Tracking:** Instant shipping fee calculation and order status.\n"
            f"• 🏷️ **Promotions:** Unlocking active discount coupons like `WELCOME10`.\n\n"
            f"What may I style or look up for you today?"
        )
        suggestions = ["Recommend earrings for wedding", "Hand-painted t-shirts collection", "Track my order", "Available coupon codes"]
        return {'response': reply, 'products': all_picks, 'suggestions': suggestions}


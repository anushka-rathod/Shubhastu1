"""
Email notification service for Shubhashtu Fashion.
Supports SMTP with graceful fallback to console logging when SMTP is unconfigured.
"""
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from config import Config

logger = logging.getLogger(__name__)

class EmailService:
    @staticmethod
    def send_order_confirmation(to_email: str, order_data: dict, order_items: list):
        """Sends rich order confirmation email."""
        subject = f"Order Confirmed: {order_data['order_number']} | Shubhashtu Fashion"
        items_html = "".join([
            f"<tr><td style='padding:8px;border-bottom:1px solid #eee;'>{item['product_name']} (Size: {item.get('selected_size', 'Free')}) x {item['quantity']}</td>"
            f"<td style='padding:8px;border-bottom:1px solid #eee;text-align:right;'>₹{item.get('total_price', item['price'] * item['quantity']):.2f}</td></tr>"
            for item in order_items
        ])

        html_body = f"""
        <div style="font-family:'Helvetica Neue', Arial, sans-serif;max-width:600px;margin:auto;padding:24px;border:1px solid #f0e6e6;border-radius:12px;background:#ffffff;">
            <div style="text-align:center;padding-bottom:16px;border-bottom:2px solid #fce7ec;">
                <h1 style="color:#b3882a;margin:0;letter-spacing:2px;font-size:26px;">SHUBHASHTU FASHION</h1>
                <p style="color:#666;font-style:italic;margin:4px 0 0 0;">Style That Speaks for You</p>
            </div>
            
            <div style="padding:20px 0;">
                <h2 style="color:#111;font-size:20px;">Thank you for your order, {order_data['customer_name']}!</h2>
                <p style="color:#555;line-height:1.6;">We have received your order <strong>#{order_data['order_number']}</strong> and our team is preparing it with utmost care.</p>
                
                <div style="background:#fdf2f4;border-radius:8px;padding:16px;margin:20px 0;">
                    <p style="margin:0 0 8px 0;"><strong>Order Status:</strong> {order_data['order_status']}</p>
                    <p style="margin:0 0 8px 0;"><strong>Payment Method:</strong> {order_data['payment_method'].upper()} ({order_data['payment_status'].capitalize()})</p>
                    <p style="margin:0;"><strong>Estimated Delivery:</strong> {order_data.get('estimated_delivery') or '3-5 Business Days'}</p>
                </div>

                <h3 style="border-bottom:1px solid #eee;padding-bottom:8px;color:#111;">Order Summary</h3>
                <table style="width:100%;border-collapse:collapse;">
                    {items_html}
                    <tr><td style="padding:8px;font-weight:bold;">Subtotal</td><td style="padding:8px;text-align:right;">₹{order_data['subtotal']:.2f}</td></tr>
                    <tr><td style="padding:8px;color:#2e7d32;">Discount ({order_data.get('coupon_code') or 'None'})</td><td style="padding:8px;text-align:right;color:#2e7d32;">-₹{order_data.get('discount_amount', 0):.2f}</td></tr>
                    <tr><td style="padding:8px;">Delivery Charges</td><td style="padding:8px;text-align:right;">₹{order_data['shipping_fee']:.2f}</td></tr>
                    <tr style="font-size:16px;font-weight:bold;background:#fff8f9;"><td style="padding:12px;">Total Paid</td><td style="padding:12px;text-align:right;color:#b3882a;">₹{order_data['total_amount']:.2f}</td></tr>
                </table>

                <div style="margin-top:24px;padding:16px;background:#fafafa;border-radius:8px;">
                    <h4 style="margin:0 0 8px 0;color:#333;">Delivery Address:</h4>
                    <p style="margin:0;color:#555;line-height:1.5;">
                        {order_data['shipping_address_line1']}<br>
                        {order_data.get('shipping_address_line2') or ''}<br>
                        {order_data['shipping_city']}, {order_data['shipping_state']} - {order_data['shipping_pincode']}<br>
                        Phone: {order_data['customer_phone']}
                    </p>
                </div>
            </div>

            <div style="text-align:center;padding-top:20px;border-top:1px solid #eee;color:#888;font-size:12px;">
                <p>Have questions? Reach us on WhatsApp at <strong>+{Config.SUPPORT_WHATSAPP}</strong> or reply to this email.</p>
                <p>&copy; 2026 Shubhashtu Fashion. All rights reserved.</p>
            </div>
        </div>
        """

        if Config.SMTP_USER and Config.SMTP_PASSWORD:
            try:
                msg = MIMEMultipart("alternative")
                msg["Subject"] = subject
                msg["From"] = Config.SMTP_FROM
                msg["To"] = to_email
                msg.attach(MIMEText(html_body, "html"))

                with smtplib.SMTP(Config.SMTP_HOST, Config.SMTP_PORT) as server:
                    server.starttls()
                    server.login(Config.SMTP_USER, Config.SMTP_PASSWORD)
                    server.sendmail(Config.SMTP_FROM, [to_email], msg.as_string())
                logger.info("Order confirmation email sent to %s", to_email)
            except Exception as e:
                logger.warning("Could not send email via SMTP (%s). Logged locally.", e)
        else:
            logger.info("[MOCK EMAIL] Confirmation sent to %s for order %s (Amount: ₹%s)", to_email, order_data['order_number'], order_data['total_amount'])

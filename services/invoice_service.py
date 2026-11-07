"""
Tax Invoice generation service for Shubhashtu Fashion.
Formats high-grade, GST-compliant printable e-commerce invoices.
"""
from datetime import datetime

def format_inr(amount: float) -> str:
    """Format number into Indian Rupee representation (e.g. ₹1,499.00)."""
    try:
        val = float(amount)
        # Indian number grouping format
        s = f"{val:.2f}"
        whole, dec = s.split('.')
        if len(whole) > 3:
            last3 = whole[-3:]
            rest = whole[:-3]
            groups = []
            while len(rest) > 2:
                groups.insert(0, rest[-2:])
                rest = rest[:-2]
            if rest:
                groups.insert(0, rest)
            groups.append(last3)
            formatted = ','.join(groups)
        else:
            formatted = whole
        return f"₹{formatted}.{dec}"
    except Exception:
        return f"₹{amount}"

def build_invoice_context(order: dict, order_items: list, store_settings: dict) -> dict:
    """Constructs complete context dictionary for rendering invoice template."""
    created_at = order.get('created_at')
    if isinstance(created_at, str):
        try:
            date_obj = datetime.strptime(created_at[:19], '%Y-%m-%d %H:%M:%S')
            invoice_date = date_obj.strftime("%d %B %Y")
        except Exception:
            invoice_date = created_at
    else:
        invoice_date = datetime.now().strftime("%d %B %Y")

    invoice_number = f"INV-{order['order_number']}"
    
    return {
        'order': order,
        'order_items': order_items,
        'invoice_number': invoice_number,
        'invoice_date': invoice_date,
        'store': store_settings,
        'format_inr': format_inr
    }


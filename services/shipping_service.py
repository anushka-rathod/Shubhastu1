"""
Shipping and Delivery calculation service for Shubhashtu Fashion.
Features:
- Indian PIN code validation, city/state resolution, and ETA calculation
- Weight-based and zone-based delivery charge calculation
- Configurable free shipping threshold and standard delivery fees
- Shiprocket REST API integration with graceful fallback to store rules
"""
import re
import json
import logging
from datetime import datetime, timedelta
import requests

logger = logging.getLogger(__name__)

# Indian PIN code circle prefix to State and Zone mapping
PINCODE_PREFIX_MAP = {
    # Northern Circle
    '11': {'state': 'Delhi', 'zone': 'metro', 'city': 'New Delhi'},
    '12': {'state': 'Haryana', 'zone': 'tier1', 'city': 'Gurugram / Faridabad'},
    '13': {'state': 'Haryana', 'zone': 'tier2', 'city': 'Ambala / Panipat'},
    '14': {'state': 'Punjab', 'zone': 'tier2', 'city': 'Ludhiana / Jalandhar'},
    '15': {'state': 'Punjab', 'zone': 'tier2', 'city': 'Bathinda / Patiala'},
    '16': {'state': 'Chandigarh', 'zone': 'tier1', 'city': 'Chandigarh'},
    '17': {'state': 'Himachal Pradesh', 'zone': 'tier2', 'city': 'Shimla / Dharamshala'},
    '18': {'state': 'Jammu & Kashmir', 'zone': 'special', 'city': 'Jammu'},
    '19': {'state': 'Jammu & Kashmir', 'zone': 'special', 'city': 'Srinagar'},
    # Central / Western Circle
    '20': {'state': 'Uttar Pradesh', 'zone': 'tier1', 'city': 'Noida / Ghaziabad'},
    '21': {'state': 'Uttar Pradesh', 'zone': 'tier2', 'city': 'Prayagraj / Kanpur'},
    '22': {'state': 'Uttar Pradesh', 'zone': 'tier2', 'city': 'Lucknow / Varanasi'},
    '23': {'state': 'Uttar Pradesh', 'zone': 'tier2', 'city': 'Gorakhpur / Mirzapur'},
    '24': {'state': 'Uttarakhand', 'zone': 'tier2', 'city': 'Dehradun / Haridwar'},
    '25': {'state': 'Uttar Pradesh', 'zone': 'tier2', 'city': 'Meerut / Moradabad'},
    '26': {'state': 'Uttarakhand', 'zone': 'tier2', 'city': 'Nainital / Almora'},
    '27': {'state': 'Uttar Pradesh', 'zone': 'tier2', 'city': 'Faizabad / Ayodhya'},
    '28': {'state': 'Uttar Pradesh', 'zone': 'tier2', 'city': 'Agra / Mathura'},
    # Rajasthan
    '30': {'state': 'Rajasthan', 'zone': 'tier1', 'city': 'Jaipur'},
    '31': {'state': 'Rajasthan', 'zone': 'tier2', 'city': 'Udaipur / Kota'},
    '32': {'state': 'Rajasthan', 'zone': 'tier2', 'city': 'Ajmer / Bharatpur'},
    '33': {'state': 'Rajasthan', 'zone': 'tier2', 'city': 'Bikaner / Sikar'},
    '34': {'state': 'Rajasthan', 'zone': 'tier2', 'city': 'Jodhpur / Barmer'},
    # Gujarat
    '36': {'state': 'Gujarat', 'zone': 'tier2', 'city': 'Rajkot / Bhavnagar'},
    '37': {'state': 'Gujarat', 'zone': 'tier2', 'city': 'Jamnagar / Bhuj'},
    '38': {'state': 'Gujarat', 'zone': 'metro', 'city': 'Ahmedabad / Gandhinagar'},
    '39': {'state': 'Gujarat', 'zone': 'tier1', 'city': 'Surat / Vadodara'},
    # Maharashtra & Goa
    '40': {'state': 'Maharashtra', 'zone': 'metro', 'city': 'Mumbai / Thane'},
    '41': {'state': 'Maharashtra', 'zone': 'metro', 'city': 'Pune / Kolhapur'},
    '42': {'state': 'Maharashtra', 'zone': 'tier2', 'city': 'Nashik / Dhule'},
    '43': {'state': 'Maharashtra', 'zone': 'tier2', 'city': 'Chhatrapati Sambhajinagar'},
    '44': {'state': 'Maharashtra', 'zone': 'tier2', 'city': 'Nagpur / Amravati'},
    '403': {'state': 'Goa', 'zone': 'tier2', 'city': 'Panaji / Margao'},
    # Madhya Pradesh & Chhattisgarh
    '45': {'state': 'Madhya Pradesh', 'zone': 'tier1', 'city': 'Indore'},
    '46': {'state': 'Madhya Pradesh', 'zone': 'tier1', 'city': 'Bhopal'},
    '47': {'state': 'Madhya Pradesh', 'zone': 'tier2', 'city': 'Gwalior'},
    '48': {'state': 'Madhya Pradesh', 'zone': 'tier2', 'city': 'Jabalpur'},
    '49': {'state': 'Chhattisgarh', 'zone': 'tier2', 'city': 'Raipur / Bilaspur'},
    # Andhra Pradesh & Telangana
    '50': {'state': 'Telangana', 'zone': 'metro', 'city': 'Hyderabad / Secunderabad'},
    '51': {'state': 'Andhra Pradesh', 'zone': 'tier2', 'city': 'Tirupati / Kadapa'},
    '52': {'state': 'Andhra Pradesh', 'zone': 'tier2', 'city': 'Vijayawada / Guntur'},
    '53': {'state': 'Andhra Pradesh', 'zone': 'tier1', 'city': 'Visakhapatnam'},
    # Karnataka
    '56': {'state': 'Karnataka', 'zone': 'metro', 'city': 'Bengaluru'},
    '57': {'state': 'Karnataka', 'zone': 'tier2', 'city': 'Mangaluru / Udupi'},
    '58': {'state': 'Karnataka', 'zone': 'tier2', 'city': 'Hubballi / Dharwad'},
    '59': {'state': 'Karnataka', 'zone': 'tier2', 'city': 'Belagavi / Kalaburagi'},
    # Tamil Nadu & Puducherry
    '60': {'state': 'Tamil Nadu', 'zone': 'metro', 'city': 'Chennai'},
    '61': {'state': 'Tamil Nadu', 'zone': 'tier2', 'city': 'Tiruchirappalli / Thanjavur'},
    '62': {'state': 'Tamil Nadu', 'zone': 'tier2', 'city': 'Madurai / Tirunelveli'},
    '63': {'state': 'Tamil Nadu', 'zone': 'tier2', 'city': 'Salem / Vellore'},
    '64': {'state': 'Tamil Nadu', 'zone': 'tier1', 'city': 'Coimbatore / Erode'},
    # Kerala
    '67': {'state': 'Kerala', 'zone': 'tier2', 'city': 'Kozhikode / Kannur'},
    '68': {'state': 'Kerala', 'zone': 'tier1', 'city': 'Kochi / Thrissur'},
    '69': {'state': 'Kerala', 'zone': 'tier1', 'city': 'Thiruvananthapuram / Kollam'},
    # West Bengal & Northeast
    '70': {'state': 'West Bengal', 'zone': 'metro', 'city': 'Kolkata / Howrah'},
    '71': {'state': 'West Bengal', 'zone': 'tier2', 'city': 'Burdwan / Hooghly'},
    '72': {'state': 'West Bengal', 'zone': 'tier2', 'city': 'Medinipur'},
    '73': {'state': 'West Bengal', 'zone': 'tier2', 'city': 'Siliguri / Darjeeling'},
    '74': {'state': 'West Bengal', 'zone': 'tier2', 'city': 'Malda / Murshidabad'},
    '744': {'state': 'Andaman & Nicobar', 'zone': 'special', 'city': 'Port Blair'},
    # Odisha
    '75': {'state': 'Odisha', 'zone': 'tier1', 'city': 'Bhubaneswar / Cuttack'},
    '76': {'state': 'Odisha', 'zone': 'tier2', 'city': 'Rourkela / Sambalpur'},
    '77': {'state': 'Odisha', 'zone': 'tier2', 'city': 'Balasore / Puri'},
    # Assam & Northeast States
    '78': {'state': 'Assam', 'zone': 'tier2', 'city': 'Guwahati / Dibrugarh'},
    '79': {'state': 'Northeast States', 'zone': 'special', 'city': 'Shillong / Imphal / Agartala'},
    # Bihar & Jharkhand
    '80': {'state': 'Bihar', 'zone': 'tier1', 'city': 'Patna'},
    '81': {'state': 'Bihar', 'zone': 'tier2', 'city': 'Bhagalpur / Gaya'},
    '82': {'state': 'Bihar', 'zone': 'tier2', 'city': 'Muzaffarpur / Darbhanga'},
    '83': {'state': 'Jharkhand', 'zone': 'tier1', 'city': 'Ranchi / Jamshedpur'},
    '84': {'state': 'Bihar', 'zone': 'tier2', 'city': 'Purnia / Begusarai'},
    '85': {'state': 'Jharkhand', 'zone': 'tier2', 'city': 'Dhanbad / Bokaro'},
}

class ShippingService:
    def __init__(self, db_conn=None):
        self._db_conn = db_conn
        self._shiprocket_token = None
        self._token_expiry = None

    def _get_setting(self, key: str, default_val: str) -> str:
        """Retrieves store shipping setting from database or default."""
        if self._db_conn:
            row = self._db_conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
            if row:
                return row['value']
        return default_val

    def lookup_pincode(self, pincode: str) -> dict:
        """Validates 6-digit Indian PIN code and returns geographical location."""
        pincode = str(pincode).strip()
        if not re.match(r'^[1-9][0-9]{5}$', pincode):
            return {
                'valid': False,
                'message': 'Please enter a valid 6-digit Indian PIN code.'
            }

        prefix3 = pincode[:3]
        prefix2 = pincode[:2]

        loc_info = PINCODE_PREFIX_MAP.get(prefix3) or PINCODE_PREFIX_MAP.get(prefix2)

        if loc_info:
            return {
                'valid': True,
                'pincode': pincode,
                'state': loc_info['state'],
                'city': loc_info['city'],
                'zone': loc_info['zone'],
                'serviceable': True
            }

        # Fallback for valid format unknown circle
        return {
            'valid': True,
            'pincode': pincode,
            'state': 'India',
            'city': 'Standard Service Hub',
            'zone': 'rest_of_india',
            'serviceable': True
        }

    def calculate_delivery(self, pincode: str, subtotal: float, weight_grams: int = 400, is_express: bool = False, is_cod: bool = False) -> dict:
        """
        Calculates shipping cost, estimated delivery days, and free shipping status.
        Uses Shiprocket API if configured, otherwise computes based on admin store rules.
        """
        pincode_info = self.lookup_pincode(pincode)
        if not pincode_info['valid']:
            return {
                'serviceable': False,
                'shipping_fee': 0.0,
                'message': pincode_info.get('message', 'Invalid PIN code'),
                'estimated_days': '',
                'estimated_date': '',
                'is_free_shipping': False
            }

        # Read rules from store settings
        standard_fee = float(self._get_setting('standard_shipping_fee', '70'))
        free_shipping_threshold = float(self._get_setting('free_shipping_threshold', '999'))
        express_fee = float(self._get_setting('express_shipping_fee', '120'))
        cod_charge = float(self._get_setting('cod_fee', '40')) if is_cod else 0.0
        remote_surcharge = float(self._get_setting('remote_zone_surcharge', '40'))

        # Check Shiprocket credentials if available
        shiprocket_email = self._get_setting('shiprocket_email', '')
        shiprocket_password = self._get_setting('shiprocket_password', '')
        rate_source = 'store_rules'
        courier_name = 'Shubhashtu Express Courier'

        zone = pincode_info.get('zone', 'rest_of_india')
        
        # Calculate delivery window based on zone
        now = datetime.now()
        if is_express:
            min_days, max_days = 1, 2
        elif zone == 'metro':
            min_days, max_days = 2, 4
        elif zone == 'tier1':
            min_days, max_days = 3, 5
        elif zone == 'special':
            min_days, max_days = 5, 8
        else:
            min_days, max_days = 4, 6

        estimated_days = f"{min_days}-{max_days} Business Days"
        eta_date = now + timedelta(days=max_days)
        estimated_date = eta_date.strftime("%d %b, %Y")

        # Weight calculation: base 500g, additional ₹30 per 500g
        weight_fee = 0.0
        if weight_grams > 500:
            extra_units = (weight_grams - 500 + 499) // 500
            weight_fee = extra_units * 30.0

        # Free shipping evaluation
        is_free = (subtotal >= free_shipping_threshold) and not is_express
        
        if is_free:
            shipping_fee = 0.0
        elif is_express:
            shipping_fee = express_fee + weight_fee
        else:
            shipping_fee = standard_fee + weight_fee
            if zone == 'special':
                shipping_fee += remote_surcharge

        # Attempt Shiprocket live check if credentials configured
        if shiprocket_email and shiprocket_password:
            sr_result = self._query_shiprocket_rate(
                shiprocket_email,
                shiprocket_password,
                pincode,
                weight_grams,
                is_cod
            )
            if sr_result and sr_result.get('serviceable'):
                rate_source = 'shiprocket'
                courier_name = sr_result.get('courier_name', courier_name)
                if not is_free:
                    shipping_fee = sr_result.get('rate', shipping_fee)
                estimated_days = sr_result.get('etd', estimated_days)

        amount_needed_for_free = max(0.0, free_shipping_threshold - subtotal)

        return {
            'serviceable': True,
            'pincode': pincode,
            'city': pincode_info.get('city', ''),
            'state': pincode_info.get('state', ''),
            'zone': zone,
            'shipping_fee': round(shipping_fee, 2),
            'cod_fee': round(cod_charge, 2),
            'total_delivery_charges': round(shipping_fee + cod_charge, 2),
            'is_free_shipping': is_free,
            'free_shipping_threshold': free_shipping_threshold,
            'amount_needed_for_free_shipping': round(amount_needed_for_free, 2),
            'estimated_days': estimated_days,
            'estimated_date': estimated_date,
            'courier_name': courier_name,
            'rate_source': rate_source,
            'is_express': is_express
        }

    def _query_shiprocket_rate(self, email: str, password: str, delivery_pincode: str, weight_grams: int, is_cod: bool):
        """Optional Shiprocket live courier rate query."""
        try:
            pickup_pincode = self._get_setting('shiprocket_pickup_pincode', '560001')
            # 1. Login if token not cached
            if not self._shiprocket_token or (self._token_expiry and datetime.now() > self._token_expiry):
                resp = requests.post(
                    'https://apiv2.shiprocket.in/v1/external/auth/login',
                    json={'email': email, 'password': password},
                    timeout=5
                )
                if resp.status_code == 200:
                    data = resp.json()
                    self._shiprocket_token = data.get('token')
                    self._token_expiry = datetime.now() + timedelta(days=9)
                else:
                    return None

            headers = {'Authorization': f'Bearer {self._shiprocket_token}'}
            params = {
                'pickup_postcode': pickup_pincode,
                'delivery_postcode': delivery_pincode,
                'weight': max(0.2, weight_grams / 1000.0),
                'cod': 1 if is_cod else 0
            }
            res = requests.get(
                'https://apiv2.shiprocket.in/v1/external/courier/serviceability/',
                headers=headers,
                params=params,
                timeout=5
            )
            if res.status_code == 200:
                data = res.json()
                couriers = data.get('data', {}).get('available_courier_companies', [])
                if couriers:
                    cheapest = min(couriers, key=lambda c: float(c.get('rate', 9999)))
                    return {
                        'serviceable': True,
                        'rate': float(cheapest.get('rate', 70)),
                        'courier_name': cheapest.get('courier_name', 'Shiprocket Partner'),
                        'etd': cheapest.get('estimated_delivery_days', '3-5') + ' Days'
                    }
        except Exception as e:
            logger.warning("Shiprocket live calculation failed, using store rules: %s", e)
        return None


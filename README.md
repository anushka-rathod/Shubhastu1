# SHUBHASHTU FASHION — Premium Indian Fashion & Accessories Store

> **"Style That Speaks for You."**

A complete, fully functional, production-ready e-commerce web platform engineered for **Shubhashtu Fashion**. Features a luxury blush pink, gold, white, and deep charcoal aesthetic, artisanal Indian jewellery, individually hand-painted wearable art t-shirts, domestic shipping calculations across all Indian PIN codes, Razorpay payment gateway integration, and a comprehensive admin management panel.

---

## 🌟 Key Features & Capabilities

### 1. Design & Branding
* **Luxury Indian Fashion Aesthetic**: Palette of pure white, blush pink (`#fdf2f4`), deep charcoal, and subtle gold accents (`#c59b27`).
* **Typography**: Playfair Display for headings paired with Plus Jakarta Sans for body text.
* **Responsive Design**: Flawlessly optimized across mobile devices, tablets, and desktop displays.
* **Micro-Interactions**: Hover image zoom, slide-over shopping bag drawer, pulse wishlist toggles, and animated toast feedback.

### 2. Product Catalog & Shopping Experience
* **Signature Collections**:
  * **Earrings**: Kundan Meenakari Chandbalis, Temple Jhumkas, Pearl Floral Studs, Afghani Tribal Drops.
  * **Hand-Painted T-Shirts**: Wearable art tees with Peacocks, Mandalas, and Royal Elephants hand-painted on 220 GSM bio-washed organic cotton.
  * **Ethnic & Kurtis**: Pure mulmul Lucknowi Chikankari sets and Chanderi Silk Anarkalis.
  * **Accessories**: Royal Zardosi velvet potli bags and Kundan choker necklaces.
* **Live Predictive Search**: Real-time dropdown search by title, category, and keywords.
* **Filters & Sorting**: Filter by Category, Highlights (`New`, `Bestseller`, `Trending`, `Sale`), Price Range, and Sort by Price (Low/High), Popularity, and Discount %.
* **Product Detail Pages**:
  * Multi-image thumbnail gallery switcher with zoom preview.
  * Size selector (`XS, S, M, L, XL, XXL` or `Free Size`).
  * Size & measurement guide popup modal.
  * Stock status (`In Stock`, `Low Stock Warning`, `Out of Stock`).
  * Instant Add to Bag and 1-Click **Buy Now** buttons.
  * Verified Customer Reviews breakdown and review submission form.

### 3. Delivery Charge Calculation Engine (Crucial Requirement)
* **Indian PIN Code Intelligence**: Validates 6-digit Indian PIN codes, automatically determines City, State, and Logistics Zone (Metro, Tier-1, Tier-2, Remote / Northeast / J&K / Islands).
* **Configurable Rules**:
  * **Free Shipping Threshold**: Free domestic delivery on orders above ₹999 (configurable).
  * **Standard Delivery Fee**: Default ₹70 for orders below threshold.
  * **Express Delivery Option**: Priority 24-hour dispatch (+₹120).
  * **Weight-Based Calculations**: Base 500g + incremental charges.
  * **Remote Zone Surcharge**: Automatic adjustments for remote regions.
* **Shiprocket Logistics Ready**: Connect your Shiprocket API credentials in `.env` or in the Admin Dashboard for automated courier rates and tracking. If unconfigured, the store uses admin-defined rates with zero fake calculations.

### 4. Razorpay Payment Gateway & Cash on Delivery
* **Primary Payment Gateway**: Built with official **Razorpay** REST API integration.
  * Supports UPI (Google Pay, PhonePe, Paytm, BHIM), Debit & Credit Cards, NetBanking, and Wallets.
  * Cryptographic **HMAC-SHA256 signature verification** on the server. Never simulates success!
  * Test mode and Live mode switchable from store settings.
  * Webhook listener (`/api/payment/razorpay/webhook`) for asynchronous payment status capture.
* **Cash on Delivery (COD)**: Available out of the box with optional configurable handling charge and admin toggle.

### 5. Secure Admin Dashboard (`/admin`)
Manage your entire boutique without modifying source code:
* **Overview Analytics**: Total Sales (₹), Total Orders, Pending Orders, Delivered Orders, Customer Count, and Low Stock Warnings.
* **Product Management**: Add, edit, and delete products; upload images or provide image URLs; manage sizes, MRP, selling price, and stock levels.
* **Category Management**: Add, organize, and manage store categories.
* **Order Management**: View and filter orders by status (`Order Placed`, `Confirmed`, `Processing`, `Shipped`, `Out for Delivery`, `Delivered`, `Cancelled`, `Refunded`).
* **Courier Dispatch**: Assign courier partner name, AWB tracking number, and live tracking links.
* **Export Reports**: 1-Click CSV export of all customer orders.
* **Promotional Coupons**: Create percentage or fixed discount coupons with minimum order values, caps, and usage limits.
* **Delivery & Shipping Settings**: Edit standard fees, free shipping limits, and Shiprocket credentials.
* **Payment Settings**: Update Razorpay Key ID and Secret directly from the dashboard.
* **Customer Reviews Moderation**: Approve or delete customer feedback.

### 6. Order Tracking & Tax Invoices
* **Unique Order IDs**: Brand-specific formatted IDs (e.g. `SHB-2026-8942`).
* **Public Order Tracking**: Enter Order Number and Phone/Email to view step-by-step milestone delivery progress.
* **Printable GST Tax Invoices**: Full itemized tax invoice (`INV-SHB-2026-XXXX`) with HSN summary, supplier address, buyer details, and print/PDF support.

---

## 🚀 Quick Start Guide

### Prerequisites
* **Python 3.10+** (Python 3.11 pre-installed)
* All core dependencies (`tornado`, `jinja2`, `requests`) are already present in your Python environment.

### 1. Launch the Application Server
Run the application using Python:
```powershell
python app.py
```

The server will automatically:
1. Initialize the SQLite database (`database.sqlite`).
2. Populate the database with 12+ premium Shubhashtu products, categories, coupons, default shipping settings, and initial admin account.
3. Start the asynchronous Tornado web server on `http://localhost:8000`.

### 2. Store URLs & Portals
| Portal | URL | Credentials |
| :--- | :--- | :--- |
| **Storefront** | [http://localhost:8000](http://localhost:8000) | Public Access / Guest Shopping |
| **Customer Sign In** | [http://localhost:8000/login](http://localhost:8000/login) | Customer registration & login |
| **Track Order** | [http://localhost:8000/track-order](http://localhost:8000/track-order) | Order ID & Phone lookup |
| **Admin Dashboard** | [http://localhost:8000/admin](http://localhost:8000/admin) | **Email:** `admin@shubhashtu.com`<br>**Password:** `ShubhashtuAdmin@2026` |

---

## 💳 Connecting Your Razorpay Payment Gateway

When you launch the store, online payment via Razorpay and Cash on Delivery (COD) are both ready:

1. Log in to your **Razorpay Dashboard**: [https://dashboard.razorpay.com](https://dashboard.razorpay.com)
2. In the left navigation, go to **Settings** &rarr; **API Keys**.
3. Click **Generate Test Key** (or Live Key when ready to launch).
4. Copy your **Key ID** (`rzp_test_...` or `rzp_live_...`) and **Key Secret**.
5. Connect them in either of two ways:
   * **Via Admin Dashboard**: Visit [http://localhost:8000/admin/payments](http://localhost:8000/admin/payments) and paste the keys.
   * **Via `.env` file**: Edit the `.env` file in the project root:
     ```ini
     RAZORPAY_KEY_ID=rzp_test_yourKeyHere
     RAZORPAY_KEY_SECRET=yourSecretHere
     RAZORPAY_TEST_MODE=True
     ```
6. *(Optional)* For webhook synchronization, add a webhook in Razorpay pointing to:
   ```
   https://yourdomain.com/api/payment/razorpay/webhook
   ```
   with event `payment.captured`.

> **Note**: If Razorpay keys are not yet entered, customers can immediately complete purchases using **Cash on Delivery (COD)**, and the checkout screen displays a helpful configuration prompt.

---

## 📦 Connecting Shiprocket Courier Logistics (Optional)

1. Sign up or log in to **Shiprocket**: [https://app.shiprocket.in](https://app.shiprocket.in)
2. Navigate to [http://localhost:8000/admin/shipping](http://localhost:8000/admin/shipping).
3. Enter your **Shiprocket Email**, **Password**, and **Store Pickup PIN Code**.
4. When configured, live courier rates from BlueDart, Delhivery, DTDC, and Shadowfax will be queried automatically. If left unconfigured, the store uses your admin-defined domestic rates.

---

## 🎟️ Promotional Coupons Included

| Coupon Code | Discount | Terms |
| :--- | :--- | :--- |
| `WELCOME10` | **10% OFF** | Min. Order ₹499 |
| `SHUBH500` | **Flat ₹500 OFF** | Min. Order ₹2,499 |
| `FESTIVE20` | **20% OFF** | Min. Order ₹1,999 (Max discount ₹1,000) |
| `FREESHIP` | **Free Delivery** | Valid on any order value |

---

## 📂 Project Structure

```
Shubhastu/
├── app.py                      # Core Tornado web server & REST routing
├── config.py                   # Environment configuration loader
├── db.py                       # SQLite database initialization & WAL mode
├── dal.py                      # Data access layer for products, orders, cart
├── seed.py                     # Initial seed catalogue, products, and admin
├── tests.py                    # Automated test suite (8 tests)
├── Logo.jpg                    # Original brand logo (150x150)
├── .env.example                # Environment variables template
├── .env                        # Local configuration
├── services/
│   ├── auth_service.py         # PBKDF2 password hashing & session management
│   ├── shipping_service.py     # Indian PIN code delivery engine & Shiprocket
│   ├── payment_service.py      # Razorpay REST API & HMAC-SHA256 signature verification
│   ├── invoice_service.py      # Tax invoice generation & INR formatting
│   └── email_service.py        # Order confirmation email notification service
├── static/
│   ├── css/custom.css          # Luxury gold/blush styling, scrollbars, print styles
│   ├── js/main.js              # Cart drawer, wishlist, predictive search, toast alerts
│   ├── js/checkout.js          # Checkout flow, live PIN lookup, Razorpay & COD
│   ├── js/admin.js             # Admin status updates, CSV export, moderation
│   └── images/
│       ├── logo.jpg            # Brand logo image
│       └── products/           # Uploaded and curated product images
└── templates/
    ├── base.html               # Storefront master layout & header/drawer/footer
    ├── index.html              # Homepage with hero showcase, story, testimonials
    ├── shop.html               # Catalog with category/price/sort filters
    ├── product_detail.html     # Product detail, image gallery, PIN checker, reviews
    ├── cart.html               # Dedicated shopping bag with coupon calculator
    ├── checkout.html           # Streamlined 2-column checkout with Razorpay SDK
    ├── order_success.html      # Celebratory order confirmation screen
    ├── order_track.html        # Public order timeline tracker
    ├── invoice.html            # Print-ready GST tax invoice
    ├── wishlist.html           # Saved items portal
    ├── login.html              # Customer login & registration
    ├── forgot_password.html    # Password reset workflow
    ├── profile.html            # Customer dashboard with saved addresses
    ├── about.html              # Brand heritage & artisanal mission
    ├── contact.html            # Working contact inquiry form & studio info
    ├── policies.html           # Shipping, Return/Refund, Privacy & Terms
    └── admin/
        ├── base_admin.html     # Admin layout with sidebar navigation
        ├── dashboard.html      # KPI overview, recent orders, metrics
        ├── products.html       # Product management table
        ├── product_form.html   # Add / Edit product with file uploads & variants
        ├── categories.html     # Category manager
        ├── orders.html         # Order management with status filters
        ├── order_detail.html   # Full order inspection, courier assign & notes
        ├── customers.html      # Customer database
        ├── coupons.html        # Coupon creator & toggle
        ├── shipping.html       # Delivery rules & Shiprocket settings
        ├── payments.html       # Razorpay credentials & COD toggle
        ├── reviews.html        # Product review moderation
        └── settings.html       # Store branding & announcements
```

---

## 🧪 Running the Automated Test Suite

To run the verification test suite:
```powershell
python tests.py
```
This tests:
* Categories and products integrity
* PIN code delivery calculation engine across Metros, Tier-2, and Remote zones
* Coupon validation and minimum order enforcement
* Cart additions, quantity updates, and line calculations
* Cryptographic PBKDF2 password security
* Razorpay HMAC-SHA256 signature verification
* Atomic order placement, stock decrement, and order tracking
* Indian Rupee (`₹`) number formatting

---

## 🔒 Security & Best Practices
* **Zero Dummy Payments**: Online payments use genuine Razorpay order generation and server-side HMAC-SHA256 verification.
* **Password Hashing**: PBKDF2-HMAC-SHA256 with 100,000 iterations and unique cryptographic salts.
* **Session Security**: Signed session tokens and HTTP-only cookies.
* **Database Transactions**: SQLite in WAL (Write-Ahead Logging) mode with foreign keys enabled.
* **GST Tax Invoices**: Standard compliance with itemized rates, HSN information, and customer tax invoices.


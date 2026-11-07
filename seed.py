"""
Seed database with realistic initial data for Shubhashtu Fashion.
Includes categories, products (Earrings, Hand-Painted T-Shirts, Ethnic Wear, Accessories),
store settings, coupons, reviews, admin account, and sample orders.
Supports idempotent upserts so re-running will always enrich existing database.
"""
from db import init_db, get_db
from config import Config
from services.auth_service import hash_password

def seed_database(force: bool = False):
    init_db()

    with get_db() as conn:
        print("Enriching database with Shubhashtu Fashion aesthetic catalogue...")

        # 1. Admin User
        admin_exists = conn.execute("SELECT id FROM users WHERE email = ?", (Config.ADMIN_EMAIL,)).fetchone()
        if not admin_exists:
            admin_hash, admin_salt = hash_password(Config.ADMIN_PASSWORD)
            conn.execute("""
                INSERT INTO users (email, password_hash, salt, full_name, phone, role)
                VALUES (?, ?, ?, ?, ?, 'admin')
            """, (Config.ADMIN_EMAIL, admin_hash, admin_salt, "Shubhashtu Store Owner", Config.SUPPORT_PHONE))

        # Sample customer
        cust_exists = conn.execute("SELECT id FROM users WHERE email = 'ananya.sharma@example.com'").fetchone()
        if not cust_exists:
            cust_hash, cust_salt = hash_password("Customer@123")
            conn.execute("""
                INSERT INTO users (email, password_hash, salt, full_name, phone, role)
                VALUES (?, ?, ?, ?, ?, 'customer')
            """, ("ananya.sharma@example.com", cust_hash, cust_salt, "Ananya Sharma", "+91 98200 12345"))
            cust_id = conn.execute("SELECT id FROM users WHERE email = 'ananya.sharma@example.com'").fetchone()[0]
            conn.execute("""
                INSERT INTO user_addresses (user_id, label, full_name, phone, address_line1, address_line2, landmark, city, state, pincode, is_default)
                VALUES (?, 'Home', 'Ananya Sharma', '+91 98200 12345', 'Flat 402, Royal Palms Residency', 'Indiranagar 100 Feet Road', 'Near Metro Station', 'Bengaluru', 'Karnataka', '560038', 1)
            """, (cust_id,))

        # 2. Store Settings
        settings_data = [
            ('store_name', Config.BRAND_NAME, 'Store brand name'),
            ('tagline', Config.BRAND_TAGLINE, 'Store marketing tagline'),
            ('support_phone', Config.SUPPORT_PHONE, 'Customer care phone number'),
            ('support_whatsapp', Config.SUPPORT_WHATSAPP, 'WhatsApp business support number'),
            ('support_email', Config.SUPPORT_EMAIL, 'Customer support email'),
            ('store_address', Config.STORE_ADDRESS, 'Physical boutique studio address'),
            ('standard_shipping_fee', '70', 'Standard domestic shipping fee in INR'),
            ('free_shipping_threshold', '999', 'Order amount in INR for automatic free shipping'),
            ('express_shipping_fee', '120', 'Express 1-2 day delivery fee in INR'),
            ('cod_fee', '40', 'Cash on Delivery handling charge in INR'),
            ('cod_enabled', '1', '1 to enable COD, 0 to disable'),
            ('remote_zone_surcharge', '40', 'Additional shipping fee for remote/northeast zones'),
            ('razorpay_key_id', Config.RAZORPAY_KEY_ID, 'Razorpay API Key ID'),
            ('razorpay_key_secret', Config.RAZORPAY_KEY_SECRET, 'Razorpay API Key Secret'),
            ('razorpay_webhook_secret', Config.RAZORPAY_WEBHOOK_SECRET, 'Razorpay Webhook secret for verification'),
            ('razorpay_test_mode', '1' if Config.RAZORPAY_TEST_MODE else '0', '1 for Test Mode, 0 for Live'),
            ('shiprocket_email', Config.SHIPROCKET_EMAIL, 'Shiprocket login email'),
            ('shiprocket_password', Config.SHIPROCKET_PASSWORD, 'Shiprocket login password'),
            ('shiprocket_pickup_pincode', Config.SHIPROCKET_PICKUP_PINCODE, 'Store dispatch pickup pincode'),
            ('announcement_bar', '✨ FREE Shipping Across India on Orders Above ₹999 | Use Code WELCOME10 for 10% OFF ✨', 'Header marquee banner text'),
            ('instagram_handle', '@shubhashtufashion', 'Instagram profile handle'),
        ]
        for key, val, desc in settings_data:
            conn.execute(
                """INSERT INTO settings (key, value, description) VALUES (?, ?, ?)
                   ON CONFLICT(key) DO UPDATE SET value=excluded.value, description=excluded.description""",
                (key, val, desc)
            )

        # 3. Categories (Upsert)
        categories = [
            ("Earrings", "earrings", "Handcrafted jhumkas, statement royal chandbalis, and temple jewelry designed with pure elegance.", "https://images.unsplash.com/photo-1535632066927-ab7c9ab60908?auto=format&fit=crop&w=800&q=80", 1),
            ("Hand-Painted T-Shirts", "hand-painted-t-shirts", "Exclusive wearable art featuring hand-painted traditional Indian motifs, peacocks, and mandalas on 220 GSM combed cotton.", "https://images.unsplash.com/photo-1521572267360-ee0c2909d518?auto=format&fit=crop&w=800&q=80", 2),
            ("Ethnic & Kurtis", "ethnic-and-kurtis", "Bespoke handcrafted ethnic wear, Lucknowi Chikankari kurtas, and regal festive ensembles.", "https://images.unsplash.com/photo-1610030469983-98e550d6193c?auto=format&fit=crop&w=800&q=80", 3),
            ("Accessories", "accessories", "Handmade zari potli bags, royal micro-velvet clutches, and bespoke bridal accents.", "https://images.unsplash.com/photo-1584917865442-de89df76afd3?auto=format&fit=crop&w=800&q=80", 4)
        ]
        cat_ids = {}
        for name, slug, desc, img, sort in categories:
            cat_row = conn.execute("SELECT id FROM categories WHERE slug = ?", (slug,)).fetchone()
            if cat_row:
                cat_id = cat_row['id']
                conn.execute(
                    "UPDATE categories SET name=?, description=?, image_url=?, sort_order=?, is_active=1 WHERE id=?",
                    (name, desc, img, sort, cat_id)
                )
            else:
                cur = conn.execute(
                    "INSERT INTO categories (name, slug, description, image_url, sort_order, is_active) VALUES (?, ?, ?, ?, ?, 1)",
                    (name, slug, desc, img, sort)
                )
                cat_id = cur.lastrowid
            cat_ids[slug] = cat_id

        # 4. Rich Aesthetic Products Collection
        products = [
            # ==========================================
            # === CATEGORY 1: EARRINGS (Hyper-Aesthetic)
            # ==========================================
            {
                "name": "Kundan Meenakari Royal Chandbali Earrings",
                "slug": "kundan-meenakari-royal-chandbali-earrings",
                "sku": "SHB-EAR-001",
                "category_id": cat_ids["earrings"],
                "short_description": "24K Gold-plated brass chandbalis encrusted with hand-cut Kundan stones and blush pink Meenakari enamel work.",
                "description": "Inspired by the royal heritage of Jaipur palaces, these magnificent Kundan Meenakari Chandbalis feature handcrafted crescent motifs adorned with micro-pearl cluster drops and delicate blush pink enamel detailing. Perfectly balanced for festive celebrations, weddings, and grand occasions.",
                "care_instructions": "Keep away from moisture, perfumes, and direct water. Store in the velvet Shubhashtu pouch provided.",
                "mrp": 2199.00,
                "price": 1499.00,
                "stock": 18,
                "weight_grams": 120,
                "badge": "Bestseller",
                "is_featured": 1,
                "sizes": "Free Size",
                "colors": "Blush Pink, Royal Gold",
                "images": [
                    "https://images.unsplash.com/photo-1535632066927-ab7c9ab60908?auto=format&fit=crop&w=800&q=80",
                    "https://images.unsplash.com/photo-1630019852942-f89202989a59?auto=format&fit=crop&w=800&q=80",
                    "https://images.unsplash.com/photo-1599643478518-a784e5dc4c8f?auto=format&fit=crop&w=800&q=80"
                ]
            },
            {
                "name": "Mayura Heritage Temple Dancing Peacock Jhumka",
                "slug": "mayura-heritage-temple-jhumka",
                "sku": "SHB-EAR-002",
                "category_id": cat_ids["earrings"],
                "short_description": "Antique gold finish handcrafted temple jhumka featuring dancing peacock motifs and ruby-pink stones.",
                "description": "Celebrate South Indian temple architecture with our Mayura Heritage Jhumkas. Hand-carved by master artisans with delicate dancing peacock engravings, faceted ruby red cubic zirconia stones, and melodious brass bell droplets.",
                "care_instructions": "Wipe with a soft dry cloth after each use. Store separately in an airtight box.",
                "mrp": 1899.00,
                "price": 1249.00,
                "stock": 14,
                "weight_grams": 95,
                "badge": "Trending",
                "is_featured": 1,
                "sizes": "Free Size",
                "colors": "Antique Gold, Ruby Red",
                "images": [
                    "https://images.unsplash.com/photo-1630019852942-f89202989a59?auto=format&fit=crop&w=800&q=80",
                    "https://images.unsplash.com/photo-1535632066927-ab7c9ab60908?auto=format&fit=crop&w=800&q=80"
                ]
            },
            {
                "name": "Gulabi Freshwater Pearl Blossom Tops",
                "slug": "gulabi-pearl-drop-floral-studs",
                "sku": "SHB-EAR-003",
                "category_id": cat_ids["earrings"],
                "short_description": "Delicate blossom floral tops featuring freshwater pearls and rose quartz accents for effortless daily elegance.",
                "description": "Minimalist yet breathtaking, our Gulabi Pearl Studs evoke the fresh blooms of springtime. Lightweight and comfortable for all-day wear with premium hypoallergenic push-back pins.",
                "care_instructions": "Avoid chemicals, hairspray, and lotion contact directly on pearl surfaces.",
                "mrp": 1299.00,
                "price": 849.00,
                "stock": 25,
                "weight_grams": 60,
                "badge": "New",
                "is_featured": 0,
                "sizes": "Free Size",
                "colors": "Rose Gold, Pearl White",
                "images": [
                    "https://images.unsplash.com/photo-1611591475870-f40889c17e88?auto=format&fit=crop&w=800&q=80",
                    "https://images.unsplash.com/photo-1535632066927-ab7c9ab60908?auto=format&fit=crop&w=800&q=80"
                ]
            },
            {
                "name": "Afghani Tribal Oxidised Silver Chandelier Drops",
                "slug": "afghani-tribal-oxidised-silver-statement-drops",
                "sku": "SHB-EAR-004",
                "category_id": cat_ids["earrings"],
                "short_description": "Boho-chic handcrafted oxidised silver finish earrings with mirror work and ghungroo tassels.",
                "description": "Make a striking impression with these artisanal tribal earrings. Handcrafted from premium silver-tone alloy with intricate geometric filigree, authentic miniature mirrors, and delicate ghungroos that whisper with every movement.",
                "care_instructions": "Store in zip-lock bags to preserve the antique silver luster.",
                "mrp": 1499.00,
                "price": 899.00,
                "stock": 22,
                "weight_grams": 110,
                "badge": "Sale",
                "is_featured": 1,
                "sizes": "Free Size",
                "colors": "Antique Oxidised Silver",
                "images": [
                    "https://images.unsplash.com/photo-1629224316810-9d8805b95e76?auto=format&fit=crop&w=800&q=80",
                    "https://images.unsplash.com/photo-1535632066927-ab7c9ab60908?auto=format&fit=crop&w=800&q=80"
                ]
            },
            {
                "name": "Jadau Polki Emerald Palace Danglers",
                "slug": "jadau-polki-emerald-palace-danglers",
                "sku": "SHB-EAR-005",
                "category_id": cat_ids["earrings"],
                "short_description": "Regal uncut Polki glass stone danglers with deep emerald green droplet beads and 22K gold matte finish.",
                "description": "Crafted to channel Mughal and Rajput royal aesthetics, these palace danglers feature high-clarity uncut polki stones set in traditional gold-leaf casing, finished with rich hydro-emerald drops that catch the light from every angle.",
                "care_instructions": "Store in a separate padded jewelry organizer. Do not submerge in water.",
                "mrp": 2799.00,
                "price": 1899.00,
                "stock": 12,
                "weight_grams": 105,
                "badge": "Exclusive",
                "is_featured": 1,
                "sizes": "Free Size",
                "colors": "Emerald Green, Palace Gold",
                "images": [
                    "https://images.unsplash.com/photo-1602751584552-8ba73aad10e1?auto=format&fit=crop&w=800&q=80",
                    "https://images.unsplash.com/photo-1535632066927-ab7c9ab60908?auto=format&fit=crop&w=800&q=80"
                ]
            },
            {
                "name": "Rajputana Pastel Enamel Lotus Chandbalis",
                "slug": "rajputana-pastel-enamel-lotus-chandbalis",
                "sku": "SHB-EAR-006",
                "category_id": cat_ids["earrings"],
                "short_description": "Delicate mint green and powder pink Meenakari lotus chandbalis with natural shell pearls.",
                "description": "Pastel perfection designed for modern brides and bridesmaid looks. Hand-painted lotus flower motifs rendered in soft pastel mint and blush enamels, encircled with tiny seed pearls that sway gently.",
                "care_instructions": "Protect from direct heat and cosmetics. Clean with microfiber cloth.",
                "mrp": 2399.00,
                "price": 1599.00,
                "stock": 16,
                "weight_grams": 90,
                "badge": "Trending",
                "is_featured": 1,
                "sizes": "Free Size",
                "colors": "Mint Green, Powder Pink",
                "images": [
                    "https://images.unsplash.com/photo-1599643478518-a784e5dc4c8f?auto=format&fit=crop&w=800&q=80",
                    "https://images.unsplash.com/photo-1630019852942-f89202989a59?auto=format&fit=crop&w=800&q=80"
                ]
            },

            # =======================================================
            # === CATEGORY 2: HAND-PAINTED T-SHIRTS (Hyper-Aesthetic)
            # =======================================================
            {
                "name": "Peacock Symphony Hand-Painted Cotton T-Shirt",
                "slug": "peacock-symphony-hand-painted-cotton-tshirt",
                "sku": "SHB-TEE-001",
                "category_id": cat_ids["hand-painted-t-shirts"],
                "short_description": "100% Combed bio-washed organic cotton t-shirt individually hand-painted with royal blue and gold peacock motif.",
                "description": "Each piece is an original work of art! Painted stroke-by-stroke by traditional Indian artists using permanent fabric acrylic colors and gold metallic accents. Cut from ultra-soft, 220 GSM breathable combed cotton for lasting comfort and luxury feel.",
                "care_instructions": "Turn inside out and wash in cold water using mild detergent. Iron on reverse only. Do not bleach.",
                "mrp": 1999.00,
                "price": 1299.00,
                "stock": 30,
                "weight_grams": 250,
                "badge": "Bestseller",
                "is_featured": 1,
                "sizes": "XS, S, M, L, XL, XXL",
                "colors": "Pure White, Blush Ivory",
                "images": [
                    "https://images.unsplash.com/photo-1521572267360-ee0c2909d518?auto=format&fit=crop&w=800&q=80",
                    "https://images.unsplash.com/photo-1503342217505-b0a15ec3261c?auto=format&fit=crop&w=800&q=80",
                    "https://images.unsplash.com/photo-1583743814966-8936f5b7be1a?auto=format&fit=crop&w=800&q=80"
                ]
            },
            {
                "name": "Sacred Mandala Hand-Painted Oversized Streetwear Tee",
                "slug": "sacred-mandala-hand-painted-oversized-tee",
                "sku": "SHB-TEE-002",
                "category_id": cat_ids["hand-painted-t-shirts"],
                "short_description": "Relaxed aesthetic streetwear tee featuring an intricate cosmic mandala painted by hand in gold & blush pigments.",
                "description": "Merge modern street couture with ancient spiritual geometry. This unisex oversized t-shirt features a centerpiece mandala hand-painted over 6 hours of meticulous brushwork. Dropped shoulder silhouette with pre-shrunk premium cotton knit.",
                "care_instructions": "Machine wash gentle cycle cold. Iron reverse side only on medium heat.",
                "mrp": 2199.00,
                "price": 1399.00,
                "stock": 20,
                "weight_grams": 280,
                "badge": "Trending",
                "is_featured": 1,
                "sizes": "S, M, L, XL, XXL",
                "colors": "Midnight Black, Stone Charcoal",
                "images": [
                    "https://images.unsplash.com/photo-1503342217505-b0a15ec3261c?auto=format&fit=crop&w=800&q=80",
                    "https://images.unsplash.com/photo-1521572267360-ee0c2909d518?auto=format&fit=crop&w=800&q=80"
                ]
            },
            {
                "name": "Gaja Heritage Hand-Painted Royal Elephant Tee",
                "slug": "gaja-heritage-hand-painted-royal-elephant-tee",
                "sku": "SHB-TEE-003",
                "category_id": cat_ids["hand-painted-t-shirts"],
                "short_description": "Iconic royal Rajasthani ceremonial elephant hand-painted with gold leaf embellishments on premium organic fabric.",
                "description": "Symbolizing wisdom, royalty, and prosperity, our Gaja Heritage tee brings centuries of royal procession art into modern casual wear. Rich metallic gold inks paired with deep maroon and emerald hand-drawn detailing.",
                "care_instructions": "Gentle hand wash recommended. Do not wring or scrub over painted motif.",
                "mrp": 2099.00,
                "price": 1349.00,
                "stock": 16,
                "weight_grams": 260,
                "badge": "New",
                "is_featured": 0,
                "sizes": "XS, S, M, L, XL",
                "colors": "Blush Sand, Soft Beige",
                "images": [
                    "https://images.unsplash.com/photo-1583743814966-8936f5b7be1a?auto=format&fit=crop&w=800&q=80",
                    "https://images.unsplash.com/photo-1521572267360-ee0c2909d518?auto=format&fit=crop&w=800&q=80"
                ]
            },
            {
                "name": "Kamala Blossom Hand-Painted Floral Tee",
                "slug": "kamala-blossom-hand-painted-floral-tee",
                "sku": "SHB-TEE-004",
                "category_id": cat_ids["hand-painted-t-shirts"],
                "short_description": "Watercolour-inspired Indian pink lotus illustration hand-painted on soft cotton jersey.",
                "description": "Subtle, poetic, and effortlessly chic. The blooming lotus flower represents purity and renewal. Hand-painted with gentle watercolor gradients of blush pink, soft rose, and gilded gold stamen highlights.",
                "care_instructions": "Cold wash inside out. Iron on reverse side.",
                "mrp": 1799.00,
                "price": 1199.00,
                "stock": 25,
                "weight_grams": 240,
                "badge": "Sale",
                "is_featured": 1,
                "sizes": "XS, S, M, L, XL, XXL",
                "colors": "Snow White, Powder Rose",
                "images": [
                    "https://images.unsplash.com/photo-1576566588028-4147f3842f27?auto=format&fit=crop&w=800&q=80",
                    "https://images.unsplash.com/photo-1521572267360-ee0c2909d518?auto=format&fit=crop&w=800&q=80"
                ]
            },
            {
                "name": "Surya Devata Celestial Sun God Artisan Tee",
                "slug": "surya-devata-celestial-sun-god-artisan-tee",
                "sku": "SHB-TEE-005",
                "category_id": cat_ids["hand-painted-t-shirts"],
                "short_description": "Vibrant Vedic solar halo hand-drawn with radiant metallic bronze and natural ochre pigments.",
                "description": "Evoking inner radiance and cosmic energy, the Surya Devata tee features intricate ray patterns radiating from a divine sun face. Hand-painted on premium 220 GSM bio-washed cotton that stays soft wear after wear.",
                "care_instructions": "Hand wash or gentle cycle cold. Keep away from harsh bleaching agents.",
                "mrp": 1999.00,
                "price": 1299.00,
                "stock": 18,
                "weight_grams": 250,
                "badge": "Exclusive",
                "is_featured": 1,
                "sizes": "S, M, L, XL, XXL",
                "colors": "Vintage Ochre, Natural Ivory",
                "images": [
                    "https://images.unsplash.com/photo-1562157873-818bc0726f68?auto=format&fit=crop&w=800&q=80",
                    "https://images.unsplash.com/photo-1503342217505-b0a15ec3261c?auto=format&fit=crop&w=800&q=80"
                ]
            },
            {
                "name": "Kalamkari Tree of Life Wearable Art Tee",
                "slug": "kalamkari-tree-of-life-wearable-art-tee",
                "sku": "SHB-TEE-006",
                "category_id": cat_ids["hand-painted-t-shirts"],
                "short_description": "Intricate Andhra Kalamkari folk motif featuring flora and fauna painted stroke-by-stroke with mineral dyes.",
                "description": "A tribute to ancient temple art, this Tree of Life tee portrays lush branches populated with songbirds and floral tendrils. Hand-painted with deep indigo, rust terracotta, and gold highlights.",
                "care_instructions": "Wash inside out with cold water. Iron on low on reverse.",
                "mrp": 2199.00,
                "price": 1399.00,
                "stock": 20,
                "weight_grams": 260,
                "badge": "New",
                "is_featured": 1,
                "sizes": "XS, S, M, L, XL",
                "colors": "Forest Olive, Warm Cream",
                "images": [
                    "https://images.unsplash.com/photo-1618354691373-d851c5c3a990?auto=format&fit=crop&w=800&q=80",
                    "https://images.unsplash.com/photo-1583743814966-8936f5b7be1a?auto=format&fit=crop&w=800&q=80"
                ]
            },

            # ==========================================
            # === CATEGORY 3: ETHNIC & KURTIS
            # ==========================================
            {
                "name": "Gulabi Chikankari Hand-Embroidered Kurta Set",
                "slug": "gulabi-chikankari-hand-embroidered-kurta-set",
                "sku": "SHB-ETH-001",
                "category_id": cat_ids["ethnic-and-kurtis"],
                "short_description": "Pure mulmul cotton Lucknowi Chikankari kurta set with matching palazzo and Kota Doria dupatta.",
                "description": "Hand-stitched in Lucknow using traditional Bakhiya, Phanda, and Ghaspatti stitches on lightweight mulmul cotton. Features delicate floral motifs across the yoke, soft lining included, paired with comfortable slip-on bottoms.",
                "care_instructions": "Hand wash gently in cold water with mild liquid detergent. Dry in shade.",
                "mrp": 3999.00,
                "price": 2799.00,
                "stock": 12,
                "weight_grams": 550,
                "badge": "Bestseller",
                "is_featured": 1,
                "sizes": "S, M, L, XL, XXL",
                "colors": "Blush Pink",
                "images": [
                    "https://images.unsplash.com/photo-1610030469983-98e550d6193c?auto=format&fit=crop&w=800&q=80",
                    "https://images.unsplash.com/photo-1583391733956-3750e0ff4e8b?auto=format&fit=crop&w=800&q=80"
                ]
            },
            {
                "name": "Chanderi Silk Gold Zari Anarkali Gown",
                "slug": "chanderi-silk-gold-zari-anarkali-gown",
                "sku": "SHB-ETH-002",
                "category_id": cat_ids["ethnic-and-kurtis"],
                "short_description": "Floor-length royal flared Anarkali in pure Chanderi silk with woven gold zari border and embellished neckline.",
                "description": "Fit for royalty. Handwoven Chanderi silk with a grand 4.5-meter flare that twirls effortlessly. Detailed with metallic gold Banarasi zari borders and crystal-handcrafted buttons along the front placket.",
                "care_instructions": "Dry clean only. Store wrapped in pure cotton or muslin fabric.",
                "mrp": 5499.00,
                "price": 3899.00,
                "stock": 8,
                "weight_grams": 650,
                "badge": "Trending",
                "is_featured": 1,
                "sizes": "S, M, L, XL",
                "colors": "Ivory Gold, Royal Cream",
                "images": [
                    "https://images.unsplash.com/photo-1583391733956-3750e0ff4e8b?auto=format&fit=crop&w=800&q=80",
                    "https://images.unsplash.com/photo-1610030469983-98e550d6193c?auto=format&fit=crop&w=800&q=80"
                ]
            },

            # ==========================================
            # === CATEGORY 4: ACCESSORIES
            # ==========================================
            {
                "name": "Royal Zardosi Handcrafted Velvet Potli Bag",
                "slug": "royal-zardosi-handcrafted-velvet-potli-bag",
                "sku": "SHB-ACC-001",
                "category_id": cat_ids["accessories"],
                "short_description": "Blush pink micro-velvet potli adorned with intricate golden dabka, pearls, and crystal tassel tie-strings.",
                "description": "Complete your festive look with this royal heirloom potli bag. Master artisans spend over 14 hours embroidering genuine metallic gold dabka threads and lustrous pearls on rich plush velvet. Features a roomy satin-lined interior for your smartphone, lipsticks, and essentials.",
                "care_instructions": "Store in the Shubhashtu satin dust pouch. Wipe with dry clean cloth.",
                "mrp": 2499.00,
                "price": 1699.00,
                "stock": 20,
                "weight_grams": 220,
                "badge": "Bestseller",
                "is_featured": 1,
                "sizes": "Free Size",
                "colors": "Blush Velvet, Antique Gold",
                "images": [
                    "https://images.unsplash.com/photo-1584917865442-de89df76afd3?auto=format&fit=crop&w=800&q=80",
                    "https://images.unsplash.com/photo-1590874103328-eac38a683ce7?auto=format&fit=crop&w=800&q=80"
                ]
            },
            {
                "name": "Kundan Pearl Floral Choker Set with Maangtikka",
                "slug": "kundan-pearl-floral-choker-set-with-maangtikka",
                "sku": "SHB-ACC-002",
                "category_id": cat_ids["accessories"],
                "short_description": "Hand-strung multi-layer pearl necklace with Jadau Kundan centerpiece, matching earrings, and maangtikka.",
                "description": "A bridal masterpiece designed for celebratory grandeur. Features high-grade imitation polki kundans nestled in gold-plated brass settings, surrounded by delicate pearl garlands and adjustable silk dori.",
                "care_instructions": "Keep away from perfumes and liquids. Store flat in velvet lined box.",
                "mrp": 3499.00,
                "price": 2299.00,
                "stock": 10,
                "weight_grams": 180,
                "badge": "New",
                "is_featured": 1,
                "sizes": "Free Size",
                "colors": "Gold & Pearl",
                "images": [
                    "https://images.unsplash.com/photo-1599643478518-a784e5dc4c8f?auto=format&fit=crop&w=800&q=80",
                    "https://images.unsplash.com/photo-1535632066927-ab7c9ab60908?auto=format&fit=crop&w=800&q=80"
                ]
            }
        ]

        for p in products:
            existing = conn.execute("SELECT id FROM products WHERE slug = ? OR sku = ?", (p["slug"], p["sku"])).fetchone()
            if existing:
                prod_id = existing['id']
                conn.execute("""
                    UPDATE products SET
                        name=?, sku=?, category_id=?, short_description=?, description=?,
                        care_instructions=?, mrp=?, price=?, stock=?, weight_grams=?,
                        badge=?, is_featured=?, is_active=1, sizes=?, colors=?
                    WHERE id=?
                """, (
                    p["name"], p["sku"], p["category_id"],
                    p["short_description"], p["description"], p["care_instructions"],
                    p["mrp"], p["price"], p["stock"], p["weight_grams"],
                    p["badge"], p["is_featured"], p["sizes"], p["colors"],
                    prod_id
                ))
                # Refresh images
                conn.execute("DELETE FROM product_images WHERE product_id = ?", (prod_id,))
            else:
                cur = conn.execute("""
                    INSERT INTO products (
                        name, slug, sku, category_id, short_description, description,
                        care_instructions, mrp, price, stock, weight_grams, badge,
                        is_featured, is_active, sizes, colors
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
                """, (
                    p["name"], p["slug"], p["sku"], p["category_id"],
                    p["short_description"], p["description"], p["care_instructions"],
                    p["mrp"], p["price"], p["stock"], p["weight_grams"],
                    p["badge"], p["is_featured"], p["sizes"], p["colors"]
                ))
                prod_id = cur.lastrowid

            for i, img in enumerate(p["images"]):
                conn.execute("""
                    INSERT INTO product_images (product_id, image_url, is_primary, sort_order)
                    VALUES (?, ?, ?, ?)
                """, (prod_id, img, 1 if i == 0 else 0, i))

        # 5. Coupons
        coupons = [
            ("WELCOME10", "Get 10% discount on your first order!", "percentage", 10.0, 499.0, 500.0, 1000, 1),
            ("SHUBH500", "Flat ₹500 discount on orders above ₹2,499", "fixed", 500.0, 2499.0, None, 500, 1),
            ("FREESHIP", "Free standard shipping on any order value", "fixed", 70.0, 0.0, None, 2000, 1),
            ("FESTIVE20", "20% festive discount on orders above ₹1,999", "percentage", 20.0, 1999.0, 1000.0, 500, 1),
        ]
        for code, desc, dtype, dval, min_val, max_d, limit, act in coupons:
            conn.execute("""
                INSERT INTO coupons (code, description, discount_type, discount_value, min_order_value, max_discount, usage_limit, is_active)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(code) DO UPDATE SET description=excluded.description, discount_value=excluded.discount_value
            """, (code, desc, dtype, dval, min_val, max_d, limit, act))

        # 6. Customer Reviews
        reviews = [
            ("kundan-meenakari-royal-chandbali-earrings", "Radhika Iyer", "radhika@example.com", 5, "Exquisite craftsmanship!", "These chandbalis are even more gorgeous in person than on the website. The blush pink enamel work is so delicate and royal. Received countless compliments at my cousin's sangeet!"),
            ("kundan-meenakari-royal-chandbali-earrings", "Meera Kulkarni", "meera@example.com", 5, "Fabulous quality", "Lightweight despite the grand look. Prompt delivery to Mumbai in 3 days. Beautiful packaging!"),
            ("mayura-heritage-temple-jhumka", "Ananya Sharma", "ananya@example.com", 5, "Authentic Temple Art", "The dancing peacock engraving is so fine. Loved the bell droplets!"),
            ("peacock-symphony-hand-painted-cotton-tshirt", "Pooja Verma", "pooja@example.com", 5, "Truly wearable art!", "The Peacock tee is pure art! The brushstrokes are so vivid and the cotton fabric is so soft and breathable. Washed it twice and colors remained just as vibrant."),
            ("peacock-symphony-hand-painted-cotton-tshirt", "Simran Bhasin", "simran@example.com", 5, "Loved the fit & packaging", "I ordered size M and it fits like a dream. Thank you Shubhashtu Fashion for this masterpiece!"),
            ("sacred-mandala-hand-painted-oversized-tee", "Karan Singh", "karan@example.com", 5, "Streetwear perfection", "The gold mandala on charcoal black looks sick! Super soft cotton and great oversized silhouette."),
            ("gulabi-chikankari-hand-embroidered-kurta-set", "Kavya Menon", "kavya@example.com", 5, "Pure Chikankari luxury", "The embroidery is authentic Lucknowi handwork. Fabric is so pure and comfortable. Best ethnic purchase online!"),
            ("royal-zardosi-handcrafted-velvet-potli-bag", "Sneha Patel", "sneha@example.com", 5, "Heirloom grade potli!", "The velvet feels so plush and royal. Fits my phone and essentials perfectly. Must-have for the wedding season!")
        ]
        review_count = conn.execute("SELECT COUNT(*) FROM reviews").fetchone()[0]
        if review_count == 0:
            for pslug, name, email, rating, title, comment in reviews:
                prow = conn.execute("SELECT id FROM products WHERE slug = ?", (pslug,)).fetchone()
                if prow:
                    conn.execute("""
                        INSERT INTO reviews (product_id, customer_name, customer_email, rating, title, comment, is_verified_buyer, is_approved)
                        VALUES (?, ?, ?, ?, ?, ?, 1, 1)
                    """, (prow['id'], name, email, rating, title, comment))

        print("Aesthetic database enrichment completed successfully!")

if __name__ == '__main__':
    seed_database()

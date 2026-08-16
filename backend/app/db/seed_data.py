"""Static demo dataset: catalogue, stores and the support knowledge base.

The knowledge-base articles are the ground truth the agent cites, so they are
written the way a real retailer's help centre is - concrete numbers, named
exceptions, and the edge cases customers actually ask about.
"""

from __future__ import annotations

CATEGORIES: list[dict] = [
    {"name": "Electronics", "slug": "electronics", "icon": "cpu",
     "description": "Phones, audio, laptops, wearables and accessories."},
    {"name": "Fashion", "slug": "fashion", "icon": "shirt",
     "description": "Clothing, footwear and accessories for men and women."},
    {"name": "Home & Kitchen", "slug": "home-kitchen", "icon": "home",
     "description": "Appliances, cookware, furniture and decor."},
    {"name": "Beauty & Personal Care", "slug": "beauty", "icon": "sparkles",
     "description": "Skincare, haircare, fragrances and grooming."},
    {"name": "Grocery", "slug": "grocery", "icon": "shopping-basket",
     "description": "Staples, snacks, beverages and household essentials."},
    {"name": "Sports & Fitness", "slug": "sports", "icon": "dumbbell",
     "description": "Equipment, activewear and outdoor gear."},
]

# (sku, name, brand, category_slug, price, mrp, stock, rating, reviews,
#  return_days, returnable, tags, attributes, description)
PRODUCTS: list[dict] = [
    # ---------------------------------------------------------- electronics --
    {"sku": "ELC-HDP-001", "name": "AuraSound Pro ANC Wireless Headphones",
     "brand": "AuraSound", "category": "electronics", "price": 8999, "mrp": 12999,
     "stock": 42, "rating": 4.5, "reviews": 2841, "return_days": 10,
     "tags": ["headphones", "wireless", "anc", "bluetooth", "audio"],
     "attributes": {"colour": "Midnight Black", "battery_hours": 40,
                    "warranty_months": 12, "connectivity": "Bluetooth 5.3"},
     "description": "Over-ear wireless headphones with hybrid active noise cancellation, "
                    "40-hour battery life and multipoint pairing. Includes carry case."},
    {"sku": "ELC-EBD-002", "name": "AuraSound Buds Air 3",
     "brand": "AuraSound", "category": "electronics", "price": 2499, "mrp": 3999,
     "stock": 0, "rating": 4.2, "reviews": 1520, "return_days": 10,
     "tags": ["earbuds", "tws", "wireless", "audio"],
     "attributes": {"colour": "Pearl White", "battery_hours": 28, "warranty_months": 12,
                    "water_resistance": "IPX5"},
     "description": "True wireless earbuds with 28-hour total playback, IPX5 sweat "
                    "resistance and low-latency gaming mode."},
    {"sku": "ELC-PHN-003", "name": "Nexus 12 Pro 5G (256 GB)",
     "brand": "Nexus", "category": "electronics", "price": 54999, "mrp": 64999,
     "stock": 12, "rating": 4.6, "reviews": 5219, "return_days": 7,
     "tags": ["smartphone", "5g", "mobile", "phone"],
     "attributes": {"colour": "Titanium Grey", "storage_gb": 256, "ram_gb": 12,
                    "warranty_months": 12, "screen_inch": 6.7},
     "description": "Flagship 5G smartphone with a 6.7-inch 120 Hz AMOLED display, "
                    "50 MP triple camera and 5000 mAh battery with 80 W fast charging."},
    {"sku": "ELC-LPT-004", "name": "Vertex Book 14 Ultra (16 GB / 512 GB)",
     "brand": "Vertex", "category": "electronics", "price": 76990, "mrp": 89990,
     "stock": 7, "rating": 4.4, "reviews": 843, "return_days": 7,
     "tags": ["laptop", "notebook", "ultrabook", "computer"],
     "attributes": {"colour": "Space Silver", "ram_gb": 16, "storage_gb": 512,
                    "warranty_months": 24, "screen_inch": 14},
     "description": "1.2 kg aluminium ultrabook with a 14-inch 2.8K OLED screen, "
                    "16 GB LPDDR5 and an 18-hour battery."},
    {"sku": "ELC-WCH-005", "name": "PulseFit Watch S2",
     "brand": "PulseFit", "category": "electronics", "price": 4499, "mrp": 6999,
     "stock": 88, "rating": 4.1, "reviews": 3102, "return_days": 10,
     "tags": ["smartwatch", "wearable", "fitness", "watch"],
     "attributes": {"colour": "Obsidian", "battery_days": 10, "warranty_months": 12,
                    "water_resistance": "5ATM"},
     "description": "AMOLED smartwatch with SpO2, continuous heart rate, 120 sport "
                    "modes and 10-day battery."},
    {"sku": "ELC-PWB-006", "name": "VoltCore 20000 mAh Power Bank",
     "brand": "VoltCore", "category": "electronics", "price": 1799, "mrp": 2499,
     "stock": 156, "rating": 4.3, "reviews": 4410, "return_days": 10,
     "tags": ["power bank", "charger", "accessory"],
     "attributes": {"colour": "Graphite", "capacity_mah": 20000, "warranty_months": 6,
                    "output_w": 45},
     "description": "45 W USB-C PD power bank that charges a laptop, with pass-through "
                    "charging and a digital display."},

    # -------------------------------------------------------------- fashion --
    {"sku": "FSH-SHO-101", "name": "Stride Runner Neo Running Shoes",
     "brand": "Stride", "category": "fashion", "price": 3299, "mrp": 4999,
     "stock": 64, "rating": 4.3, "reviews": 1870, "return_days": 14,
     "tags": ["shoes", "running", "sneakers", "footwear"],
     "attributes": {"colour": "Cobalt Blue", "sizes": "6-12 UK", "material": "Knit mesh"},
     "description": "Lightweight running shoes with a responsive EVA midsole and "
                    "breathable knit upper. True to size."},
    {"sku": "FSH-JKT-102", "name": "Northwind Puffer Jacket",
     "brand": "Northwind", "category": "fashion", "price": 4599, "mrp": 7999,
     "stock": 23, "rating": 4.4, "reviews": 612, "return_days": 14,
     "tags": ["jacket", "winter", "outerwear", "puffer"],
     "attributes": {"colour": "Olive", "sizes": "S-XXL", "material": "Recycled polyester"},
     "description": "Water-repellent puffer jacket rated to -5 °C, with a packable "
                    "hood and zip pockets."},
    {"sku": "FSH-TSH-103", "name": "Everyday Cotton Crew Tee (Pack of 3)",
     "brand": "BasicsCo", "category": "fashion", "price": 999, "mrp": 1799,
     "stock": 210, "rating": 4.0, "reviews": 5240, "return_days": 14,
     "tags": ["t-shirt", "tee", "cotton", "basics"],
     "attributes": {"colour": "Assorted", "sizes": "S-XXL", "material": "100% combed cotton"},
     "description": "Pre-shrunk 180 GSM combed cotton crew-neck tees in a three-pack."},
    {"sku": "FSH-BAG-104", "name": "Trekker 35L Laptop Backpack",
     "brand": "Trekker", "category": "fashion", "price": 2199, "mrp": 3499,
     "stock": 47, "rating": 4.5, "reviews": 2033, "return_days": 14,
     "tags": ["backpack", "bag", "laptop", "travel"],
     "attributes": {"colour": "Charcoal", "capacity_l": 35, "warranty_months": 24},
     "description": "Water-resistant 35 L backpack with a padded 16-inch laptop sleeve "
                    "and a luggage pass-through strap."},

    # ------------------------------------------------------- home & kitchen --
    {"sku": "HOM-MIX-201", "name": "ChefMate 750 W Mixer Grinder",
     "brand": "ChefMate", "category": "home-kitchen", "price": 3499, "mrp": 5499,
     "stock": 31, "rating": 4.2, "reviews": 3891, "return_days": 7,
     "tags": ["mixer", "grinder", "kitchen", "appliance"],
     "attributes": {"colour": "White", "power_w": 750, "warranty_months": 24, "jars": 3},
     "description": "750 W mixer grinder with three stainless-steel jars and overload "
                    "protection. Two-year motor warranty."},
    {"sku": "HOM-AIR-202", "name": "PureBreeze HEPA Air Purifier",
     "brand": "PureBreeze", "category": "home-kitchen", "price": 12999, "mrp": 17999,
     "stock": 9, "rating": 4.6, "reviews": 742, "return_days": 7,
     "tags": ["air purifier", "hepa", "appliance", "home"],
     "attributes": {"colour": "White", "coverage_sqft": 450, "warranty_months": 12,
                    "filter": "H13 True HEPA"},
     "description": "H13 True HEPA purifier covering 450 sq ft with a real-time PM2.5 "
                    "display and 24 dB sleep mode."},
    {"sku": "HOM-COK-203", "name": "IronCast Non-stick Cookware Set (5 pc)",
     "brand": "IronCast", "category": "home-kitchen", "price": 2799, "mrp": 4499,
     "stock": 58, "rating": 4.1, "reviews": 1204, "return_days": 7,
     "tags": ["cookware", "pan", "kitchen", "non-stick"],
     "attributes": {"colour": "Black", "pieces": 5, "warranty_months": 12,
                    "induction_safe": True},
     "description": "Five-piece induction-friendly non-stick set with a granite-effect "
                    "coating, PFOA free."},
    {"sku": "HOM-VAC-204", "name": "SwiftClean Cordless Vacuum V8",
     "brand": "SwiftClean", "category": "home-kitchen", "price": 15999, "mrp": 21999,
     "stock": 4, "rating": 4.4, "reviews": 488, "return_days": 7,
     "tags": ["vacuum", "cordless", "cleaning", "appliance"],
     "attributes": {"colour": "Nickel", "runtime_min": 45, "warranty_months": 24},
     "description": "Cordless stick vacuum with 45-minute runtime, HEPA filtration and "
                    "a self-standing dock."},

    # --------------------------------------------------------------- beauty --
    {"sku": "BTY-SRM-301", "name": "GlowLab Vitamin C Serum 30 ml",
     "brand": "GlowLab", "category": "beauty", "price": 899, "mrp": 1499,
     "stock": 133, "rating": 4.3, "reviews": 6721, "return_days": 0,
     "returnable": False,
     "tags": ["serum", "skincare", "vitamin c", "beauty"],
     "attributes": {"volume_ml": 30, "skin_type": "All", "shelf_life_months": 24},
     "description": "10% L-ascorbic acid serum with ferulic acid for brightness and "
                    "even tone. Dermatologically tested."},
    {"sku": "BTY-SHM-302", "name": "HerbRoot Anti-Hairfall Shampoo 400 ml",
     "brand": "HerbRoot", "category": "beauty", "price": 549, "mrp": 799,
     "stock": 96, "rating": 4.0, "reviews": 2210, "return_days": 0,
     "returnable": False,
     "tags": ["shampoo", "haircare", "beauty"],
     "attributes": {"volume_ml": 400, "sulphate_free": True},
     "description": "Sulphate-free shampoo with bhringraj and biotin for thinning hair."},

    # -------------------------------------------------------------- grocery --
    {"sku": "GRC-COF-401", "name": "Highland Roast Arabica Coffee 500 g",
     "brand": "Highland", "category": "grocery", "price": 649, "mrp": 899,
     "stock": 74, "rating": 4.5, "reviews": 1888, "return_days": 0,
     "returnable": False,
     "tags": ["coffee", "beverage", "grocery", "arabica"],
     "attributes": {"weight_g": 500, "roast": "Medium-dark", "origin": "Chikmagalur"},
     "description": "Single-origin medium-dark roast Arabica beans, roasted weekly."},
    {"sku": "GRC-OIL-402", "name": "PureHarvest Cold-Pressed Groundnut Oil 5 L",
     "brand": "PureHarvest", "category": "grocery", "price": 1249, "mrp": 1599,
     "stock": 41, "rating": 4.2, "reviews": 967, "return_days": 0,
     "returnable": False,
     "tags": ["oil", "cooking", "grocery"],
     "attributes": {"volume_l": 5, "process": "Cold pressed"},
     "description": "Wood-pressed groundnut oil in a food-grade jar, no refining."},

    # --------------------------------------------------------------- sports --
    {"sku": "SPT-YOG-501", "name": "ZenFlex TPE Yoga Mat 6 mm",
     "brand": "ZenFlex", "category": "sports", "price": 1299, "mrp": 1999,
     "stock": 112, "rating": 4.4, "reviews": 2544, "return_days": 10,
     "tags": ["yoga", "mat", "fitness", "sports"],
     "attributes": {"colour": "Teal", "thickness_mm": 6, "material": "TPE"},
     "description": "Non-slip 6 mm TPE mat with alignment lines and a carry strap."},
    {"sku": "SPT-DMB-502", "name": "IronGrip Adjustable Dumbbell 24 kg (Pair)",
     "brand": "IronGrip", "category": "sports", "price": 8499, "mrp": 12999,
     "stock": 6, "rating": 4.5, "reviews": 421, "return_days": 10,
     "tags": ["dumbbell", "weights", "gym", "fitness"],
     "attributes": {"weight_kg": 24, "adjustable": True, "warranty_months": 12},
     "description": "Pair of quick-adjust dumbbells covering 5-24 kg per hand in 2 kg "
                    "increments."},
    {"sku": "SPT-CYC-503", "name": "TrailBlazer 21-Speed Mountain Bike",
     "brand": "TrailBlazer", "category": "sports", "price": 18999, "mrp": 24999,
     "stock": 3, "rating": 4.3, "reviews": 189, "return_days": 7,
     "tags": ["bicycle", "cycle", "mountain bike", "sports"],
     "attributes": {"colour": "Matte Red", "frame_size_in": 18, "gears": 21,
                    "warranty_months": 12},
     "description": "Hardtail mountain bike with a 21-speed drivetrain, dual disc "
                    "brakes and a 6061 aluminium frame."},
]

STORES: list[dict] = [
    {"name": "NovaMart Koramangala", "address": "80 Feet Road, 6th Block, Koramangala",
     "city": "Bengaluru", "pincode": "560095", "phone": "+91 80 4123 5567",
     "opening_hours": "10:00 - 21:30", "latitude": 12.9345, "longitude": 77.6266},
    {"name": "NovaMart Andheri West", "address": "Link Road, Opposite Infiniti Mall, Andheri West",
     "city": "Mumbai", "pincode": "400053", "phone": "+91 22 6789 2211",
     "opening_hours": "10:30 - 22:00", "latitude": 19.1364, "longitude": 72.8296},
    {"name": "NovaMart Connaught Place", "address": "N-Block, Outer Circle, Connaught Place",
     "city": "Delhi", "pincode": "110001", "phone": "+91 11 4567 8890",
     "opening_hours": "11:00 - 21:00", "latitude": 28.6315, "longitude": 77.2167},
    {"name": "NovaMart Banjara Hills", "address": "Road No. 12, Banjara Hills",
     "city": "Hyderabad", "pincode": "500034", "phone": "+91 40 2355 7788",
     "opening_hours": "10:00 - 21:30", "latitude": 17.4126, "longitude": 78.4392},
    {"name": "NovaMart Salt Lake", "address": "Sector V, Salt Lake City",
     "city": "Kolkata", "pincode": "700091", "phone": "+91 33 4009 1122",
     "opening_hours": "10:30 - 21:00", "latitude": 22.5726, "longitude": 88.4339},
    {"name": "NovaMart Anna Nagar", "address": "2nd Avenue, Anna Nagar",
     "city": "Chennai", "pincode": "600040", "phone": "+91 44 2626 4400",
     "opening_hours": "10:00 - 21:30", "latitude": 13.0850, "longitude": 80.2101},
]

# ---------------------------------------------------------------------------
# Knowledge base - the agent's single source of truth for policy answers
# ---------------------------------------------------------------------------
KB_ARTICLES: list[dict] = [
    {
        "title": "Return policy: what you can return and by when",
        "category": "returns",
        "tags": ["return", "refund", "policy", "window"],
        "content": """NovaMart accepts returns on most products within the return window shown on the
product page. The window starts on the day the order is delivered, not the day it was placed.

Standard return windows by category:
- Fashion (clothing, footwear, bags): 14 days
- Electronics accessories, headphones, smartwatches, fitness gear: 10 days
- Large appliances, laptops, smartphones, furniture: 7 days
- Beauty, personal care, grocery and other consumables: not returnable once the seal is broken

To be eligible the item must be unused, in its original packaging, with all tags, manuals,
free gifts and accessories included. Serial numbers must match the ones we shipped.

Items we never accept back:
- Products marked "Non-returnable" on the product page
- Innerwear, swimwear, cosmetics and food items where the seal is broken
- Digital gift cards and downloadable content
- Items damaged by misuse, or where the manufacturer's warranty seal is tampered with

If an item arrives damaged, defective or is the wrong product, the normal window does not
apply - report it within 48 hours of delivery and we will arrange a free replacement or a
full refund, whichever you prefer.""",
    },
    {
        "title": "How to start a return and what happens next",
        "category": "returns",
        "tags": ["return", "rma", "pickup", "process"],
        "content": """You can start a return from Orders > select the order > Return item, or by asking
the support assistant. We will need the reason for the return.

Once the return is approved you receive an RMA number by email and SMS. Keep it handy.

Free reverse pickup is available on every serviceable pincode. Our courier partner attempts
pickup within 2 business days of approval, and makes up to three attempts. Pack the item in
its original box with all accessories, and write the RMA number on the outside of the parcel.

If your pincode is not serviceable for reverse pickup, you can self-ship the item to the
returns address in your approval email. We reimburse courier charges up to Rs 150 on
submitting the receipt.

After pickup, the item passes a quality check at our warehouse within 24-48 hours. Once it
clears, the refund is initiated automatically. If it fails the quality check we ship the item
back to you free of charge and explain why.""",
    },
    {
        "title": "Refund timelines by payment method",
        "category": "refunds",
        "tags": ["refund", "money back", "timeline", "payment"],
        "content": """Refunds are initiated within 24 hours of the returned item passing quality check,
or immediately when an order is cancelled before dispatch.

Time to reach you after we initiate:
- UPI: 1-2 business days
- Credit and debit cards: 3-5 business days
- Net banking: 3-5 business days
- Wallets (Paytm, PhonePe, Amazon Pay): 1-2 business days
- EMI transactions: 5-7 business days, and the bank reverses the EMI in the next statement cycle
- Cash on delivery: refunded to the bank account you provide, in 3-5 business days
- NovaMart Wallet credit: instant

Shipping fees are refunded when the return is due to our error (wrong, damaged or defective
item). For a change-of-mind return, the original shipping fee is not refunded.

If a refund has not reached you two business days after the stated timeline, share the ARN
(Acquirer Reference Number) from your refund email with your bank - they can trace it. Our
support team can also raise a payment trace on your behalf.""",
    },
    {
        "title": "Cancelling an order",
        "category": "orders",
        "tags": ["cancel", "cancellation", "order"],
        "content": """You can cancel an order yourself at any time before it is dispatched - that means
while the status is Pending, Confirmed or Packed. Go to Orders, open the order, and choose
Cancel. There is no cancellation fee, and any amount paid is refunded in full.

Once the order status changes to Shipped or Out for delivery, self-cancellation is no longer
possible because the parcel is already with the courier. You have two options:
1. Refuse the parcel at the door. It comes back to us automatically and a full refund is
   processed once it reaches our warehouse.
2. Accept the delivery and then raise a return, if the item is returnable.

Partial cancellation of individual items is supported on multi-item orders that have not been
packed. Once packed, the whole order must be cancelled or returned together.

Orders paid by EMI can be cancelled the same way; the bank reverses the EMI plan within one
statement cycle and any processing fee already charged is refunded.""",
    },
    {
        "title": "Delivery timelines, charges and same-day delivery",
        "category": "shipping",
        "tags": ["delivery", "shipping", "charges", "timeline"],
        "content": """Standard delivery takes 2-4 business days in metro cities and 4-7 business days
elsewhere. The exact promised date is shown at checkout and on your order page - that date is
what we commit to.

Shipping charges:
- Orders of Rs 999 and above: free standard delivery
- Orders below Rs 999: Rs 49 standard delivery
- Express delivery (next business day): Rs 99 in serviceable pincodes
- Same-day delivery: Rs 149, available in Bengaluru, Mumbai, Delhi NCR and Hyderabad on orders
  placed before 12:00 noon

Large appliances and furniture are delivered by a specialist team who will call you to book a
two-hour slot, and installation is scheduled within 48 hours of delivery.

We deliver Monday to Saturday. Sunday and public holiday deliveries happen only for same-day
and express orders.

If your parcel misses its promised date by more than 48 hours you are entitled to a Rs 200
delay voucher - ask support and we will issue it.""",
    },
    {
        "title": "Tracking your order and understanding the status",
        "category": "shipping",
        "tags": ["track", "tracking", "status", "courier"],
        "content": """Every shipped order gets a tracking number by SMS and email, and it is shown on the
order page. You can also ask the support assistant to track it for you.

What each status means:
- Confirmed: payment received, the warehouse has the order
- Packed: the item is boxed and waiting for courier pickup
- Shipped: the courier has collected the parcel and it is moving
- Out for delivery: it is on a delivery vehicle and will arrive today
- Delivered: handed over, with the recipient name recorded
- Exception: a delivery attempt failed - usually a wrong address, nobody available, or an
  unreachable phone number

Couriers attempt delivery three times. After the third failed attempt the parcel returns to us
and we refund automatically.

If tracking has not updated for more than 48 hours, that usually means a hub scan was missed
rather than a lost parcel. Contact support and we will raise a trace with the courier; if the
parcel cannot be located within 7 days we refund or reship at your choice.""",
    },
    {
        "title": "Damaged, defective or wrong item received",
        "category": "returns",
        "tags": ["damaged", "defective", "wrong item", "replacement"],
        "content": """Report a damaged, defective or wrong item within 48 hours of delivery. This applies
even to products that are normally non-returnable.

What we need:
- Photographs of the item and of the outer packaging
- A photo of the shipping label
- For electronics, a short video showing the fault

Once the report is filed you choose a free replacement (subject to stock) or a full refund
including shipping charges. Replacements ship within 2 business days of the faulty item being
picked up; for high-value electronics we ship the replacement first and collect the faulty
unit at the same time.

For items that arrived visibly crushed or leaking, refuse the delivery if you can - that gets
you a refund fastest.

Manufacturing defects discovered after the return window are handled under the product's
warranty rather than the return policy. See the warranty article.""",
    },
    {
        "title": "Warranty coverage and how to claim",
        "category": "warranty",
        "tags": ["warranty", "repair", "service centre", "claim"],
        "content": """Warranty length is shown on each product page and printed on the invoice. Typical
cover: 12 months on consumer electronics, 24 months on large appliances and laptops, 6 months
on batteries and power banks, and no warranty on consumables.

Warranty covers manufacturing defects only. It does not cover physical damage, liquid damage,
unauthorised repairs, normal wear, or damage from a power surge without a surge protector.

To claim, you need the invoice - download it any time from Orders > Invoice. During the first
30 days after delivery, NovaMart handles the claim end to end: we collect the item, get it
repaired or replaced, and return it to you. After 30 days the manufacturer's service network
handles the repair directly; we will give you the nearest authorised service centre and the
brand's helpline.

Standard repair turnaround is 7-10 business days. If a repair takes longer than 21 days the
manufacturer replaces the unit under most brand policies.

Extended warranty purchased at checkout starts the day the manufacturer warranty ends and is
claimed the same way, quoting the extended-warranty certificate number.""",
    },
    {
        "title": "Payment methods, failed payments and double charges",
        "category": "payments",
        "tags": ["payment", "upi", "card", "failed", "double charge", "emi"],
        "content": """We accept UPI, credit and debit cards, net banking, wallets, EMI (cards and
cardless), and cash on delivery on eligible orders.

If a payment fails but money has left your account, the amount is almost always an
authorisation hold that your bank reverses automatically within 5-7 business days. No order is
created in this case, so nothing is shipped. If it has not reversed after 7 business days,
share your bank statement with support and we will raise a chargeback trace.

Double charges happen when a payment is retried before the first attempt times out. Only one
order is created. The duplicate amount is refunded automatically within 5-7 business days; you
do not need to do anything, but support can escalate it if you would like it tracked.

Cash on delivery is available on orders up to Rs 20,000 in serviceable pincodes. A Rs 29 COD
handling fee applies. COD is not available on high-value electronics or on items marked
Prepaid only.

No-cost EMI is available on select cards for orders above Rs 5,000, over 3, 6 or 9 months.
The interest is borne by NovaMart as an upfront discount, which is why cancelling a no-cost
EMI order refunds the discounted amount rather than the full MRP.

We never ask for your CVV, OTP, UPI PIN or card PIN over chat, voice or email. Anyone who does
is not from NovaMart.""",
    },
    {
        "title": "Coupons, offers and price-drop protection",
        "category": "offers",
        "tags": ["coupon", "discount", "offer", "promo", "price match"],
        "content": """Coupon codes are applied at checkout in the Apply coupon box. One coupon per order;
coupons cannot be combined with each other but do stack with bank card offers.

Current standing codes:
- WELCOME10: 10% off your first order above Rs 999, capped at Rs 500
- FESTIVE500: flat Rs 500 off orders above Rs 2,999
- FREESHIP: free standard delivery on any order value

Coupons cannot be applied after an order is placed. If you forgot one, cancel the order before
dispatch and reorder.

Price-drop protection: if the price of an item you bought drops within 7 days of your order
date, we refund the difference as NovaMart Wallet credit. Ask support with the order number
and we will check the price history. This does not apply during flash sales or clearance
events, or to items sold by third-party sellers.

Loyalty points earned on an order are credited 15 days after delivery, once the return window
has closed. If you return the item, the points are reversed.""",
    },
    {
        "title": "NovaMart loyalty programme: tiers and benefits",
        "category": "account",
        "tags": ["loyalty", "points", "tier", "rewards", "membership"],
        "content": """You earn 1 loyalty point for every Rs 100 spent. 100 points equal Rs 50 of wallet
credit, redeemable on any order.

Tiers are based on your spend in the last 12 months:
- Standard: default
- Silver: Rs 25,000 spent - free standard delivery on every order
- Gold: Rs 75,000 spent - free express delivery, a 30-day return window on fashion, and
  priority support queueing
- Platinum: Rs 2,00,000 spent - everything in Gold plus a dedicated relationship manager,
  early access to sales, and free installation on appliances

Tier status is reviewed on the first of every month and holds for 12 months from the date it
was earned. Points expire 24 months after they are credited.

Points are credited 15 days after delivery. Points from a returned order are reversed.""",
    },
    {
        "title": "Store pickup, click and collect, and store returns",
        "category": "stores",
        "tags": ["store", "pickup", "click and collect", "showroom"],
        "content": """Click and collect lets you order online and pick up from a NovaMart store, usually
within 4 hours for in-stock items. There is no fee, and you can pay online or at the counter.

Bring your order number and any government photo ID. Somebody else can collect on your behalf
if you share the pickup OTP with them.

Uncollected orders are held for 7 days, after which they are cancelled and refunded
automatically.

You can also return an online order at any NovaMart store within the item's return window,
which is the fastest option - the refund is initiated the same day after an in-store quality
check. Bring the item in its original packaging along with the invoice.

Store hours vary by location; most stores open at 10:00 and close between 21:00 and 22:00.
Ask support for the address, phone number and exact timings of your nearest store.""",
    },
    {
        "title": "Changing a delivery address or phone number after ordering",
        "category": "orders",
        "tags": ["address", "change", "edit order", "phone"],
        "content": """The delivery address can be changed while the order status is Pending, Confirmed or
Packed. Open the order and choose Change address. The new address must be in a serviceable
pincode, and the delivery estimate may change.

Once the order is Shipped the address is locked in the courier's system. In that case ask
support - for some couriers we can request an in-transit address change within the same city,
which usually adds 1-2 days. Across cities it is not possible; you would need to refuse the
delivery and reorder.

The contact phone number can be updated at any time before delivery and is worth keeping
current, because couriers call before attempting delivery.

Changing the address does not change the payment method. Cash on delivery orders moving to a
non-COD pincode are cancelled and refunded automatically.""",
    },
    {
        "title": "Account, sign-in and password help",
        "category": "account",
        "tags": ["login", "password", "otp", "account", "sign in"],
        "content": """Sign in with your registered email address and password, or with an OTP sent to your
registered mobile number.

If you have forgotten your password, use Forgot password on the sign-in screen. The reset link
is valid for 30 minutes and can only be used once. Check your spam folder if it does not
arrive within 5 minutes.

OTP not arriving is nearly always a network delay - wait 60 seconds before requesting another,
and note that requesting a new OTP invalidates the previous one. After five failed attempts
the account is locked for 30 minutes as a security measure.

To change your registered email or mobile number, sign in and go to Profile > Contact details;
both changes require verification on the old and the new contact.

To close your account, ask support. We delete personal data within 30 days, keeping only what
tax law requires us to retain on past invoices.""",
    },
]

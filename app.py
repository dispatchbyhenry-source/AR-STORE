import os
import sqlite3
from datetime import datetime
from functools import wraps

from flask import Flask, abort, flash, g, jsonify, redirect, render_template, request, session, url_for
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.utils import secure_filename

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE = os.environ.get("DATABASE_PATH", os.path.join(BASE_DIR, "store.db"))

app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)
app.config.update(SECRET_KEY=os.environ.get("SECRET_KEY", "change-this-secret-before-production"), MAX_CONTENT_LENGTH=8 * 1024 * 1024)
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "ChangeMe123!")

CURRENCIES = {"EUR": (1 / 302, "EUR"), "USD": (1 / 278, "USD")}
FREE_DELIVERY_MINIMUM_USD = 40
GERMANY_STANDARD_SHIPPING = 1812  # internal base amount; displayed as about EUR 6
INTERNATIONAL_SHIPPING = 6040  # internal base amount; displayed as about EUR 20
LANGUAGES = {"en": "English", "ur": "اردو", "ar": "العربية"}

PRODUCTS = [
    ("Slim-Fit Stretch Denim Jeans", "Pants", 3499, 4200, "-17% OFF", 4.8, 32, "AR-PNT-01", "https://images.unsplash.com/photo-1542272604-780c36856842?w=800", "30,32,34,36", "Dark Indigo,Washed Black", "Premium cotton denim with comfortable stretch and reinforced stitching."),
    ("Tailored Cotton Chino Trousers", "Pants", 2899, 3500, "HOT", 4.7, 19, "AR-PNT-02", "https://images.unsplash.com/photo-1624378439575-d8705ad7ae80?w=800", "30,32,34", "Olive Green,Khaki Tan", "Modern tapered chinos made from combed cotton twill."),
    ("Royal Oxford Formal Cotton Shirt", "Shirts", 2299, 2800, "NEW", 4.9, 54, "AR-SHR-01", "https://images.unsplash.com/photo-1596755094514-f87e34085b2c?w=800", "Small,Medium,Large,Extra Large", "Pure White,Sky Blue", "Luxury long-staple cotton oxford shirt with an executive collar."),
    ("Modern Stretch Pique Polo Shirt", "Shirts", 1899, 2200, "POPULAR", 4.5, 21, "AR-SHR-02", "https://images.unsplash.com/photo-1602810318383-e386cc2a3ccf?w=800", "Medium,Large,Extra Large", "Navy Blue,Maroon", "Breathable knit polo with active stretch and moisture control."),
    ("Genuine Cowhide Biker Leather Jacket", "Jackets", 8999, 11500, "-22% OFF", 5.0, 88, "AR-JKT-01", "https://images.unsplash.com/photo-1551028719-00167b16eac5?w=800", "Medium,Large,Extra Large,Double Extra Large", "Obsidian Black,Antique Brown", "Full-grain cowhide jacket with YKK zips and quilted lining."),
    ("Tactical Windproof Bomber Jacket", "Jackets", 5499, 6500, "FEATURED", 4.6, 14, "AR-JKT-02", "https://images.unsplash.com/photo-1548883354-7622d03aca27?w=800", "Small,Medium,Large", "Army Green,Matte Black", "Water-repellent shell with thermal insulation and storm cuffs."),
    ("Minimalist RFID Leather Bifold Wallet", "Wallets", 1499, 1999, "BESTSELLER", 4.8, 43, "AR-WLT-01", "https://images.unsplash.com/photo-1627123424574-724758594e93?w=800", "Standard Pocket", "Tan Brown,Classic Black", "Handcrafted leather wallet with RFID protection."),
    ("Luxury Structured Designer Purse", "Purses", 4999, 6200, "-19% OFF", 4.9, 37, "AR-PRS-01", "https://images.unsplash.com/photo-1584917865442-de89df76afd3?w=800", "Medium Tote", "Burgundy Red,Nude Beige", "Genuine leather handbag with gold-tone hardware."),
    ("Reversible Full-Grain Leather Belt", "Belts", 1299, 1650, "2-IN-1", 4.7, 29, "AR-BLT-01", "https://images.unsplash.com/photo-1553062407-98eeb64c6a62?w=800", "32-34 Waist,36-38 Waist", "Black/Brown Reversible", "Dual-sided leather belt with rotatable alloy buckle."),
    ("Velocity Knit Running Shoes", "Shoes", 5999, 7200, "NEW", 4.9, 61, "AR-SHO-01", "https://images.unsplash.com/photo-1542291026-7eec264c27ff?w=800", "40,41,42,43,44", "Crimson Red,Midnight Black", "Responsive knit running shoes with cushioned grip sole."),
    ("Classic Leather Court Sneakers", "Shoes", 6799, 7900, "TOP RATED", 4.8, 47, "AR-SHO-02", "https://images.unsplash.com/photo-1525966222134-fcfa99b8ae77?w=800", "39,40,41,42,43", "White/Red,Black/Red", "Premium everyday court sneakers with soft leather upper."),
]

LANGUAGES.update({"de": "Deutsch", "fr": "French", "es": "Spanish", "it": "Italian", "tr": "Turkish", "pt": "Portuguese", "zh": "Chinese", "ja": "Japanese"})
GALLERY_IMAGES = {"Shoes": ["https://images.unsplash.com/photo-1542291026-7eec264c27ff?w=1000", "https://images.unsplash.com/photo-1525966222134-fcfa99b8ae77?w=1000", "https://images.unsplash.com/photo-1460353581641-37baddab0fa2?w=1000"], "Pants": ["https://images.unsplash.com/photo-1542272604-780c36856842?w=1000", "https://images.unsplash.com/photo-1473966968600-fa801b869a1a?w=1000"], "Shirts": ["https://images.unsplash.com/photo-1596755094514-f87e34085b2c?w=1000", "https://images.unsplash.com/photo-1603252109303-2751441dd157?w=1000"], "Jackets": ["https://images.unsplash.com/photo-1551028719-00167b16eac5?w=1000", "https://images.unsplash.com/photo-1548883354-7622d03aca27?w=1000"]}

def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DATABASE, timeout=30)
        g.db.row_factory = sqlite3.Row
    return g.db

@app.teardown_appcontext
def close_db(_error=None):
    db = g.pop("db", None)
    if db is not None: db.close()

def init_db():
    db = get_db()
    db.executescript("""
    CREATE TABLE IF NOT EXISTS products (id INTEGER PRIMARY KEY, name TEXT NOT NULL, category TEXT NOT NULL, price REAL NOT NULL, old_price REAL, badge TEXT, rating REAL DEFAULT 0, reviews_count INTEGER DEFAULT 0, sku TEXT UNIQUE, image TEXT, sizes TEXT, colors TEXT, description TEXT, stock INTEGER NOT NULL DEFAULT 20, active INTEGER DEFAULT 1);
    CREATE TABLE IF NOT EXISTS reviews (id INTEGER PRIMARY KEY, product_id INTEGER NOT NULL, name TEXT NOT NULL, rating INTEGER NOT NULL CHECK(rating BETWEEN 1 AND 5), body TEXT NOT NULL, created_at TEXT NOT NULL, FOREIGN KEY(product_id) REFERENCES products(id));
    CREATE TABLE IF NOT EXISTS contacts (id INTEGER PRIMARY KEY, name TEXT NOT NULL, email TEXT NOT NULL, message TEXT NOT NULL, created_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS listings (id INTEGER PRIMARY KEY, seller_name TEXT NOT NULL, title TEXT NOT NULL, category TEXT NOT NULL, price REAL NOT NULL, description TEXT NOT NULL, created_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS orders (id INTEGER PRIMARY KEY, customer_name TEXT NOT NULL, email TEXT NOT NULL, address TEXT NOT NULL, country TEXT NOT NULL DEFAULT 'Germany', payment_method TEXT NOT NULL DEFAULT 'pay_on_delivery', currency TEXT NOT NULL, total REAL NOT NULL, shipping REAL NOT NULL DEFAULT 0, items TEXT NOT NULL, created_at TEXT NOT NULL);
    """)
    existing_order_columns = {row[1] for row in db.execute("PRAGMA table_info(orders)")}
    for column, definition in (("country", "TEXT NOT NULL DEFAULT 'Germany'"), ("payment_method", "TEXT NOT NULL DEFAULT 'pay_on_delivery'"), ("shipping", "REAL NOT NULL DEFAULT 0")):
        if column not in existing_order_columns:
            db.execute(f"ALTER TABLE orders ADD COLUMN {column} {definition}")
    existing_product_columns = {row[1] for row in db.execute("PRAGMA table_info(products)")}
    if "stock" not in existing_product_columns:
        db.execute("ALTER TABLE products ADD COLUMN stock INTEGER NOT NULL DEFAULT 20")
    if not db.execute("SELECT 1 FROM products LIMIT 1").fetchone():
        db.executemany("INSERT INTO products (name,category,price,old_price,badge,rating,reviews_count,sku,image,sizes,colors,description) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", PRODUCTS)
        db.executemany("INSERT INTO reviews (product_id,name,rating,body,created_at) VALUES (?,?,?,?,?)", [(10,"Sarah Williams",5,"The fit is spot-on and the red colour looks even better in person.","2026-08-10"),(10,"Daniel Cooper",5,"Light, comfortable and genuinely supportive for daily runs.","2026-08-12"),(5,"Ahmed Hassan",5,"Excellent stitching and a premium leather finish.","2026-08-08")])
    db.commit()

@app.before_request
def setup():
    init_db()
    session.setdefault("currency", "EUR")
    session.setdefault("language", "en")
    session.setdefault("cart", {})

@app.context_processor
def helpers():
    return {"currencies": CURRENCIES, "languages": LANGUAGES, "currency": session["currency"], "language": session["language"], "cart_count": sum(session["cart"].values()), "is_admin": session.get("is_admin", False)}

def product(row):
    item = dict(row)
    item["sizes"] = item["sizes"].split(",")
    item["colors"] = item["colors"].split(",")
    image_folder = os.path.join(BASE_DIR, "static", "images", item["sku"])
    local_gallery = [f"/static/images/{item['sku']}/{filename}" for filename in ("main.jpg", "2.jpg", "3.jpg") if os.path.exists(os.path.join(image_folder, filename))]
    item["gallery"] = local_gallery or ([item["image"]] + [image for image in GALLERY_IMAGES.get(item["category"], []) if image != item["image"]][:2])
    item["image"] = item["gallery"][0]
    return item

def fetch_product(product_id):
    row = get_db().execute("SELECT * FROM products WHERE id=? AND active=1", (product_id,)).fetchone()
    if not row: abort(404)
    return product(row)

@app.route("/")
def home():
    db = get_db()
    products = [product(r) for r in db.execute("SELECT * FROM products WHERE active=1 ORDER BY id").fetchall()]
    categories = db.execute("SELECT category, COUNT(*) AS count FROM products WHERE active=1 GROUP BY category ORDER BY category").fetchall()
    return render_template("home.html", products=products[:8], categories=categories, deal=next(p for p in products if p["category"] == "Shoes"))

@app.route("/products")
def products():
    category, search = request.args.get("category", "All"), request.args.get("search", "").strip()
    query, args = "SELECT * FROM products WHERE active=1", []
    if category != "All": query += " AND category=?"; args.append(category)
    if search: query += " AND (name LIKE ? OR category LIKE ? OR description LIKE ?)"; args.extend([f"%{search}%"] * 3)
    rows = [product(r) for r in get_db().execute(query + " ORDER BY id DESC", args).fetchall()]
    categories = [r[0] for r in get_db().execute("SELECT DISTINCT category FROM products WHERE active=1 ORDER BY category")]
    return render_template("products.html", products=rows, categories=categories, selected=category, search=search)

@app.route("/product/<int:product_id>")
def product_detail(product_id):
    item = fetch_product(product_id)
    db = get_db()
    reviews = db.execute("SELECT * FROM reviews WHERE product_id=? ORDER BY id DESC", (product_id,)).fetchall()
    related = [product(r) for r in db.execute("SELECT * FROM products WHERE category=? AND id!=? AND active=1 LIMIT 4", (item["category"], product_id)).fetchall()]
    return render_template("product_detail.html", product=item, reviews=reviews, related=related)

@app.post("/product/<int:product_id>/review")
def add_review(product_id):
    fetch_product(product_id)
    name, body = request.form.get("name", "").strip(), request.form.get("body", "").strip()
    try: rating = int(request.form.get("rating", 0))
    except ValueError: rating = 0
    if not name or not body or rating not in range(1, 6): flash("Please enter a name, a 1–5 rating, and your review.", "error")
    else:
        db = get_db(); db.execute("INSERT INTO reviews (product_id,name,rating,body,created_at) VALUES (?,?,?,?,?)", (product_id,name,rating,body,datetime.utcnow().strftime("%Y-%m-%d")))
        db.execute("UPDATE products SET reviews_count=reviews_count+1, rating=ROUND(((rating*reviews_count)+?)/(reviews_count+1),1) WHERE id=?", (rating, product_id)); db.commit(); flash("Thank you — your review is live.", "success")
    return redirect(url_for("product_detail", product_id=product_id) + "#reviews")

@app.post("/cart/add/<int:product_id>")
def add_cart(product_id):
    item = fetch_product(product_id)
    selected_size = request.form.get("size", item["sizes"][0])
    if selected_size not in item["sizes"]:
        flash("Please select a valid size.", "error")
        return redirect(url_for("product_detail", product_id=product_id))
    cart = session["cart"]; key = f"{product_id}:{selected_size}"; cart[key] = cart.get(key, 0) + 1; session["cart"] = cart; flash(f"{item['name']} ({selected_size}) added to your cart.", "success")
    return redirect(request.referrer or url_for("cart"))

@app.post("/cart/remove/<int:product_id>")
def remove_cart(product_id):
    cart = session["cart"]; cart.pop(request.form.get("cart_key", ""), None); session["cart"] = cart
    return redirect(url_for("cart"))

def cart_items():
    items, total = [], 0
    for cart_key, quantity in session["cart"].items():
        item_id, selected_size = (cart_key.split(":", 1) if ":" in cart_key else (cart_key, "Standard"))
        row = get_db().execute("SELECT * FROM products WHERE id=?", (item_id,)).fetchone()
        if row:
            item = product(row); item["quantity"] = quantity; item["selected_size"] = selected_size; item["cart_key"] = cart_key; item["subtotal"] = item["price"] * quantity; total += item["subtotal"]; items.append(item)
    return items, total

def shipping_quote(items, subtotal, country):
    item_count = sum(item["quantity"] for item in items)
    qualifying_total = subtotal / 278
    if country.strip().lower() == "germany" and item_count >= 2 and qualifying_total >= FREE_DELIVERY_MINIMUM_USD:
        return 0, "Free delivery: 2+ products and order value above $40 within Germany."
    if country.strip().lower() == "germany":
        return GERMANY_STANDARD_SHIPPING, "Germany standard delivery"
    return INTERNATIONAL_SHIPPING, "International delivery charge"

@app.route("/cart", methods=["GET", "POST"])
def cart():
    items, total = cart_items()
    country = request.form.get("country", "Germany") if request.method == "POST" else request.args.get("country", "Germany")
    shipping, shipping_label = shipping_quote(items, total, country)
    if request.method == "POST":
        name, email, address = (request.form.get(k, "").strip() for k in ("name", "email", "address"))
        payment_method = request.form.get("payment_method", "")
        valid_methods = {"pay_on_delivery", "bank_transfer"}
        if not items or not name or not email or not address or not country or payment_method not in valid_methods: flash("Add items and complete all checkout fields, including payment method.", "error")
        else:
            grand_total = total + shipping
            db=get_db(); db.execute("INSERT INTO orders (customer_name,email,address,country,payment_method,currency,total,shipping,items,created_at) VALUES (?,?,?,?,?,?,?,?,?,?)", (name,email,address,country,payment_method,session["currency"],grand_total,shipping,str(items),datetime.utcnow().isoformat())); db.commit(); session["cart"]={}; flash("Order placed successfully. We will contact you shortly.", "success"); return redirect(url_for("home"))
    return render_template("cart.html", items=items, total=total, shipping=shipping, grand_total=total + shipping, shipping_label=shipping_label, selected_country=country)

@app.route("/sell", methods=["GET", "POST"])
def sell():
    if request.method == "POST":
        fields = [request.form.get(k, "").strip() for k in ("seller_name", "title", "category", "description")]
        try: price=float(request.form.get("price", 0))
        except ValueError: price=0
        if not all(fields) or price <= 0: flash("Please complete every listing field with a valid price.", "error")
        else: get_db().execute("INSERT INTO listings (seller_name,title,category,price,description,created_at) VALUES (?,?,?,?,?,?)", (*fields[:3],price,fields[3],datetime.utcnow().isoformat())); get_db().commit(); flash("Your listing has been submitted for review.", "success")
    return render_template("sell.html")

@app.route("/contact", methods=["GET", "POST"])
def contact():
    if request.method == "POST":
        name,email,message=(request.form.get(k, "").strip() for k in ("name","email","message"))
        if not name or not email or not message: flash("Please complete all contact fields.", "error")
        else: get_db().execute("INSERT INTO contacts (name,email,message,created_at) VALUES (?,?,?,?)", (name,email,message,datetime.utcnow().isoformat())); get_db().commit(); flash("Your message has been sent to our support team.", "success")
    return render_template("contact.html")

@app.post("/preferences")
def preferences():
    currency, language = request.form.get("currency"), request.form.get("language")
    if currency in CURRENCIES: session["currency"] = currency
    if language in LANGUAGES: session["language"] = language
    return redirect(request.referrer or url_for("home"))

@app.get("/api/products")
def api_products(): return jsonify([product(r) for r in get_db().execute("SELECT * FROM products WHERE active=1").fetchall()])

def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("is_admin"):
            flash("Please sign in to access the admin dashboard.", "error")
            return redirect(url_for("admin_login"))
        return view(*args, **kwargs)
    return wrapped

def save_product_images(sku):
    folder = os.path.join(BASE_DIR, "static", "images", sku)
    os.makedirs(folder, exist_ok=True)
    allowed_extensions = {"jpg", "jpeg", "png", "webp"}
    for field, target in (("main_image", "main.jpg"), ("image_2", "2.jpg"), ("image_3", "3.jpg")):
        uploaded = request.files.get(field)
        if uploaded and uploaded.filename:
            extension = secure_filename(uploaded.filename).rsplit(".", 1)[-1].lower() if "." in uploaded.filename else ""
            if extension not in allowed_extensions:
                raise ValueError("Images must be JPG, JPEG, PNG, or WEBP files.")
            uploaded.save(os.path.join(folder, target))

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        if request.form.get("username") == ADMIN_USERNAME and request.form.get("password") == ADMIN_PASSWORD:
            session["is_admin"] = True
            flash("Welcome to the admin dashboard.", "success")
            return redirect(url_for("admin_dashboard"))
        flash("Incorrect username or password.", "error")
    return render_template("admin_login.html")

@app.post("/admin/logout")
@admin_required
def admin_logout():
    session.pop("is_admin", None)
    flash("You have been signed out.", "success")
    return redirect(url_for("home"))

@app.get("/admin")
@admin_required
def admin_dashboard():
    db = get_db()
    return render_template("admin_dashboard.html", products=[product(row) for row in db.execute("SELECT * FROM products ORDER BY id DESC")], orders=db.execute("SELECT * FROM orders ORDER BY id DESC LIMIT 20").fetchall(), reviews=db.execute("SELECT reviews.*, products.name AS product_name FROM reviews JOIN products ON products.id=reviews.product_id ORDER BY reviews.id DESC LIMIT 20").fetchall(), contacts=db.execute("SELECT * FROM contacts ORDER BY id DESC LIMIT 20").fetchall(), listings=db.execute("SELECT * FROM listings ORDER BY id DESC LIMIT 20").fetchall())

@app.route("/admin/product/new", methods=["GET", "POST"])
@admin_required
def admin_product_new():
    if request.method == "POST":
        fields = {key: request.form.get(key, "").strip() for key in ("name", "category", "sku", "badge", "sizes", "colors", "description")}
        try: price, old_price, stock = float(request.form.get("price", 0)), float(request.form.get("old_price", 0) or 0), int(request.form.get("stock", 0))
        except ValueError: price, old_price, stock = 0, 0, -1
        if not all(fields[key] for key in ("name", "category", "sku", "sizes", "colors", "description")) or price <= 0 or stock < 0:
            flash("Complete all required product fields with a valid price and stock quantity.", "error")
        else:
            try:
                db = get_db(); db.execute("INSERT INTO products (name,category,price,old_price,badge,rating,reviews_count,sku,image,sizes,colors,description,stock) VALUES (?,?,?,?,?,0,0,?,?,?,?,?,?)", (fields["name"],fields["category"],price,old_price,fields["badge"],fields["sku"],"",fields["sizes"],fields["colors"],fields["description"],stock)); db.commit(); save_product_images(fields["sku"]); flash("Product created successfully.", "success"); return redirect(url_for("admin_dashboard"))
            except (sqlite3.IntegrityError, ValueError) as error:
                flash(f"Product was not saved: {error}", "error")
    return render_template("admin_product_form.html", product=None)

@app.route("/admin/product/<int:product_id>/edit", methods=["GET", "POST"])
@admin_required
def admin_product_edit(product_id):
    db = get_db(); row = db.execute("SELECT * FROM products WHERE id=?", (product_id,)).fetchone()
    if not row: abort(404)
    if request.method == "POST":
        fields = {key: request.form.get(key, "").strip() for key in ("name", "category", "sku", "badge", "sizes", "colors", "description")}
        try: price, old_price, stock = float(request.form.get("price", 0)), float(request.form.get("old_price", 0) or 0), int(request.form.get("stock", 0))
        except ValueError: price, old_price, stock = 0, 0, -1
        if not all(fields[key] for key in ("name", "category", "sku", "sizes", "colors", "description")) or price <= 0 or stock < 0: flash("Complete all required product fields with a valid price and stock quantity.", "error")
        else:
            try:
                db.execute("UPDATE products SET name=?,category=?,price=?,old_price=?,badge=?,sku=?,sizes=?,colors=?,description=?,stock=?,active=? WHERE id=?", (fields["name"],fields["category"],price,old_price,fields["badge"],fields["sku"],fields["sizes"],fields["colors"],fields["description"],stock,1 if request.form.get("active") else 0,product_id)); db.commit(); save_product_images(fields["sku"]); flash("Product updated successfully.", "success"); return redirect(url_for("admin_dashboard"))
            except (sqlite3.IntegrityError, ValueError) as error: flash(f"Product was not updated: {error}", "error")
    return render_template("admin_product_form.html", product=dict(row))

@app.post("/admin/product/<int:product_id>/delete")
@admin_required
def admin_product_delete(product_id):
    get_db().execute("DELETE FROM products WHERE id=?", (product_id,)); get_db().commit(); flash("Product deleted.", "success")
    return redirect(url_for("admin_dashboard"))

@app.post("/admin/review/<int:review_id>/delete")
@admin_required
def admin_review_delete(review_id):
    get_db().execute("DELETE FROM reviews WHERE id=?", (review_id,)); get_db().commit(); flash("Review deleted.", "success")
    return redirect(url_for("admin_dashboard"))

@app.errorhandler(404)
def not_found(_): return render_template("404.html"), 404

if __name__ == "__main__":
    app.run(debug=os.environ.get("FLASK_DEBUG") == "1", host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))

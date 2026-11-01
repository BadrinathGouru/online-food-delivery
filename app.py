from functools import wraps
import os
import secrets

from flask import (
    Flask,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
import mysql.connector
from werkzeug.security import check_password_hash, generate_password_hash

app = Flask(__name__)

# Secret key from environment variable with development fallback
app.secret_key = os.environ.get(
    "FLASK_SECRET_KEY",
    "foodflow-secret-key-development-mode-2026"
)

app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
if os.environ.get("FLASK_ENV") == "production":
    app.config["SESSION_COOKIE_SECURE"] = True


# -------------------- DATABASE CONNECTION --------------------

def get_db_connection():
    return mysql.connector.connect(
        host=os.environ.get("DB_HOST", "localhost"),
        user=os.environ.get("DB_USER", "root"),
        password=os.environ.get("DB_PASSWORD", "password@123"),
        database=os.environ.get("DB_NAME", "food_delivery")
    )


# -------------------- CSRF PROTECTION --------------------

def generate_csrf_token():
    if "_csrf_token" not in session:
        session["_csrf_token"] = secrets.token_hex(32)
    return session["_csrf_token"]

app.jinja_env.globals["csrf_token"] = generate_csrf_token


@app.before_request
def csrf_protect():
    if request.method in ("POST", "PUT", "PATCH", "DELETE"):
        token = (
            request.headers.get("X-CSRFToken")
            or request.headers.get("X-CSRF-Token")
            or request.form.get("csrf_token")
        )
        if not token and request.is_json:
            json_data = request.get_json(silent=True) or {}
            token = json_data.get("csrf_token")

        expected = session.get("_csrf_token")
        if not expected or not token or not secrets.compare_digest(str(token), str(expected)):
            if request.path.startswith("/api/"):
                return jsonify({"error": "CSRF token missing or invalid."}), 400
            flash("Session expired or invalid form submission. Please try again.", "error")
            if session.get("is_admin"):
                return redirect(url_for("admin_dashboard"))
            if session.get("customer_id"):
                return redirect(url_for("customer_home"))
            return redirect(url_for("common_login"))


# -------------------- ROLE-BASED ACCESS CONTROL --------------------

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get("is_admin"):
            if request.path.startswith("/api/"):
                return jsonify({"error": "Unauthorized. Admin privileges required."}), 403
            flash("Administrator login required.", "error")
            return redirect(url_for("admin_login"))
        return f(*args, **kwargs)
    return decorated_function


def customer_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get("customer_id"):
            if request.path.startswith("/api/"):
                return jsonify({"error": "Unauthorized. Customer login required."}), 401
            flash("Please log in as a customer to access that page.", "error")
            return redirect(url_for("common_login"))
        return f(*args, **kwargs)
    return decorated_function


# -------------------- ADMIN CREDENTIALS --------------------

ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD_HASH = os.environ.get("ADMIN_PASSWORD_HASH")
if not ADMIN_PASSWORD_HASH:
    _admin_plain = os.environ.get("ADMIN_PASSWORD", "admin@123")
    ADMIN_PASSWORD_HASH = generate_password_hash(_admin_plain)


# -------------------- LANDING & AUTHENTICATION --------------------

@app.route("/")
def index():
    if session.get("is_admin"):
        return redirect(url_for("admin_dashboard"))
    if session.get("customer_id"):
        return redirect(url_for("customer_home"))
    return render_template("login.html")


@app.route("/login", methods=["GET", "POST"])
def common_login():
    if request.method == "GET":
        if session.get("is_admin"):
            return redirect(url_for("admin_dashboard"))
        if session.get("customer_id"):
            return redirect(url_for("customer_home"))
        return render_template("login.html")

    account_type = request.form.get("account_type", "customer").strip().lower()

    if account_type == "admin":
        username = request.form.get("username", "").strip() or request.form.get("email", "").strip()
        password = request.form.get("password", "")

        if not username or not password:
            flash("Enter your admin username and password.", "error")
            return redirect(url_for("common_login"))

        if username == ADMIN_USERNAME and check_password_hash(ADMIN_PASSWORD_HASH, password):
            session.clear()
            session["is_admin"] = True
            generate_csrf_token()
            flash("Welcome to the Admin Dashboard!", "success")
            return redirect(url_for("admin_dashboard"))

        flash("Invalid admin username or password.", "error")
        return redirect(url_for("common_login"))

    # Customer account type (default)
    email = request.form.get("email", "").strip().lower() or request.form.get("username", "").strip().lower()
    password = request.form.get("password", "")

    if not email or not password:
        flash("Enter your email and password.", "error")
        return redirect(url_for("common_login"))

    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute(
            """
            SELECT customer_id, name, email, phone, password_hash
            FROM customers
            WHERE email = %s
            """,
            (email,)
        )

        customer = cursor.fetchone()

        if (
            customer is None
            or not customer["password_hash"]
            or not check_password_hash(
                customer["password_hash"], password
            )
        ):
            flash("Invalid email or password.", "error")
            return redirect(url_for("common_login"))

        session.clear()
        session["customer_id"] = customer["customer_id"]
        session["customer_name"] = customer["name"]
        session["customer_email"] = customer["email"]
        session["customer_phone"] = customer.get("phone") or ""
        generate_csrf_token()

        flash(f"Welcome back, {customer['name']}!", "success")
        return redirect(url_for("customer_home"))

    except mysql.connector.Error:
        app.logger.exception("Customer login failed")
        flash("Unable to log in right now. Please try again.", "error")
        return redirect(url_for("common_login"))

    finally:
        if cursor is not None:
            cursor.close()
        if conn is not None and conn.is_connected():
            conn.close()


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "GET":
        if session.get("customer_id"):
            return redirect(url_for("customer_home"))
        return render_template("signup.html")

    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip().lower()
    phone = request.form.get("phone", "").strip()
    password = request.form.get("password", "")
    confirm_password = request.form.get("confirm_password", "")

    if not name or not email or not password:
        flash("Name, email, and password are required.", "error")
        return redirect(url_for("signup"))

    if "@" not in email or len(email) > 255:
        flash("Enter a valid email address.", "error")
        return redirect(url_for("signup"))

    if len(name) > 100 or len(phone) > 15:
        flash("Name or phone number is too long.", "error")
        return redirect(url_for("signup"))

    if len(password) < 8:
        flash("Password must contain at least 8 characters.", "error")
        return redirect(url_for("signup"))

    if password != confirm_password:
        flash("Passwords do not match.", "error")
        return redirect(url_for("signup"))

    conn = None
    cursor = None

    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute(
            "SELECT customer_id FROM customers WHERE email = %s",
            (email,)
        )

        if cursor.fetchone():
            flash("An account with this email already exists.", "error")
            return redirect(url_for("signup"))

        password_hash = generate_password_hash(password)

        cursor.execute(
            """
            INSERT INTO customers (name, email, phone, password_hash)
            VALUES (%s, %s, %s, %s)
            """,
            (name, email, phone or None, password_hash)
        )

        conn.commit()

        flash("Account created successfully. Please log in.", "success")
        return redirect(url_for("common_login"))

    except mysql.connector.Error:
        if conn is not None:
            conn.rollback()

        app.logger.exception("Customer signup failed")
        flash("Unable to create your account. Please try again.", "error")
        return redirect(url_for("signup"))

    finally:
        if cursor is not None:
            cursor.close()
        if conn is not None and conn.is_connected():
            conn.close()


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("common_login"))


@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if session.get("is_admin"):
        return redirect(url_for("admin_dashboard"))
    if request.method == "GET":
        return render_template("admin_login.html")

    username = request.form.get("username", "").strip()
    password = request.form.get("password", "")

    if username == ADMIN_USERNAME and check_password_hash(ADMIN_PASSWORD_HASH, password):
        session.clear()
        session["is_admin"] = True
        generate_csrf_token()
        flash("Welcome to the Admin Dashboard!", "success")
        return redirect(url_for("admin_dashboard"))

    flash("Invalid admin credentials.", "error")
    return redirect(url_for("admin_login"))


@app.route("/admin/logout", methods=["POST"])
def admin_logout():
    session.clear()
    flash("Admin logged out.", "success")
    return redirect(url_for("common_login"))


# -------------------- PROTECTED APPLICATION PAGES --------------------

@app.route("/home")
@customer_required
def customer_home():
    return render_template("index.html")


@app.route("/admin")
@admin_required
def admin_dashboard():
    return render_template("admin.html")


# ============================================================
# CUSTOMER APIs
# ============================================================

# -------------------- CUSTOMER MENU API --------------------

@app.route("/api/menu", methods=["GET"])
def get_menu():
    conn = None
    cursor = None

    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("""
            SELECT r.name AS restaurant,
                   m.item_id,
                   m.item_name,
                   m.category,
                   m.price
            FROM restaurants r
            JOIN menu_items m
                ON r.restaurant_id = m.restaurant_id
            WHERE m.available = TRUE
            ORDER BY r.name, m.item_name
        """)

        items = cursor.fetchall()

        for item in items:
            item["price"] = float(item["price"])

        return jsonify(items)

    except mysql.connector.Error:
        app.logger.exception("Failed to load menu")
        return jsonify({"error": "Unable to load menu."}), 500

    finally:
        if cursor is not None:
            cursor.close()
        if conn is not None and conn.is_connected():
            conn.close()


# -------------------- PLACE CUSTOMER ORDER --------------------

@app.route("/api/orders", methods=["POST"])
@customer_required
def place_order():
    customer_id = session.get("customer_id")
    data = request.get_json(silent=True) or {}

    items = data.get("items", [])
    phone = str(data.get("phone", "")).strip()
    delivery_address = str(data.get("delivery_address", "")).strip()
    building_details = str(data.get("building_details", "")).strip()

    if (
        not isinstance(items, list)
        or not items
        or not delivery_address
    ):
        return jsonify({
            "error": "Please provide your delivery address and cart items."
        }), 400

    conn = None
    cursor = None

    try:
        conn = get_db_connection()
        conn.start_transaction()
        cursor = conn.cursor(dictionary=True)

        if phone:
            cursor.execute(
                "UPDATE customers SET phone = %s WHERE customer_id = %s",
                (phone, customer_id)
            )

        validated_items = []
        total = 0.0
        seen_ids = set()

        for item in items:
            if not isinstance(item, dict):
                conn.rollback()
                return jsonify({"error": "Invalid cart item."}), 400

            try:
                item_id = int(item["item_id"])
                quantity = int(item["quantity"])
            except (KeyError, TypeError, ValueError):
                conn.rollback()
                return jsonify({"error": "Invalid cart item."}), 400

            if (
                item_id < 1
                or quantity < 1
                or quantity > 100
                or item_id in seen_ids
            ):
                conn.rollback()
                return jsonify({
                    "error": "Invalid item or quantity."
                }), 400

            seen_ids.add(item_id)

            cursor.execute("""
                SELECT item_id, price
                FROM menu_items
                WHERE item_id = %s
                  AND available = TRUE
            """, (item_id,))

            food = cursor.fetchone()

            if food is None:
                conn.rollback()
                return jsonify({
                    "error": "A food item is unavailable."
                }), 400

            price = float(food["price"])
            total += price * quantity

            validated_items.append(
                (item_id, quantity, price)
            )

        total = round(total, 2)

        cursor.execute("""
            INSERT INTO orders (customer_id, total_amount)
            VALUES (%s, %s)
        """, (customer_id, total))

        order_id = cursor.lastrowid

        for item_id, quantity, price in validated_items:
            cursor.execute("""
                INSERT INTO order_items
                    (order_id, item_id, quantity, unit_price)
                VALUES (%s, %s, %s, %s)
            """, (order_id, item_id, quantity, price))

        cursor.execute("""
            INSERT INTO deliveries (order_id, delivery_address, building_details)
            VALUES (%s, %s, %s)
        """, (order_id, delivery_address, building_details or None))

        conn.commit()

        return jsonify({
            "message": "Order placed successfully!",
            "order_id": order_id,
            "total_amount": total
        }), 201

    except mysql.connector.Error:
        if conn is not None:
            conn.rollback()

        app.logger.exception("Failed to place order")

        return jsonify({
            "error": "Could not place order."
        }), 500

    finally:
        if cursor is not None:
            cursor.close()
        if conn is not None and conn.is_connected():
            conn.close()


# -------------------- CUSTOMER ORDER HISTORY --------------------

@app.route("/api/orders", methods=["GET"])
@customer_required
def get_orders():
    customer_id = session.get("customer_id")
    conn = None
    cursor = None

    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("""
            SELECT o.order_id,
                   c.name AS customer_name,
                   c.email,
                   o.order_date,
                   o.total_amount,
                   o.order_status,
                   oi.order_item_id,
                   oi.item_id,
                   m.item_name,
                   oi.quantity,
                   oi.unit_price
            FROM orders o
            JOIN customers c
                ON o.customer_id = c.customer_id
            JOIN order_items oi
                ON o.order_id = oi.order_id
            JOIN menu_items m
                ON oi.item_id = m.item_id
            WHERE o.customer_id = %s
            ORDER BY o.order_id DESC, oi.order_item_id
        """, (customer_id,))

        rows = cursor.fetchall()
        orders = {}

        for row in rows:
            order_id = row["order_id"]

            if order_id not in orders:
                orders[order_id] = {
                    "order_id": order_id,
                    "customer_name": row["customer_name"],
                    "email": row["email"],
                    "order_date": row["order_date"].isoformat(
                        sep=" ", timespec="seconds"
                    ),
                    "total_amount": float(row["total_amount"]),
                    "order_status": row["order_status"],
                    "items": []
                }

            orders[order_id]["items"].append({
                "item_id": row["item_id"],
                "item_name": row["item_name"],
                "quantity": row["quantity"],
                "unit_price": float(row["unit_price"])
            })

        return jsonify(list(orders.values()))

    except mysql.connector.Error:
        app.logger.exception("Failed to load order history")

        return jsonify({
            "error": "Unable to retrieve order history."
        }), 500

    finally:
        if cursor is not None:
            cursor.close()
        if conn is not None and conn.is_connected():
            conn.close()


# -------------------- CANCEL CUSTOMER ORDER --------------------

@app.route("/api/orders/<int:order_id>/cancel", methods=["POST"])
@customer_required
def cancel_order(order_id):
    customer_id = session.get("customer_id")
    conn = None
    cursor = None

    try:
        conn = get_db_connection()
        conn.start_transaction()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("""
            SELECT customer_id, order_status
            FROM orders
            WHERE order_id = %s
            FOR UPDATE
        """, (order_id,))

        order = cursor.fetchone()

        if order is None:
            conn.rollback()
            return jsonify({"error": "Order not found."}), 404

        if order["customer_id"] != customer_id:
            conn.rollback()
            return jsonify({
                "error": "You are not authorized to cancel this order."
            }), 403

        if order["order_status"] != "Pending":
            conn.rollback()
            return jsonify({
                "error": "Only pending orders can be cancelled."
            }), 409

        cursor.execute("""
            UPDATE orders
            SET order_status = 'Cancelled'
            WHERE order_id = %s
        """, (order_id,))

        cursor.execute("""
            UPDATE deliveries
            SET delivery_status = 'Cancelled'
            WHERE order_id = %s
              AND delivery_status != 'Delivered'
        """, (order_id,))

        cursor.execute("""
            UPDATE delivery_persons dp
            JOIN deliveries d
                ON dp.delivery_person_id = d.delivery_person_id
            SET dp.is_available = TRUE
            WHERE d.order_id = %s
              AND d.delivery_status = 'Cancelled'
        """, (order_id,))

        conn.commit()

        return jsonify({
            "message": f"Order #{order_id} cancelled successfully.",
            "order_id": order_id,
            "order_status": "Cancelled"
        }), 200

    except mysql.connector.Error:
        if conn is not None:
            conn.rollback()

        app.logger.exception("Failed to cancel order")

        return jsonify({
            "error": "Could not cancel order."
        }), 500

    finally:
        if cursor is not None:
            cursor.close()
        if conn is not None and conn.is_connected():
            conn.close()


# ============================================================
# ADMIN DASHBOARD APIs
# ============================================================

# -------------------- DASHBOARD STATISTICS --------------------

@app.route("/api/admin/stats", methods=["GET"])
@admin_required
def admin_stats():
    conn = None
    cursor = None

    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("""
            SELECT
                COUNT(*) AS total_orders,
                COALESCE(SUM(order_status = 'Pending'), 0) AS pending_orders,
                COALESCE(SUM(order_status = 'Preparing'), 0) AS preparing_orders,
                COALESCE(SUM(order_status = 'Delivered'), 0) AS delivered_orders,
                COALESCE(
                    SUM(
                        CASE
                            WHEN order_status != 'Cancelled'
                            THEN total_amount
                            ELSE 0
                        END
                    ), 0
                ) AS total_sales
            FROM orders
        """)

        stats = cursor.fetchone()

        for key in (
            "total_orders",
            "pending_orders",
            "preparing_orders",
            "delivered_orders"
        ):
            stats[key] = int(stats[key])

        stats["total_sales"] = float(stats["total_sales"])

        return jsonify(stats)

    except mysql.connector.Error:
        app.logger.exception("Failed to load admin statistics")

        return jsonify({
            "error": "Unable to load dashboard statistics."
        }), 500

    finally:
        if cursor is not None:
            cursor.close()
        if conn is not None and conn.is_connected():
            conn.close()


# -------------------- ADMIN ORDER LIST --------------------

@app.route("/api/admin/orders", methods=["GET"])
@admin_required
def admin_get_orders():
    conn = None
    cursor = None

    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("""
            SELECT o.order_id,
                   c.name AS customer_name,
                   c.email,
                   c.phone,
                   o.order_date,
                   o.total_amount,
                   o.order_status,
                   GROUP_CONCAT(
                       CONCAT(m.item_name, ' x ', oi.quantity)
                       ORDER BY m.item_name
                       SEPARATOR ', '
                   ) AS items
            FROM orders o
            JOIN customers c
                ON o.customer_id = c.customer_id
            LEFT JOIN order_items oi
                ON o.order_id = oi.order_id
            LEFT JOIN menu_items m
                ON oi.item_id = m.item_id
            GROUP BY o.order_id,
                     c.name,
                     c.email,
                     c.phone,
                     o.order_date,
                     o.total_amount,
                     o.order_status
            ORDER BY o.order_id DESC
        """)

        orders = cursor.fetchall()

        for order in orders:
            if order["order_date"] is not None:
                order["order_date"] = order["order_date"].isoformat(
                    sep=" ", timespec="seconds"
                )

            order["total_amount"] = float(order["total_amount"])
            order["items"] = order["items"] or "No items"

        return jsonify(orders)

    except mysql.connector.Error:
        app.logger.exception("Failed to load admin orders")

        return jsonify({
            "error": "Unable to load orders."
        }), 500

    finally:
        if cursor is not None:
            cursor.close()
        if conn is not None and conn.is_connected():
            conn.close()


# -------------------- UPDATE ORDER STATUS --------------------

@app.route(
    "/api/admin/orders/<int:order_id>/status",
    methods=["PATCH"]
)
@admin_required
def admin_update_order_status(order_id):
    data = request.get_json(silent=True) or {}
    new_status = data.get("order_status")

    if new_status not in (
        "Pending", "Preparing", "Delivered", "Cancelled"
    ):
        return jsonify({"error": "Invalid order status."}), 400

    conn = None
    cursor = None

    try:
        conn = get_db_connection()
        conn.start_transaction()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("""
            SELECT order_status
            FROM orders
            WHERE order_id = %s
            FOR UPDATE
        """, (order_id,))

        order = cursor.fetchone()

        if order is None:
            conn.rollback()
            return jsonify({"error": "Order not found."}), 404

        current_status = order["order_status"]

        allowed = {
            "Pending": ("Preparing", "Cancelled"),
            "Preparing": ("Delivered",),
            "Delivered": (),
            "Cancelled": ()
        }

        if new_status not in allowed[current_status]:
            conn.rollback()
            return jsonify({
                "error": (
                    f"Cannot change status from {current_status} "
                    f"to {new_status}."
                )
            }), 409

        cursor.execute("""
            UPDATE orders
            SET order_status = %s
            WHERE order_id = %s
        """, (new_status, order_id))

        if new_status in ("Preparing", "Delivered"):
            cursor.execute("""
                INSERT INTO deliveries (order_id)
                VALUES (%s)
                ON DUPLICATE KEY UPDATE order_id = VALUES(order_id)
            """, (order_id,))

        if new_status == "Delivered":
            cursor.execute("""
                UPDATE deliveries
                SET delivery_status = 'Delivered',
                    delivered_at = COALESCE(delivered_at, NOW())
                WHERE order_id = %s
            """, (order_id,))

            cursor.execute("""
                UPDATE delivery_persons dp
                JOIN deliveries d
                    ON dp.delivery_person_id = d.delivery_person_id
                SET dp.is_available = TRUE
                WHERE d.order_id = %s
            """, (order_id,))

        if new_status == "Cancelled":
            cursor.execute("""
                UPDATE deliveries
                SET delivery_status = 'Cancelled'
                WHERE order_id = %s
                  AND delivery_status != 'Delivered'
            """, (order_id,))

            cursor.execute("""
                UPDATE delivery_persons dp
                JOIN deliveries d
                    ON dp.delivery_person_id = d.delivery_person_id
                SET dp.is_available = TRUE
                WHERE d.order_id = %s
            """, (order_id,))

        conn.commit()

        return jsonify({
            "message": (
                f"Order #{order_id} status updated to {new_status}."
            ),
            "order_id": order_id,
            "order_status": new_status
        })

    except mysql.connector.Error:
        if conn is not None:
            conn.rollback()

        app.logger.exception("Failed to update order status")

        return jsonify({
            "error": "Could not update order status."
        }), 500

    finally:
        if cursor is not None:
            cursor.close()
        if conn is not None and conn.is_connected():
            conn.close()


# ============================================================
# DELIVERY MANAGEMENT APIs
# ============================================================

# -------------------- LIST DELIVERY PERSONNEL --------------------

@app.route("/api/admin/delivery-persons", methods=["GET"])
@admin_required
def get_delivery_persons():
    conn = None
    cursor = None

    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("""
            SELECT delivery_person_id,
                   name,
                   phone,
                   is_available
            FROM delivery_persons
            ORDER BY name
        """)

        people = cursor.fetchall()

        for person in people:
            person["is_available"] = bool(person["is_available"])

        return jsonify(people)

    except mysql.connector.Error:
        app.logger.exception("Failed to load delivery personnel")

        return jsonify({
            "error": "Unable to load delivery personnel."
        }), 500

    finally:
        if cursor is not None:
            cursor.close()
        if conn is not None and conn.is_connected():
            conn.close()


# -------------------- ADD DELIVERY PERSONNEL --------------------

@app.route("/api/admin/delivery-persons", methods=["POST"])
@admin_required
def add_delivery_person():
    data = request.get_json(silent=True) or {}

    name = str(data.get("name", "")).strip()
    phone = str(data.get("phone", "")).strip()

    if not name or not phone:
        return jsonify({
            "error": "Name and phone number are required."
        }), 400

    if len(name) > 100 or len(phone) > 15:
        return jsonify({
            "error": "Name or phone number is too long."
        }), 400

    conn = None
    cursor = None

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO delivery_persons (name, phone)
            VALUES (%s, %s)
        """, (name, phone))

        person_id = cursor.lastrowid
        conn.commit()

        return jsonify({
            "message": "Delivery person added successfully.",
            "delivery_person_id": person_id,
            "name": name,
            "phone": phone
        }), 201

    except mysql.connector.Error:
        if conn is not None:
            conn.rollback()

        app.logger.exception("Failed to add delivery person")

        return jsonify({
            "error": "Could not add delivery person."
        }), 500

    finally:
        if cursor is not None:
            cursor.close()
        if conn is not None and conn.is_connected():
            conn.close()


# -------------------- LIST DELIVERIES --------------------

@app.route("/api/admin/deliveries", methods=["GET"])
@admin_required
def get_deliveries():
    conn = None
    cursor = None

    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("""
            SELECT d.delivery_id,
                   d.order_id,
                   d.delivery_address,
                   d.building_details,
                   d.delivery_status,
                   d.assigned_at,
                   d.delivered_at,
                   o.order_status,
                   c.name AS customer_name,
                   c.phone AS customer_phone,
                   dp.delivery_person_id,
                   dp.name AS delivery_person_name,
                   dp.phone AS delivery_person_phone
            FROM deliveries d
            JOIN orders o
                ON d.order_id = o.order_id
            JOIN customers c
                ON o.customer_id = c.customer_id
            LEFT JOIN delivery_persons dp
                ON d.delivery_person_id = dp.delivery_person_id
            ORDER BY d.delivery_id DESC
        """)

        deliveries = cursor.fetchall()

        for delivery in deliveries:
            for field in ("assigned_at", "delivered_at"):
                if delivery[field] is not None:
                    delivery[field] = delivery[field].isoformat(
                        sep=" ", timespec="seconds"
                    )

        return jsonify(deliveries)

    except mysql.connector.Error:
        app.logger.exception("Failed to load deliveries")

        return jsonify({
            "error": "Unable to load deliveries."
        }), 500

    finally:
        if cursor is not None:
            cursor.close()
        if conn is not None and conn.is_connected():
            conn.close()


# -------------------- ASSIGN DELIVERY PERSON --------------------

@app.route("/api/admin/deliveries/assign", methods=["POST"])
@app.route("/api/admin/deliveries", methods=["POST"])
@admin_required
def assign_delivery():
    data = request.get_json(silent=True) or {}

    try:
        order_id = int(data.get("order_id"))
        person_id = int(data.get("delivery_person_id"))
    except (TypeError, ValueError):
        return jsonify({
            "error": "Valid order ID and delivery person ID are required."
        }), 400

    address = str(data.get("delivery_address", "")).strip()
    building = str(data.get("building_details", "")).strip()

    if len(address) > 255 or len(building) > 150:
        return jsonify({
            "error": "Delivery address details are too long."
        }), 400

    conn = None
    cursor = None

    try:
        conn = get_db_connection()
        conn.start_transaction()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("""
            SELECT order_status
            FROM orders
            WHERE order_id = %s
            FOR UPDATE
        """, (order_id,))

        order = cursor.fetchone()

        if order is None:
            conn.rollback()
            return jsonify({"error": "Order not found."}), 404

        if order["order_status"] not in ("Pending", "Preparing"):
            conn.rollback()
            return jsonify({
                "error": (
                    "Only pending or preparing orders can be assigned."
                )
            }), 409

        cursor.execute("""
            SELECT delivery_person_id, name
            FROM delivery_persons
            WHERE delivery_person_id = %s
              AND is_available = TRUE
            FOR UPDATE
        """, (person_id,))

        person = cursor.fetchone()

        if person is None:
            conn.rollback()
            return jsonify({
                "error": "Delivery person not found or unavailable."
            }), 409

        cursor.execute("""
            SELECT delivery_id,
                   delivery_person_id,
                   delivery_status
            FROM deliveries
            WHERE order_id = %s
            FOR UPDATE
        """, (order_id,))

        delivery = cursor.fetchone()

        if delivery is not None and delivery["delivery_status"] in (
            "Delivered", "Cancelled", "Picked Up", "Out for Delivery"
        ):
            conn.rollback()
            return jsonify({
                "error": (
                    "This delivery has already progressed "
                    "and cannot be reassigned."
                )
            }), 409

        if (
            delivery is not None
            and delivery["delivery_person_id"] is not None
        ):
            cursor.execute("""
                UPDATE delivery_persons
                SET is_available = TRUE
                WHERE delivery_person_id = %s
            """, (delivery["delivery_person_id"],))

        cursor.execute("""
            INSERT INTO deliveries (
                order_id,
                delivery_person_id,
                delivery_address,
                building_details,
                delivery_status,
                assigned_at
            )
            VALUES (%s, %s, %s, %s, 'Assigned', NOW())
            ON DUPLICATE KEY UPDATE
                delivery_person_id = VALUES(delivery_person_id),
                delivery_address = VALUES(delivery_address),
                building_details = VALUES(building_details),
                delivery_status = 'Assigned',
                assigned_at = NOW(),
                delivered_at = NULL
        """, (
            order_id,
            person_id,
            address or "Address not provided",
            building or None
        ))

        cursor.execute("""
            UPDATE delivery_persons
            SET is_available = FALSE
            WHERE delivery_person_id = %s
        """, (person_id,))

        conn.commit()

        return jsonify({
            "message": (
                f"Order #{order_id} assigned to "
                f"{person['name']} successfully."
            )
        }), 200

    except mysql.connector.Error:
        if conn is not None:
            conn.rollback()

        app.logger.exception("Failed to assign delivery")

        return jsonify({
            "error": "Could not assign delivery."
        }), 500

    finally:
        if cursor is not None:
            cursor.close()
        if conn is not None and conn.is_connected():
            conn.close()


# -------------------- UPDATE DELIVERY STATUS --------------------

@app.route(
    "/api/admin/deliveries/<int:delivery_id>/status",
    methods=["PATCH"]
)
@admin_required
def update_delivery_status(delivery_id):
    data = request.get_json(silent=True) or {}
    new_status = data.get("delivery_status")

    allowed_statuses = (
        "Picked Up",
        "Out for Delivery",
        "Delivered",
        "Cancelled"
    )

    if new_status not in allowed_statuses:
        return jsonify({"error": "Invalid delivery status."}), 400

    conn = None
    cursor = None

    try:
        conn = get_db_connection()
        conn.start_transaction()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("""
            SELECT d.delivery_status,
                   d.delivery_person_id,
                   d.order_id,
                   o.order_status
            FROM deliveries d
            JOIN orders o
                ON d.order_id = o.order_id
            WHERE d.delivery_id = %s
            FOR UPDATE
        """, (delivery_id,))

        delivery = cursor.fetchone()

        if delivery is None:
            conn.rollback()
            return jsonify({"error": "Delivery not found."}), 404

        current = delivery["delivery_status"]

        allowed_transitions = {
            "Unassigned": (),
            "Assigned": ("Picked Up", "Cancelled"),
            "Picked Up": ("Out for Delivery", "Cancelled"),
            "Out for Delivery": ("Delivered", "Cancelled"),
            "Delivered": (),
            "Cancelled": ()
        }

        if new_status not in allowed_transitions[current]:
            conn.rollback()
            return jsonify({
                "error": (
                    f"Cannot change delivery status from {current} "
                    f"to {new_status}."
                )
            }), 409

        if new_status in (
            "Picked Up", "Out for Delivery", "Delivered"
        ):
            if delivery["delivery_person_id"] is None:
                conn.rollback()
                return jsonify({
                    "error": (
                        "Assign a delivery person before "
                        "progressing this delivery."
                    )
                }), 409

        if (
            new_status == "Delivered"
            and delivery["order_status"] == "Cancelled"
        ):
            conn.rollback()
            return jsonify({
                "error": "A cancelled order cannot be delivered."
            }), 409

        if new_status == "Delivered":
            cursor.execute("""
                UPDATE deliveries
                SET delivery_status = 'Delivered',
                    delivered_at = NOW()
                WHERE delivery_id = %s
            """, (delivery_id,))

            cursor.execute("""
                UPDATE orders
                SET order_status = 'Delivered'
                WHERE order_id = %s
                  AND order_status IN ('Pending', 'Preparing')
            """, (delivery["order_id"],))

            cursor.execute("""
                UPDATE delivery_persons
                SET is_available = TRUE
                WHERE delivery_person_id = %s
            """, (delivery["delivery_person_id"],))

        elif new_status == "Cancelled":
            cursor.execute("""
                UPDATE deliveries
                SET delivery_status = 'Cancelled'
                WHERE delivery_id = %s
            """, (delivery_id,))

            if delivery["delivery_person_id"] is not None:
                cursor.execute("""
                    UPDATE delivery_persons
                    SET is_available = TRUE
                    WHERE delivery_person_id = %s
                """, (delivery["delivery_person_id"],))

        else:
            cursor.execute("""
                UPDATE deliveries
                SET delivery_status = %s
                WHERE delivery_id = %s
            """, (new_status, delivery_id))

        conn.commit()

        return jsonify({
            "message": f"Delivery status updated to {new_status}.",
            "delivery_id": delivery_id,
            "delivery_status": new_status
        }), 200

    except mysql.connector.Error:
        if conn is not None:
            conn.rollback()

        app.logger.exception("Failed to update delivery status")

        return jsonify({
            "error": "Could not update delivery status."
        }), 500

    finally:
        if cursor is not None:
            cursor.close()
        if conn is not None and conn.is_connected():
            conn.close()


# ============================================================
# ADMIN MENU MANAGEMENT APIs
# ============================================================

# -------------------- LIST RESTAURANTS FOR ADMIN --------------------

@app.route("/api/admin/restaurants", methods=["GET"])
@admin_required
def admin_get_restaurants():
    conn = None
    cursor = None

    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("""
            SELECT restaurant_id, name
            FROM restaurants
            ORDER BY name
        """)

        return jsonify(cursor.fetchall())

    except mysql.connector.Error:
        app.logger.exception(
            "Failed to load restaurants for menu management"
        )

        return jsonify({
            "error": "Unable to load restaurants."
        }), 500

    finally:
        if cursor is not None:
            cursor.close()
        if conn is not None and conn.is_connected():
            conn.close()


# -------------------- LIST ALL MENU ITEMS FOR ADMIN --------------------

@app.route("/api/admin/menu", methods=["GET"])
@admin_required
def admin_get_menu():
    conn = None
    cursor = None

    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("""
            SELECT m.item_id,
                   m.restaurant_id,
                   r.name AS restaurant,
                   m.item_name,
                   m.category,
                   m.price,
                   m.available
            FROM menu_items m
            JOIN restaurants r
                ON r.restaurant_id = m.restaurant_id
            ORDER BY r.name, m.item_name
        """)

        items = cursor.fetchall()

        for item in items:
            item["price"] = float(item["price"])
            item["available"] = bool(item["available"])

        return jsonify(items)

    except mysql.connector.Error:
        app.logger.exception("Failed to load admin menu")

        return jsonify({
            "error": "Unable to load menu items."
        }), 500

    finally:
        if cursor is not None:
            cursor.close()
        if conn is not None and conn.is_connected():
            conn.close()


# -------------------- ADD MENU ITEM --------------------

@app.route("/api/admin/menu", methods=["POST"])
@admin_required
def admin_add_menu_item():
    data = request.get_json(silent=True) or {}

    item_name = str(data.get("item_name", "")).strip()
    category = str(data.get("category", "")).strip()

    try:
        restaurant_id = int(data.get("restaurant_id"))
        price = float(data.get("price"))
    except (TypeError, ValueError):
        return jsonify({
            "error": "Choose a restaurant and enter a valid price."
        }), 400

    if not item_name or len(item_name) > 150:
        return jsonify({
            "error": (
                "Food name is required and must be "
                "150 characters or fewer."
            )
        }), 400

    if len(category) > 100:
        return jsonify({
            "error": "Category must be 100 characters or fewer."
        }), 400

    if price <= 0 or price > 100000:
        return jsonify({
            "error": (
                "Price must be greater than ₹0 "
                "and no more than ₹100,000."
            )
        }), 400

    available = data.get("available", True)

    if not isinstance(available, bool):
        return jsonify({
            "error": "Availability must be true or false."
        }), 400

    conn = None
    cursor = None

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT restaurant_id
            FROM restaurants
            WHERE restaurant_id = %s
        """, (restaurant_id,))

        if cursor.fetchone() is None:
            return jsonify({
                "error": "Selected restaurant was not found."
            }), 404

        cursor.execute("""
            INSERT INTO menu_items (
                restaurant_id,
                item_name,
                category,
                price,
                available
            )
            VALUES (%s, %s, %s, %s, %s)
        """, (
            restaurant_id,
            item_name,
            category or None,
            round(price, 2),
            available
        ))

        item_id = cursor.lastrowid
        conn.commit()

        return jsonify({
            "message": "Food item added successfully.",
            "item_id": item_id
        }), 201

    except mysql.connector.Error:
        if conn is not None:
            conn.rollback()

        app.logger.exception("Failed to add menu item")

        return jsonify({
            "error": (
                "Could not add food item. Check the restaurant "
                "and database fields."
            )
        }), 500

    finally:
        if cursor is not None:
            cursor.close()
        if conn is not None and conn.is_connected():
            conn.close()


# -------------------- UPDATE MENU ITEM --------------------

@app.route("/api/admin/menu/<int:item_id>", methods=["PATCH"])
@admin_required
def admin_update_menu_item(item_id):
    data = request.get_json(silent=True) or {}

    allowed_fields = {
        "item_name",
        "category",
        "price",
        "available",
        "restaurant_id"
    }

    updates = {}

    if not data or any(key not in allowed_fields for key in data):
        return jsonify({
            "error": "Provide valid menu fields to update."
        }), 400

    if "item_name" in data:
        name = str(data["item_name"]).strip()

        if not name or len(name) > 150:
            return jsonify({
                "error": (
                    "Food name is required and must be "
                    "150 characters or fewer."
                )
            }), 400

        updates["item_name"] = name

    if "category" in data:
        category = str(data["category"] or "").strip()

        if len(category) > 100:
            return jsonify({
                "error": "Category must be 100 characters or fewer."
            }), 400

        updates["category"] = category or None

    if "price" in data:
        try:
            price = float(data["price"])
        except (TypeError, ValueError):
            return jsonify({"error": "Enter a valid price."}), 400

        if price <= 0 or price > 100000:
            return jsonify({
                "error": (
                    "Price must be greater than ₹0 "
                    "and no more than ₹100,000."
                )
            }), 400

        updates["price"] = round(price, 2)

    if "available" in data:
        if not isinstance(data["available"], bool):
            return jsonify({
                "error": "Availability must be true or false."
            }), 400

        updates["available"] = data["available"]

    if "restaurant_id" in data:
        try:
            updates["restaurant_id"] = int(data["restaurant_id"])
        except (TypeError, ValueError):
            return jsonify({
                "error": "Choose a valid restaurant."
            }), 400

    if not updates:
        return jsonify({
            "error": "No valid changes were provided."
        }), 400

    conn = None
    cursor = None

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        if "restaurant_id" in updates:
            cursor.execute("""
                SELECT restaurant_id
                FROM restaurants
                WHERE restaurant_id = %s
            """, (updates["restaurant_id"],))

            if cursor.fetchone() is None:
                return jsonify({
                    "error": "Selected restaurant was not found."
                }), 404

        fields = ", ".join(
            f"{field} = %s" for field in updates
        )

        values = list(updates.values()) + [item_id]

        cursor.execute(
            f"UPDATE menu_items SET {fields} WHERE item_id = %s",
            values
        )

        if cursor.rowcount == 0:
            cursor.execute("""
                SELECT item_id
                FROM menu_items
                WHERE item_id = %s
            """, (item_id,))

            if cursor.fetchone() is None:
                conn.rollback()
                return jsonify({
                    "error": "Food item not found."
                }), 404

        conn.commit()

        return jsonify({
            "message": "Food item updated successfully.",
            "item_id": item_id
        })

    except mysql.connector.Error:
        if conn is not None:
            conn.rollback()

        app.logger.exception("Failed to update menu item")

        return jsonify({
            "error": "Could not update food item."
        }), 500

    finally:
        if cursor is not None:
            cursor.close()
        if conn is not None and conn.is_connected():
            conn.close()


# -------------------- REMOVE MENU ITEM --------------------
# Soft-delete: mark unavailable so order history is preserved.

@app.route("/api/admin/menu/<int:item_id>", methods=["DELETE"])
@admin_required
def admin_delete_menu_item(item_id):
    conn = None
    cursor = None

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE menu_items
            SET available = FALSE
            WHERE item_id = %s
        """, (item_id,))

        if cursor.rowcount == 0:
            cursor.execute("""
                SELECT item_id
                FROM menu_items
                WHERE item_id = %s
            """, (item_id,))

            if cursor.fetchone() is None:
                conn.rollback()
                return jsonify({
                    "error": "Food item not found."
                }), 404

        conn.commit()

        return jsonify({
            "message": "Food item removed from customer menu."
        })

    except mysql.connector.Error:
        if conn is not None:
            conn.rollback()

        app.logger.exception("Failed to remove menu item")

        return jsonify({
            "error": "Could not remove food item."
        }), 500

    finally:
        if cursor is not None:
            cursor.close()
        if conn is not None and conn.is_connected():
            conn.close()


# -------------------- RUN APPLICATION --------------------

if __name__ == "__main__":
    app.run(debug=True)

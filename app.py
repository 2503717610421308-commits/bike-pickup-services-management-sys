import os
import re
import sqlite3
from datetime import date
from functools import wraps

from flask import (Flask, abort, flash, g, redirect, render_template, request,
                   session, url_for)
from werkzeug.security import check_password_hash, generate_password_hash

from database.init_db import init_db

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "database.db")

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "bike-service-dev-secret-change-me")

BOOKING_STATUSES = ["Pending", "Confirmed", "Pickup Scheduled", "Bike Received",
                    "Service In Progress", "Completed", "Cancelled"]
PICKUP_STATUSES = ["Requested", "Assigned", "Picked Up", "At Service Center",
                   "Delivered", "Cancelled"]
TRACKER_STEPS = ["Pending", "Confirmed", "Pickup Scheduled", "Bike Received",
                 "Service In Progress", "Completed"]
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


# ---------------------------------------------------------------- database
def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(_exc):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def query(sql, args=(), one=False):
    cur = get_db().execute(sql, args)
    rows = cur.fetchall()
    return (rows[0] if rows else None) if one else rows


def execute(sql, args=()):
    db = get_db()
    cur = db.execute(sql, args)
    db.commit()
    return cur


# -------------------------------------------------------------- decorators
def login_required(f):
    @wraps(f)
    def wrapper(*a, **kw):
        if "user_id" not in session:
            flash("Please log in to continue.", "warning")
            return redirect(url_for("login"))
        return f(*a, **kw)
    return wrapper


def admin_required(f):
    @wraps(f)
    @login_required
    def wrapper(*a, **kw):
        if session.get("role") != "admin":
            abort(403)
        return f(*a, **kw)
    return wrapper


def customer_required(f):
    @wraps(f)
    @login_required
    def wrapper(*a, **kw):
        if session.get("role") != "customer":
            abort(403)
        return f(*a, **kw)
    return wrapper


@app.template_filter("badge")
def badge_filter(status):
    return "status-" + str(status).lower().replace(" ", "-")


@app.context_processor
def inject_globals():
    return {"booking_statuses": BOOKING_STATUSES, "pickup_statuses": PICKUP_STATUSES,
            "today": date.today().isoformat()}


# ------------------------------------------------------------------ public
@app.route("/")
def index():
    services = query("SELECT * FROM services ORDER BY id")
    return render_template("index.html", services=services)


@app.route("/register", methods=["GET", "POST"])
def register():
    if "user_id" in session:
        return redirect(url_for("login"))
    errors, form = {}, {}
    if request.method == "POST":
        form = {k: request.form.get(k, "").strip() for k in ("name", "email", "phone")}
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")
        form["email"] = form["email"].lower()
        if not form["name"]:
            errors["name"] = "Full name is required."
        if not form["email"]:
            errors["email"] = "Email is required."
        elif not EMAIL_RE.match(form["email"]):
            errors["email"] = "Enter a valid email address."
        elif query("SELECT id FROM users WHERE email = ?", (form["email"],), one=True):
            errors["email"] = "This email is already registered."
        digits = re.sub(r"\D", "", form["phone"])
        if not form["phone"]:
            errors["phone"] = "Phone number is required."
        elif not re.fullmatch(r"\+?[0-9\s\-]+", form["phone"]) or not 10 <= len(digits) <= 13:
            errors["phone"] = "Enter a valid phone number (10-13 digits)."
        if not password:
            errors["password"] = "Password is required."
        elif len(password) < 6:
            errors["password"] = "Password must be at least 6 characters."
        if not confirm:
            errors["confirm_password"] = "Please confirm your password."
        elif password != confirm:
            errors["confirm_password"] = "Passwords do not match."
        if not errors:
            execute("INSERT INTO users (name, email, phone, password, role) VALUES (?,?,?,?, 'customer')",
                    (form["name"], form["email"], form["phone"], generate_password_hash(password)))
            flash("Registration successful! Please log in.", "success")
            return redirect(url_for("login"))
    return render_template("register.html", errors=errors, form=form)


@app.route("/login", methods=["GET", "POST"])
def login():
    if "user_id" in session:
        return redirect(url_for("admin_dashboard" if session["role"] == "admin" else "customer_dashboard"))
    error, email = None, ""
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = query("SELECT * FROM users WHERE email = ?", (email,), one=True)
        if user and check_password_hash(user["password"], password):
            session.clear()
            session.update(user_id=user["id"], name=user["name"], role=user["role"])
            flash(f"Welcome back, {user['name']}!", "success")
            return redirect(url_for("admin_dashboard" if user["role"] == "admin" else "customer_dashboard"))
        error = "Invalid email or password. Please try again."
    return render_template("login.html", error=error, email=email)


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("index"))


# ---------------------------------------------------------------- customer
@app.route("/customer/dashboard")
@customer_required
def customer_dashboard():
    uid = session["user_id"]
    count = lambda sql: query(sql, (uid,), one=True)[0]
    stats = {
        "bikes": count("SELECT COUNT(*) FROM bikes WHERE user_id=?"),
        "bookings": count("SELECT COUNT(*) FROM bookings WHERE user_id=?"),
        "pending": count("SELECT COUNT(*) FROM bookings WHERE user_id=? AND status='Pending'"),
        "completed": count("SELECT COUNT(*) FROM bookings WHERE user_id=? AND status='Completed'"),
    }
    recent = query("""SELECT b.*, bk.bike_number, s.service_name FROM bookings b
                      JOIN bikes bk ON bk.id=b.bike_id JOIN services s ON s.id=b.service_id
                      WHERE b.user_id=? ORDER BY b.id DESC LIMIT 5""", (uid,))
    return render_template("customer_dashboard.html", stats=stats, recent=recent)


@app.route("/customer/bikes")
@customer_required
def customer_bikes():
    bikes = query("SELECT * FROM bikes WHERE user_id=? ORDER BY id DESC", (session["user_id"],))
    return render_template("add_bike.html", bikes=bikes, errors={}, form={})


@app.route("/customer/bikes/add", methods=["GET", "POST"])
@customer_required
def add_bike():
    uid = session["user_id"]
    errors, form = {}, {}
    if request.method == "POST":
        form = {k: request.form.get(k, "").strip() for k in ("bike_number", "brand", "model", "year", "color")}
        form["bike_number"] = form["bike_number"].upper()
        for k, label in (("bike_number", "Bike number"), ("brand", "Brand"), ("model", "Model"),
                         ("year", "Year"), ("color", "Color")):
            if not form[k]:
                errors[k] = f"{label} is required."
        if "bike_number" not in errors and query("SELECT id FROM bikes WHERE bike_number=?",
                                                 (form["bike_number"],), one=True):
            errors["bike_number"] = "A bike with this number is already registered."
        if "year" not in errors:
            if not form["year"].isdigit() or not 1980 <= int(form["year"]) <= date.today().year + 1:
                errors["year"] = f"Enter a valid year (1980-{date.today().year + 1})."
        if not errors:
            execute("INSERT INTO bikes (user_id, bike_number, brand, model, year, color) VALUES (?,?,?,?,?,?)",
                    (uid, form["bike_number"], form["brand"], form["model"], int(form["year"]), form["color"]))
            flash("Bike added successfully!", "success")
            return redirect(url_for("customer_dashboard"))
    bikes = query("SELECT * FROM bikes WHERE user_id=? ORDER BY id DESC", (uid,))
    return render_template("add_bike.html", bikes=bikes, errors=errors, form=form)


@app.route("/customer/service/book", methods=["GET", "POST"])
@customer_required
def book_service():
    uid = session["user_id"]
    bikes = query("SELECT * FROM bikes WHERE user_id=? ORDER BY brand", (uid,))
    services = query("SELECT * FROM services ORDER BY service_name")
    errors, form = {}, {}
    if not bikes:
        flash("Please add a bike before booking a service.", "warning")
        return redirect(url_for("add_bike"))
    if request.method == "POST":
        form = {k: request.form.get(k, "").strip() for k in
                ("bike_id", "service_id", "booking_date", "preferred_time", "problem_description")}
        bike = query("SELECT id FROM bikes WHERE id=? AND user_id=?",
                     (form["bike_id"] or 0, uid), one=True)
        service = query("SELECT * FROM services WHERE id=?", (form["service_id"] or 0,), one=True)
        if not bike:
            errors["bike_id"] = "Select one of your bikes."
        if not service:
            errors["service_id"] = "Select a service."
        if not form["booking_date"]:
            errors["booking_date"] = "Choose a booking date."
        elif form["booking_date"] < date.today().isoformat():
            errors["booking_date"] = "Booking date cannot be in the past."
        if not form["preferred_time"]:
            errors["preferred_time"] = "Choose a preferred time."
        if not errors:
            execute("""INSERT INTO bookings (user_id, bike_id, service_id, booking_date, preferred_time,
                       problem_description, estimated_cost, status) VALUES (?,?,?,?,?,?,?, 'Pending')""",
                    (uid, bike["id"], service["id"], form["booking_date"], form["preferred_time"],
                     form["problem_description"], service["price"]))
            flash("Service booked successfully! Status: Pending.", "success")
            return redirect(url_for("my_bookings"))
    return render_template("book_service.html", bikes=bikes, services=services, errors=errors, form=form)


@app.route("/customer/pickup/request", methods=["GET", "POST"])
@customer_required
def pickup_request():
    uid = session["user_id"]
    bookings = query("""SELECT b.id, bk.bike_number, s.service_name, b.booking_date FROM bookings b
                        JOIN bikes bk ON bk.id=b.bike_id JOIN services s ON s.id=b.service_id
                        WHERE b.user_id=? AND b.status != 'Cancelled'
                        AND b.id NOT IN (SELECT booking_id FROM pickups WHERE status != 'Cancelled')
                        ORDER BY b.id DESC""", (uid,))
    errors, form = {}, {"booking_id": request.args.get("booking_id", "")}
    if request.method == "POST":
        form = {k: request.form.get(k, "").strip() for k in
                ("booking_id", "pickup_address", "pickup_date", "pickup_time", "contact_phone")}
        booking = query("SELECT * FROM bookings WHERE id=? AND user_id=?",
                        (form["booking_id"] or 0, uid), one=True)
        if not booking:
            errors["booking_id"] = "Select a valid booking."
        elif booking["status"] == "Cancelled":
            errors["booking_id"] = "Pickup cannot be requested for a cancelled booking."
        elif query("SELECT id FROM pickups WHERE booking_id=? AND status != 'Cancelled'",
                   (booking["id"],), one=True):
            errors["booking_id"] = "A pickup is already requested for this booking."
        if len(form["pickup_address"]) < 10:
            errors["pickup_address"] = "Enter the full pickup address (at least 10 characters)."
        if not form["pickup_date"]:
            errors["pickup_date"] = "Choose a pickup date."
        elif form["pickup_date"] < date.today().isoformat():
            errors["pickup_date"] = "Pickup date cannot be in the past."
        if not form["pickup_time"]:
            errors["pickup_time"] = "Choose a pickup time."
        digits = re.sub(r"\D", "", form["contact_phone"])
        if not re.fullmatch(r"\+?[0-9\s\-]+", form["contact_phone"]) or not 10 <= len(digits) <= 13:
            errors["contact_phone"] = "Enter a valid contact phone (10-13 digits)."
        if not errors:
            execute("""INSERT INTO pickups (booking_id, user_id, pickup_address, pickup_date, pickup_time,
                       contact_phone, status) VALUES (?,?,?,?,?,?, 'Requested')""",
                    (booking["id"], uid, form["pickup_address"], form["pickup_date"],
                     form["pickup_time"], form["contact_phone"]))
            flash("Pickup requested successfully!", "success")
            return redirect(url_for("booking_details", booking_id=booking["id"]))
    elif not form.get("contact_phone"):
        form["contact_phone"] = query("SELECT phone FROM users WHERE id=?", (uid,), one=True)["phone"]
    return render_template("pickup_request.html", bookings=bookings, errors=errors, form=form)


@app.route("/customer/bookings")
@customer_required
def my_bookings():
    rows = query("""SELECT b.*, bk.bike_number, bk.brand, bk.model, s.service_name FROM bookings b
                    JOIN bikes bk ON bk.id=b.bike_id JOIN services s ON s.id=b.service_id
                    WHERE b.user_id=? ORDER BY b.id DESC""", (session["user_id"],))
    return render_template("my_bookings.html", bookings=rows)


@app.route("/customer/booking/<int:booking_id>")
@customer_required
def booking_details(booking_id):
    booking = query("""SELECT b.*, u.name AS customer_name, u.email, u.phone,
                       bk.bike_number, bk.brand, bk.model, bk.year, bk.color,
                       s.service_name, s.description, s.price, s.estimated_days
                       FROM bookings b JOIN users u ON u.id=b.user_id
                       JOIN bikes bk ON bk.id=b.bike_id JOIN services s ON s.id=b.service_id
                       WHERE b.id=? AND b.user_id=?""", (booking_id, session["user_id"]), one=True)
    if not booking:
        abort(404)
    pickup = query("SELECT * FROM pickups WHERE booking_id=? ORDER BY id DESC LIMIT 1", (booking_id,), one=True)
    current = TRACKER_STEPS.index(booking["status"]) if booking["status"] in TRACKER_STEPS else -1
    return render_template("booking_details.html", b=booking, pickup=pickup,
                           steps=TRACKER_STEPS, current=current)


# ------------------------------------------------------------------- admin
@app.route("/admin/dashboard")
@admin_required
def admin_dashboard():
    c = lambda sql: query(sql, one=True)[0]
    stats = {
        "customers": c("SELECT COUNT(*) FROM users WHERE role='customer'"),
        "bikes": c("SELECT COUNT(*) FROM bikes"),
        "services": c("SELECT COUNT(*) FROM services"),
        "bookings": c("SELECT COUNT(*) FROM bookings"),
        "pending": c("SELECT COUNT(*) FROM bookings WHERE status='Pending'"),
        "pickups": c("SELECT COUNT(*) FROM pickups"),
        "completed": c("SELECT COUNT(*) FROM bookings WHERE status='Completed'"),
    }
    recent = query("""SELECT b.*, u.name AS customer_name, bk.bike_number, s.service_name FROM bookings b
                      JOIN users u ON u.id=b.user_id JOIN bikes bk ON bk.id=b.bike_id
                      JOIN services s ON s.id=b.service_id ORDER BY b.id DESC LIMIT 8""")
    return render_template("admin_dashboard.html", stats=stats, recent=recent)


@app.route("/admin/customers")
@admin_required
def manage_customers():
    rows = query("SELECT id, name, email, phone, created_at FROM users WHERE role='customer' ORDER BY id DESC")
    return render_template("manage_customers.html", customers=rows)


@app.route("/admin/customers/delete/<int:user_id>", methods=["POST"])
@admin_required
def delete_customer(user_id):
    user = query("SELECT role FROM users WHERE id=?", (user_id,), one=True)
    if not user:
        abort(404)
    if user["role"] == "admin" or user_id == session["user_id"]:
        flash("The admin account cannot be deleted.", "danger")
    else:
        execute("DELETE FROM users WHERE id=?", (user_id,))
        flash("Customer and all related data deleted.", "success")
    return redirect(url_for("manage_customers"))


@app.route("/admin/bikes")
@admin_required
def manage_bikes():
    rows = query("""SELECT bk.*, u.name AS customer_name FROM bikes bk
                    JOIN users u ON u.id=bk.user_id ORDER BY bk.id DESC""")
    return render_template("manage_bikes.html", bikes=rows)


@app.route("/admin/bikes/delete/<int:bike_id>", methods=["POST"])
@admin_required
def delete_bike(bike_id):
    if not query("SELECT id FROM bikes WHERE id=?", (bike_id,), one=True):
        abort(404)
    execute("DELETE FROM bikes WHERE id=?", (bike_id,))
    flash("Bike deleted (its bookings and pickups were removed too).", "success")
    return redirect(url_for("manage_bikes"))


def read_service_form():
    f = {k: request.form.get(k, "").strip() for k in ("service_name", "description", "price", "estimated_days")}
    errors = {}
    if not f["service_name"]:
        errors["service_name"] = "Service name is required."
    if not f["description"]:
        errors["description"] = "Description is required."
    try:
        if float(f["price"]) < 0:
            raise ValueError
    except ValueError:
        errors["price"] = "Enter a valid price."
    if not f["estimated_days"].isdigit() or int(f["estimated_days"]) < 1:
        errors["estimated_days"] = "Enter estimated days (1 or more)."
    return f, errors


@app.route("/admin/services")
@admin_required
def manage_services():
    return render_template("manage_services.html", services=query("SELECT * FROM services ORDER BY id"),
                           edit=None, form={}, errors={})


@app.route("/admin/services/add", methods=["GET", "POST"])
@admin_required
def add_service():
    if request.method == "GET":
        return redirect(url_for("manage_services"))
    f, errors = read_service_form()
    if not errors and query("SELECT id FROM services WHERE lower(service_name)=lower(?)",
                            (f["service_name"],), one=True):
        errors["service_name"] = "A service with this name already exists."
    if errors:
        return render_template("manage_services.html", services=query("SELECT * FROM services ORDER BY id"),
                               edit=None, form=f, errors=errors)
    execute("INSERT INTO services (service_name, description, price, estimated_days) VALUES (?,?,?,?)",
            (f["service_name"], f["description"], float(f["price"]), int(f["estimated_days"])))
    flash("Service added.", "success")
    return redirect(url_for("manage_services"))


@app.route("/admin/services/edit/<int:service_id>", methods=["GET", "POST"])
@admin_required
def edit_service(service_id):
    service = query("SELECT * FROM services WHERE id=?", (service_id,), one=True)
    if not service:
        abort(404)
    services = query("SELECT * FROM services ORDER BY id")
    if request.method == "GET":
        return render_template("manage_services.html", services=services, edit=service,
                               form=dict(service), errors={})
    f, errors = read_service_form()
    if not errors and query("SELECT id FROM services WHERE lower(service_name)=lower(?) AND id != ?",
                            (f["service_name"], service_id), one=True):
        errors["service_name"] = "Another service already uses this name."
    if errors:
        return render_template("manage_services.html", services=services, edit=service, form=f, errors=errors)
    execute("UPDATE services SET service_name=?, description=?, price=?, estimated_days=? WHERE id=?",
            (f["service_name"], f["description"], float(f["price"]), int(f["estimated_days"]), service_id))
    flash("Service updated.", "success")
    return redirect(url_for("manage_services"))


@app.route("/admin/services/delete/<int:service_id>", methods=["POST"])
@admin_required
def delete_service(service_id):
    if query("SELECT id FROM bookings WHERE service_id=? LIMIT 1", (service_id,), one=True):
        flash("This service has bookings and cannot be deleted.", "danger")
    else:
        execute("DELETE FROM services WHERE id=?", (service_id,))
        flash("Service deleted.", "success")
    return redirect(url_for("manage_services"))


@app.route("/admin/bookings")
@admin_required
def manage_bookings():
    rows = query("""SELECT b.*, u.name AS customer_name, bk.bike_number, bk.brand, bk.model, s.service_name
                    FROM bookings b JOIN users u ON u.id=b.user_id JOIN bikes bk ON bk.id=b.bike_id
                    JOIN services s ON s.id=b.service_id ORDER BY b.id DESC""")
    return render_template("manage_bookings.html", bookings=rows)


@app.route("/admin/bookings/update/<int:booking_id>", methods=["POST"])
@admin_required
def update_booking(booking_id):
    status = request.form.get("status")
    if status not in BOOKING_STATUSES:
        flash("Invalid status.", "danger")
    elif not query("SELECT id FROM bookings WHERE id=?", (booking_id,), one=True):
        abort(404)
    else:
        execute("UPDATE bookings SET status=? WHERE id=?", (status, booking_id))
        flash(f"Booking #{booking_id} updated to {status}.", "success")
    return redirect(url_for("manage_bookings"))


@app.route("/admin/pickups")
@admin_required
def manage_pickups():
    rows = query("""SELECT p.*, u.name AS customer_name FROM pickups p
                    JOIN users u ON u.id=p.user_id ORDER BY p.id DESC""")
    return render_template("manage_pickups.html", pickups=rows)


@app.route("/admin/pickups/update/<int:pickup_id>", methods=["POST"])
@admin_required
def update_pickup(pickup_id):
    status = request.form.get("status")
    if status not in PICKUP_STATUSES:
        flash("Invalid status.", "danger")
    elif not query("SELECT id FROM pickups WHERE id=?", (pickup_id,), one=True):
        abort(404)
    else:
        execute("UPDATE pickups SET status=? WHERE id=?", (status, pickup_id))
        flash(f"Pickup #{pickup_id} updated to {status}.", "success")
    return redirect(url_for("manage_pickups"))


# ------------------------------------------------------------------ errors
def error_page(code, title, message):
    return render_template("error.html", code=code, title=title, message=message), code


@app.errorhandler(403)
def forbidden(_e):
    return error_page(403, "Access denied", "You do not have permission to view this page.")


@app.errorhandler(404)
def not_found(_e):
    return error_page(404, "Page not found", "The page you are looking for does not exist.")


@app.errorhandler(500)
def server_error(_e):
    return error_page(500, "Something went wrong", "An unexpected error occurred. Please try again later.")


init_db(DB_PATH)

if __name__ == "__main__":
    app.run(debug=False, host="127.0.0.1", port=5000)

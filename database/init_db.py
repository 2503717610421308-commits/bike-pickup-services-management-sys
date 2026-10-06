"""Database initialisation. Safe to run many times - never deletes existing data."""
import os
import sqlite3
from datetime import date, timedelta
from werkzeug.security import generate_password_hash

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "database.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    phone TEXT NOT NULL,
    password TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'customer' CHECK (role IN ('customer','admin')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS bikes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    bike_number TEXT NOT NULL UNIQUE,
    brand TEXT NOT NULL,
    model TEXT NOT NULL,
    year INTEGER NOT NULL,
    color TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS services (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    service_name TEXT NOT NULL UNIQUE,
    description TEXT NOT NULL,
    price REAL NOT NULL,
    estimated_days INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS bookings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    bike_id INTEGER NOT NULL,
    service_id INTEGER NOT NULL,
    booking_date TEXT NOT NULL,
    preferred_time TEXT NOT NULL,
    problem_description TEXT,
    estimated_cost REAL NOT NULL,
    status TEXT NOT NULL DEFAULT 'Pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (bike_id) REFERENCES bikes(id) ON DELETE CASCADE,
    FOREIGN KEY (service_id) REFERENCES services(id) ON DELETE RESTRICT
);
CREATE TABLE IF NOT EXISTS pickups (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    booking_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    pickup_address TEXT NOT NULL,
    pickup_date TEXT NOT NULL,
    pickup_time TEXT NOT NULL,
    contact_phone TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'Requested',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (booking_id) REFERENCES bookings(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);
"""

DEFAULT_SERVICES = [
    ("General Service", "Complete check-up, cleaning, lubrication and minor adjustments.", 799, 1),
    ("Oil Change", "Engine oil and oil filter replacement with a quick performance check.", 499, 1),
    ("Brake Service", "Brake pad inspection, replacement, brake fluid and cable adjustment.", 599, 1),
    ("Engine Service", "Engine tuning, spark plug check, carburetor/injector cleaning.", 1999, 3),
    ("Chain Service", "Chain cleaning, lubrication, tension adjustment and sprocket inspection.", 349, 1),
    ("Battery Check", "Battery health test, terminal cleaning and charging system check.", 249, 1),
    ("Full Service", "Complete bike overhaul covering engine, brakes, chain, electricals and wash.", 3499, 4),
]


def init_db(db_path=DB_PATH):
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA)
    cur = conn.cursor()
    if not cur.execute("SELECT 1 FROM users WHERE email = ?", ("admin@bikecare.com",)).fetchone():
        cur.execute(
            "INSERT INTO users (name, email, phone, password, role) VALUES (?,?,?,?,?)",
            ("Administrator", "admin@bikecare.com", "9999999999",
             generate_password_hash("admin123"), "admin"),
        )
    if cur.execute("SELECT COUNT(*) FROM services").fetchone()[0] == 0:
        cur.executemany(
            "INSERT INTO services (service_name, description, price, estimated_days) VALUES (?,?,?,?)",
            DEFAULT_SERVICES,
        )

    demo_email = "demo@bikecare.com"
    demo_user = cur.execute("SELECT id FROM users WHERE email = ?", (demo_email,)).fetchone()
    if not demo_user:
        cur.execute(
            "INSERT INTO users (name, email, phone, password, role) VALUES (?,?,?,?, 'customer')",
            ("Demo Customer", demo_email, "9876543210",
             generate_password_hash("demo123")),
        )
        demo_user_id = cur.lastrowid
        bike_numbers = []
        for index in (1, 2):
            bike_number = f"DEMO-{demo_user_id}-{index:03d}"
            suffix = 1
            while cur.execute(
                "SELECT 1 FROM bikes WHERE bike_number = ?", (bike_number,)
            ).fetchone():
                bike_number = f"DEMO-{demo_user_id}-{index:03d}-{suffix}"
                suffix += 1
            bike_numbers.append(bike_number)
        cur.executemany(
            """INSERT INTO bikes (user_id, bike_number, brand, model, year, color)
               VALUES (?,?,?,?,?,?)""",
            [
                (demo_user_id, bike_numbers[0], "Honda", "Activa 6G", 2022, "Blue"),
                (demo_user_id, bike_numbers[1], "Royal Enfield", "Classic 350", 2021, "Black"),
            ],
        )
        bikes = {
            bike_number: bike_id
            for bike_id, bike_number in cur.execute(
                "SELECT id, bike_number FROM bikes WHERE user_id = ?", (demo_user_id,)
            )
        }
        services = {
            service_name: (service_id, price)
            for service_id, service_name, price in cur.execute(
                "SELECT id, service_name, price FROM services"
            )
        }
        general_service = (
            "General Service" if "General Service" in services else next(iter(services))
        )
        engine_service = "Engine Service" if "Engine Service" in services else general_service
        oil_service = "Oil Change" if "Oil Change" in services else general_service
        today = date.today()
        demo_bookings = [
            (bikes[bike_numbers[0]], general_service, today - timedelta(days=10),
             "Routine maintenance", "Completed"),
            (bikes[bike_numbers[1]], engine_service, today,
             "Engine inspection and tuning", "Service In Progress"),
            (bikes[bike_numbers[0]], oil_service, today + timedelta(days=2),
             "Oil change requested", "Pending"),
        ]
        booking_ids = []
        for bike_id, service_name, booking_date, problem, status in demo_bookings:
            service_id, price = services[service_name]
            cur.execute(
                """INSERT INTO bookings
                   (user_id, bike_id, service_id, booking_date, preferred_time,
                    problem_description, estimated_cost, status)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (demo_user_id, bike_id, service_id, booking_date.isoformat(),
                 "10:00", problem, price, status),
            )
            booking_ids.append(cur.lastrowid)
        cur.executemany(
            """INSERT INTO pickups
               (booking_id, user_id, pickup_address, pickup_date, pickup_time,
                contact_phone, status)
               VALUES (?,?,?,?,?,?,?)""",
            [
                   (booking_ids[0], demo_user_id,
                 "12 Demo Street, Bengaluru, Karnataka", (today - timedelta(days=10)).isoformat(),
                 "09:00", "9876543210", "Delivered"),
                   (booking_ids[1], demo_user_id,
                 "12 Demo Street, Bengaluru, Karnataka", today.isoformat(),
                 "09:30", "9876543210", "At Service Center"),
            ],
        )
    conn.commit()
    conn.close()


if __name__ == "__main__":
    init_db()
    print("Database initialised at", DB_PATH)

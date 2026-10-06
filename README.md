# Bike Pickup and Services Management System

A Flask + SQLite web application where customers register bikes, book services and request doorstep pickup, and an admin manages everything.

## Features
**Customer:** register, log in/out, add and view bikes, book a service (price and estimated days shown automatically), request pickup, track booking and pickup status with a visual progress tracker, view booking details and service history.

**Admin:** dashboard with totals, manage customers, bikes, services (add/edit/delete), bookings and pickups, and update booking/pickup status.

## Technologies Used
- HTML5, CSS3, JavaScript, Bootstrap 5, Bootstrap Icons
- Python, Flask, Werkzeug
- SQLite

## Project Structure
```
Bike_Pickup_Service_Management/
├── app.py
├── requirements.txt
├── database.db
├── README.md
├── templates/        (all HTML pages + error.html for 403/404/500)
├── static/
│   ├── css/style.css
│   ├── js/script.js
│   └── images/
└── database/init_db.py
```

## Installation
1. Install Python 3.9 or newer from python.org (tick "Add Python to PATH").
2. Extract the ZIP and open the `Bike_Pickup_Service_Management` folder in VS Code.
3. Open a terminal in VS Code (Terminal > New Terminal).

## Setup
```
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

## Database
SQLite is used. When you run `python app.py`, the app creates `database.db` if missing, creates all tables (users, bikes, services, bookings, pickups), adds the default admin and default services. Existing data is never deleted. You can also run `python database/init_db.py` on its own.

## Default Admin Login
Admin Email: admin@bikecare.com

Admin Password: admin123

(Passwords are stored hashed with Werkzeug.)

## Demo Customer Login
Email: demo@bikecare.com

Password: demo123

The demo customer includes sample bikes, service bookings and pickup history. These records are added only when the demo account does not already exist; normal database initialisation does not overwrite existing data.

## How to Run
```
python app.py
```
Then open: http://127.0.0.1:5000

An internet connection is needed for Bootstrap, Bootstrap Icons and fonts (loaded from a CDN).

## Customer Registration
Click **Register** on the home page or navbar, fill in name, email, phone and password (min 6 characters), then log in. Then: Add Bike > Book Service > Request Pickup > My Bookings.

## Admin Features
Dashboard, Customers (view/delete), Bikes (view/delete), Services (add/edit/delete), Bookings (update status), Pickups (update status).

## Customer Features
Dashboard, My Bikes, Add Bike, Book Service, Request Pickup, My Bookings, Booking Details with progress tracker, Logout.

## Troubleshooting
- **`python` not found:** reinstall Python with "Add to PATH", or try `py` instead of `python`.
- **Activation blocked in PowerShell:** run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`, or use Command Prompt.
- **`No module named flask`:** activate the venv and run `pip install -r requirements.txt`.
- **Port 5000 in use:** change `port=5000` at the bottom of `app.py`.
- **Page looks unstyled:** check your internet connection (Bootstrap CDN).
- **Reset all data:** stop the server, delete `database.db`, run `python app.py` again.

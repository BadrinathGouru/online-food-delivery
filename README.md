# 🍽️ FoodFlow — Online Food Delivery Management System

A full-stack online food delivery platform built with **Python (Flask)**, **MySQL**, and modern **vanilla JavaScript & CSS3**.

---

## ✨ Features

### 👤 Customer Portal
- **Common Landing Login (`/`):** Unified authentication interface supporting both **Customer** and **Admin** account types.
- **Customer Registration (`/signup`):** Password hashing with salt (Werkzeug PBKDF2).
- **Interactive Storefront (`/home`):**
  - Live food menu search by dish or restaurant name.
  - Category filtering (Biryani, Pizza, Burger, Noodles, Desserts, Beverages, etc.).
  - Real-time shopping cart with item increment, decrement, and subtotal calculation.
  - Checkout form capturing delivery address and apartment/building details.
  - Isolated customer order history with pending order cancellation.

### 🛠️ Admin Dashboard (`/admin`)
- **Key Metrics Overview:** Total orders, pending, preparing, delivered, and revenue counters.
- **Order Management:** View all customer orders and advance status (`Pending` ➔ `Preparing` ➔ `Delivered` / `Cancelled`).
- **Menu Management:** Add new food items, update pricing, toggle availability, and soft-delete items.
- **Delivery Staff & Fleet Tracking:** Register delivery personnel and assign orders with real-time availability tracking.

### 🔒 Security & Architecture
- **Role-Based Access Control (RBAC):** Customer routes (`/home`, `/api/orders`) and Admin routes (`/admin`, `/api/admin/...`) strictly enforce session roles.
- **CSRF Protection:** Double-submit / session-backed CSRF tokens validated on all state-changing HTTP methods (`POST`, `PUT`, `PATCH`, `DELETE`).
- **Timing-Safe Comparison:** `secrets.compare_digest` used for cryptographic checks.
- **Environment-Driven Configuration:** Configurable secret key, database credentials, and admin setup.

---

## 🚀 Quickstart

### 1. Prerequisites
- Python 3.10+
- MySQL Server running locally on port `3306`

### 2. Database Setup
Create the `food_delivery` database in MySQL and initialize the required tables:
```sql
CREATE DATABASE IF NOT EXISTS food_delivery;
USE food_delivery;

CREATE TABLE IF NOT EXISTS customers (
    customer_id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(255) NOT NULL UNIQUE,
    phone VARCHAR(15),
    password_hash VARCHAR(255)
);

CREATE TABLE IF NOT EXISTS restaurants (
    restaurant_id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL
);

CREATE TABLE IF NOT EXISTS menu_items (
    item_id INT AUTO_INCREMENT PRIMARY KEY,
    restaurant_id INT NOT NULL,
    item_name VARCHAR(150) NOT NULL,
    category VARCHAR(100),
    price DECIMAL(10,2) NOT NULL,
    available BOOLEAN DEFAULT TRUE,
    FOREIGN KEY (restaurant_id) REFERENCES restaurants(restaurant_id)
);

CREATE TABLE IF NOT EXISTS orders (
    order_id INT AUTO_INCREMENT PRIMARY KEY,
    customer_id INT NOT NULL,
    order_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    total_amount DECIMAL(10,2) NOT NULL,
    order_status ENUM('Pending', 'Preparing', 'Delivered', 'Cancelled') DEFAULT 'Pending',
    FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
);

CREATE TABLE IF NOT EXISTS order_items (
    order_item_id INT AUTO_INCREMENT PRIMARY KEY,
    order_id INT NOT NULL,
    item_id INT NOT NULL,
    quantity INT NOT NULL,
    unit_price DECIMAL(10,2) NOT NULL,
    FOREIGN KEY (order_id) REFERENCES orders(order_id) ON DELETE CASCADE,
    FOREIGN KEY (item_id) REFERENCES menu_items(item_id)
);

CREATE TABLE IF NOT EXISTS delivery_persons (
    delivery_person_id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    phone VARCHAR(15) NOT NULL,
    is_available BOOLEAN DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS deliveries (
    delivery_id INT AUTO_INCREMENT PRIMARY KEY,
    order_id INT NOT NULL UNIQUE,
    delivery_person_id INT NULL,
    delivery_address VARCHAR(255) NOT NULL,
    building_details VARCHAR(150),
    delivery_status ENUM('Unassigned', 'Assigned', 'Picked Up', 'Out for Delivery', 'Delivered', 'Cancelled') DEFAULT 'Unassigned',
    assigned_at DATETIME NULL,
    delivered_at DATETIME NULL,
    FOREIGN KEY (order_id) REFERENCES orders(order_id) ON DELETE CASCADE,
    FOREIGN KEY (delivery_person_id) REFERENCES delivery_persons(delivery_person_id) ON DELETE SET NULL
);
```

### 3. Install Dependencies
```powershell
pip install -r requirements.txt
```

### 4. Run the Application
```powershell
python app.py
```

Visit in your browser:
- **Landing & Login:** `http://127.0.0.1:5000/`
- **Customer Storefront:** `http://127.0.0.1:5000/home`
- **Admin Dashboard:** `http://127.0.0.1:5000/admin` *(Default: `admin` / `admin@123`)*

---

## 📁 Project Structure

```text
online-food-delivery/
├── app.py                  # Core Flask app, APIs, RBAC, CSRF, and routing
├── requirements.txt        # Python package dependencies
├── .env.example            # Environment variable template
├── .gitignore              # Git ignore rules
├── templates/
│   ├── login.html          # Common login page with Customer & Admin tabs
│   ├── signup.html         # Customer registration page
│   ├── index.html          # Customer storefront, cart & order history
│   ├── admin.html          # Administrator operational dashboard
│   └── admin_login.html    # Standalone admin login (backward-compatible)
└── static/
    ├── css/
    │   ├── style.css       # Customer storefront styling
    │   ├── auth.css        # Authentication pages styling
    │   └── admin.css       # Admin dashboard styling
    └── js/
        ├── script.js       # Customer menu, cart & ordering scripts
        └── admin.js        # Admin dashboard management scripts
```

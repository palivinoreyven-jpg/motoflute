import calendar
import random
import smtplib
from datetime import datetime
from email.message import EmailMessage

import MySQLdb.cursors
from flask import Flask, render_template, request, redirect, url_for, session
from flask_mysqldb import MySQL
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = 'motoflute_web_secret_key'

# Database Configuration
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = 'Adminven1!'
app.config['MYSQL_DB'] = 'inventory_db'
app.config['MYSQL_CURSORCLASS'] = 'DictCursor'

# SMTP / Email Configuration
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'palivinoreyven@gmail.com'
app.config['MAIL_PASSWORD'] = 'hdlwsuubiizjrjts'
SENDER_NAME = 'palivinoreyven@gmail.com'

mysql = MySQL(app)


def send_email(to_email, subject, body):
    try:
        msg = EmailMessage()
        msg.set_content(body)
        msg['Subject'] = subject
        msg['From'] = f"{SENDER_NAME} <{app.config['MAIL_USERNAME']}>"
        msg['To'] = to_email

        with smtplib.SMTP(app.config['MAIL_SERVER'], app.config['MAIL_PORT']) as server:
            server.starttls()
            server.login(app.config['MAIL_USERNAME'], app.config['MAIL_PASSWORD'])
            server.send_message(msg)
        return True
    except Exception as e:
        print(f"--> Failed to send email: {e}")
        return False


# 1. Main Dashboard Route (Hub with Analytics, Product Updates & Recent Transactions)
# 1. Main Dashboard Route (Hub with Analytics, Product Updates & Recent Transactions)
@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    role = session.get('role', 'staff')
    user_id = session.get('user_id')
    selected_staff_id = request.args.get('staff_id', 'all')

    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    # Get list of all staff for Admin filter dropdown
    staff_members = []
    if role == 'admin':
        cursor.execute("SELECT id, name FROM users WHERE role = 'staff' ORDER BY name ASC")
        staff_members = cursor.fetchall()

    # Determine filter target ID:
    # target_id is None -> All staff data (Overall Admin view)
    # target_id is int  -> Specific staff member's data
    if role == 'admin':
        if selected_staff_id != 'all' and selected_staff_id.isdigit():
            target_id = int(selected_staff_id)
        else:
            target_id = None
            selected_staff_id = 'all'
    else:
        target_id = user_id
        selected_staff_id = str(user_id)

    # 1. 7-Day Revenue Query
    if target_id is None:
        cursor.execute("""
            SELECT DATE(created_at) AS sale_date, COALESCE(SUM(total_amount), 0) AS daily_revenue
            FROM orders
            WHERE created_at >= CURDATE() - INTERVAL 6 DAY
            GROUP BY DATE(created_at)
            ORDER BY sale_date ASC
        """)
    else:
        cursor.execute("""
            SELECT DATE(created_at) AS sale_date, COALESCE(SUM(total_amount), 0) AS daily_revenue
            FROM orders
            WHERE staff_id = %s AND created_at >= CURDATE() - INTERVAL 6 DAY
            GROUP BY DATE(created_at)
            ORDER BY sale_date ASC
        """, (target_id,))
    
    rev_7days_data = cursor.fetchall()
    days_7_labels = [
        row['sale_date'].strftime('%b %d') if hasattr(row['sale_date'], 'strftime') else str(row['sale_date'])
        for row in rev_7days_data
    ]
    days_7_values = [float(row['daily_revenue']) for row in rev_7days_data]
    total_7days_revenue = sum(days_7_values)

    # 2. Monthly Revenue Query
    if target_id is None:
        cursor.execute("""
            SELECT YEAR(created_at) AS yr, MONTH(created_at) AS mth, COALESCE(SUM(total_amount), 0) AS monthly_revenue
            FROM orders
            WHERE created_at >= CURDATE() - INTERVAL 11 MONTH
            GROUP BY YEAR(created_at), MONTH(created_at)
            ORDER BY yr ASC, mth ASC
        """)
    else:
        cursor.execute("""
            SELECT YEAR(created_at) AS yr, MONTH(created_at) AS mth, COALESCE(SUM(total_amount), 0) AS monthly_revenue
            FROM orders
            WHERE staff_id = %s AND created_at >= CURDATE() - INTERVAL 11 MONTH
            GROUP BY YEAR(created_at), MONTH(created_at)
            ORDER BY yr ASC, mth ASC
        """, (target_id,))
    
    monthly_data = cursor.fetchall()
    monthly_labels = [f"{calendar.month_abbr[int(row['mth'])]} {row['yr']}" for row in monthly_data]
    monthly_values = [float(row['monthly_revenue']) for row in monthly_data]
    total_monthly_revenue = sum(monthly_values)

    # 3. Recent Transactions Query (Latest 10 Orders)
    if target_id is None:
        cursor.execute("""
            SELECT id, customer_name, total_amount, created_at 
            FROM orders ORDER BY id DESC LIMIT 10
        """)
    else:
        cursor.execute("""
            SELECT id, customer_name, total_amount, created_at 
            FROM orders WHERE staff_id = %s ORDER BY id DESC LIMIT 10
        """, (target_id,))
    recent_transactions = cursor.fetchall()

    # 4. Product Updates / New Additions Record Query
    if target_id is None:
        cursor.execute("""
            SELECT id, name, category, price, quantity 
            FROM products ORDER BY id DESC LIMIT 10
        """)
    else:
        cursor.execute("""
            SELECT id, name, category, price, quantity 
            FROM products WHERE user_id = %s ORDER BY id DESC LIMIT 10
        """, (target_id,))
    product_updates = cursor.fetchall()

    # 5. Peak Day Analysis Query
    if target_id is None:
        cursor.execute("""
            SELECT DAYNAME(created_at) AS day_name, COUNT(id) AS total_orders
            FROM orders GROUP BY DAYNAME(created_at), DAYOFWEEK(created_at)
            ORDER BY DAYOFWEEK(created_at) ASC
        """)
    else:
        cursor.execute("""
            SELECT DAYNAME(created_at) AS day_name, COUNT(id) AS total_orders
            FROM orders WHERE staff_id = %s
            GROUP BY DAYNAME(created_at), DAYOFWEEK(created_at)
            ORDER BY DAYOFWEEK(created_at) ASC
        """, (target_id,))
    peak_orders_data = cursor.fetchall()
    peak_day_labels = [row['day_name'] for row in peak_orders_data]
    peak_day_values = [int(row['total_orders']) for row in peak_orders_data]

    cursor.close()

    # Format transaction dates
    for tx in recent_transactions:
        if tx.get('created_at') and hasattr(tx['created_at'], 'strftime'):
            tx['formatted_date'] = tx['created_at'].strftime('%b %d, %Y %I:%M %p')
        else:
            tx['formatted_date'] = str(tx.get('created_at', 'N/A'))

    return render_template(
        'index.html',
        role=role,
        days_7_labels=days_7_labels,
        days_7_values=days_7_values,
        total_7days_revenue=total_7days_revenue,
        monthly_labels=monthly_labels,
        monthly_values=monthly_values,
        total_monthly_revenue=total_monthly_revenue,
        recent_transactions=recent_transactions,
        product_updates=product_updates,
        peak_day_labels=peak_day_labels,
        peak_day_values=peak_day_values,
        staff_members=staff_members,
        selected_staff_id=selected_staff_id
    )


# 2. User Control Route (Staff Management)
@app.route('/usercontrol')
def usercontrol():
    if 'user' not in session:
        return redirect(url_for('login'))

    role = session.get('role')

    if role != 'admin':
        return redirect(url_for('inventory'))

    cursor = mysql.connection.cursor()
    cursor.execute("SELECT id, name, email, is_verified FROM users WHERE role = 'staff' ORDER BY id DESC")
    staff_list = cursor.fetchall()
    cursor.close()

    return render_template('usercontrol.html', role=role, staff_list=staff_list)


# 3. Inventory Route (Inventory Management & Product Grid)
@app.route('/inventory')
def inventory():
    if 'user' not in session:
        return redirect(url_for('login'))

    cursor = mysql.connection.cursor()
    user_id = session.get('user_id')
    role = session.get('role')

    # Fetch unique categories for filtering
    if role == 'admin':
        cursor.execute("SELECT DISTINCT category FROM products WHERE category IS NOT NULL AND category != ''")
    else:
        cursor.execute("SELECT DISTINCT category FROM products WHERE user_id = %s AND category IS NOT NULL AND category != ''", (user_id,))
    categories = [row['category'] for row in cursor.fetchall()]

    # Fetch staff list for Admin filtering dropdown
    all_staff = []
    if role == 'admin':
        cursor.execute("SELECT id, name FROM users WHERE role = 'staff'")
        all_staff = cursor.fetchall()

        cursor.execute("""
            SELECT p.id, p.name, p.category, p.price, p.quantity, p.description, u.name AS staff_name 
            FROM products p 
            LEFT JOIN users u ON p.user_id = u.id 
            ORDER BY p.id DESC
        """)
    else:
        cursor.execute("""
            SELECT id, name, category, price, quantity, description 
            FROM products 
            WHERE user_id = %s 
            ORDER BY id DESC
        """, (user_id,))

    items = cursor.fetchall()
    cursor.close()

    return render_template('inventory.html', items=items, categories=categories, role=role, all_staff=all_staff)


# 4. Add Product Route
@app.route('/add_product', methods=['POST'])
def add_product():
    if 'user' not in session:
        return redirect(url_for('login'))

    name = request.form.get('name')
    category = request.form.get('category')
    price = float(request.form.get('price', 0.0))
    quantity = int(request.form.get('quantity', 0))
    description = request.form.get('description')
    
    user_id = None if session.get('role') == 'admin' else session.get('user_id')

    cursor = mysql.connection.cursor()
    cursor.execute("""
        INSERT INTO products (name, category, price, quantity, description, user_id)
        VALUES (%s, %s, %s, %s, %s, %s)
    """, (name, category, price, quantity, description, user_id))
    
    mysql.connection.commit()
    cursor.close()

    return redirect(url_for('inventory'))


# 5. Restock Route
@app.route('/restock/<int:product_id>', methods=['POST'])
def restock(product_id):
    if 'user' not in session:
        return redirect(url_for('login'))

    try:
        qty_to_add = int(request.form.get('quantity', 0))
    except (ValueError, TypeError):
        qty_to_add = 0

    if qty_to_add > 0:
        cursor = mysql.connection.cursor()
        if session.get('role') == 'admin':
            cursor.execute("UPDATE products SET quantity = quantity + %s WHERE id = %s AND user_id IS NULL", (qty_to_add, product_id))
        else:
            cursor.execute("UPDATE products SET quantity = quantity + %s WHERE id = %s AND user_id = %s", (qty_to_add, product_id, session.get('user_id')))
        
        mysql.connection.commit()
        cursor.close()

    return redirect(url_for('inventory'))


# 6. Update Product Details Route
@app.route('/update_product/<int:product_id>', methods=['POST'])
def update_product(product_id):
    if 'user' not in session:
        return redirect(url_for('login'))

    name = request.form.get('name')
    category = request.form.get('category')
    price = float(request.form.get('price', 0.0))
    description = request.form.get('description')

    cursor = mysql.connection.cursor()

    if session.get('role') == 'admin':
        cursor.execute("""
            UPDATE products 
            SET name = %s, category = %s, price = %s, description = %s
            WHERE id = %s AND user_id IS NULL
        """, (name, category, price, description, product_id))
    else:
        cursor.execute("""
            UPDATE products 
            SET name = %s, category = %s, price = %s, description = %s
            WHERE id = %s AND user_id = %s
        """, (name, category, price, description, product_id, session.get('user_id')))

    mysql.connection.commit()
    cursor.close()

    return redirect(url_for('inventory'))


# 7. Admin User Control Action Routes (Approve, Revoke, Delete)
@app.route('/approve_user/<int:user_id>', methods=['POST'])
def approve_user(user_id):
    if session.get('role') != 'admin':
        return redirect(url_for('dashboard'))

    cursor = mysql.connection.cursor()
    cursor.execute("UPDATE users SET is_verified = 1 WHERE id = %s AND role = 'staff'", (user_id,))
    mysql.connection.commit()
    cursor.close()

    return redirect(url_for('usercontrol'))


@app.route('/revoke_user/<int:user_id>', methods=['POST'])
def revoke_user(user_id):
    if session.get('role') != 'admin':
        return redirect(url_for('dashboard'))

    cursor = mysql.connection.cursor()
    cursor.execute("UPDATE users SET is_verified = 0 WHERE id = %s AND role = 'staff'", (user_id,))
    mysql.connection.commit()
    cursor.close()

    return redirect(url_for('usercontrol'))


@app.route('/delete_user/<int:user_id>', methods=['POST'])
def delete_user(user_id):
    if session.get('role') != 'admin':
        return redirect(url_for('dashboard'))

    cursor = mysql.connection.cursor()
    cursor.execute("UPDATE products SET user_id = NULL WHERE user_id = %s", (user_id,))
    cursor.execute("DELETE FROM users WHERE id = %s AND role = 'staff'", (user_id,))
    mysql.connection.commit()
    cursor.close()

    return redirect(url_for('usercontrol'))


# 8. Authentication Routes
@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user' in session:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        username_or_email = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()

        cursor = mysql.connection.cursor()
        cursor.execute("SELECT id, name, email, password, role, is_verified FROM users WHERE email = %s OR name = %s", 
                       (username_or_email, username_or_email))
        user = cursor.fetchone()
        cursor.close()

        if user and check_password_hash(user['password'], password):
            if not user.get('is_verified'):
                return render_template('login.html', error="Your account access is revoked or pending admin approval.")
            
            session['user_id'] = user['id']
            session['user'] = user['name']
            session['role'] = user['role']
            
            if user['role'] == 'admin':
                return redirect(url_for('dashboard'))
            return redirect(url_for('inventory'))
            
        return render_template('login.html', error="Invalid credentials. Please try again.")

    return render_template('login.html')


@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if 'user' in session:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '').strip()
        confirm_password = request.form.get('confirm_password', '').strip()

        if password != confirm_password:
            return render_template('signup.html', error="Passwords do not match!")

        cursor = mysql.connection.cursor()
        cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
        if cursor.fetchone():
            cursor.close()
            return render_template('signup.html', error="Email address is already registered!")
        cursor.close()

        otp_code = str(random.randint(100000, 999999))
        email_sent = send_email(
            to_email=email,
            subject="Motoflute Web - Registration OTP Code",
            body=f"Hello {name}!\n\nYour OTP for account registration is: {otp_code}"
        )

        if not email_sent:
            return render_template('signup.html', error=f"Failed to send OTP email. (Dev Code: {otp_code})")

        session['pending_user'] = {'name': name, 'email': email, 'password': generate_password_hash(password)}
        session['otp'] = otp_code
        return redirect(url_for('verify_otp'))

    return render_template('signup.html')


@app.route('/verify_otp', methods=['GET', 'POST'])
def verify_otp():
    if 'pending_user' not in session or 'otp' not in session:
        return redirect(url_for('signup'))

    if request.method == 'POST':
        user_otp = request.form.get('otp', '').strip()

        if user_otp and user_otp == session.get('otp'):
            pending_user = session.get('pending_user')

            cursor = mysql.connection.cursor()
            cursor.execute("INSERT INTO users (name, email, password, role, is_verified) VALUES (%s, %s, %s, 'staff', 0)", 
                           (pending_user['name'], pending_user['email'], pending_user['password']))
            mysql.connection.commit()
            cursor.close()

            session.pop('pending_user', None)
            session.pop('otp', None)

            return render_template('login.html', error="Registration successful! Your account is pending admin approval.")

        return render_template('verify_otp.html', error="Invalid OTP code. Please try again.")

    return render_template('verify_otp.html')


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


# 9. Shop / POS System Routes & Checkout
@app.route('/shop')
def shop():
    if 'user' not in session:
        return redirect(url_for('login'))

    role = session.get('role')
    user_id = session.get('user_id')
    cursor = mysql.connection.cursor()

    if role == 'admin':
        cursor.execute("SELECT id, name, category, price, quantity, description FROM products WHERE quantity > 0 AND user_id IS NULL ORDER BY id DESC")
    else:
        cursor.execute("SELECT id, name, category, price, quantity, description FROM products WHERE quantity > 0 AND user_id = %s ORDER BY id DESC", (user_id,))

    items = cursor.fetchall()
    cursor.close()

    cart = session.get('cart', [])
    return render_template('shop.html', items=items, cart=cart, role=role)


@app.route('/add_to_cart/<int:product_id>', methods=['POST'])
def add_to_cart(product_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    quantity = int(request.form.get('quantity', 1))
    role = session.get('role', 'staff')
    user_id = session.get('user_id')

    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    if role == 'admin':
        cursor.execute("SELECT * FROM products WHERE id = %s AND user_id IS NULL", (product_id,))
    else:
        cursor.execute("SELECT * FROM products WHERE id = %s AND user_id = %s", (product_id, user_id))

    product = cursor.fetchone()
    cursor.close()

    if product and product['quantity'] >= quantity:
        cart = session.get('cart', [])
        
        found = False
        for item in cart:
            if item['id'] == product_id:
                item['qty'] += quantity
                found = True
                break
                
        if not found:
            cart.append({
                'id': product['id'],
                'name': product['name'],
                'price': float(product['price']),
                'qty': quantity
            })
            
        session['cart'] = cart
        session.modified = True

    return redirect(url_for('shop'))


@app.route('/remove_from_cart/<int:item_index>')
def remove_from_cart(item_index):
    cart = session.get('cart', [])
    if 0 <= item_index < len(cart):
        cart.pop(item_index)
        session['cart'] = cart
        session.modified = True
    return redirect(url_for('shop'))


@app.route('/clear_cart')
def clear_cart():
    session.pop('cart', None)
    return redirect(url_for('shop'))


@app.route('/checkout', methods=['POST'])
def checkout():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    cart = session.get('cart', [])
    if not cart:
        return redirect(url_for('shop'))

    customer_name = request.form.get('customer_name', '').strip() or 'Guest'
    role = session.get('role', 'staff')
    user_id = session.get('user_id')

    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    total_amount = sum(float(item['qty']) * float(item['price']) for item in cart)

    cursor.execute("""
        INSERT INTO orders (customer_name, total_amount, staff_id, created_at)
        VALUES (%s, %s, %s, NOW())
    """, (customer_name, total_amount, user_id))

    for item in cart:
        if role == 'admin':
            cursor.execute("""
                UPDATE products 
                SET quantity = quantity - %s 
                WHERE id = %s AND user_id IS NULL AND quantity >= %s
            """, (item['qty'], item['id'], item['qty']))
        else:
            cursor.execute("""
                UPDATE products 
                SET quantity = quantity - %s 
                WHERE id = %s AND user_id = %s AND quantity >= %s
            """, (item['qty'], item['id'], user_id, item['qty']))

    mysql.connection.commit()
    cursor.close()

    session.pop('cart', None)
    return redirect(url_for('shop'))


def init_admin():
    with app.app_context():
        cursor = mysql.connection.cursor()
        cursor.execute("SELECT id FROM users WHERE role = 'admin'")
        if not cursor.fetchone():
            cursor.execute("""
                INSERT INTO users (name, email, password, role, is_verified) 
                VALUES (%s, %s, %s, 'admin', 1)
            """, ("Admin", "palivinoreyven@gmail.com", generate_password_hash("Adminven1!")))
            mysql.connection.commit()
        cursor.close()


if __name__ == '__main__':
    init_admin()
    app.run(debug=True)
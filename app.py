from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
import os
import json
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__, template_folder='template')
app.secret_key = "your_secret_key"
# Database Configuration (Using SQLite)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///sandhai.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'static/uploads'  # Folder to store uploaded images
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif'}

# Ensure the upload folder exists   
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

db = SQLAlchemy(app)

# User Model
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    mobile = db.Column(db.String(15), nullable=False)
    full_name = db.Column(db.String(100), nullable=False)
    city = db.Column(db.String(50), nullable=False)
    state = db.Column(db.String(50), nullable=False)
    pincode = db.Column(db.String(10), nullable=False)
    password = db.Column(db.String(200), nullable=False)  # Hashed Password
    is_admin = db.Column(db.Boolean, default=False)  # New field for admin status


# Helper function to check allowed file extensions
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']


# Product Model
class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(300), nullable=False)
    price = db.Column(db.Float, nullable=False)
    category = db.Column(db.String(50), nullable=False)  # New column
    images = db.Column(db.JSON, nullable=False)  # New column

# Feedback Model
class Feedback(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), nullable=False)
    feedback_text = db.Column(db.Text, nullable=False)

# Rating Model
class Rating(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), nullable=False)
    rating = db.Column(db.Integer, nullable=False)

# Cart Model
class Cart(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    quantity = db.Column(db.Integer, default=1)

# Order Model
class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    total_price = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), default='Pending')  # Status: Pending, Shipped, Delivered

# Initialize Database
with app.app_context():
    db.create_all()  # Create all tables

    # Check if admin already exists
    admin_user = User.query.filter_by(username="admin").first()
    if not admin_user:
        admin = User(
            username="admin",
            email="admin@example.com",
            mobile="9876543210",
            full_name="Admin",
            city="AdminCity",
            state="AdminState",
            pincode="123456",
            password=generate_password_hash("admin@123"),  # Secure password
            is_admin=True  # Mark as admin
        )
        db.session.add(admin)
        db.session.commit()

# Home Route
@app.route('/')
def home():
    username = session.get('username')
    products = Product.query.all()
    products_by_category = {}
    for product in products:
        product.images = json.loads(product.images)  # Deserialize JSON to list
        if product.category not in products_by_category:
            products_by_category[product.category] = []
        products_by_category[product.category].append(product)
    return render_template('index.html', products=products, username=username)

# Search Route
@app.route('/search', methods=['GET'])
def search():
    # Get the search query from the URL parameters
    query = request.args.get('query', '')

    # Search for products matching the query
    products = Product.query.filter(Product.name.contains(query)).all()
    username=session.get('username')
    # Deserialize the images field for each product
    for product in products:
        if isinstance(product.images, str):  # Check if images is a JSON string
            product.images = json.loads(product.images)  # Deserialize JSON to list
        else:
            product.images = []  # Set to an empty list if no images are available

    # Render the search results template
    return render_template('search.html', products=products, query=query ,username=username )

@app.route('/edit-product/<int:product_id>', methods=['GET', 'POST'])
def edit_product(product_id):
    product = Product.query.get_or_404(product_id)  # Fetch the product or return 404 if not found

    if request.method == 'POST':
        # Update product details
        product.name = request.form.get('name')
        product.description = request.form.get('description')
        product.price = request.form.get('price')
        product.category = request.form.get('category')

        db.session.commit()  # Save changes to the database
        flash("Product updated successfully!", "success")
        return redirect(url_for('admin_dashboard'))  # Redirect to the admin dashboard

    # Render the edit form with the current product details
    return render_template('edit_product.html', product=product)   

# Login Route
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        user = User.query.filter_by(username=username).first()
        
        if user and check_password_hash(user.password, password):
            session['user_id'] = user.id  # Store user ID in session
            session['username'] = username
            session['is_admin'] = user.is_admin  # Store admin status

            if user.is_admin:
                return redirect(url_for('admin_dashboard'))  # Redirect admin to dashboard
            
            return redirect(url_for('home'))  # Redirect normal users to home

        flash("Invalid credentials!", "error")

    return render_template('login.html')

# Purchase Now Route
@app.route('/purchase_now/<int:product_id>', methods=['POST'])
def purchase_now(product_id):
    if 'user_id' not in session:
        flash("Please login to purchase!", "warning")
        return redirect(url_for('login'))

    user_id = session['user_id']
    product = Product.query.get(product_id)

    if not product:
        flash("Product not found!", "danger")
        return redirect(url_for('home'))

    new_order = Order(
        user_id=user_id,
        product_id=product.id,
        quantity=1,
        total_price=product.price
    )

    db.session.add(new_order)
    Cart.query.filter_by(user_id=user_id, product_id=product.id).delete()
    db.session.commit()

    flash("Order placed successfully!", "success")
    return redirect(url_for('order_summary'))

# Cart Route
@app.route('/cart')
def cart():
    if 'user_id' not in session:
        flash("Please login to view your cart!", "warning")
        return redirect(url_for('login'))
    
    user_id = session['user_id']
    cart_items = db.session.query(Cart, Product).join(Product).filter(Cart.user_id == user_id).all()
    total_price = sum(item.Cart.quantity * item.Product.price for item in cart_items)

    return render_template('cart.html', cart_items=cart_items, total_price=total_price)

# Add to Cart Route
@app.route('/add_to_cart/<int:product_id>', methods=['POST'])
def add_to_cart(product_id):
    if 'user_id' not in session:
        flash("Please login to add items to your cart!", "warning")
        return redirect(url_for('login'))
    
    user_id = session['user_id']
    existing_item = Cart.query.filter_by(user_id=user_id, product_id=product_id).first()

    if existing_item:
        existing_item.quantity += 1
    else:
        new_item = Cart(user_id=user_id, product_id=product_id, quantity=1)
        db.session.add(new_item)

    db.session.commit()
    flash("Product added to cart!", "success")
    return redirect(url_for('cart'))

# Remove from Cart Route
@app.route('/remove_from_cart/<int:cart_id>', methods=['POST'])
def remove_from_cart(cart_id):
    if 'user_id' not in session:
        flash("Please login to remove items from your cart!", "warning")
        return redirect(url_for('login'))
    
    cart_item = Cart.query.get(cart_id)
    if cart_item:
        db.session.delete(cart_item)
        db.session.commit()
        flash("Item removed from cart!", "success")
    
    return redirect(url_for('cart'))

# Checkout Route
@app.route('/checkout', methods=['POST'])
def checkout():
    if 'user_id' not in session:
        flash("Please login to place an order!", "warning")
        return redirect(url_for('login'))
    
    user_id = session['user_id']
    cart_items = db.session.query(Cart, Product).join(Product).filter(Cart.user_id == user_id).all()

    if not cart_items:
        flash("Your cart is empty!", "warning")
        return redirect(url_for('cart'))

    for item in cart_items:
        new_order = Order(
            user_id=user_id,
            product_id=item.Product.id,
            quantity=item.Cart.quantity,
            total_price=item.Product.price * item.Cart.quantity
        )
        db.session.add(new_order)

    Cart.query.filter_by(user_id=user_id).delete()
    db.session.commit()

    flash("Order placed successfully!", "success")
    return redirect(url_for('order_summary'))

@app.route('/order')
def order_summary():
    if 'user_id' not in session:
        flash("Please login to view your orders!", "warning")
        return redirect(url_for('login'))
    
    user_id = session['user_id']
    orders = db.session.query(Order, Product).join(Product).filter(Order.user_id == user_id).all()
    
    # Deserialize the images field for each product if it's a JSON string
    for order, product in orders:
        if product.images:
            if isinstance(product.images, str):  # Check if images is a string
                try:
                    product.images = json.loads(product.images)
                except json.JSONDecodeError:
                    product.images = []  # Set to an empty list if JSON decoding fails
            elif isinstance(product.images, list):  # If it's already a list, do nothing
                pass
            else:
                product.images = []  # Set to an empty list for any other unexpected type
        else:
            product.images = []  # Set to an empty list if no images are available
    
    return render_template('order.html', orders=orders)

@app.route('/order/details/<int:order_id>')
def order_details(order_id):
    if 'user_id' not in session:
        flash("Please login to view order details!", "warning")
        return redirect(url_for('login'))
    
    order = db.session.query(Order, Product).join(Product).filter(Order.id == order_id).first()
    if not order:
        flash("Order not found!", "danger")
        return redirect(url_for('order_summary'))
    
    # Deserialize the images field for the product
    if order.Product.images:
        order.Product.images = json.loads(order.Product.images)
    else:
        order.Product.images = []  # Set to an empty list if no images are available
    
    return render_template('order_details.html', order=order)

@app.route('/cancel_order/<int:order_id>', methods=['POST'])
def cancel_order(order_id):
    if 'user_id' not in session:
        flash("Please login to cancel orders!", "warning")
        return redirect(url_for('login'))
    
    order = Order.query.get(order_id)
    if not order:
        flash("Order not found!", "danger")
        return redirect(url_for('order_summary'))
    
    if order.status != 'Pending':
        flash("You can only cancel pending orders!", "warning")
        return redirect(url_for('order_summary'))
    
    # Delete the order from the database
    db.session.delete(order)
    db.session.commit()
    
    flash("Order cancelled and removed successfully!", "success")
    return redirect(url_for('order_summary'))

@app.route('/delete_order/<int:order_id>', methods=['POST'])
def delete_order(order_id):
    if 'user_id' not in session:
        flash("Please login to delete orders!", "warning")
        return redirect(url_for('login'))
    
    order = Order.query.get(order_id)
    if not order:
        flash("Order not found!", "danger")
        return redirect(url_for('order_summary'))
    
    if order.status != 'cancelled':
        flash("You can only delete cancelled orders!", "warning")
        return redirect(url_for('order_summary'))
    
    # Delete the order from the database
    db.session.delete(order)
    db.session.commit()
    
    flash("Order deleted successfully!", "success")
    return redirect(url_for('order_summary'))

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

# Create the database tables
with app.app_context():
    db.create_all()

# Routes
@app.route('/admin-dashboard')
def admin_dashboard():
    if not session.get('is_admin'):
        flash("Unauthorized access!", "error")
        return redirect(url_for('home'))
    
    # Group products by category
    products = Product.query.all()
    products_by_category = {}
    for product in products:
        product.images = json.loads(product.images)  # Deserialize JSON to list
        if product.category not in products_by_category:
            products_by_category[product.category] = []
        products_by_category[product.category].append(product)
    categories = db.session.query(Product.category).distinct().all()
    for category in categories:
        products = Product.query.filter_by(category=category[0]).all()
        products_by_category[category[0]] = products
    return render_template('admin-dashboard.html', products_by_category=products_by_category)

@app.route('/add_product', methods=['POST'])
def add_product():
    if not session.get('is_admin'):
        flash("Unauthorized access!", "error")
        return redirect(url_for('home'))
    
    try:
        # Get form data
        name = request.form.get('name')
        description = request.form.get('description')
        price = float(request.form.get('price'))
        category = request.form.get('category')  # Ensure this matches the selected category
        images = []

        # Save uploaded images
        for file in request.files.getlist('images'):
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(file_path)
                images.append(filename)
            else:
                flash("Invalid file type!", "error")
                return redirect(url_for('admin_dashboard'))
        
        if not images:
            flash("At least one image is required!", "error")
            return redirect(url_for('admin_dashboard'))
        
        # Create new product
        new_product = Product(
            name=name,
            description=description,
            price=price,
            category=category,  # Ensure the category is set correctly
            images=json.dumps(images)  # Store image filenames as JSON
        )
        db.session.add(new_product)
        db.session.commit()
        
        flash("Product added successfully!", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error adding product: {str(e)}", "error")
        print(f"Error: {str(e)}")  # Debugging: Print the error to the console
    
    return redirect(url_for('admin_dashboard'))

@app.route('/delete_product/<int:product_id>', methods=['POST'])
def delete_product(product_id):
    if not session.get('is_admin'):
        flash("Unauthorized access!", "error")
        return redirect(url_for('home'))
    
    product = Product.query.get(product_id)
    if product:
        db.session.delete(product)
        db.session.commit()
        flash("Product deleted successfully!", "success")
    
    return redirect(url_for('admin_dashboard'))

# Register Route
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        mobile = request.form['mobile']
        full_name = request.form['full_name']
        city = request.form['city']
        state = request.form['state']
        pincode = request.form['pincode']
        password = request.form['password']

        # Check if username already exists
        if User.query.filter_by(username=username).first():
            flash("Username already exists!", "error")
            return redirect(url_for('register'))

        # Check if email is already registered
        if User.query.filter_by(email=email).first():
            flash("Email already registered!", "error")
            return redirect(url_for('register'))

        # Validate mobile number (Only numbers & 10 digits)
        if not mobile.isdigit() or len(mobile) != 10:
            flash("Invalid mobile number! Enter a 10-digit number.", "error")
            return redirect(url_for('register'))

        # Validate pincode (Only numbers & 6 digits)
        if not pincode.isdigit() or len(pincode) != 6:
            flash("Invalid pincode! Enter a 6-digit number.", "error")
            return redirect(url_for('register'))

        # Hash the password
        hashed_password = generate_password_hash(password)

        # Create a new user
        new_user = User(
            username=username,
            email=email,
            mobile=mobile,
            full_name=full_name,
            city=city,
            state=state,
            pincode=pincode,
            password=hashed_password
        )

        db.session.add(new_user)
        db.session.commit()

        flash("Registration successful! You can now log in.", "success")
        return redirect(url_for('login'))  # Redirect to the login route

    return render_template('register.html')

@app.route('/electronics')
def electronics():
    if 'user_id' not in session:
        flash("Please login to view products!", "warning")
        return redirect(url_for('login'))
    
    # Fetch only electronics products
    products = Product.query.filter_by(category='Electronics').all()
    
    # Get the username from the session
    username = session.get('username')
    products_by_category = {}
    for product in products:
        product.images = json.loads(product.images)  # Deserialize JSON to list
        if product.category not in products_by_category:
            products_by_category[product.category] = []
        products_by_category[product.category].append(product)
    return render_template('electronics.html', products=products, username=username)

@app.route('/fashion')
def fashion():
    if 'user_id' not in session:
        flash("Please login to view products!", "warning")
        return redirect(url_for('login'))
    
    # Fetch only fashion products
    products = Product.query.filter_by(category='Fashion').all()
    
    # Get the username from the session
    username = session.get('username')
    products_by_category = {}
    for product in products:
        product.images = json.loads(product.images)  # Deserialize JSON to list
        if product.category not in products_by_category:
            products_by_category[product.category] = []
        products_by_category[product.category].append(product)
    return render_template('fashion.html', products=products, username=username)

@app.route('/home-kitchen')
def home_kitchen():
    # Check if the user is logged in
    if 'user_id' not in session:
        flash("Please login to view products!", "warning")
        return redirect(url_for('login'))
    
    # Fetch only home & kitchen products
    products = Product.query.filter_by(category='Home & Kitchen').all()

    # Deserialize images for each product
    for product in products:
        product.images = json.loads(product.images)  # Deserialize JSON to list

    # Get the username from the session
    username = session.get('username')

    products_by_category = {}
    for product in products:
     if isinstance(product.images, str):  # Check if it's a JSON string
        product.images = json.loads(product.images)  # Deserialize JSON to list
    # If it's already a list, no need to deserialize
        if product.category not in products_by_category:
            products_by_category[product.category] = []
        products_by_category[product.category].append(product)
    # Render the template with products and username
    return render_template('home_kitchen.html', products=products, username=username)

# Books Route
@app.route('/books')
def books():
    if 'user_id' not in session:
        flash("Please login to view products!", "warning")
        return redirect(url_for('login'))
    
    # Fetch only books products
    products = Product.query.filter_by(category='Books').all()

    for product in products:
        product.images = json.loads(product.images)  # Deserialize JSON to list

    username = session.get('username')
    products_by_category = {}
    for product in products:
     if isinstance(product.images, str):  # Check if it's a JSON string
        product.images = json.loads(product.images)  # Deserialize JSON to list
    # If it's already a list, no need to deserialize
        if product.category not in products_by_category:
            products_by_category[product.category] = []
        products_by_category[product.category].append(product)
    return render_template('books.html', products=products, username=username)
# Toys & Games Route
@app.route('/toys-games')
def toys_games():
    if 'user_id' not in session:
        flash("Please login to view products!", "warning")
        return redirect(url_for('login'))
    
    # Fetch only toys & games products
    products = Product.query.filter_by(category='Toys & Games').all()
    
    for product in products:
        product.images = json.loads(product.images)  # Deserialize JSON to list

    username = session.get('username')
    products_by_category = {}
    for product in products:
     if isinstance(product.images, str):  # Check if it's a JSON string
        product.images = json.loads(product.images)  # Deserialize JSON to list
    # If it's already a list, no need to deserialize
        if product.category not in products_by_category:
            products_by_category[product.category] = []
        products_by_category[product.category].append(product)
    return render_template('toys_games.html', products=products , username=username)

# Beauty Route
@app.route('/beauty')
def beauty():
    if 'user_id' not in session:
        flash("Please login to view products!", "warning")
        return redirect(url_for('login'))
    
    # Fetch only beauty products
    products = Product.query.filter_by(category='Beauty').all()
    for product in products:
        product.images = json.loads(product.images)  # Deserialize JSON to list

    username = session.get('username')
    products_by_category = {}
    for product in products:
     if isinstance(product.images, str):  # Check if it's a JSON string
        product.images = json.loads(product.images)  # Deserialize JSON to list
    # If it's already a list, no need to deserialize
        if product.category not in products_by_category:
            products_by_category[product.category] = []
        products_by_category[product.category].append(product)
    return render_template('beauty.html', products=products , username=username)

# Sports Route
@app.route('/sports')
def sports():
    if 'user_id' not in session:
        flash("Please login to view products!", "warning")
        return redirect(url_for('login'))
    
    # Fetch only sports products
    products = Product.query.filter_by(category='Sports').all()
    for product in products:
        product.images = json.loads(product.images)  # Deserialize JSON to list

    username = session.get('username')
    products_by_category = {}
    for product in products:
     if isinstance(product.images, str):  # Check if it's a JSON string
        product.images = json.loads(product.images)  # Deserialize JSON to list
    # If it's already a list, no need to deserialize
        if product.category not in products_by_category:
            products_by_category[product.category] = []
        products_by_category[product.category].append(product)
    return render_template('sports.html', products=products , username=username)

# Groceries Route
@app.route('/groceries')
def groceries():
    if 'user_id' not in session:
        flash("Please login to view products!", "warning")
        return redirect(url_for('login'))
    
    # Fetch only groceries products
    products = Product.query.filter_by(category='Groceries').all()
    for product in products:
        product.images = json.loads(product.images)  # Deserialize JSON to list

    username = session.get('username')
    products_by_category = {}
    for product in products:
     if isinstance(product.images, str):  # Check if it's a JSON string
        product.images = json.loads(product.images)  # Deserialize JSON to list
    # If it's already a list, no need to deserialize
        if product.category not in products_by_category:
            products_by_category[product.category] = []
        products_by_category[product.category].append(product)
    return render_template('groceries.html', products=products , username=username)

@app.route('/account')
def account():
    if 'user_id' not in session:
        flash("Please login to view your account!", "warning")
        return redirect(url_for('login'))
    
    user_id = session['user_id']
    user = User.query.get(user_id)
    
    if not user:
        flash("User not found!", "danger")
        return redirect(url_for('home'))
    
    return render_template('user_account.html', user=user)

@app.route('/update_account', methods=['GET', 'POST'])
def update_account():
    if 'user_id' not in session:
        flash("Please login to update your account!", "warning")
        return redirect(url_for('login'))
    
    user_id = session['user_id']
    user = User.query.get(user_id)
    
    if not user:
        flash("User not found!", "danger")
        return redirect(url_for('home'))
    
    if request.method == 'POST':
        user.email = request.form['email']
        user.mobile = request.form['mobile']
        user.full_name = request.form['full_name']
        user.city = request.form['city']
        user.state = request.form['state']
        user.pincode = request.form['pincode']
        
        db.session.commit()
        flash("Account updated successfully!", "success")
        return redirect(url_for('account'))
    
    return render_template('update_account.html', user=user)

# Feedback Route
@app.route('/feedback', methods=['GET', 'POST'])
def feedback():
    if request.method == 'POST':
        username = session.get('username', 'Guest')
        feedback_text = request.form['feedback']

        new_feedback = Feedback(username=username, feedback_text=feedback_text)
        db.session.add(new_feedback)
        db.session.commit()

        flash("Thank you for your feedback!", "success")
        return redirect(url_for('home'))  # Redirect to home after submission

    return render_template('feedback.html')

# Rate Us Route
@app.route('/rate-us', methods=['GET', 'POST'])
def rate_us():
    if request.method == 'POST':
        username = session.get('username', 'Guest')
        rating = int(request.form['rating'])

        new_rating = Rating(username=username, rating=rating)
        db.session.add(new_rating)
        db.session.commit()

        flash("Thank you for your rating!", "success")
        return redirect(url_for('home'))  # Redirect to home after submission

    return render_template('rate_us.html')

# Logout Route
@app.route("/logout")
def logout():
    session.pop('username', None)  # Remove username from session
    session.pop('user_id', None)  # Remove user_id from session
    session.pop('is_admin', None)  # Remove admin status from session
    flash("You have been logged out!", "success")
    return redirect(url_for('home'))  # Redirect to home page after logout

if __name__ == '__main__':
    with app.app_context():
        db.create_all()  # Ensure tables are created
    app.run(debug=True)
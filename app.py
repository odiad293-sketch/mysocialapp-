from flask import Flask, render_template_string, request, redirect, session, jsonify, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from flask_socketio import SocketIO, emit, join_room
from datetime import datetime
import os
import re
from werkzeug.utils import secure_filename

# ================ APP SETUP ================
app = Flask(__name__)
app.secret_key = "chatternet_secret_key"
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///chatternet.db"
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB upload limit
db = SQLAlchemy(app)
socketio = SocketIO(app)

# Ensure upload folder exists
if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

# ================ DATABASE MODELS ================
followers = db.Table('followers',
    db.Column('follower_id', db.Integer, db.ForeignKey('user.id')),
    db.Column('followed_id', db.Integer, db.ForeignKey('user.id'))
)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(50), nullable=False)
    posts = db.relationship('Post', backref='author_ref', lazy=True)
    is_banned = db.Column(db.Boolean, default=False)
    is_admin = db.Column(db.Boolean, default=False)
    followed = db.relationship(
        'User', secondary=followers,
        primaryjoin=(followers.c.follower_id == id),
        secondaryjoin=(followers.c.followed_id == id),
        backref=db.backref('followers', lazy='dynamic'), lazy='dynamic'
    )

class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    author = db.Column(db.String(50), nullable=False)
    content = db.Column(db.Text, nullable=True)
    image_filename = db.Column(db.String(200), nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender = db.Column(db.String(50), nullable=False)
    receiver = db.Column(db.String(50), nullable=False)
    text = db.Column(db.Text, nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

class Logo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(200), nullable=False)

with app.app_context():
    db.create_all()
    # Set first user as admin automatically if no admin exists
    if not User.query.filter_by(is_admin=True).first():
        first_user = User.query.first()
        if first_user:
            first_user.is_admin = True
            db.session.commit()

# ================ ROUTES ================

# Splash Logo Page
@app.route('/splash')
def splash():
    logo = Logo.query.first()
    return render_template_string(SPLASH_HTML, logo=logo)

@app.route('/')
def home():
    return redirect('/splash')

# Login
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        user = User.query.filter_by(email=email, password=password).first()
        if user:
            if user.is_banned:
                return "Your account is banned."
            session['user'] = user.username
            return redirect('/dashboard')
        else:
            return render_template_string(LOGIN_HTML, error="Invalid credentials")
    return render_template_string(LOGIN_HTML, error=None)

# Signup
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
            return render_template_string(SIGNUP_HTML, error="Invalid email address")
        if User.query.filter_by(username=username).first() or User.query.filter_by(email=email).first():
            return render_template_string(SIGNUP_HTML, error="Username or email already exists")
        new_user = User(username=username, email=email, password=password)
        # If first user ever, make admin
        if User.query.count() == 0:
            new_user.is_admin = True
        db.session.add(new_user)
        db.session.commit()
        return redirect('/login')
    return render_template_string(SIGNUP_HTML, error=None)

# Logout
@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect('/login')

# Dashboard
@app.route('/dashboard')
def dashboard():
    if "user" not in session:
        return redirect('/login')
    user = User.query.filter_by(username=session["user"]).first()
    posts = Post.query.order_by(Post.timestamp.desc()).all()
    return render_template_string(DASHBOARD_HTML, posts=posts, user=user)

# Profile Page
@app.route('/profile/<username>')
def profile(username):
    user = User.query.filter_by(username=username).first()
    if not user:
        return "User not found"
    posts = Post.query.filter_by(author=user.username).order_by(Post.timestamp.desc()).all()
    return render_template_string(PROFILE_HTML, profile=user, posts=posts)

# Create post
@app.route('/post', methods=['POST'])
def create_post():
    if "user" not in session:
        return redirect('/login')
    content = request.form.get('content')
    image = request.files.get('image')
    filename = None
    if image:
        filename = secure_filename(image.filename)
        image.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
    new_post = Post(author=session["user"], content=content, image_filename=filename)
    db.session.add(new_post)
    db.session.commit()
    return redirect('/dashboard')

# Messenger
@app.route('/messenger')
def messenger():
    if "user" not in session:
        return redirect('/login')
    return render_template_string(MESSENGER_HTML, user=session["user"])

# Get messages
@app.route('/get_messages/<friend>')
def get_messages(friend):
    user = session.get("user")
    if not user:
        return jsonify([])
    msgs = Message.query.filter(
        ((Message.sender==user) & (Message.receiver==friend)) |
        ((Message.sender==friend) & (Message.receiver==user))
    ).order_by(Message.timestamp.asc()).all()
    return jsonify([{"sender": m.sender, "text": m.text, "time": m.timestamp.strftime("%H:%M")} for m in msgs])

# Search friends
@app.route('/search_users')
def search_users():
    if "user" not in session:
        return redirect('/login')
    query = request.args.get('q', '')
    users = User.query.filter(User.username.contains(query), User.username != session['user']).all()
    return jsonify([u.username for u in users])

# Admin Page
@app.route('/admin', methods=['GET', 'POST'])
def admin_page():
    if "user" not in session:
        return redirect('/login')
    current = User.query.filter_by(username=session["user"]).first()
    if not current.is_admin:
        return "Access denied"
    users = User.query.all()
    logo = Logo.query.first()
    if request.method == 'POST':
        ban_username = request.form.get('ban_user')
        new_logo = request.files.get('logo')
        if ban_username:
            u = User.query.filter_by(username=ban_username).first()
            if u:
                u.is_banned = True
                db.session.commit()
        if new_logo:
            filename = secure_filename(new_logo.filename)
            new_logo.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            logo_record = Logo.query.first()
            if not logo_record:
                logo_record = Logo(filename=filename)
                db.session.add(logo_record)
            else:
                logo_record.filename = filename
            db.session.commit()
    return render_template_string(ADMIN_HTML, users=users, logo=logo)

# ================ SOCKET.IO ================
@socketio.on('send_message')
def handle_message(data):
    sender = data['sender']
    receiver = data['receiver']
    text = data['text']
    msg = Message(sender=sender, receiver=receiver, text=text)
    db.session.add(msg)
    db.session.commit()
    # Notify receiver in real-time
    emit('receive_message', {'sender': sender, 'text': text}, room=receiver)
    emit('receive_message', {'sender': sender, 'text': text}, room=sender)
    # Admin notification
    admin_user = User.query.filter_by(is_admin=True).first()
    if admin_user:
        emit('admin_notify', {'receiver': receiver}, room=admin_user.username)

@socketio.on('join')
def on_join(data):
    username = data['username']
    join_room(username)

# =================== HTML TEMPLATES ===================
SPLASH_HTML = """
<!DOCTYPE html>
<html>
<head>
<title>Welcome</title>
<style>
body { margin:0; background:#1877f2; display:flex; justify-content:center; align-items:center; height:100vh; }
img { width:50%; max-width:300px; }
</style>
<meta http-equiv="refresh" content="2;url=/login" />
</head>
<body>
{% if logo %}
<img src="/static/uploads/{{logo.filename}}">
{% else %}
<h1 style="color:white;">Welcome to Chatternet</h1>
{% endif %}
</body>
</html>
"""

LOGIN_HTML = """
<!DOCTYPE html>
<html>
<head>
<title>Login</title>
<style>
body { margin:0; font-family:Arial; display:flex; justify-content:center; align-items:center; height:100vh; background:#f0f2f5; }
form { background:white; padding:30px; border-radius:15px; box-shadow:0 0 20px rgba(0,0,0,0.2); text-align:center; width:300px; }
input { width:90%; padding:10px; margin:10px 0; border-radius:5px; border:1px solid #ccc; }
button { width:95%; padding:10px; border:none; background:#1877f2; color:white; font-size:16px; border-radius:5px; cursor:pointer; }
.error { color:red; }
a { text-decoration:none; color:#1877f2; }
</style>
</head>
<body>
<form method="POST">
<h2>Login</h2>
{% if error %}<div class="error">{{error}}</div>{% endif %}
<input type="email" name="email" placeholder="Email" required>
<input type="password" name="password" placeholder="Password" required>
<button>Login</button>
<p>Don't have an account? <a href="/signup">Sign up</a></p>
</form>
</body>
</html>
"""

SIGNUP_HTML = """
<!DOCTYPE html>
<html>
<head>
<title>Sign Up</title>
<style>
body { margin:0; font-family:Arial; display:flex; justify-content:center; align-items:center; height:100vh; background:#f0f2f5; }
form { background:white; padding:30px; border-radius:15px; box-shadow:0 0 20px rgba(0,0,0,0.2); text-align:center; width:300px; }
input { width:90%; padding:10px; margin:10px 0; border-radius:5px; border:1px solid #ccc; }
button { width:95%; padding:10px; border:none; background:#1877f2; color:white; font-size:16px; border-radius:5px; cursor:pointer; }
.error { color:red; }
a { text-decoration:none; color:#1877f2; }
</style>
</head>
<body>
<form method="POST">
<h2>Sign Up</h2>
{% if error %}<div class="error">{{error}}</div>{% endif %}
<input name="username" placeholder="Username" required>
<input type="email" name="email" placeholder="Email" required>
<input type="password" name="password" placeholder="Password" required>
<button>Sign Up</button>
<p>Already have an account? <a href="/login">Login</a></p>
</form>
</body>
</html>
"""


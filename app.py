# ================= PART 1 =================
from flask import Flask, render_template_string, request, redirect, session, jsonify, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_socketio import SocketIO, emit, join_room
from datetime import datetime
from werkzeug.utils import secure_filename
import os

# ================= CONFIG ===================
app = Flask(__name__)
app.secret_key = "chatternet_secret_key"
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///chatternet.db"
app.config["UPLOAD_FOLDER"] = "static/uploads"
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024  # 5MB max for uploads
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif"}

db = SQLAlchemy(app)
socketio = SocketIO(app)

# Ensure upload folder exists
os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

# ================= DATABASE MODELS ===================
followers = db.Table('followers',
    db.Column('follower_id', db.Integer, db.ForeignKey('user.id')),
    db.Column('followed_id', db.Integer, db.ForeignKey('user.id'))
)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(50), nullable=False)
    email_or_phone = db.Column(db.String(100), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    banned = db.Column(db.Boolean, default=False)
    posts = db.relationship("Post", backref="author_obj", lazy=True)
    followers = db.relationship(
        "User", secondary=followers,
        primaryjoin=(followers.c.followed_id==id),
        secondaryjoin=(followers.c.follower_id==id),
        backref=db.backref("following", lazy="dynamic"),
        lazy="dynamic"
    )

class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    author = db.Column(db.String(50), nullable=False)
    content = db.Column(db.Text, nullable=False)
    image = db.Column(db.String(200), nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender = db.Column(db.String(50), nullable=False)
    receiver = db.Column(db.String(50), nullable=False)
    text = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

class Logo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(200), nullable=False)

with app.app_context():
    db.create_all()

# ================= HELPERS ===================
def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

def get_admin():
    return User.query.filter_by(is_admin=True).first()

# ================= ROUTES - PART 1 ===================

@app.route('/')
def splash():
    logo = Logo.query.first()
    logo_url = url_for('static', filename='uploads/' + logo.filename) if logo else ""
    return render_template_string(SPLASH_HTML, logo_url=logo_url)

@app.route('/login', methods=['GET','POST'])
def login():
    if request.method=='POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username, password=password).first()
        if user:
            if user.banned:
                return "Your account has been banned."
            session['user'] = user.username
            return redirect('/dashboard')
        else:
            return "Invalid credentials."
    return render_template_string(LOGIN_HTML)

@app.route('/signup', methods=['GET','POST'])
def signup():
    if request.method=='POST':
        username = request.form['username']
        password = request.form['password']
        email_or_phone = request.form['email_or_phone']
        if User.query.filter_by(username=username).first():
            return "Username exists."
        is_first = User.query.count() == 0
        new_user = User(username=username, password=password, email_or_phone=email_or_phone, is_admin=is_first)
        db.session.add(new_user)
        db.session.commit()
        return redirect('/login')
    return render_template_string(SIGNUP_HTML)

@app.route('/dashboard')
def dashboard():
    if 'user' not in session:
        return redirect('/login')
    user = User.query.filter_by(username=session['user']).first()
    posts = Post.query.order_by(Post.timestamp.desc()).all()
    admin = get_admin()
    return render_template_string(DASHBOARD_HTML, posts=posts, user=user, admin=admin)

@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect('/login')

# ================= HTML TEMPLATES - PART 1 ===================
SPLASH_HTML = """
<!DOCTYPE html>
<html>
<head>
<title>Chatternet</title>
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<style>
body{margin:0; display:flex; justify-content:center; align-items:center; height:100vh; background:#1877f2;}
img{width:200px; height:auto; animation:fadein 2s;}
@keyframes fadein{from{opacity:0}to{opacity:1}}
</style>
</head>
<body>
{% if logo_url %}
<img src="{{logo_url}}">
{% else %}
<h1 style="color:white;">Chatternet</h1>
{% endif %}
<script>setTimeout(()=>{ window.location='/login'; },2000);</script>
</body>
</html>
"""

LOGIN_HTML = """
<!DOCTYPE html>
<html>
<head>
<title>Login - Chatternet</title>
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<style>
body{margin:0; display:flex; justify-content:center; align-items:center; height:100vh; background:#f0f2f5;}
form{background:white; padding:30px; border-radius:10px; width:90%; max-width:400px; box-shadow:0 0 10px rgba(0,0,0,0.2);}
input{width:100%; margin:10px 0; padding:10px; border-radius:5px; border:1px solid #ccc;}
button{width:100%; padding:10px; border:none; border-radius:5px; background:#1877f2; color:white; font-weight:bold;}
a{color:#1877f2; text-decoration:none;}
</style>
</head>
<body>
<form method="POST">
<h2>Login</h2>
<input name="username" placeholder="Username" required>
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
<title>Signup - Chatternet</title>
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<style>
body{margin:0; display:flex; justify-content:center; align-items:center; height:100vh; background:#f0f2f5;}
form{background:white; padding:30px; border-radius:10px; width:90%; max-width:400px; box-shadow:0 0 10px rgba(0,0,0,0.2);}
input{width:100%; margin:10px 0; padding:10px; border-radius:5px; border:1px solid #ccc;}
button{width:100%; padding:10px; border:none; border-radius:5px; background:#1877f2; color:white; font-weight:bold;}
a{color:#1877f2; text-decoration:none;}
</style>
</head>
<body>
<form method="POST">
<h2>Sign Up</h2>
<input name="username" placeholder="Username" required>
<input type="password" name="password" placeholder="Password" required>
<input name="email_or_phone" placeholder="Email or Phone" required>
<button>Sign Up</button>
<p>Already have an account? <a href="/login">Login</a></p>
</form>
</body>
</html>
"""

# For now, we’ll define a placeholder for dashboard (full CSS & posts in part 2)
DASHBOARD_HTML = "<h1>Loading dashboard...</h1>"

if __name__ == "__main__":
    socketio.run(app, debug=True)

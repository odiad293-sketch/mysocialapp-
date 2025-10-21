# ================= Single-File Chatternet App =================
from flask import Flask, render_template_string, request, redirect, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_socketio import SocketIO, emit, join_room
from datetime import datetime
import os

app = Flask(__name__)
app.secret_key = "chatternet_secret_key"
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///chatternet.db"
app.config['UPLOAD_FOLDER'] = 'static/uploads'
db = SQLAlchemy(app)
socketio = SocketIO(app)

if not os.path.exists('static/uploads'):
    os.makedirs('static/uploads')

# ================= DATABASE MODELS =================
followers = db.Table('followers',
    db.Column('follower_id', db.Integer, db.ForeignKey('user.id')),
    db.Column('followed_id', db.Integer, db.ForeignKey('user.id'))
)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(50), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    posts = db.relationship('Post', backref='author', lazy=True)
    followed = db.relationship(
        'User', secondary=followers,
        primaryjoin=(followers.c.follower_id == id),
        secondaryjoin=(followers.c.followed_id == id),
        backref=db.backref('followers', lazy='dynamic'), lazy='dynamic'
    )

class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    author_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    content = db.Column(db.Text)
    image = db.Column(db.String(100))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    receiver_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    text = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

class Logo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(100), nullable=False)

with app.app_context():
    db.create_all()
    # Set first user as admin if none exists
    if User.query.count() == 0:
        admin = User(username="admin", password="admin123", email="admin@example.com", is_admin=True)
        db.session.add(admin)
        db.session.commit()

# ================== ROUTES =========================
@app.route('/')
def home():
    logo = Logo.query.first()
    if logo:
        return f'<img src="/static/uploads/{logo.filename}" style="width:100%;height:100vh;object-fit:cover;">'
    return redirect('/login')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method=='POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username, password=password).first()
        if user:
            session['user_id'] = user.id
            return redirect('/dashboard')
        return "Invalid credentials"
    return render_template_string(LOGIN_HTML)

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method=='POST':
        username = request.form['username']
        password = request.form['password']
        email = request.form['email']
        if User.query.filter_by(username=username).first():
            return "Username exists"
        if User.query.filter_by(email=email).first():
            return "Email exists"
        new_user = User(username=username, password=password, email=email)
        db.session.add(new_user)
        db.session.commit()
        return redirect('/login')
    return render_template_string(SIGNUP_HTML)

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    return redirect('/login')

@app.route('/dashboard')
def dashboard():
    user = User.query.get(session.get('user_id'))
    posts = Post.query.order_by(Post.timestamp.desc()).all()
    return render_template_string(DASHBOARD_HTML, user=user, posts=posts)

@app.route('/profile/<int:user_id>')
def profile(user_id):
    user = User.query.get(user_id)
    posts = Post.query.filter_by(author=user).order_by(Post.timestamp.desc()).all()
    return render_template_string(PROFILE_HTML, profile_user=user, posts=posts)

@app.route('/post', methods=['POST'])
def post():
    user = User.query.get(session.get('user_id'))
    if not user:
        return redirect('/login')
    content = request.form.get('content')
    image = None
    if 'image' in request.files:
        img = request.files['image']
        if img.filename != '':
            img.save(os.path.join(app.config['UPLOAD_FOLDER'], img.filename))
            image = img.filename
    new_post = Post(author=user, content=content, image=image)
    db.session.add(new_post)
    db.session.commit()
    return redirect('/dashboard')

@app.route('/messenger')
def messenger():
    user = User.query.get(session.get('user_id'))
    return render_template_string(MESSENGER_HTML, user=user, users=User.query.all())

@app.route('/admin')
def admin():
    user = User.query.get(session.get('user_id'))
    if not user or not user.is_admin:
        return redirect('/dashboard')
    users = User.query.all()
    notifications = [f"Message sent from {m.sender_id} to {m.receiver_id}" for m in Message.query.all()]
    return render_template_string(ADMIN_HTML, users=users, notifications=notifications)

@app.route('/ban_user', methods=['POST'])
def ban_user():
    user = User.query.get(session.get('user_id'))
    if not user or not user.is_admin:
        return redirect('/dashboard')
    uid = request.form['user_id']
    u = User.query.get(uid)
    if u:
        db.session.delete(u)
        db.session.commit()
    return redirect('/admin')

@app.route('/upload_logo', methods=['POST'])
def upload_logo():
    user = User.query.get(session.get('user_id'))
    if not user or not user.is_admin:
        return redirect('/dashboard')
    if 'logo' in request.files:
        file = request.files['logo']
        if file.filename != '':
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], file.filename))
            if Logo.query.first():
                db.session.query(Logo).delete()
            db.session.add(Logo(filename=file.filename))
            db.session.commit()
    return redirect('/admin')

# ================== SOCKET.IO ====================
@socketio.on('send_message')
def handle_message(data):
    sender = User.query.get(data['sender_id'])
    receiver = User.query.get(data['receiver_id'])
    text = data['text']
    msg = Message(sender_id=sender.id, receiver_id=receiver.id, text=text)
    db.session.add(msg)
    db.session.commit()
    emit('receive_message', {'sender': sender.username, 'text': text}, room=f"user_{receiver.id}")
    emit('receive_message', {'sender': sender.username, 'text': text}, room=f"user_{sender.id}")

@socketio.on('join')
def join(data):
    join_room(f"user_{data['user_id']}")

# =================== HTML TEMPLATES ===================
LOGIN_HTML = """
<!DOCTYPE html>
<html>
<head>
<title>Chatternet Login</title>
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<style>
body { margin:0; font-family:Arial; background:#e9ebee; display:flex; justify-content:center; align-items:center; height:100vh; }
form { background:white; padding:30px; border-radius:15px; width:90%; max-width:350px; box-shadow:0 2px 10px rgba(0,0,0,0.1); }
input { width:100%; padding:10px; margin:10px 0; border-radius:5px; border:1px solid #ccc; }
button { width:100%; padding:10px; border:none; border-radius:5px; background:#1877f2; color:white; font-weight:bold; }
a { text-decoration:none; color:#1877f2; }
</style>
</head>
<body>
<form method="POST">
<h2 style="text-align:center;">Login</h2>
<input name="username" placeholder="Username" required>
<input type="password" name="password" placeholder="Password" required>
<button>Login</button>
<p style="text-align:center;">Don't have an account? <a href="/signup">Sign Up</a></p>
</form>
</body>
</html>
"""

SIGNUP_HTML = """
<!DOCTYPE html>
<html>
<head>
<title>Chatternet Signup</title>
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<style>
body { margin:0; font-family:Arial; background:#f0f2f5; display:flex; justify-content:center; align-items:center; height:100vh; }
form { background:white; padding:30px; border-radius:15px; width:90%; max-width:350px; box-shadow:0 2px 10px rgba(0,0,0,0.1); }
input { width:100%; padding:10px; margin:10px 0; border-radius:5px; border:1px solid #ccc; }
button { width:100%; padding:10px; border:none; border-radius:5px; background:#27ae60; color:white; font-weight:bold; }
a { text-decoration:none; color:#1877f2; }
</style>
</head>
<body>
<form method="POST">
<h2 style="text-align:center;">Sign Up</h2>
<input name="username" placeholder="Username" required>
<input type="email" name="email" placeholder="Email" required>
<input type="password" name="password" placeholder="Password" required>
<button>Sign Up</button>
<p style="text-align:center;">Already have an account? <a href="/login">Login</a></p>
</form>
</body>
</html>
"""


if __name__ == "__main__":
    socketio.run(app, debug=True)

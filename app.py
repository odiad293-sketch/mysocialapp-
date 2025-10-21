from flask import Flask, render_template_string, request, redirect, session, jsonify, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_socketio import SocketIO, emit, join_room
from datetime import datetime
import os

# ================= APP CONFIG =================
app = Flask(__name__)
app.secret_key = "chatternet_secret_key"
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///chatternet.db"
app.config['UPLOAD_FOLDER'] = "static"
db = SQLAlchemy(app)
socketio = SocketIO(app)

# ================= DATABASE MODELS ==============
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(50), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    banned = db.Column(db.Boolean, default=False)

class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    author = db.Column(db.String(50), nullable=False)
    content = db.Column(db.Text)
    image = db.Column(db.String(100))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender = db.Column(db.String(50), nullable=False)
    receiver = db.Column(db.String(50), nullable=False)
    text = db.Column(db.Text)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

class Logo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(100), nullable=False)

class Follow(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    follower = db.Column(db.String(50), nullable=False)
    followed = db.Column(db.String(50), nullable=False)

with app.app_context():
    db.create_all()
    if not os.path.exists('static'):
        os.makedirs('static')

# ================= ROUTES =======================
@app.route('/')
def home():
    logo = Logo.query.first()
    posts = Post.query.order_by(Post.timestamp.desc()).all()
    user = session.get("user")
    return render_template_string(HOME_HTML, user=user, posts=posts, logo=logo)

@app.route('/login', methods=['GET','POST'])
def login():
    if request.method=='POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username, password=password).first()
        if user:
            if user.banned:
                return "You are banned."
            session['user'] = user.username
            return redirect('/')
        return "Invalid credentials."
    return render_template_string(LOGIN_HTML)

@app.route('/signup', methods=['GET','POST'])
def signup():
    if request.method=='POST':
        username = request.form['username']
        password = request.form['password']
        if User.query.filter_by(username=username).first():
            return "Username already exists."
        is_first = (User.query.count()==0)
        new_user = User(username=username, password=password, is_admin=is_first)
        db.session.add(new_user)
        db.session.commit()
        return redirect('/login')
    return render_template_string(SIGNUP_HTML)

@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect('/login')

@app.route('/post', methods=['POST'])
def post():
    user = session.get("user")
    if not user: return redirect('/login')
    content = request.form.get('content')
    file = request.files.get('image')
    filename = None
    if file and file.filename != "":
        filename = f"{datetime.utcnow().timestamp()}_{file.filename}"
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
    new_post = Post(author=user, content=content, image=filename)
    db.session.add(new_post)
    db.session.commit()
    return redirect('/')

@app.route('/profile/<username>')
def profile(username):
    user = session.get("user")
    profile_user = User.query.filter_by(username=username).first()
    if not profile_user:
        return "User not found."
    posts = Post.query.filter_by(author=username).order_by(Post.timestamp.desc()).all()
    return render_template_string(PROFILE_HTML, user=user, profile_user=profile_user, posts=posts)

@app.route('/messenger')
def messenger():
    user = session.get("user")
    if not user: return redirect('/login')
    users = User.query.filter(User.username!=user).all()
    return render_template_string(MESSENGER_HTML, user=user, users=users)

@app.route('/get_messages/<friend>')
def get_messages(friend):
    user = session.get("user")
    if not user: return jsonify([])
    msgs = Message.query.filter(
        ((Message.sender==user)&(Message.receiver==friend))|
        ((Message.sender==friend)&(Message.receiver==user))
    ).order_by(Message.timestamp.asc()).all()
    return jsonify([{"sender":m.sender,"text":m.text,"time":m.timestamp.strftime("%H:%M")} for m in msgs])

@app.route('/friends', methods=['GET','POST'])
def friends():
    user = session.get("user")
    if not user: return redirect('/login')
    if request.method=='POST':
        target = request.form.get('username')
        if target and target != user and not Follow.query.filter_by(follower=user, followed=target).first():
            db.session.add(Follow(follower=user, followed=target))
            db.session.commit()
        return redirect('/friends')
    search = request.args.get('search')
    if search:
        users = User.query.filter(User.username.contains(search), User.username!=user).all()
    else:
        users = User.query.filter(User.username!=user).all()
    following = [f.followed for f in Follow.query.filter_by(follower=user).all()]
    return render_template_string(FRIENDS_HTML, user=user, users=users, following=following)

@app.route('/admin', methods=['GET','POST'])
def admin():
    user = session.get("user")
    admin = User.query.filter_by(username=user, is_admin=True).first()
    if not admin: return "Access denied."
    users = User.query.filter(User.username!=user).all()
    if request.method=='POST':
        action = request.form.get('action')
        target = request.form.get('target')
        t_user = User.query.filter_by(username=target).first()
        if t_user:
            if action=="ban":
                t_user.banned = True
            elif action=="unban":
                t_user.banned = False
            db.session.commit()
        file = request.files.get('logo')
        if file:
            filename = "logo.png"
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            if Logo.query.first():
                db.session.query(Logo).delete()
            db.session.add(Logo(filename=filename))
            db.session.commit()
        return redirect('/admin')
    logo = Logo.query.first()
    new_msgs_count = db.session.query(Message.receiver, db.func.count(Message.id)).group_by(Message.receiver).all()
    new_msgs_dict = {receiver:count for receiver,count in new_msgs_count}
    return render_template_string(ADMIN_HTML, user=user, users=users, logo=logo, new_msgs=new_msgs_dict)

# ================= SOCKET.IO ==================
@socketio.on('join')
def on_join(data):
    join_room(data['username'])

@socketio.on('send_message')
def handle_message(data):
    sender = data['sender']
    receiver = data['receiver']
    text = data['text']
    msg = Message(sender=sender, receiver=receiver, text=text)
    db.session.add(msg)
    db.session.commit()
    admin = User.query.filter_by(is_admin=True).first()
    if admin:
        emit('admin_notify', {'receiver':receiver}, room=admin.username)
    emit('receive_message', {'sender':sender,'text':text,'time':msg.timestamp.strftime("%H:%M")}, room=receiver)
    emit('receive_message', {'sender':sender,'text':text,'time':msg.timestamp.strftime("%H:%M")}, room=sender)

# ================= HTML TEMPLATES =================
# ---- LOGIN ----
LOGIN_HTML = """
<!DOCTYPE html>
<html><head><title>Login</title></head>
<body style="text-align:center; background:#f0f2f5;">
<h2>Login</h2>
<form method="POST">
<input name="username" placeholder="Username" required><br>
<input type="password" name="password" placeholder="Password" required><br>
<button>Login</button>
</form>
<p>Don't have an account? <a href="/signup">Sign up</a></p>
</body></html>
"""

# ---- SIGNUP ----
SIGNUP_HTML = """
<!DOCTYPE html>
<html><head><title>Signup</title></head>
<body style="text-align:center; background:#f0f2f5;">
<h2>Sign Up</h2>
<form method="POST">
<input name="username" placeholder="Username" required><br>
<input type="password" name="password" placeholder="Password" required><br>
<button>Sign Up</button>
</form>
<p>Already have account? <a href="/login">Login</a></p>
</body></html>
"""

# ---- HOME / DASHBOARD ----
HOME_HTML = """
<!DOCTYPE html>
<html>
<head>
<title>Chatternet</title>
<style>
body { font-family: Arial; background:#e9ebee; margin:0;}
header { background:#1877f2; color:white; padding:10px; font-size:20px; text-align:center; }
.feed { max-width:500px; margin:20px auto; background:white; border-radius:10px; padding:10px; }
.post { border-bottom:1px solid #ccc; padding:10px; }
.post img { max-width:100%; height:auto; margin-top:5px; }
.nav-btn { padding:5px 10px; margin:2px; background:#1877f2; color:white; border:none; border-radius:5px; }
</style>
</head>
<body>
<header>
{% if logo %}<img src="/static/{{logo.filename}}" width="50" height="50">{% endif %}
Chatternet
</header>
{% if user %}
<div style="text-align:center; margin:10px;">
<button onclick="window.location.href='/messenger'" class="nav-btn">Messenger</button>
<button onclick="window.location.href='/friends'" class="nav-btn">Friends</button>
<button onclick="window.location.href='/profile/{{user}}'" class="nav-btn">My Profile</button>
{% if user=='{{user}}' and users|selectattr('is_admin')|list %}<button onclick="window.location.href='/admin'" class="nav-btn">Admin</button>{% endif %}
<a href="/logout" class="nav-btn">Logout</a>
</div>
<div class="feed">
<h3>Post something</h3>
<form method="POST" action="/post" enctype="multipart/form-data">
<textarea name="content" style="width:100%;height:60px;" placeholder="What's on your mind?"></textarea><br>
<input type="file" name="image"><br>
<button>Post</button>
</form>
</div>
{% for post in posts %}
<div class="feed post">
<b>{{post.author}}</b>: {{post.content}} <br>
{% if post.image %}<img src="/static/{{post.image}}">{% endif %}
<small>{{post.timestamp.strftime('%Y-%m-%d %H:%M')}}</small>
</div>
{% endfor %}
{% else %}
<p style="text-align:center;">Please <a href="/login">login</a> to see the content.</p>
{% endif %}
</body>
</html>
"""

# ---- PROFILE HTML ----
PROFILE_HTML = """
<!DOCTYPE html>
<html>
<head><title>{{profile_user.username}}'s Profile</title></head>
<body style="text-align:center; background:#f0f2f5;">
<h2>{{profile_user.username}}'s Profile</h2>
<a href="/">Dashboard</a> | <a href="/messenger">Messenger</a> | <a href="/friends">Friends</a>
{% for post in posts %}
<div style="border:1px solid #ccc; margin:10px; padding:10px;">
<b>{{post.author}}</b>: {{post.content}} <br>
{% if post.image %}<img src="/static/{{post.image}}" style="max-width:300px;"><br>{% endif %}
<small>{{post.timestamp.strftime('%Y-%m-%d %H:%M')}}</small>
</div>
{% endfor %}
</body>
</html>
"""

# ---- FRIENDS HTML ----
FRIENDS_HTML = """
<!DOCTYPE html>
<html>
<head><title>Friends</title></head>
<body style="text-align:center;">
<h2>Search & Follow Friends</h2>
<form method="GET">
<input name="search" placeholder="Search by username">
<button>Search</button>
</form>
{% for u in users %}
<div>
{{u.username}}
{% if u.username not in following %}
<form method="POST" style="display:inline;">
<input type="hidden" name="username" value="{{u.username}}">
<button>Follow</button>
</form>
{% else %}Following{% endif %}
</div>
{% endfor %}
<br><a href="/">Dashboard</a>
</body>
</html>
"""

# ---- MESSENGER HTML ----
MESSENGER_HTML = """
<!DOCTYPE html>
<html>
<head>
<title>Messenger</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.7.2/socket.io.js"></script>
<style>
body { font-family: Arial; margin:0; background:#e9ebee; }
.chatbox { max-width:500px; margin:20px auto; background:white; border-radius:10px; padding:10px; }
.msg { padding:5px; margin:5px; border-radius:15px; }
.self { background:#1877f2; color:white; text-align:right; }
.other { background:#f0f0f0; color:black; text-align:left; }
</style>
</head>
<body>
<h2 style="text-align:center;">Messenger</h2>
<select id="friendSelect">
<option value="">Select Friend</option>
{% for u in users %}
<option value="{{u.username}}">{{u.username}}</option>
{% endfor %}
</select>
<div id="messages" style="height:300px; overflow-y:auto; border:1px solid #ccc; margin:10px; padding:5px

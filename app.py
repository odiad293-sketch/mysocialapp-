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
# ================= PART 2 ===================
# ================= ROUTES - DASHBOARD, PROFILE, ADMIN, MESSENGER ===================

@app.route('/profile/<username>')
def profile(username):
    if 'user' not in session:
        return redirect('/login')
    user = User.query.filter_by(username=username).first()
    if not user:
        return "User not found."
    posts = Post.query.filter_by(author=username).order_by(Post.timestamp.desc()).all()
    current_user = User.query.filter_by(username=session['user']).first()
    return render_template_string(PROFILE_HTML, profile_user=user, posts=posts, current_user=current_user)

@app.route('/admin')
def admin_page():
    if 'user' not in session:
        return redirect('/login')
    current_user = User.query.filter_by(username=session['user']).first()
    if not current_user.is_admin:
        return "Access denied."
    users = User.query.all()
    messages = Message.query.order_by(Message.timestamp.desc()).all()
    return render_template_string(ADMIN_HTML, users=users, messages=messages)

@app.route('/messenger')
def messenger_page():
    if 'user' not in session:
        return redirect('/login')
    user = User.query.filter_by(username=session['user']).first()
    friends = user.following.all() + user.followers.all()
    friends = list({f.username:f for f in friends}.values())  # remove duplicates
    return render_template_string(MESSENGER_HTML, user=user, friends=friends)

@app.route('/send_message', methods=['POST'])
def send_message():
    if 'user' not in session:
        return redirect('/login')
    sender = session['user']
    receiver = request.form['receiver']
    text = request.form['text']
    if not text or not receiver:
        return redirect('/messenger')
    msg = Message(sender=sender, receiver=receiver, text=text)
    db.session.add(msg)
    db.session.commit()
    return redirect('/messenger')

@app.route('/follow/<username>')
def follow_user(username):
    if 'user' not in session:
        return redirect('/login')
    current_user = User.query.filter_by(username=session['user']).first()
    target_user = User.query.filter_by(username=username).first()
    if target_user and target_user != current_user:
        if not current_user.is_following(target_user):
            current_user.following.append(target_user)
            db.session.commit()
    return redirect(url_for('profile', username=username))

@app.route('/unfollow/<username>')
def unfollow_user(username):
    if 'user' not in session:
        return redirect('/login')
    current_user = User.query.filter_by(username=session['user']).first()
    target_user = User.query.filter_by(username=username).first()
    if target_user and current_user.is_following(target_user):
        current_user.following.remove(target_user)
        db.session.commit()
    return redirect(url_for('profile', username=username))

# ================= SOCKET.IO HANDLERS ===================
@socketio.on('join')
def handle_join(data):
    username = data['username']
    join_room(username)

@socketio.on('send_message_socket')
def handle_socket_message(data):
    sender = data['sender']
    receiver = data['receiver']
    text = data['text']
    msg = Message(sender=sender, receiver=receiver, text=text)
    db.session.add(msg)
    db.session.commit()
    # Emit to both sender and receiver only
    emit('receive_message', {'sender': sender, 'text': text}, room=receiver)
    emit('receive_message', {'sender': sender, 'text': text}, room=sender)

# ================= HELPER METHODS FOR FOLLOW ===================
def is_following(self, user):
    return self.following.filter(followers.c.followed_id==user.id).count() > 0

User.is_following = is_following

# ================= HTML TEMPLATES - PART 2 ===================

DASHBOARD_HTML = """
<!DOCTYPE html>
<html>
<head>
<title>Dashboard - Chatternet</title>
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<style>
body{margin:0; font-family:Arial; background:#f0f2f5;}
header{background:#1877f2; color:white; padding:15px; text-align:center; font-size:20px; position:sticky; top:0;}
.container{max-width:800px; margin:20px auto; padding:10px;}
.feed, .profile-section{background:white; border-radius:10px; padding:10px; margin-bottom:20px; box-shadow:0 0 5px rgba(0,0,0,0.2);}
.post{border-bottom:1px solid #ccc; padding:10px;}
button{background:#1877f2; color:white; border:none; padding:5px 10px; border-radius:5px; cursor:pointer;}
button:hover{opacity:0.9;}
a{color:#1877f2; text-decoration:none;}
</style>
</head>
<body>
<header>📘 Chatternet - Welcome {{user.username}}</header>
<div class="container">
{% if admin and admin.username == user.username %}
<p><a href="/admin">Go to Admin Page</a></p>
{% endif %}
<p><a href="/messenger">Messenger</a> | <a href="/profile/{{user.username}}">My Profile</a> | <a href="/logout">Logout</a></p>

<div class="feed">
<h3>📝 What's on your mind?</h3>
<form method="POST" action="/post" enctype="multipart/form-data">
<textarea name="content" placeholder="Write something..." style="width:100%; height:60px;"></textarea><br>
<input type="file" name="image">
<br><button>Post</button>
</form>
<hr>
{% for post in posts %}
<div class="post">
<b>{{post.author}}</b>: {{post.content}}<br>
{% if post.image %}
<img src="{{url_for('static', filename='uploads/' + post.image)}}" style="max-width:100%; border-radius:5px;"><br>
{% endif %}
<small>{{post.timestamp}}</small>
</div>
{% endfor %}
</div>
</div>
</body>
</html>
"""

PROFILE_HTML = """
<!DOCTYPE html>
<html>
<head>
<title>{{profile_user.username}} - Profile</title>
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<style>
body{margin:0; font-family:Arial; background:#f0f2f5;}
header{background:#1877f2; color:white; padding:15px; text-align:center; font-size:20px;}
.container{max-width:800px; margin:20px auto; padding:10px;}
.feed{background:white; border-radius:10px; padding:10px; margin-bottom:20px; box-shadow:0 0 5px rgba(0,0,0,0.2);}
.post{border-bottom:1px solid #ccc; padding:10px;}
button{background:#1877f2; color:white; border:none; padding:5px 10px; border-radius:5px; cursor:pointer;}
button:hover{opacity:0.9;}
a{color:#1877f2; text-decoration:none;}
</style>
</head>
<body>
<header>{{profile_user.username}} - Profile</header>
<div class="container">
<p><a href="/dashboard">Back to Dashboard</a> | <a href="/messenger">Messenger</a></p>
{% if current_user.username != profile_user.username %}
{% if current_user.is_following(profile_user) %}
<a href="/unfollow/{{profile_user.username}}"><button>Unfollow</button></a>
{% else %}
<a href="/follow/{{profile_user.username}}"><button>Follow</button></a>
{% endif %}
{% endif %}
<div class="feed">
<h3>Posts by {{profile_user.username}}</h3>
{% for post in posts %}
<div class="post">
{{post.content}}<br>
{% if post.image %}
<img src="{{url_for('static', filename='uploads/' + post.image)}}" style="max-width:100%; border-radius:5px;"><br>
{% endif %}
<small>{{post.timestamp}}</small>
</div>
{% endfor %}
</div>
</div>
</body>
</html>
"""

ADMIN_HTML = """
<!DOCTYPE html>
<html>
<head>
<title>Admin Panel</title>
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<style>
body{margin:0; font-family:Arial; background:#f0f2f5;}
header{background:#ff4d4d; color:white; padding:15px; text-align:center; font-size:20px;}
.container{max-width:800px; margin:20px auto; padding:10px;}
.user-list, .messages{background:white; border-radius:10px; padding:10px; margin-bottom:20px; box-shadow:0 0 5px rgba(0,0,0,0.2);}
button{background:#ff4d4d; color:white; border:none; padding:5px 10px; border-radius:5px; cursor:pointer;}
button:hover{opacity:0.9;}
a{color:#1877f2; text-decoration:none;}
</style>
</head>
<body>
<header>Admin Panel</header>
<div class="container">
<p><a href="/dashboard">Back to Dashboard</a></p>
<div class="user-list">
<h3>Users</h3>
{% for u in users %}
<div>
<b>{{u.username}}</b> | Email/Phone: {{u.email_or_phone}} | {% if u.banned %}BANNED{% else %}Active{% endif %}
{% if not u.is_admin %}
<a href="/ban/{{u.username}}"><button>Ban</button></a>
{% endif %}
</div>
{% endfor %}
</div>
<div class="messages">
<h3>Message Notifications</h3>
{% for m in messages %}
<div>{{m.sender}} sent a message to {{m.receiver}} at {{m.timestamp}}</div>
{% endfor %}
</div>
</div>
</body>
</html>
"""

MESSENGER_HTML = """
<!DOCTYPE html>
<html>
<head>
<title>Messenger - Chatternet</title>
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.7.2/socket.io.js"></script>
<style>
body{margin:0; font-family:Arial; background:#f0f2f5;}
header{background:#1877f2; color:white; padding:15px; text-align:center; font-size:20px;}
.container{max-width:800px; margin:20px auto; padding:10px;}
.chatbox{background:white; border-radius:10px; padding:10px; box-shadow:0 0 5px rgba(0,0,0,0.2);}
.msg{padding:5px; margin:5px; border-radius:15px;}
.self{background:#1877f2; color:white; text-align:right;}
.other{background:#f0f0f0; color:black; text-align:left;}
select,input,button{padding:10px; margin:5px;}
button{background:#1877f2; color:white; border:none; border-radius:5px; cursor:pointer;}
button:hover{opacity:0.9;}
</style>
</head>
<body>
<header>Messenger - {{user.username}}</header>
<div class="container">
<p><a href="/dashboard">Dashboard</a> | <a href="/profile/{{user.username}}">My Profile</a></p>
<div class="chatbox">
<h4>💬 Chat</h4>
<select id="friendSelect" style="width:100%;">
{% for f in friends %}
<option value="{{f.username}}">{{f.username}}</option>
{% endfor %}
</select>
<div id="messages" style="height:300px; overflow-y:auto; border:1px solid #ccc; padding:5px;"></div>
<input id="msgInput" placeholder="Type message..." style="width:70%;">
<button id="sendBtn">Send</button>
</div>
</div>
<script>
const socket = io();
const user = "{{user.username}}";
socket.emit('join', {username:user});

document.getElementById("sendBtn").onclick = () => {
    const receiver = document.getElementById("friendSelect").value;
    const text = document.getElementById("msgInput").value;
    if(!receiver || !text) return;
    socket.emit('send_message_socket', {sender:user, receiver, text});
    document.getElementById("msgInput").value = "";
};

socket.on('receive_message', data=>{
    const div = document.createElement("div");
    div.className = "msg " + (data.sender===user ? "self":"other");
    div.innerText = data.sender + ": " + data.text;
    document.getElementById("messages").appendChild(div);
});
</script>
</body>
</html>
"""

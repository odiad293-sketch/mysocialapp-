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

# =================== DASHBOARD HTML ===================
DASHBOARD_HTML = """
<!DOCTYPE html>
<html>
<head>
<title>Chatternet Dashboard</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.7.2/socket.io.js"></script>
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<style>
body { margin:0; font-family:Arial; background:#f0f2f5; }
header { background:#1877f2; color:white; padding:15px; font-size:20px; text-align:center; position:sticky; top:0; }
.container { max-width:700px; margin:20px auto; }
.post-box { background:white; border-radius:10px; padding:15px; margin-bottom:20px; box-shadow:0 2px 8px rgba(0,0,0,0.1);}
textarea { width:100%; padding:10px; border-radius:5px; border:1px solid #ccc; }
button { background:#1877f2; color:white; padding:10px 20px; border:none; border-radius:5px; cursor:pointer; margin-top:10px; }
.post { background:white; padding:10px; border-radius:8px; margin-bottom:10px; box-shadow:0 1px 5px rgba(0,0,0,0.1);}
.post img { max-width:100%; border-radius:5px; margin-top:5px; }
.navbar { display:flex; justify-content:space-between; margin-bottom:10px; }
.navbar button { padding:8px 15px; }
</style>
</head>
<body>
<header>📘 Chatternet - Welcome {{user.username}}</header>
<div class="container">
<div class="navbar">
    <div>
        <button onclick="window.location='/profile/{{user.username}}'">My Profile</button>
        <button onclick="window.location='/messenger'">Messenger</button>
        {% if user.is_admin %}
        <button onclick="window.location='/admin'">Admin</button>
        {% endif %}
    </div>
    <div>
        <button onclick="window.location='/logout'">Logout</button>
    </div>
</div>

<div class="post-box">
<form method="POST" action="/post" enctype="multipart/form-data">
<textarea name="content" placeholder="What's on your mind?"></textarea>
<input type="file" name="image" accept="image/*"><br>
<button>Post</button>
</form>
</div>

{% for post in posts %}
<div class="post">
<b>{{post.author}}</b> <small>{{post.timestamp}}</small>
<p>{{post.content}}</p>
{% if post.image_filename %}
<img src="/static/uploads/{{post.image_filename}}">
{% endif %}
</div>
{% endfor %}
</div>
</body>
</html>
"""

# =================== PROFILE HTML ===================
PROFILE_HTML = """
<!DOCTYPE html>
<html>
<head>
<title>{{profile.username}} - Profile</title>
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<style>
body { margin:0; font-family:Arial; background:#f0f2f5; }
header { background:#1877f2; color:white; padding:15px; font-size:20px; text-align:center; position:sticky; top:0; }
.container { max-width:700px; margin:20px auto; }
.post { background:white; padding:10px; border-radius:8px; margin-bottom:10px; box-shadow:0 1px 5px rgba(0,0,0,0.1);}
.post img { max-width:100%; border-radius:5px; margin-top:5px; }
button { background:#1877f2; color:white; padding:8px 15px; border:none; border-radius:5px; cursor:pointer; margin:5px 0; }
</style>
</head>
<body>
<header>{{profile.username}}'s Profile</header>
<div class="container">
<button onclick="window.location='/dashboard'">Back to Dashboard</button>
<h2>Posts</h2>
{% for post in posts %}
<div class="post">
<p>{{post.content}}</p>
{% if post.image_filename %}
<img src="/static/uploads/{{post.image_filename}}">
{% endif %}
<small>{{post.timestamp}}</small>
</div>
{% endfor %}
</div>
</body>
</html>
"""

# =================== MESSENGER HTML ===================
MESSENGER_HTML = """
<!DOCTYPE html>
<html>
<head>
<title>Messenger - {{user}}</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.7.2/socket.io.js"></script>
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<style>
body { margin:0; font-family:Arial; background:#f0f2f5; display:flex; flex-direction:column; height:100vh; }
header { background:#1877f2; color:white; padding:15px; text-align:center; font-size:20px; position:sticky; top:0; }
.container { flex:1; display:flex; }
.users { width:30%; border-right:1px solid #ccc; overflow-y:auto; background:white; }
.users input { width:90%; margin:10px; padding:5px; border-radius:5px; border:1px solid #ccc; }
.user { padding:10px; cursor:pointer; border-bottom:1px solid #eee; }
.user:hover { background:#f0f0f0; }
.chat { flex:1; display:flex; flex-direction:column; }
.messages { flex:1; overflow-y:auto; padding:10px; }
.message { padding:5px 10px; margin:5px; border-radius:15px; max-width:70%; }
.self { background:#1877f2; color:white; align-self:flex-end; }
.other { background:#e0e0e0; align-self:flex-start; }
input#msgInput { width:80%; padding:10px; margin:5px; border-radius:5px; border:1px solid #ccc; }
button#sendBtn { padding:10px 15px; border:none; background:#1877f2; color:white; border-radius:5px; cursor:pointer; }
.notification { color:red; font-weight:bold; }
</style>
</head>
<body>
<header>Messenger - {{user}} <span id="notif" class="notification"></span></header>
<div class="container">
<div class="users">
<input type="text" id="searchUser" placeholder="Search users">
<div id="userList"></div>
</div>
<div class="chat">
<div id="messages" class="messages"></div>
<div>
<input id="msgInput" placeholder="Type a message">
<button id="sendBtn">Send</button>
</div>
</div>
</div>
<script>
const socket = io();
const user = "{{user}}";
let currentFriend = null;
socket.emit('join', {username:user});

function loadUsers(query='') {
    fetch('/search_users?q='+query).then(r=>r.json()).then(data=>{
        const userList = document.getElementById('userList');
        userList.innerHTML = '';
        data.forEach(u=>{
            const div = document.createElement('div');
            div.className='user';
            div.innerText=u;
            div.onclick = ()=>{ selectFriend(u); };
            userList.appendChild(div);
        });
    });
}

document.getElementById('searchUser').oninput = (e)=>{ loadUsers(e.target.value); };

function selectFriend(friend){
    currentFriend=friend;
    document.getElementById('messages').innerHTML='';
    fetch('/get_messages/'+friend).then(r=>r.json()).then(data=>{
        data.forEach(m=>{
            const div = document.createElement('div');
            div.className='message ' + (m.sender===user?'self':'other');
            div.innerText = m.sender + ': ' + m.text;
            document.getElementById('messages').appendChild(div);
        });
    });
}

document.getElementById('sendBtn').onclick = ()=>{
    const text=document.getElementById('msgInput').value;
    if(!currentFriend || !text) return;
    socket.emit('send_message',{sender:user,receiver:currentFriend,text:text});
    document.getElementById('msgInput').value='';
};

socket.on('receive_message',data=>{
    if(data.sender===currentFriend || data.sender===user){
        const div=document.createElement('div');
        div.className='message '+(data.sender===user?'self':'other');
        div.innerText = data.sender + ': ' + data.text;
        document.getElementById('messages').appendChild(div);
        document.getElementById('messages').scrollTop=document.getElementById('messages').scrollHeight;
    }
});

socket.on('admin_notify',data=>{
    if(currentFriend!==data.receiver){
        document.getElementById('notif').innerText='🔔 New message for '+data.receiver;
        setTimeout(()=>{document.getElementById('notif').innerText='';},3000);
    }
});

loadUsers();
</script>
</body>
</html>
"""


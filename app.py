from flask import Flask, render_template_string, request, redirect, session, jsonify, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_socketio import SocketIO, emit, join_room
from datetime import datetime
import os
import time

app = Flask(__name__)
app.secret_key = "chatternet_secret_key"
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///chatternet.db"
app.config['UPLOAD_FOLDER'] = "static"
db = SQLAlchemy(app)
socketio = SocketIO(app)

# ================= DATABASE MODELS =================
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(50), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=True)
    phone = db.Column(db.String(20), unique=True, nullable=True)
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

# ================= ROUTES =========================
@app.route('/')
def splash():
    logo = Logo.query.first()
    return render_template_string(SPLASH_HTML, logo=logo)

@app.route('/dashboard')
def home():
    user = session.get("user")
    if not user: return redirect('/login')
    logo = Logo.query.first()
    posts = Post.query.order_by(Post.timestamp.desc()).all()
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
            return redirect('/dashboard')
        return "Invalid credentials."
    return render_template_string(LOGIN_HTML)

@app.route('/signup', methods=['GET','POST'])
def signup():
    if request.method=='POST':
        username = request.form['username']
        password = request.form['password']
        email = request.form.get('email')
        phone = request.form.get('phone')

        if not email and not phone:
            return "You must provide either email or phone."

        if User.query.filter_by(username=username).first():
            return "Username already exists."
        if email and User.query.filter_by(email=email).first():
            return "Email already in use."
        if phone and User.query.filter_by(phone=phone).first():
            return "Phone number already in use."

        is_first = (User.query.count()==0)
        new_user = User(username=username, password=password, email=email, phone=phone, is_admin=is_first)
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
    return redirect('/dashboard')

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

# ================= HTML TEMPLATES ==================
SPLASH_HTML = """<!DOCTYPE html>
<html><head><title>Welcome</title>
<script>
setTimeout(function(){ window.location.href='/dashboard'; }, 3000);
</script>
</head><body>
{% if logo %}<img src="/static/{{logo.filename}}" width="200">{% else %}<h1>Welcome to Chatternet</h1>{% endif %}
</body></html>
"""

LOGIN_HTML = """<!DOCTYPE html>
<html><head><title>Login</title></head><body>
<h2>Login</h2>
<form method="POST">
<input name="username" placeholder="Username" required><br>
<input name="password" type="password" placeholder="Password" required><br>
<button>Login</button>
<p><a href="/signup">Sign up</a></p>
</form>
</body></html>
"""

SIGNUP_HTML = """<!DOCTYPE html>
<html><head><title>Signup</title></head><body>
<h2>Signup</h2>
<form method="POST">
<input name="username" placeholder="Username" required><br>
<input name="password" type="password" placeholder="Password" required><br>
<input name="email" placeholder="Email (optional)"><br>
<input name="phone" placeholder="Phone (optional)"><br>
<button>Sign Up</button>
<p><a href="/login">Already have an account?</a></p>
</form>
</body></html>
"""

HOME_HTML = """<!DOCTYPE html>
<html><head><title>Dashboard</title></head><body>
{% if logo %}<img src="/static/{{logo.filename}}" width="200">{% endif %}
<h2>Welcome {{user}}</h2>
<a href="/logout">Logout</a> | <a href="/messenger">Messenger</a> | <a href="/friends">Friends</a> | <a href="/profile/{{user}}">Profile</a> {% if user==User.query.filter_by(is_admin=True).first().username %}| <a href="/admin">Admin</a>{% endif %}
<h3>Create Post</h3>
<form method="POST" action="/post" enctype="multipart/form-data">
<textarea name="content" placeholder="Post content"></textarea><br>
<input type="file" name="image"><br>
<button>Post</button>
</form>
<h3>Posts</h3>
{% for post in posts %}
<div><b>{{post.author}}</b>: {{post.content}} {% if post.image %}<br><img src="/static/{{post.image}}" width="100">{% endif %} <small>{{post.timestamp}}</small></div>
{% endfor %}
</body></html>
"""

PROFILE_HTML = """<!DOCTYPE html>
<html><head><title>{{profile_user.username}}</title></head><body>
<h2>{{profile_user.username}}'s Profile</h2>
<a href="/dashboard">Back</a>
<h3>Posts</h3>
{% for post in posts %}
<div>{{post.content}} {% if post.image %}<br><img src="/static/{{post.image}}" width="100">{% endif %}</div>
{% endfor %}
</body></html>
"""

FRIENDS_HTML = """<!DOCTYPE html>
<html><head><title>Friends</title></head><body>
<h2>Find Friends</h2>
<form method="GET">
<input name="search" placeholder="Search users">
<button>Search</button>
</form>
<form method="POST">
{% for u in users %}
<div>{{u.username}} {% if u.username not in following %}<button name="username" value="{{u.username}}">Follow</button>{% else %}Following{% endif %}</div>
{% endfor %}
</form>
<a href="/dashboard">Back</a>
</body></html>
"""

MESSENGER_HTML = """<!DOCTYPE html>
<html><head><title>Messenger</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.7.2/socket.io.js"></script>
</head><body>
<h2>Messenger</h2>
<a href="/dashboard">Back</a>
<select id="friendSelect">
{% for u in users %}
<option value="{{u.username}}">{{u.username}}</option>
{% endfor %}
</select><br>
<div id="messages" style="height:300px; overflow-y:auto; border:1px solid #ccc; margin:10px; padding:5px;"></div>
<input id="msgInput" placeholder="Type a message">
<button id="sendBtn">Send</button>

<script>
const socket = io();
const user = "{{user}}";
socket.emit('join',{username:user});
document.getElementById("sendBtn").onclick = ()=>{
    const receiver = document.getElementById("friendSelect").value;
    const text = document.getElementById("msgInput").value;
    if(!receiver || !text) return;
    socket.emit('send_message',{sender:user,receiver,text});
    document.getElementById("msgInput").value="";
};
socket.on('receive_message', data=>{
    const div = document.createElement("div");
    div.innerText = data.sender + ": " + data.text;
    document.getElementById("messages").appendChild(div);
});
socket.on('admin_notify', data=>{
    console.log("Admin notified: message sent to "+data.receiver);
});
</script>
</body></html>
"""

ADMIN_HTML = """<!DOCTYPE html>
<html><head><title>Admin</title></head><body>
<h2>Admin Panel</h2>
<a href="/dashboard">Back</a>
<h3>Manage Users</h3>
<form method="POST" enctype="multipart/form-data">
{% for u in users %}
<div>{{u.username}} 
<button name="action" value="ban" type="submit" formaction="?target={{u.username}}">Ban</button>
<button name="action" value="unban" type="submit" formaction="?target={{u.username}}">Unban</button>
</div>
{% endfor %}
<h3>Upload Logo</h3>
<input type="file" name="logo">
<button type="submit">Upload</button>
</form>
<h3>Message Notifications</h3>
<ul>
{% for r,count in new_msgs.items() %}
<li>{{r}} received {{count}} messages</li>
{% endfor %}
</ul>
</body></html>
"""

if __name__ == "__main__":
    socketio.run(app, debug=True)

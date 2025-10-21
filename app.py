from flask import Flask, render_template_string, request, redirect, session, jsonify
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
    followers = db.relationship('Follow', backref='user', lazy=True)

class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    author = db.Column(db.String(50), nullable=False)
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender = db.Column(db.String(50), nullable=False)
    receiver = db.Column(db.String(50), nullable=False)
    text = db.Column(db.Text, nullable=False)
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
    content = request.form['content']
    new_post = Post(author=user, content=content)
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
    # Count new messages for notifications (admin sees only counts)
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
    # Notify admin that a message was sent (count only)
    admin = User.query.filter_by(is_admin=True).first()
    if admin:
        emit('admin_notify', {'receiver':receiver}, room=admin.username)
    emit('receive_message', {'sender':sender,'text':text,'time':msg.timestamp.strftime("%H:%M")}, room=receiver)
    emit('receive_message', {'sender':sender,'text':text,'time':msg.timestamp.strftime("%H:%M")}, room=sender)

# ================= HTML TEMPLATES =================
LOGIN_HTML = """
<!DOCTYPE html><html><head><title>Login</title></head>
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

SIGNUP_HTML = """
<!DOCTYPE html><html><head><title>Signup</title></head>
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

HOME_HTML = """
<!DOCTYPE html>
<html><head><title>Chatternet</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.7.2/socket.io.js"></script>
<style>
body{font-family:Arial; margin:0; background:#e9ebee;}
header{background:#1877f2; color:white; padding:10px; text-align:center;}
.feed{max-width:500px;margin:20px auto; background:white; border-radius:10px; padding:10px;}
.post{border-bottom:1px solid #ccc; padding:10px;}
button{background:#1877f2;color:white;border:none;padding:5px 10px;border-radius:5px;margin:5px;}
#notif{color:red;font-weight:bold;}
</style>
</head>
<body>
{% if logo %}
<div style="text-align:center;"><img src="/static/{{logo.filename}}" style="max-width:200px;"></div>
<script>setTimeout(()=>{document.querySelector('img').style.display='none';},3000);</script>
{% endif %}
<header>Chatternet <span id="notif"></span></header>
<div style="text-align:center; margin-top:10px;">
<button onclick="window.location.href='/messenger'">Messenger</button>
<button onclick="window.location.href='/friends'">Find Friends</button>
{% if session.user and session.user == 'Destiny' %}<button onclick="window.location.href='/admin'">Admin</button>{% endif %}
<button onclick="window.location.href='/profile/{{user}}'">Profile</button>
<button onclick="window.location.href='/logout'">Logout</button>
</div>

<div class="feed">
<h3>What's on your mind, {{user}}?</h3>
<form method="POST" action="/post">
<textarea name="content" style="width:100%;height:60px;"></textarea><br>
<button>Post</button>
</form>
{% for post in posts %}
<div class="post"><b>{{post.author}}</b>: {{post.content}} <small>{{post.timestamp}}</small></div>
{% endfor %}
</div>

<script>
const socket=io();
const user="{{user}}";
socket.emit('join',{username:user});
socket.on('admin_notify',data=>{
    document.getElementById('notif').innerText='🔔 New message to '+data.receiver;
});
</script>
</body></html>
"""

PROFILE_HTML = """
<!DOCTYPE html>
<html><head><title>{{profile_user.username}}'s Profile</title></head>
<body style="text-align:center;">
<h2>{{profile_user.username}}'s Profile</h2>
{% if user==profile_user.username %}
<form method="POST" action="/post">
<textarea name="content" style="width:300px;height:60px;"></textarea><br>
<button>Post</button>
</form>
{% endif %}
<h3>Posts</h3>
{% for post in posts %}
<div><b>{{post.author}}</b>: {{post.content}} <small>{{post.timestamp}}</small></div>
{% endfor %}
<button onclick="window.location.href='/'">Back to Dashboard</button>
</body></html>
"""

MESSENGER_HTML = """
<!DOCTYPE html>
<html><head><title>Messenger</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.7.2/socket.io.js"></script>
<style>
body{font-family:Arial; background:#f0f2f5;}
.chatbox{max-width:500px;margin:20px auto;background:white;padding:10px;border-radius:10px;}
.msg{padding:5px;margin:5px;border-radius:15px;}
.self{background:#1877f2;color:white;text-align:right;}
.other{background:#f0f0f0;color:black;text-align:left;}
#notif{color:red;font-weight:bold;}
</style>
</head>
<body>
<h2 style="text-align:center;">Messenger <span id="notif"></span></h2>
<select id="friendSelect">
<option value="">Select Friend</option>
{% for u in users %}<option value="{{u.username}}">{{u.username}}</option>{% endfor %}
</select>
<div id="messages" style="height:300px; overflow-y:auto; border:1px solid #ccc; padding:5px;"></div>
<input id="msgInput" style="width:70%;">
<button id="sendBtn">Send</button>
<br><button onclick="window.location.href='/'">Back to Dashboard</button>

<script>
const socket=io();
const user="{{user}}";
socket.emit('join',{username:user});

function loadMessages(friend){
    if(!friend) return;
    fetch('/get_messages/'+friend).then(r=>r.json()).then(data=>{
        const mbox=document.getElementById('messages'); mbox.innerHTML='';
        data.forEach(d=>{
            const div=document.createElement('div');
            div.className='msg '+(d.sender==user?'self':'other');
            div.innerText=d.sender+': '+d.text;
            mbox.appendChild(div);
        });
        mbox.scrollTop=mbox.scrollHeight;
    });
}

document.getElementById('friendSelect').onchange=()=>{loadMessages(document.getElementById('friendSelect').value);}
document.getElementById('sendBtn').onclick=()=>{
    const friend=document.getElementById('friendSelect').value;
    const text=document.getElementById('msgInput').value;
    if(!friend||!text) return;
    socket.emit('send_message',{sender:user,receiver:friend,text:text});
    document.getElementById('msgInput').value='';
}
socket.on('receive_message',data=>{
    const friend=document.getElementById('friendSelect').value;
    if(data.sender==friend||data.sender==user){
        const div=document.createElement('div');
        div.className='msg '+(data.sender==user?'self':'other');
        div.innerText=data.sender+': '+data.text;
        document.getElementById('messages').appendChild(div);
        document.getElementById('messages').scrollTop=document.getElementById('messages').scrollHeight;
        document.getElementById('notif').innerText='🔔 New message from '+data.sender;
    }
});
</script>
</body></html>
"""

FRIENDS_HTML = """
<!DOCTYPE html>
<html><head><title>Find Friends</title></head>
<body style="text-align:center;">
<h2>Find Friends</h2>
<form method="GET">
<input name="search" placeholder="Search username"><button>Search</button>
</form>
<h3>Users</h3>
{% for u in users %}
<div>
{{u.username}}
{% if u.username not in following %}
<form method="POST" style="display:inline;">
<input type="hidden" name="username" value="{{u.username}}">
<button>Add Friend</button>
</form>
{% else %} (Following) {% endif %}
</div>
{% endfor %}
<button onclick="window.location.href='/'">Back to Dashboard</button>
</body></html>
"""

ADMIN_HTML = """
<!DOCTYPE html>
<html><head><title>Admin Panel</title></head>
<body style="text-align:center;">
<h2>Admin Panel</h2>
<h3>Manage Users</h3>
<table border=1 style="margin:auto;">
<tr><th>Username</th><th>Status</th><th>Action</th><th>New Messages</th></tr>
{% for u in users %}
<tr>
<td>{{u.username}}</td>
<td>{{'Banned' if u.banned else 'Active'}}</td>
<td>
<form method="POST" style="display:inline;">
<input type="hidden" name="target" value="{{u.username}}">
<button name="action" value="{{'ban' if not u.banned else 'unban'}}">{{'Ban' if not u.banned else 'Unban'}}</button>
</form>
</td>
<td>{{new_msgs.get(u.username,0)}}</td>
</tr>
{% endfor %}
</table>
<h3>Upload Logo</h3>
<form method="POST" enctype="multipart/form-data">
<input type="file" name="logo" accept="image/*"><br>
<button>Upload</button>
</form>
<br>
<button onclick="window.location.href='/'">Back to Dashboard</button>
<script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.7.2/socket.io.js"></script>
<script>
const socket=io();
socket.emit('join',{username:'Destiny'});
socket.on('admin_notify',data=>{
    alert('User '+data.receiver+' received a new message!');
});
</script>
</body></html>
"""

# ================= RUN APP =====================
if __name__=="__main__":
    if not os.path.exists('static'):
        os.makedirs('static')
    socketio.run(app, debug=True)

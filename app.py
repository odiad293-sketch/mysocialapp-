from flask import Flask, render_template_string, request, redirect, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_socketio import SocketIO, emit, join_room
from datetime import datetime
import os

app = Flask(__name__)
app.secret_key = "chatternet_secret_key"
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///chatternet.db"
db = SQLAlchemy(app)
socketio = SocketIO(app)

# ================= DATABASE MODELS =================
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(50), nullable=False)

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

with app.app_context():
    db.create_all()

# ================== ROUTES =========================
@app.route('/')
def home():
    if "user" not in session:
        return redirect('/login')
    posts = Post.query.order_by(Post.timestamp.desc()).all()
    user = session["user"]
    return render_template_string(DASHBOARD_HTML, posts=posts, user=user)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username, password=password).first()
        if user:
            session['user'] = user.username
            return redirect('/')
        else:
            return "Invalid credentials. Try again."
    return render_template_string(LOGIN_HTML)

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if User.query.filter_by(username=username).first():
            return "Username already exists."
        new_user = User(username=username, password=password)
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
    if "user" in session:
        content = request.form['content']
        new_post = Post(author=session["user"], content=content)
        db.session.add(new_post)
        db.session.commit()
    return redirect('/')

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

# ================ SOCKET.IO HANDLERS ================
@socketio.on('send_message')
def handle_message(data):
    sender = data['sender']
    receiver = data['receiver']
    text = data['text']
    msg = Message(sender=sender, receiver=receiver, text=text)
    db.session.add(msg)
    db.session.commit()
    emit('receive_message', {'sender': sender, 'text': text}, room=receiver)
    emit('receive_message', {'sender': sender, 'text': text}, room=sender)

@socketio.on('join')
def on_join(data):
    username = data['username']
    join_room(username)

# ================ HTML (INLINE TEMPLATE) ================
LOGIN_HTML = """
<!DOCTYPE html>
<html>
<head>
<title>Chatternet Login</title>
<style>
body { font-family: Arial; background:#e9ebee; text-align:center; }
form { margin-top:100px; background:white; display:inline-block; padding:30px; border-radius:10px; }
input { display:block; margin:10px auto; padding:10px; width:200px; }
button { background:#1877f2; color:white; border:none; padding:10px 20px; border-radius:5px; }
</style>
</head>
<body>
<h1>Welcome to Chatternet</h1>
<form method="POST">
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
<head><title>Signup</title></head>
<body style="text-align:center; background:#f0f2f5;">
<h2>Create your Chatternet account</h2>
<form method="POST">
<input name="username" placeholder="Username" required><br>
<input type="password" name="password" placeholder="Password" required><br>
<button>Sign Up</button>
</form>
<p><a href="/login">Already have an account?</a></p>
</body>
</html>
"""

DASHBOARD_HTML = """
<!DOCTYPE html>
<html>
<head>
<title>Chatternet</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.7.2/socket.io.js"></script>
<style>
body { font-family: Arial; margin:0; background:#e9ebee; }
header { background:#1877f2; color:white; padding:10px; font-size:20px; text-align:center; }
.feed { max-width:500px; margin:20px auto; background:white; border-radius:10px; padding:10px; }
.post { border-bottom:1px solid #ccc; padding:10px; }
.chatbox { position:fixed; bottom:0; right:0; width:300px; background:white; border-radius:10px 10px 0 0; }
.msg { padding:5px; margin:5px; border-radius:15px; }
.self { background:#1877f2; color:white; text-align:right; }
.other { background:#f0f0f0; color:black; text-align:left; }
</style>
</head>
<body>
<header>📘 Chatternet</header>

{% if user == 'Destiny' %}
<div class="feed" style="border:2px solid #1877f2;">
<h3>📌 Chatternet Staff Feed (Admin Destiny)</h3>
<p>Welcome everyone to Chatternet Beta! Post freely, chat kindly and enjoy.</p>
</div>
{% endif %}

<div class="feed">
<h3>📝 What's on your mind, {{user}}?</h3>
<form method="POST" action="/post">
<textarea name="content" style="width:100%;height:60px;" placeholder="Write something..."></textarea><br>
<button>Post</button>
</form>
{% for post in posts %}
<div class="post"><b>{{post.author}}</b>: {{post.content}} <small>{{post.timestamp}}</small></div>
{% endfor %}
</div>

<div class="chatbox" id="chatbox">
<h4>💬 Messenger</h4>
<select id="friendSelect" style="width:100%;"></select>
<div id="messages" style="height:200px; overflow-y:auto;"></div>
<input id="msgInput" placeholder="Type message..." style="width:80%;">
<button id="sendBtn">Send</button>
</div>

<script>
const socket = io();
const user = "{{user}}";
socket.emit('join', {username:user});

async function loadFriends(){
    const res = await fetch('/get_messages/' + user);
    const users = await res.json();
}
document.getElementById("sendBtn").onclick = () => {
    const receiver = document.getElementById("friendSelect").value;
    const text = document.getElementById("msgInput").value;
    if(!receiver || !text) return;
    socket.emit('send_message', {sender:user, receiver, text});
    document.getElementById("msgInput").value = "";
};
socket.on('receive_message', data => {
    const div = document.createElement("div");
    div.className = "msg " + (data.sender === user ? "self":"other");
    div.innerText = data.sender + ": " + data.text;
    document.getElementById("messages").appendChild(div);
});
</script>
</body>
</html>
"""

if __name__ == "__main__":
    socketio.run(app, debug=True)

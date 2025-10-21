from flask import Flask, render_template_string, request, redirect, url_for, session
import sqlite3, os

app = Flask(__name__)
app.secret_key = "chatternet_secret"

DB = "chatternet.db"

# ---------- Database ----------
def init_db():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password TEXT,
        bio TEXT DEFAULT '',
        photo TEXT DEFAULT ''
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS posts(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        content TEXT,
        likes INTEGER DEFAULT 0,
        FOREIGN KEY(user_id) REFERENCES users(id)
    )""")
    conn.commit()
    conn.close()

init_db()

# ---------- Templates ----------
base_html = """
<!DOCTYPE html>
<html>
<head>
<title>ChatterNet</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
body {margin:0;font-family:Arial;background:#f0f2f5;}
.topbar {background:#1877f2;color:white;padding:10px 15px;display:flex;align-items:center;}
.logo {font-size:24px;font-weight:bold;}
.container {display:flex;justify-content:center;margin-top:20px;}
.card {background:white;padding:20px;border-radius:10px;box-shadow:0 0 5px rgba(0,0,0,0.1);}
input,button {padding:8px;margin:5px;width:90%;}
.btn {background:#1877f2;color:white;border:none;border-radius:5px;cursor:pointer;}
.nav {background:white;padding:10px;display:flex;justify-content:space-around;position:fixed;bottom:0;left:0;right:0;border-top:1px solid #ccc;}
a{text-decoration:none;color:#1877f2;}
</style>
</head>
<body>
<div class="topbar">
  <div class="logo">🟦 ChatterNet</div>
  {% if 'user' in session %}
    <div style="margin-left:auto;">Welcome, {{session['user']}} | <a href="{{url_for('logout')}}" style="color:white;">Logout</a></div>
  {% endif %}
</div>

<div class="container">
  {% block body %}{% endblock %}
</div>
</body>
</html>
"""

login_html = """
{% extends base %}
{% block body %}
<div class="card" style="width:300px;text-align:center;">
  <h3>Login to ChatterNet</h3>
  <form method="POST">
    <input type="text" name="username" placeholder="Username" required><br>
    <input type="password" name="password" placeholder="Password" required><br>
    <button class="btn">Login</button>
  </form>
  <p>or <a href="{{url_for('register')}}">Create account</a></p>
  {% if msg %}<p style="color:red;">{{msg}}</p>{% endif %}
</div>
{% endblock %}
"""

register_html = """
{% extends base %}
{% block body %}
<div class="card" style="width:300px;text-align:center;">
  <h3>Create ChatterNet Account</h3>
  <form method="POST">
    <input type="text" name="username" placeholder="Username" required><br>
    <input type="password" name="password" placeholder="Password" required><br>
    <button class="btn">Register</button>
  </form>
  <p>Already have an account? <a href="{{url_for('login')}}">Login</a></p>
  {% if msg %}<p style="color:red;">{{msg}}</p>{% endif %}
</div>
{% endblock %}
"""

home_html = """
{% extends base %}
{% block body %}
<div style="width:600px;">
  <div class="card">
    <form method="POST" action="{{url_for('post')}}">
      <textarea name="content" rows="3" style="width:100%;" placeholder="What's on your mind?" required></textarea><br>
      <button class="btn">Post</button>
    </form>
  </div>
  <br>
  {% for p in posts %}
  <div class="card">
    <b>{{p['username']}}</b><br>
    <p>{{p['content']}}</p>
    <small>❤️ {{p['likes']}} likes</small>
  </div>
  <br>
  {% endfor %}
</div>
{% endblock %}
"""

# ---------- Routes ----------
@app.route("/")
def index():
    if 'user' in session:
        return redirect(url_for('home'))
    return redirect(url_for('login'))

@app.route("/login", methods=["GET","POST"])
def login():
    msg=""
    if request.method=="POST":
        u,p=request.form['username'],request.form['password']
        conn=sqlite3.connect(DB)
        c=conn.cursor()
        c.execute("SELECT * FROM users WHERE username=? AND password=?",(u,p))
        user=c.fetchone()
        conn.close()
        if user:
            session['user']=u
            return redirect(url_for('home'))
        else:
            msg="Invalid login."
    return render_template_string(login_html,base=base_html,msg=msg)

@app.route("/register",methods=["GET","POST"])
def register():
    msg=""
    if request.method=="POST":
        u,p=request.form['username'],request.form['password']
        try:
            conn=sqlite3.connect(DB)
            c=conn.cursor()
            c.execute("INSERT INTO users(username,password) VALUES(?,?)",(u,p))
            conn.commit()
            conn.close()
            return redirect(url_for('login'))
        except:
            msg="Username already exists."
    return render_template_string(register_html,base=base_html,msg=msg)

@app.route("/home")
def home():
    if 'user' not in session: return redirect(url_for('login'))
    conn=sqlite3.connect(DB)
    c=conn.cursor()
    c.execute("SELECT posts.id, users.username, posts.content, posts.likes FROM posts JOIN users ON posts.user_id=users.id ORDER BY posts.id DESC")
    posts=[{'id':r[0],'username':r[1],'content':r[2],'likes':r[3]} for r in c.fetchall()]
    conn.close()
    return render_template_string(home_html,base=base_html,posts=posts)

@app.route("/post",methods=["POST"])
def post():
    if 'user' not in session: return redirect(url_for('login'))
    content=request.form['content']
    conn=sqlite3.connect(DB)
    c=conn.cursor()
    c.execute("SELECT id FROM users WHERE username=?",(session['user'],))
    uid=c.fetchone()[0]
    c.execute("INSERT INTO posts(user_id,content) VALUES(?,?)",(uid,content))
    conn.commit()
    conn.close()
    return redirect(url_for('home'))

@app.route("/logout")
def logout():
    session.pop('user',None)
    return redirect(url_for('login'))

if __name__=="__main__":
    app.run(host="0.0.0.0",port=10000)

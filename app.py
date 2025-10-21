from flask import Flask, render_template_string, request, redirect, url_for, session, jsonify
import sqlite3, os

app = Flask(__name__)
app.secret_key = "mysecretkey"

# ===================== DATABASE =====================
DB_NAME = "social.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password TEXT,
        photo TEXT
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS posts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        content TEXT,
        likes INTEGER DEFAULT 0,
        FOREIGN KEY(user_id) REFERENCES users(id)
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS comments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        post_id INTEGER,
        user_id INTEGER,
        text TEXT,
        FOREIGN KEY(post_id) REFERENCES posts(id),
        FOREIGN KEY(user_id) REFERENCES users(id)
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS follows (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        follower_id INTEGER,
        following_id INTEGER
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sender_id INTEGER,
        receiver_id INTEGER,
        message TEXT
    )""")
    conn.commit()
    conn.close()

init_db()

# ===================== ROUTES =====================

@app.route("/")
def home():
    if "user" not in session:
        return redirect("/login")
    user = session["user"]
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT posts.id, users.username, posts.content, posts.likes FROM posts JOIN users ON posts.user_id = users.id ORDER BY posts.id DESC")
    posts = c.fetchall()
    conn.close()
    return render_template_string(HOME_HTML, user=user, posts=posts)

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        try:
            c.execute("INSERT INTO users (username, password) VALUES (?,?)", (username, password))
            conn.commit()
        except:
            return "Username already taken."
        conn.close()
        return redirect("/login")
    return render_template_string(REGISTER_HTML)

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE username=? AND password=?", (username, password))
        user = c.fetchone()
        conn.close()
        if user:
            session["user"] = username
            return redirect("/")
        else:
            return "Login failed"
    return render_template_string(LOGIN_HTML)

@app.route("/logout")
def logout():
    session.pop("user", None)
    return redirect("/login")

@app.route("/post", methods=["POST"])
def post():
    if "user" not in session:
        return redirect("/login")
    content = request.form["content"]
    username = session["user"]
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT id FROM users WHERE username=?", (username,))
    user_id = c.fetchone()[0]
    c.execute("INSERT INTO posts (user_id, content) VALUES (?,?)", (user_id, content))
    conn.commit()
    conn.close()
    return redirect("/")

@app.route("/like/<int:post_id>")
def like(post_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("UPDATE posts SET likes = likes + 1 WHERE id=?", (post_id,))
    conn.commit()
    conn.close()
    return redirect("/")

@app.route("/comment/<int:post_id>", methods=["POST"])
def comment(post_id):
    text = request.form["text"]
    username = session["user"]
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT id FROM users WHERE username=?", (username,))
    user_id = c.fetchone()[0]
    c.execute("INSERT INTO comments (post_id, user_id, text) VALUES (?,?,?)", (post_id, user_id, text))
    conn.commit()
    conn.close()
    return redirect("/")

@app.route("/admin")
def admin():
    if session.get("user") != "admin":
        return "Access denied."
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT * FROM users")
    users = c.fetchall()
    c.execute("SELECT * FROM posts")
    posts = c.fetchall()
    conn.close()
    return render_template_string(ADMIN_HTML, users=users, posts=posts)

# ===================== HTML =====================

LOGIN_HTML = """
<h2>Login</h2>
<form method="post">
  <input name="username" placeholder="Username"><br>
  <input name="password" type="password" placeholder="Password"><br>
  <button>Login</button>
</form>
<a href="/register">Register</a>
"""

REGISTER_HTML = """
<h2>Register</h2>
<form method="post">
  <input name="username" placeholder="Username"><br>
  <input name="password" type="password" placeholder="Password"><br>
  <button>Register</button>
</form>
"""

HOME_HTML = """
<h2>Welcome {{user}}</h2>
<form method="post" action="/post">
  <textarea name="content" placeholder="What's on your mind?" style="width:100%;height:60px;"></textarea>
  <button>Post</button>
</form>
<hr>
{% for post in posts %}
  <div>
    <b>{{post[1]}}</b>: {{post[2]}} <br>
    ❤️ {{post[3]}} <a href="/like/{{post[0]}}">Like</a>
    <form method="post" action="/comment/{{post[0]}}">
      <input name="text" placeholder="Comment...">
    </form>
  </div>
  <hr>
{% endfor %}
<a href="/logout">Logout</a>
{% if user == "admin" %}
  <a href="/admin">Admin Dashboard</a>
{% endif %}
"""

ADMIN_HTML = """
<h2>Admin Dashboard</h2>
<h3>Users</h3>
<ul>
{% for u in users %}
  <li>{{u[1]}}</li>
{% endfor %}
</ul>
<h3>Posts</h3>
<ul>
{% for p in posts %}
  <li>{{p[2]}}</li>
{% endfor %}
</ul>
<a href="/">Back</a>
"""

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)

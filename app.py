from flask import Flask, request, redirect, url_for, g
import sqlite3, os

app = Flask(__name__)

DB_NAME = "mysocial.db"

# ------------------------------------
# Database Setup
# ------------------------------------
def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(DB_NAME)
        g.db.row_factory = sqlite3.Row
    return g.db

@app.teardown_appcontext
def close_db(error):
    db = g.pop('db', None)
    if db:
        db.close()

def init_db():
    db = get_db()
    db.executescript('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS posts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        content TEXT,
        FOREIGN KEY(user_id) REFERENCES users(id)
    );
    ''')
    db.commit()

# Initialize the database
with app.app_context():
    init_db()

# ------------------------------------
# Routes
# ------------------------------------

@app.route('/')
def home():
    return """
    <style>
      body {font-family: Arial; background:#f0f2f5; text-align:center;}
      .btn {display:inline-block; background:#1877f2; color:#fff; padding:10px 20px;
            margin:5px; border-radius:8px; text-decoration:none;}
    </style>
    <h1 style='color:#1877f2;'>MySocial Network</h1>
    <a href='/register' class='btn'>Register</a>
    <a href='/login' class='btn'>Login</a>
    """

# ------------------------------------
# Registration
# ------------------------------------
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        db = get_db()
        try:
            db.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, password))
            db.commit()
            return f"<h3>✅ Account created for {username}!</h3><a href='/login'>Go to Login</a>"
        except:
            return "<h3>❌ Username already exists.</h3><a href='/register'>Try again</a>"

    return """
    <h2>Create your account</h2>
    <form method='POST'>
      <input type='text' name='username' placeholder='Username' required><br><br>
      <input type='password' name='password' placeholder='Password' required><br><br>
      <button type='submit'>Register</button>
    </form>
    """

# ------------------------------------
# Login
# ------------------------------------
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()

        db = get_db()
        user = db.execute("SELECT * FROM users WHERE username=? AND password=?", (username, password)).fetchone()

        if user:
            return redirect(url_for('dashboard', user=username))
        else:
            return "<h3>❌ Invalid credentials</h3><a href='/login'>Try again</a>"

    return """
    <h2>Login</h2>
    <form method='POST'>
      <input type='text' name='username' placeholder='Username' required><br><br>
      <input type='password' name='password' placeholder='Password' required><br><br>
      <button type='submit'>Login</button>
    </form>
    """

# ------------------------------------
# Dashboard
# ------------------------------------
@app.route('/dashboard/<user>', methods=['GET', 'POST'])
def dashboard(user):
    db = get_db()
    user_row = db.execute("SELECT id FROM users WHERE username=?", (user,)).fetchone()
    if not user_row:
        return "<h3>User not found</h3>"

    if request.method == 'POST':
        content = request.form.get('content', '').strip()
        if content:
            db.execute("INSERT INTO posts (user_id, content) VALUES (?, ?)", (user_row['id'], content))
            db.commit()

    posts = db.execute("""
        SELECT p.content, u.username FROM posts p
        JOIN users u ON p.user_id = u.id
        ORDER BY p.id DESC
    """).fetchall()

    html = f"""
    <style>
      body {{ font-family: Arial; background:#f0f2f5; text-align:center; }}
      .nav {{ background:#fff; padding:10px; border-bottom:1px solid #ccc; }}
      .btn {{ background:#1877f2; color:white; border:none; padding:8px 20px; border-radius:5px; margin:5px; }}
      textarea {{ width:90%; max-width:400px; height:60px; border-radius:8px; border:1px solid #ccc; padding:5px; }}
      .post {{ background:#fff; border-radius:10px; padding:10px; margin:10px auto; width:90%; max-width:400px; box-shadow:0 0 4px #ccc; text-align:left; }}
    </style>
    <div class='nav'>
      <b>Welcome, {user}</b><br>
      <a href='/' class='btn'>Logout</a>
    </div>
    <form method='POST'>
      <textarea name='content' placeholder="What's on your mind?"></textarea><br>
      <button type='submit' class='btn'>Post</button>
    </form>
    <hr>
    """

    for post in posts:
        html += f"<div class='post'><b>{post['username']}</b><br>{post['content']}</div>"

    return html

# ------------------------------------
# Run app
# ------------------------------------
if __name__ == '__main__':
    if not os.path.exists(DB_NAME):
        with app.app_context():
            init_db()
    app.run(host='0.0.0.0', port=10000, debug=True)

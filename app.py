from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3, os
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = "chatter_secret"

# Database setup
if not os.path.exists("database.db"):
    conn = sqlite3.connect("database.db")
    c = conn.cursor()
    c.execute('''CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT, password TEXT)''')
    c.execute('''CREATE TABLE posts (id INTEGER PRIMARY KEY, user_id INTEGER, content TEXT)''')
    conn.commit()
    conn.close()

def get_db_connection():
    conn = sqlite3.connect("database.db")
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/')
def home():
    if "user_id" in session:
        conn = get_db_connection()
        posts = conn.execute('SELECT posts.content, users.username FROM posts JOIN users ON posts.user_id = users.id ORDER BY posts.id DESC').fetchall()
        conn.close()
        return render_template('home.html', posts=posts)
    return redirect(url_for('login'))

@app.route('/register', methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form['username']
        password = generate_password_hash(request.form['password'])
        conn = get_db_connection()
        conn.execute('INSERT INTO users (username, password) VALUES (?, ?)', (username, password))
        conn.commit()
        conn.close()
        flash("Account created! Please log in.")
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        conn = get_db_connection()
        user = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        conn.close()

        if user and check_password_hash(user["password"], password):
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            return redirect(url_for("home"))
        else:
            flash("Invalid credentials.")
            return render_template("login.html")

    # 👇 This handles GET requests — so users can see the login page
    return render_template("login.html")
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/post', methods=["POST"])
def post():
    if "user_id" in session:
        content = request.form['content']
        conn = get_db_connection()
        conn.execute('INSERT INTO posts (user_id, content) VALUES (?, ?)', (session["user_id"], content))
        conn.commit()
        conn.close()
        return redirect(url_for('home'))
    return redirect(url_for('login'))

if __name__ == "__main__":
    app.run(debug=True)

from flask import Flask, request, redirect, url_for

app = Flask(__name__)

# -----------------------
# In-memory data storage
# -----------------------
users = {"admin": "1234"}
posts = [
    {"author": "admin", "content": "Welcome to MySocialApp 🚀", "likes": 3},
]

# -----------------------
# Home page
# -----------------------
@app.route('/')
def home():
    html = """
    <style>
      body { font-family: Arial; background: #f0f2f5; text-align:center; }
      .post { background:#fff; border-radius:10px; padding:10px; margin:10px auto; width:90%; max-width:400px; box-shadow:0 0 4px #ccc; }
    </style>
    <h1>MySocialApp</h1>
    <a href='/login'>Login</a>
    <hr>
    """
    for post in reversed(posts):
        html += f"<div class='post'><b>{post['author']}</b><br>{post['content']}<br><small>❤️ {post['likes']} likes</small></div>"
    return html

# -----------------------
# Login page
# -----------------------
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()

        if username in users and users[username] == password:
            return redirect(url_for('dashboard', user=username))
        else:
            return """
            <h2>Login failed ❌</h2>
            <a href='/login'>Try again</a>
            """

    # Login form
    return """
    <style>
      body { font-family: Arial; background:#f0f2f5; text-align:center; padding-top:50px; }
      input { padding:10px; width:250px; margin:8px; border-radius:5px; border:1px solid #ccc; }
      button { background:#1877f2; color:#fff; border:none; padding:10px 50px; border-radius:6px; }
    </style>
    <h2>Login to MySocialApp</h2>
    <form method='POST'>
      <input type='text' name='username' placeholder='Username' required><br>
      <input type='password' name='password' placeholder='Password' required><br>
      <button type='submit'>Login</button>
    </form>
    """

# -----------------------
# Dashboard
# -----------------------
@app.route('/dashboard/<user>', methods=['GET', 'POST'])
def dashboard(user):
    if request.method == 'POST':
        new_post = request.form.get('post', '').strip()
        if new_post:
            posts.append({"author": user, "content": new_post, "likes": 0})

    html = f"""
    <style>
      body {{ font-family: Arial; background:#f0f2f5; text-align:center; }}
      textarea {{ width:90%; max-width:400px; height:60px; border-radius:8px; border:1px solid #ccc; padding:5px; }}
      button {{ background:#1877f2; color:#fff; border:none; padding:10px 20px; border-radius:6px; }}
      .post {{ background:#fff; border-radius:10px; padding:10px; margin:10px auto; width:90%; max-width:400px; box-shadow:0 0 4px #ccc; text-align:left; }}
    </style>
    <h2>Welcome, {user} 👋</h2>
    <form method='POST'>
      <textarea name='post' placeholder="What's on your mind?"></textarea><br>
      <button type='submit'>Post</button>
    </form>
    <br><a href='/'>Logout</a><hr>
    """

    for post in reversed(posts):
        html += f"<div class='post'><b>{post['author']}</b><br>{post['content']}<br><small>❤️ {post['likes']} likes</small></div>"
    return html

# -----------------------
# Run app
# -----------------------
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000, debug=True)

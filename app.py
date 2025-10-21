from flask import Flask, request, redirect, url_for

app = Flask(__name__)

# -----------------------
# Fake user database
# -----------------------
users = {"admin": "1234"}
posts = [
    {"author": "admin", "content": "Welcome to MySocialApp! 🚀", "likes": 3},
]

# -----------------------
# Home page
# -----------------------
@app.route('/')
def home():
    html = "<h1>MySocialApp</h1><p><a href='/login'>Login</a></p>"
    for post in posts:
        html += f"<div style='border:1px solid #ccc;padding:10px;margin:10px;'>"
        html += f"<b>{post['author']}</b>: {post['content']}<br>"
        html += f"<small>❤️ {post['likes']} likes</small></div>"
    return html

# -----------------------
# Login page
# -----------------------
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        if username in users and users[username] == password:
            return redirect(url_for('dashboard', user=username))
        else:
            return "<h2>Login failed ❌</h2><a href='/login'>Try again</a>"

    # HTML form for login
    return """
    <center>
    <h2>Login to MySocialApp</h2>
    <form method='POST'>
      <input type='text' name='username' placeholder='Username' required><br><br>
      <input type='password' name='password' placeholder='Password' required><br><br>
      <button type='submit'>Login</button>
    </form>
    </center>
    """

# -----------------------
# Dashboard
# -----------------------
@app.route('/dashboard/<user>', methods=['GET', 'POST'])
def dashboard(user):
    if request.method == 'POST':
        new_post = request.form.get('post')
        if new_post:
            posts.append({"author": user, "content": new_post, "likes": 0})

    html = f"<h2>Welcome, {user} 👋</h2>"
    html += """
    <form method='POST'>
      <textarea name='post' rows='3' cols='40' placeholder='What’s on your mind?'></textarea><br>
      <button type='submit'>Post</button>
    </form>
    <a href='/'>Logout</a>
    <hr>
    """
    for post in reversed(posts):
        html += f"<div style='border:1px solid #ddd;padding:10px;margin:10px;'>"
        html += f"<b>{post['author']}</b>: {post['content']}<br>"
        html += f"<small>❤️ {post['likes']} likes</small></div>"
    return html

# -----------------------
# Run app
# -----------------------
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000, debug=True)

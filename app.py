from flask import Flask, render_template, request, redirect, url_for

app = Flask(__name__)

# ----------------------------
# HOME ROUTE
# ----------------------------
@app.route('/')
def home():
    return redirect(url_for('login'))

# ----------------------------
# LOGIN ROUTE
# ----------------------------
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        # Simple example authentication
        if username == 'admin' and password == '1234':
            return "<h2>Welcome, Admin!</h2><p>Login successful ✅</p>"
        else:
            return render_template('login.html', error="Invalid username or password")
    
    # If it's GET request, just show login page
    return render_template('login.html')

# ----------------------------
# RUN LOCALLY (for testing)
# ----------------------------
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000, debug=True)

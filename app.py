from flask import Flask, render_template, request, redirect, url_for, session, flash
from database.db_connection import get_db_connection  # Corrected import
import threading
from queue import Queue
import pyttsx3


app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Change this to something strong in production!

@app.route('/')
def home():
    return render_template('home.html')  # instead of redirect

# Admin login
@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute(
            "SELECT * FROM admins WHERE username = %s AND a_password = %s",
            (username, password)
        )
        admin = cursor.fetchone()

        conn.close()

        if admin:
            session['admin_id'] = admin['admin_id']
            session['admin_username'] = admin['username']
            return redirect(url_for('admin_dashboard'))
        else:
            flash('Invalid admin credentials', 'danger')

    return render_template('admin_login.html')


# Admin dashboard
@app.route('/admin/dashboard')
def admin_dashboard():
    if 'admin_id' not in session:
        flash('Admin login required!', 'warning')
        return redirect(url_for('admin_login'))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute(
        "SELECT t.token_id, t.token_number, t.status, u.username FROM tokens t JOIN users u ON t.user_id = u.user_id WHERE t.status IN ('waiting', 'called') ORDER BY t.token_number ASC"
    )
    queue = cursor.fetchall()

    conn.close()

    return render_template('admin_dashboard.html', admin_username=session['admin_username'], queue=queue)


# Admin logout
@app.route('/admin/logout')
def admin_logout():
    session.pop('admin_id', None)
    session.pop('admin_username', None)
    return redirect(url_for('admin_login'))

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        flash('Please login first', 'warning')
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Fetch live queue
    cursor.execute(
        "SELECT t.token_number, t.status, u.username FROM tokens t JOIN users u ON t.user_id = u.user_id WHERE t.status IN ('waiting', 'called') ORDER BY t.token_number ASC"
    )
    queue = cursor.fetchall()

    conn.close()

    return render_template('dashboard.html', username=session['username'], queue=queue)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute(
            "SELECT * FROM users WHERE username = %s AND u_password = %s",
            (username, password)
        )
        user = cursor.fetchone()

        conn.close()

        if user:
            session['user_id'] = user['user_id']
            session['username'] = user['username']
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid username or password', 'danger')

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/my_tokens')
def view_my_tokens():
    if 'user_id' not in session:
        flash('Please login first', 'warning')
        return redirect(url_for('login'))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute(
        "SELECT * FROM tokens WHERE user_id = %s ORDER BY issued_at DESC",
        (session['user_id'],)
    )
    tokens = cursor.fetchall()

    conn.close()
    return render_template('my_tokens.html', tokens=tokens)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        phone = request.form['phone']
        email = request.form['email']

        conn = get_db_connection()
        cursor = conn.cursor()

        try:
            cursor.execute(
                "INSERT INTO users (username, u_password, phone, email) VALUES (%s, %s, %s, %s)",
                (username, password, phone, email)
            )
            conn.commit()
            flash('Registration successful! Please login.', 'success')
            return redirect(url_for('login'))
        except Exception as e:
            flash(f'Error: {e}', 'danger')
            conn.rollback()
        finally:
            conn.close()

    return render_template('register.html')


@app.route('/take_token', methods=['GET', 'POST'])
def take_token():
    if 'user_id' not in session:
        flash('Please login first', 'warning')
        return redirect(url_for('login'))

    conn = get_db_connection()
    cursor = conn.cursor()

    if request.method == 'POST':
        user_id = session['user_id']

        # Get the highest current token number
        cursor.execute("SELECT MAX(token_number) FROM tokens WHERE status IN ('waiting', 'called')")
        last_token = cursor.fetchone()[0]

        new_token_number = (last_token + 1) if last_token else 1

        cursor.execute(
            "INSERT INTO tokens (user_id, token_number) VALUES (%s, %s)",
            (user_id, new_token_number)
        )
        conn.commit()
        conn.close()
        return redirect(url_for('view_my_tokens'))

    conn.close()
    return render_template('take_token.html')



@app.route('/call/<int:token_id>')
def call_token(token_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Get current token info
    cursor.execute("SELECT token_number FROM tokens WHERE token_id = %s", (token_id,))
    token = cursor.fetchone()
    
    if token:
        x = token['token_number']
        target_token_number = x + 3
        
        # Find user with token_number = x+3 and status = 'waiting'
        cursor.execute(
            "SELECT t.token_number, u.phone FROM tokens t JOIN users u ON t.user_id = u.user_id WHERE t.token_number = %s AND t.status = 'waiting'",
            (target_token_number,)
        )
        target = cursor.fetchone()
        
        if target:
            phone_number = target['phone']  # Ensure it's in international format like '+91XXXXXXXXXX'
            message = f"Reminder: Your token number {target_token_number} is approaching. Current called number is {x}."
            
            from notification import send_whatsapp_reminder
            send_whatsapp_reminder(phone_number, message)
    
        # Update current token as called
        cursor.execute("UPDATE tokens SET status='called', called_at=NOW() WHERE token_id=%s", (token_id,))
        conn.commit()
        # ✅ Add announcement task
        announcement_queue.put({'token': x, 'counter': 1})
    cursor.close()
    conn.close()
    return redirect(url_for('admin_dashboard'))

@app.route('/skip/<int:token_id>')
def skip_token(token_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE tokens SET status='missed' WHERE token_id=%s", (token_id,))
    conn.commit()
    cursor.close()
    conn.close()
    return redirect(url_for('admin_dashboard'))

@app.route('/done/<int:token_id>')
def mark_done(token_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE tokens SET status='done' WHERE token_id=%s", (token_id,))
    conn.commit()
    cursor.close()
    conn.close()
    return redirect(url_for('admin_dashboard'))

"""
@app.route('/admin/analytics')
def analytics():
    if 'admin_id' not in session:
        flash('Admin login required!', 'warning')
        return redirect(url_for('admin_login'))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT COUNT(*) AS total_tokens FROM tokens")
    total_tokens = cursor.fetchone()['total_tokens']

    cursor.execute("SELECT COUNT(*) AS completed_tokens FROM tokens WHERE status = 'done'")
    completed_tokens = cursor.fetchone()['completed_tokens']

    cursor.execute("SELECT COUNT(DISTINCT user_id) AS total_users FROM users")
    total_users = cursor.fetchone()['total_users']

    conn.close()

    return render_template('analytics.html', admin_username=session['admin_username'],
                           total_tokens=total_tokens, completed_tokens=completed_tokens, total_users=total_users)
"""

# --- Announcement Queue ---
announcement_queue = Queue()

def announcement_worker():
    engine = pyttsx3.init()
    engine.setProperty('rate', 150)
    while True:
        task = announcement_queue.get()
        try:
            token = task['token']
            counter = task['counter']
            engine.say(f"Token number {token}, please proceed to counter {counter}")
            engine.runAndWait()
        except Exception as e:
            print(f"Announcement Error: {e}")
        announcement_queue.task_done()

# Start the worker in a background thread
threading.Thread(target=announcement_worker, daemon=True).start()








if __name__ == '__main__':
    app.run(debug=True)


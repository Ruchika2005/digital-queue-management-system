from flask import Flask, render_template, request, redirect, url_for, session, flash
from database.db_connection import get_db_connection  # Corrected import
import threading
from queue import Queue
import pyttsx3
from datetime import datetime, timedelta
from collections import Counter
import random
import matplotlib.pyplot as plt
import io
import base64



app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Change this to something strong in production!

@app.route('/')
def home():
    return render_template('home.html')  # instead of redirect





@app.route('/cancel_token/<int:token_id>', methods=['POST'])
def cancel_token(token_id):
    # Connect to MySQL database
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Fetch the token details from the database
    cursor.execute('SELECT * FROM tokens WHERE token_id = %s', (token_id,))
    token = cursor.fetchone()

    if not token:
        flash("Token not found", "danger")
        return redirect(url_for('view_my_tokens'))

    # Check if the token belongs to the current user (assuming user_id is in session)
    current_user_id = session.get('user_id')  # Adjust based on how you store user_id
    if token['user_id'] != current_user_id:  # Ensure the token is owned by the current user
        flash("Unauthorized action", "danger")
        return redirect(url_for('view_my_tokens'))

    # Check if the token status is 'waiting' or 'called'
    if token['status'] in ['waiting', 'called']:  # Status should be 'waiting' or 'called'
        # Update the token status to 'Cancelled'
        cursor.execute('UPDATE tokens SET status = %s WHERE token_id = %s', ('missed', token_id))  # Use 'missed' to mark cancellation
        conn.commit()
        flash("Token cancelled successfully", "success")
    else:
        flash("Cannot cancel this token", "warning")

    # Close the connection and cursor
    cursor.close()
    conn.close()

    return redirect(url_for('view_my_tokens'))

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

    # Connect to the database
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Get the user's tokens ordered by issued_at in descending order
    cursor.execute(
        "SELECT * FROM tokens WHERE user_id = %s ORDER BY issued_at DESC",
        (session['user_id'],)
    )
    tokens = cursor.fetchall()

    # Close the connection
    conn.close()

    # Render the template and pass the tokens
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

@app.route('/admin/analytics')
def analytics():
    if 'admin_id' not in session:
        flash('Admin login required!', 'warning')
        return redirect(url_for('admin_login'))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # 1. Tokens served per hour
    cursor.execute("""
        SELECT HOUR(called_at) as hour, COUNT(*) as count 
        FROM tokens 
        WHERE status='done' AND called_at IS NOT NULL 
        GROUP BY hour ORDER BY hour
    """)
    hour_data = cursor.fetchall()
    labels = [f"{row['hour']}:00" for row in hour_data]
    token_counts = [row['count'] for row in hour_data]

    # 2. Average wait time per hour
    cursor.execute("""
        SELECT TIME_TO_SEC(TIMEDIFF(called_at, issued_at))/60 AS wait_minutes, HOUR(called_at) as hour 
        FROM tokens 
        WHERE status='done' AND called_at IS NOT NULL
    """)
    waits = cursor.fetchall()

    # Debugging: Print the raw waits data
    print("Waits:", waits)

    # Organize waits by hour
    hour_waits = {}
    for row in waits:
        hour = row['hour']
        hour_waits.setdefault(hour, []).append(row['wait_minutes'])

    # Prepare labels and average wait times
    wait_labels = [f"{h}:00" for h in sorted(hour_waits)]
    avg_waits = [round(sum(v)/len(v), 2) for h, v in sorted(hour_waits.items())]

    # Debugging output (optional)
    print("Wait Labels:", wait_labels)
    print("Avg Wait Times:", avg_waits)

    # 3. Token status summary
    cursor.execute("SELECT status, COUNT(*) as count FROM tokens GROUP BY status")
    status_data = cursor.fetchall()
    status_map = {'waiting': 0, 'called': 0, 'done': 0, 'missed': 0}
    for row in status_data:
        status_map[row['status']] = row['count']

    cursor.close()
    conn.close()

    return render_template("analytics.html",
        labels=labels,  # For chart 1 and 2 (tokens per hour and wait times)
        token_counts=token_counts,  # For chart 1
        wait_labels=wait_labels,    # For chart 2
        wait_times=avg_waits,       # For chart 2
        status_labels=list(status_map.keys()),  # For chart 3
        status_counts=list(status_map.values())  # For chart 3
    )


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




# Simulating a database of snapshots
snapshots = []

# Simulated data for tokens (This can be fetched dynamically in a real app)
tokens = [
    {'token_number': 1, 'username': 'user1', 'status': 'completed'},
    {'token_number': 2, 'username': 'user2', 'status': 'pending'},
    {'token_number': 3, 'username': 'user3', 'status': 'completed'},
]

@app.route('/admin/snapshot')
def snapshot():
    # Show list of snapshots
    return render_template('snapshot.html', snapshots=snapshots)

@app.route('/admin/snapshot/create')
def create_snapshot():
    # Create a snapshot by saving the current system state
    snapshot_id = len(snapshots) + 1  # Unique ID for the snapshot
    total_tokens = len(tokens)
    completed_tokens = sum(1 for token in tokens if token['status'] == 'completed')
    snapshot_data = {
        'id': snapshot_id,
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'total_tokens': total_tokens,
        'completed_tokens': completed_tokens
    }
    snapshots.append(snapshot_data)

    # Redirect to the snapshot page after creating a snapshot
    return redirect(url_for('snapshot'))


if __name__ == '__main__':
    app.run(debug=True)
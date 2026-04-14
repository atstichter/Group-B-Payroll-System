from flask import Flask, render_template, request, redirect, url_for, session
import sqlite3
from datetime import datetime, timedelta

app = Flask(__name__)
app.secret_key = 'demo_secret_key'
DB = 'payroll.db'

# Database
def init_db():
    conn = sqlite3.connect(DB)
    c = conn.cursor()

    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT UNIQUE,
        password TEXT,
        role TEXT
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS hours (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        date TEXT,
        hours REAL,
        type TEXT
    )''')

    conn.commit()
    conn.close()

def query_db(query, args=(), one=False):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute(query, args)
    rv = c.fetchall()
    conn.commit()
    conn.close()
    return (rv[0] if rv else None) if one else rv

# Login Page
@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = query_db(
            'SELECT * FROM users WHERE email=? AND password=?',
            (request.form['email'], request.form['password']), one=True
        )

        if user:
            session['user_id'] = user[0]
            session['role'] = user[3]
            return redirect(url_for(user[3]))

    return render_template('login.html')

# Employee Homepage
@app.route('/employee', methods=['GET', 'POST'])
def employee():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']

    if request.method == 'POST':
        query_db(
            'INSERT INTO hours (user_id, date, hours, type) VALUES (?, ?, ?, ?)',
            (user_id, request.form['date'], request.form['hours'], request.form['type'])
        )

    records = query_db('SELECT date, hours, type FROM hours WHERE user_id=?', (user_id,))

    # Weekly summary calculation
    total_hours = sum(r[1] or 0 for r in records if r[2] == 'work')
    overtime = max(0, total_hours - 40)
    regular = total_hours - overtime
    pay = (regular * 25) + (overtime * 25 * 1.5)

    return render_template('employee.html', records=records, pay=pay)

# Manager Homepage
@app.route('/manager', methods=['GET', 'POST'])
def manager():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    users = query_db("SELECT id, email FROM users WHERE role='employee'")

    selected_id = request.args.get('user_id')
    records = []

    if selected_id:
        records = query_db('SELECT id, date, hours, type FROM hours WHERE user_id=?', (selected_id,))

    if request.method == 'POST':
        query_db(
            'UPDATE hours SET hours=?, type=? WHERE id=?',
            (request.form['hours'], request.form['type'], request.form['record_id'])
        )
        return redirect(url_for('manager', user_id=selected_id))

    return render_template('manager.html', users=users, records=records, selected_id=selected_id)


if __name__ == '__main__':
    init_db()

    try:
        query_db("INSERT INTO users (email, password, role) VALUES (?, ?, ?)",
                 ('employee@test.com', '1234', 'employee'))
        query_db("INSERT INTO users (email, password, role) VALUES (?, ?, ?)",
                 ('manager@test.com', '1234', 'manager'))
    except:
        pass

    app.run(debug=True)
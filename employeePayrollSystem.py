from flask import Flask, render_template, request, redirect, url_for, session
import sqlite3
from datetime import datetime, timedelta

app = Flask(__name__)
app.secret_key = 'demo_secret_key'
DB = 'payroll.db'
HOURLY_RATE = 25


# database initialization
def init_db():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    # FIX: Added UNIQUE constraint to email to prevent duplicates
    c.execute('CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, email TEXT UNIQUE, password TEXT, role TEXT)')
    c.execute(
        'CREATE TABLE IF NOT EXISTS hours (id INTEGER PRIMARY KEY, user_id INTEGER, date TEXT, hours REAL, type TEXT)')
    c.execute(
        'CREATE TABLE IF NOT EXISTS punches (id INTEGER PRIMARY KEY, user_id INTEGER, clock_in TEXT, clock_out TEXT)')
    conn.commit()
    conn.close()


def query_db(q, a=(), one=False):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute(q, a)
    r = c.fetchall()
    conn.commit()
    conn.close()
    return (r[0] if r else None) if one else r


# login page
@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        # Now guaranteed to return only one user per email
        u = query_db('SELECT * FROM users WHERE email=? AND password=?',
                     (request.form['email'], request.form['password']), True)
        if u:
            session['user_id'] = u[0];
            session['role'] = u[3]
            return redirect(url_for(u[3]))
        else:
            # Optional: Add a flash message for invalid login
            return render_template('login.html', error="Invalid credentials")
    return render_template('login.html')


# employee homepage
@app.route('/employee', methods=['GET', 'POST'])
def employee():
    if 'user_id' not in session: return redirect('/')
    uid = session['user_id']

    active = query_db('SELECT * FROM punches WHERE user_id=? AND clock_out IS NULL', (uid,), True)

    if request.method == 'POST':
        if 'clock_in' in request.form and not active:
            query_db('INSERT INTO punches (user_id,clock_in) VALUES (?,?)', (uid, datetime.now().isoformat()))
        elif 'clock_out' in request.form and active:
            cin = datetime.fromisoformat(active[2]);
            cout = datetime.now()
            hrs = (cout - cin).total_seconds() / 3600
            query_db('INSERT INTO hours (user_id,date,hours,type) VALUES (?,?,?,?)',
                     (uid, cout.date().isoformat(), hrs, 'work'))
            query_db('UPDATE punches SET clock_out=? WHERE id=?', (cout.isoformat(), active[0]))
        return redirect('/employee')

    today = datetime.now()
    start = today - timedelta(days=today.weekday() + 1 if today.weekday() != 6 else 0)

    # Fetch all records for the user
    all_rec = query_db('SELECT id, date, hours, type FROM hours WHERE user_id=?', (uid,))

    # Filter for current week for summary
    weekly_records = []
    cal = {i: 0 for i in range(7)};
    total = 0
    for r in all_rec:
        d = datetime.fromisoformat(r[1])
        if d >= start:
            idx = (d.weekday() + 1) % 7
            cal[idx] += r[2];
            total += r[2]
            weekly_records.append(r)

    ot = max(0, total - 40);
    pay = (total - ot) * 25 + ot * 37.5

    return render_template('employee.html', active=active, clock_in=active[2] if active else None, calendar=cal,
                           total=round(total, 2), pay=round(pay, 2), weekly_records=weekly_records)


# Manager homepage
@app.route('/manager', methods=['GET', 'POST'])
def manager():
    if 'user_id' not in session: return redirect('/')

    users = query_db("SELECT id,email FROM users WHERE role='employee'")
    sid = request.args.get('user_id')

    active_punch = None
    if sid:
        active_punch = query_db('SELECT * FROM punches WHERE user_id=? AND clock_out IS NULL', (sid,), True)

    rec = [];
    cal = {i: 0 for i in range(7)}

    if sid:
        rec = query_db('SELECT id,date,hours,type FROM hours WHERE user_id=?', (sid,))
        today = datetime.now();
        start = today - timedelta(days=today.weekday() + 1 if today.weekday() != 6 else 0)
        for r in rec:
            d = datetime.fromisoformat(r[1])
            if d >= start:
                cal[(d.weekday() + 1) % 7] += r[2]

    if request.method == 'POST':
        if 'delete' in request.form:
            query_db('DELETE FROM hours WHERE id=?', (request.form['record_id'],))
        elif 'add' in request.form:
            query_db('INSERT INTO hours (user_id,date,hours,type) VALUES (?,?,?,?)',
                     (sid, request.form['date'], request.form['hours'], request.form['type']))
        else:
            query_db('UPDATE hours SET hours=?,type=? WHERE id=?',
                     (request.form['hours'], request.form['type'], request.form['record_id']))
        return redirect(f'/manager?user_id={sid}')

    return render_template('manager.html', users=users, records=rec, calendar=cal, selected_id=sid,
                           active_punch=active_punch)


if __name__ == '__main__':
    init_db()

    # FIX: Use INSERT OR IGNORE to prevent duplicate users on restart
    # This ensures we only have ONE employee and ONE manager
    try:
        query_db("INSERT OR IGNORE INTO users (email, password, role) VALUES (?, ?, ?)",
                 ('employee@test.com', '1234', 'employee'))
        query_db("INSERT OR IGNORE INTO users (email, password, role) VALUES (?, ?, ?)",
                 ('manager@test.com', '1234', 'manager'))
    except Exception as e:
        print(f"Error initializing users: {e}")

    app.run(debug=True)
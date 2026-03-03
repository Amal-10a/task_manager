from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from datetime import datetime, timedelta
import sqlite3
import os
import requests

app = Flask(__name__, static_folder='static')
app.secret_key = 'task_manager_secret_key_2024'

# Database setup
DB_NAME = "task_manager.db"

# GitHub OAuth configuration
GITHUB_CLIENT_ID = os.environ.get('GITHUB_OAUTH_CLIENT_ID', '')
GITHUB_CLIENT_SECRET = os.environ.get('GITHUB_OAUTH_CLIENT_SECRET', '')
GITHUB_REDIRECT_URI = os.environ.get('GITHUB_REDIRECT_URI', '')

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL,
            name TEXT NOT NULL
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            assigned_to INTEGER,
            due_date TEXT,
            due_time TEXT,
            status TEXT DEFAULT 'معلقة',
            priority TEXT DEFAULT 'عادية',
            created_by INTEGER,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (assigned_to) REFERENCES users(id),
            FOREIGN KEY (created_by) REFERENCES users(id)
        )
    ''')
    cursor.execute("SELECT * FROM users WHERE username = 'admin'")
    if not cursor.fetchone():
        cursor.execute("INSERT INTO users (username, password, role, name) VALUES (?, ?, ?, ?)",
                       ('admin', 'admin123', 'مدير', 'المدير العام'))
    conn.commit()
    conn.close()

init_db()

def get_db_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def get_user_by_id(user_id):
    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
    conn.close()
    return user

def get_all_employees():
    conn = get_db_connection()
    employees = conn.execute('SELECT * FROM users WHERE role = ?', ('موظف',)).fetchall()
    conn.close()
    return employees

def get_tasks_for_user(user_id, role):
    conn = get_db_connection()
    if role == 'مدير':
        tasks = conn.execute('''
            SELECT t.*, u.name as assigned_to_name, creator.name as created_by_name
            FROM tasks t
            LEFT JOIN users u ON t.assigned_to = u.id
            LEFT JOIN users creator ON t.created_by = creator.id
            ORDER BY t.due_date ASC
        ''').fetchall()
    else:
        tasks = conn.execute('''
            SELECT t.*, u.name as assigned_to_name, creator.name as created_by_name
            FROM tasks t
            LEFT JOIN users u ON t.assigned_to = u.id
            LEFT JOIN users creator ON t.created_by = creator.id
            WHERE t.assigned_to = ?
            ORDER BY t.due_date ASC
        ''', (user_id,)).fetchall()
    conn.close()
    return tasks

def check_expiring_tasks():
    conn = get_db_connection()
    now = datetime.now()
    tomorrow = (now + timedelta(days=1)).strftime('%Y-%m-%d')
    today = now.strftime('%Y-%m-%d')
    expiring = conn.execute('''
        SELECT t.*, u.name as assigned_to_name
        FROM tasks t
        LEFT JOIN users u ON t.assigned_to = u.id
        WHERE t.status != 'مكتملة' AND t.due_date IS NOT NULL
        AND t.due_date IN (?, ?)
    ''', (today, tomorrow)).fetchall()
    overdue = conn.execute('''
        SELECT t.*, u.name as assigned_to_name
        FROM tasks t
        LEFT JOIN users u ON t.assigned_to = u.id
        WHERE t.status != 'مكتملة' AND t.due_date IS NOT NULL
        AND t.due_date < ?
    ''', (today,)).fetchall()
    conn.close()
    return {'expiring': expiring, 'overdue': overdue}

@app.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return redirect(url_for('dashboard'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE username = ? AND password = ?',
                           (username, password)).fetchone()
        conn.close()
        if user:
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['role'] = user['role']
            session['name'] = user['name']
            return redirect(url_for('dashboard'))
        else:
            flash('اسم المستخدم أو كلمة المرور خطأ', 'error')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/github/login')
def github_login():
    if not GITHUB_CLIENT_ID or not GITHUB_CLIENT_SECRET:
        flash('GitHub OAuth غير مكون - يرجى إضافة المتغيرات البيئية', 'error')
        return redirect(url_for('login'))
    
    import secrets
    session['github_state'] = secrets.token_hex(16)
    
    redirect_uri = GITHUB_REDIRECT_URI
    if not redirect_uri:
        flash('يرجى تكوين GITHUB_REDIRECT_URI', 'error')
        return redirect(url_for('login'))
    
    github_auth_url = f"https://github.com/login/oauth/authorize?client_id={GITHUB_CLIENT_ID}&redirect_uri={redirect_uri}&scope=read:user&state={session['github_state']}"
    return redirect(github_auth_url)

@app.route('/github/callback')
def github_callback():
    error = request.args.get('error')
    if error:
        flash(f'خطأ من GitHub: {error}', 'error')
        return redirect(url_for('login'))
    
    code = request.args.get('code')
    state = request.args.get('state')
    
    if state != session.get('github_state'):
        flash('خطأ في الأمان', 'error')
        return redirect(url_for('login'))
    
    token_url = "https://github.com/login/oauth/access_token"
    token_data = {
        'client_id': GITHUB_CLIENT_ID,
        'client_secret': GITHUB_CLIENT_SECRET,
        'code': code,
        'redirect_uri': GITHUB_REDIRECT_URI
    }
    token_headers = {'Accept': 'application/json'}
    
    try:
        token_response = requests.post(token_url, data=token_data, headers=token_headers)
        token_result = token_response.json()
        
        if 'access_token' not in token_result:
            flash('فشل في الحصول على التوكن', 'error')
            return redirect(url_for('login'))
        
        access_token = token_result['access_token']
        
        user_url = "https://api.github.com/user"
        user_headers = {'Authorization': f'token {access_token}'}
        user_response = requests.get(user_url, headers=user_headers)
        user_data = user_response.json()
        
        github_username = user_data.get('login')
        github_name = user_data.get('name') or github_username
        
        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE username = ?', (github_username,)).fetchone()
        
        if not user:
            conn.execute('INSERT INTO users (username, password, role, name) VALUES (?, ?, ?, ?)',
                        (github_username, 'github_oauth', 'موظف', github_name))
            conn.commit()
            user = conn.execute('SELECT * FROM users WHERE username = ?', (github_username,)).fetchone()
        
        conn.close()
        
        session['user_id'] = user['id']
        session['username'] = user['username']
        session['role'] = user['role']
        session['name'] = user['name']
        session['github_token'] = access_token
        
        flash('تم تسجيل الدخول بنجاح عبر GitHub', 'success')
        return redirect(url_for('dashboard'))
        
    except Exception as e:
        flash(f'خطأ: {str(e)}', 'error')
        return redirect(url_for('login'))

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user = get_user_by_id(session['user_id'])
    tasks = get_tasks_for_user(session['user_id'], session['role'])
    alerts = check_expiring_tasks()
    conn = get_db_connection()
    stats = {}
    if session['role'] == 'مدير':
        stats['total_employees'] = conn.execute('SELECT COUNT(*) FROM users WHERE role = ?', ('موظف',)).fetchone()[0]
        stats['total_tasks'] = conn.execute('SELECT COUNT(*) FROM tasks').fetchone()[0]
    else:
        stats['total_employees'] = 0
        stats['total_tasks'] = conn.execute('SELECT COUNT(*) FROM tasks WHERE assigned_to = ?', 
                                           (session['user_id'],)).fetchone()[0]
    stats['pending_tasks'] = conn.execute('SELECT COUNT(*) FROM tasks WHERE status = ?', ('معلقة',)).fetchone()[0]
    stats['in_progress_tasks'] = conn.execute('SELECT COUNT(*) FROM tasks WHERE status = ?', ('قيد التنفيذ',)).fetchone()[0]
    stats['completed_tasks'] = conn.execute('SELECT COUNT(*) FROM tasks WHERE status = ?', ('مكتملة',)).fetchone()[0]
    conn.close()
    return render_template('dashboard.html', user=user, tasks=tasks, stats=stats, alerts=alerts)

@app.route('/employees', methods=['GET', 'POST'])
def employees():
    if 'user_id' not in session or session['role'] != 'مدير':
        flash('غير مصرح لك بهذه الصفحة', 'error')
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        name = request.form['name']
        try:
            conn = get_db_connection()
            conn.execute('INSERT INTO users (username, password, role, name) VALUES (?, ?, ?, ?)',
                        (username, password, 'موظف', name))
            conn.commit()
            conn.close()
            flash('تم إضافة الموظف بنجاح', 'success')
        except sqlite3.IntegrityError:
            flash('اسم المستخدم موجود بالفعل', 'error')
        return redirect(url_for('employees'))
    user = get_user_by_id(session['user_id'])
    employees_list = get_all_employees()
    return render_template('employees.html', employees=employees_list, user=user)

@app.route('/delete_employee/<int:employee_id>')
def delete_employee(employee_id):
    if 'user_id' not in session or session['role'] != 'مدير':
        flash('غير مصرح لك بهذه الصفحة', 'error')
        return redirect(url_for('dashboard'))
    conn = get_db_connection()
    conn.execute('DELETE FROM tasks WHERE assigned_to = ?', (employee_id,))
    conn.execute('DELETE FROM users WHERE id = ?', (employee_id,))
    conn.commit()
    conn.close()
    flash('تم حذف الموظف ومهامه', 'success')
    return redirect(url_for('employees'))

@app.route('/employee/<int:employee_id>/tasks')
def employee_tasks(employee_id):
    if 'user_id' not in session or session['role'] != 'مدير':
        flash('غير مصرح لك بهذه الصفحة', 'error')
        return redirect(url_for('dashboard'))
    conn = get_db_connection()
    employee = conn.execute('SELECT * FROM users WHERE id = ?', (employee_id,)).fetchone()
    tasks = conn.execute('''
        SELECT t.*, creator.name as created_by_name
        FROM tasks t
        LEFT JOIN users creator ON t.created_by = creator.id
        WHERE t.assigned_to = ?
        ORDER BY t.due_date ASC
    ''', (employee_id,)).fetchall()
    conn.close()
    user = get_user_by_id(session['user_id'])
    return render_template('employee_tasks.html', employee=employee, tasks=tasks, user=user)

@app.route('/add_task', methods=['POST'])
def add_task():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    title = request.form['title']
    description = request.form['description']
    if session['role'] == 'مدير':
        assigned_to = request.form['assigned_to']
    else:
        assigned_to = session['user_id']
    due_date = request.form['due_date']
    due_time = request.form['due_time']
    priority = request.form['priority']
    conn = get_db_connection()
    conn.execute('''
        INSERT INTO tasks (title, description, assigned_to, due_date, due_time, priority, created_by)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (title, description, assigned_to, due_date, due_time, priority, session['user_id']))
    conn.commit()
    conn.close()
    flash('تم إضافة المهمة بنجاح', 'success')
    return redirect(url_for('tasks'))

@app.route('/tasks', methods=['GET', 'POST'])
def tasks():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    employees = get_all_employees()
    user = get_user_by_id(session['user_id'])
    tasks_list = get_tasks_for_user(session['user_id'], session['role'])
    return render_template('tasks.html', tasks=tasks_list, employees=employees, user=user)

@app.route('/update_task/<int:task_id>', methods=['POST'])
def update_task(task_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    status = request.form['status']
    conn = get_db_connection()
    conn.execute('UPDATE tasks SET status = ? WHERE id = ?', (status, task_id))
    conn.commit()
    conn.close()
    flash('تم تحديث حالة المهمة', 'success')
    return redirect(url_for('tasks'))

@app.route('/delete_task/<int:task_id>')
def delete_task(task_id):
    if 'user_id' not in session or session['role'] != 'مدير':
        flash('غير مصرح لك بهذه الصفحة', 'error')
        return redirect(url_for('dashboard'))
    conn = get_db_connection()
    conn.execute('DELETE FROM tasks WHERE id = ?', (task_id,))
    conn.commit()
    conn.close()
    flash('تم حذف المهمة', 'success')
    return redirect(url_for('tasks'))

@app.route('/api/alerts')
def api_alerts():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    alerts = check_expiring_tasks()
    return jsonify({
        'expiring': [dict(row) for row in alerts['expiring']],
        'overdue': [dict(row) for row in alerts['overdue']]
    })

@app.route('/toggle_theme')
def toggle_theme():
    if 'theme' in session:
        session.pop('theme')
    else:
        session['theme'] = 'dark'
    return redirect(request.referrer or url_for('dashboard'))

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)

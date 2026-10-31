import os, io, sqlite3, uuid, secrets
from datetime import datetime
from zoneinfo import ZoneInfo
from functools import wraps

import pandas as pd
import qrcode
from flask import Flask, request, redirect, url_for, session, flash, send_file, abort, jsonify, render_template_string
from werkzeug.security import generate_password_hash, check_password_hash
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", secrets.token_hex(32))
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "attendance.db")
QR_DIR = os.path.join(BASE_DIR, "static", "qrcodes")
LOGO_DIR = os.path.join(BASE_DIR, "static", "images")
os.makedirs(QR_DIR, exist_ok=True)
os.makedirs(LOGO_DIR, exist_ok=True)
IST = ZoneInfo("Asia/Kolkata")

# Demo accounts for local testing. Set environment variables before real deployment.
USERS = {
    os.environ.get("ATTENDANCE_ADMIN_USER", "admin"): {
        "password": generate_password_hash(os.environ.get("ATTENDANCE_ADMIN_PASSWORD", "Admin@123")),
        "role": "admin"
    },
    os.environ.get("ATTENDANCE_FACULTY_USER", "faculty"): {
        "password": generate_password_hash(os.environ.get("ATTENDANCE_FACULTY_PASSWORD", "Faculty@123")),
        "role": "faculty"
    }
}

def now_ist():
    return datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S")

def db():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys=ON")
    return con

def init_db():
    con = db()
    con.executescript("""
    CREATE TABLE IF NOT EXISTS students(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      name TEXT NOT NULL,
      register_number TEXT NOT NULL UNIQUE,
      academic_year TEXT NOT NULL,
      qr_token TEXT NOT NULL UNIQUE,
      created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS events(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      event_name TEXT NOT NULL,
      start_time TEXT NOT NULL,
      close_time TEXT,
      status TEXT NOT NULL DEFAULT 'OPEN'
    );
    CREATE TABLE IF NOT EXISTS attendance(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      student_id INTEGER NOT NULL REFERENCES students(id),
      event_id INTEGER NOT NULL REFERENCES events(id),
      attendance_time TEXT NOT NULL,
      UNIQUE(student_id,event_id)
    );
    """)
    con.commit(); con.close()
init_db()

def login_required(fn):
    @wraps(fn)
    def wrapped(*a, **kw):
        if not session.get("username"):
            return redirect(url_for("login"))
        return fn(*a, **kw)
    return wrapped

def admin_required(fn):
    @wraps(fn)
    @login_required
    def wrapped(*a, **kw):
        if session.get("role") != "admin": abort(403)
        return fn(*a, **kw)
    return wrapped

LAYOUT = r'''<!doctype html><html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{{ title }} | College Event Attendance</title>
<style>
:root{--navy:#12345a;--blue:#205b91;--pale:#eef4fa;--ink:#172536;--muted:#627286;--green:#18794e;--red:#b42318}
*{box-sizing:border-box}body{margin:0;background:#f3f6fa;color:var(--ink);font:16px/1.55 Arial,Helvetica,sans-serif}
header{background:linear-gradient(110deg,var(--navy),var(--blue));color:#fff;padding:20px clamp(16px,4vw,48px);box-shadow:0 3px 12px #102a4325}
.brand{display:flex;align-items:center;gap:18px}.logo{width:96px;height:96px;object-fit:contain;background:white;border-radius:12px;padding:5px;flex-shrink:0}
.brand h1{font-size:clamp(22px,2.3vw,32px);line-height:1.2;margin:0;font-weight:700}.brand p{margin:6px 0 0;color:#e3edf8;font-size:15px}.userline{margin-top:12px;font-size:14px;color:#e8f1fa}
nav{background:#fff;border-bottom:1px solid #dce4ee;padding:0 clamp(12px,4vw,48px);display:flex;gap:6px;flex-wrap:wrap;box-shadow:0 2px 6px #00000008}
nav a{color:var(--navy);font-weight:700;text-decoration:none;padding:14px 12px;border-bottom:3px solid transparent}nav a:hover{background:var(--pale);border-bottom-color:var(--blue)}
main{width:min(1200px,94%);margin:30px auto 42px}.page-title{font-size:28px;margin:0 0 18px}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:18px}.card{background:#fff;border:1px solid #e1e8f0;border-radius:14px;padding:24px;margin-bottom:20px;box-shadow:0 5px 18px #1836500b}
.stat{font-size:34px;font-weight:800;color:var(--navy);margin:5px 0}.muted{color:var(--muted)}label{display:block;font-weight:700;margin:12px 0 5px}input,select{width:100%;max-width:540px;padding:12px 13px;border:1px solid #c7d2df;border-radius:8px;font-size:16px;background:#fff;color:var(--ink)}input[type=file]{max-width:650px;background:#f8fafc}button,.btn{display:inline-block;background:var(--blue);color:#fff;border:0;border-radius:8px;padding:12px 17px;font-size:15px;font-weight:700;text-decoration:none;cursor:pointer;margin:8px 5px 0 0}button:hover,.btn:hover{filter:brightness(.92)}.danger{background:var(--red)}.success{color:var(--green);font-weight:700}.error{color:var(--red);font-weight:700}.notice{background:#edf6ff;border-left:4px solid var(--blue);padding:12px 15px;border-radius:6px;margin:12px 0}
.table-wrap{width:100%;overflow-x:auto;border-radius:8px}table{width:100%;border-collapse:collapse;background:#fff;min-width:720px}th,td{padding:13px 12px;border-bottom:1px solid #e1e7ef;text-align:left;font-size:15px}th{background:#eaf1f8;color:#183b60;font-size:14px}tbody tr:hover{background:#f8fbff}.qr{width:112px;height:112px;object-fit:contain}.actions{display:flex;gap:8px;flex-wrap:wrap}.actions form{margin:0}footer{text-align:center;color:var(--muted);padding:20px;font-size:13px}
.login-wrap{max-width:560px;margin:42px auto}.login-wrap .card{padding:38px}.login-wrap input{max-width:none;padding:14px 15px;font-size:17px}.empty{padding:18px;color:var(--muted)}
@media(max-width:600px){header{padding:16px}.logo{width:68px;height:68px}.brand{gap:12px}.brand h1{font-size:20px}nav a{padding:11px 8px;font-size:14px}main{width:94%;margin-top:20px}.card{padding:17px}.page-title{font-size:24px}}
</style></head><body>
<header><div class="brand">
<img class="logo" src="{{ url_for('static', filename='images/college_logo.png') }}" alt="College logo" onerror="this.style.display='none'">
<div><h1>QR Code Event Attendance System</h1><p>Smart, reliable attendance for college events</p></div></div>
{% if session.get('username') %}<div class="userline">Signed in as <b>{{ session.get('username') }}</b> · {{ session.get('role')|title }}</div>{% endif %}</header>
{% if session.get('username') %}<nav>
<a href="{{ url_for('dashboard') }}">Dashboard</a><a href="{{ url_for('students') }}">Students</a><a href="{{ url_for('events') }}">Events</a><a href="{{ url_for('scanner') }}">Scan Attendance</a><a href="{{ url_for('reports') }}">Reports</a><a href="{{ url_for('logout') }}">Logout</a>
</nav>{% endif %}<main>
{% for category,message in get_flashed_messages(with_categories=true) %}<div class="card {{ category }}">{{ message }}</div>{% endfor %}
{{ content|safe }}</main><footer>QR Code Event Attendance Management System</footer></body></html>'''

def page(title, content, **ctx):
    return render_template_string(LAYOUT, title=title, content=render_template_string(content, **ctx))

@app.route('/', methods=['GET','POST'])
def login():
    if session.get('username'): return redirect(url_for('dashboard'))
    if request.method=='POST':
        username=request.form.get('username','').strip(); password=request.form.get('password','')
        user=USERS.get(username)
        if user and check_password_hash(user['password'],password):
            session.clear(); session['username']=username; session['role']=user['role']
            return redirect(url_for('dashboard'))
        flash('Invalid username or password. Please try again.','error')
    content='''<div class="login-wrap"><div class="card"><h2 class="page-title">Welcome back</h2><p class="muted">Sign in to manage college event attendance.</p><form method="post"><label>Username</label><input name="username" autocomplete="username" required><label>Password</label><input type="password" name="password" autocomplete="current-password" required><button type="submit">Sign in</button></form></div></div>'''
    return page('Login',content)

@app.route('/logout')
def logout():
    session.clear(); return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    con=db(); students_count=con.execute('SELECT COUNT(*) FROM students').fetchone()[0]; events_count=con.execute('SELECT COUNT(*) FROM events').fetchone()[0]; attendance_count=con.execute('SELECT COUNT(*) FROM attendance').fetchone()[0]
    opened=con.execute("SELECT * FROM events WHERE status='OPEN' ORDER BY id DESC").fetchall(); con.close()
    content='''<h2 class="page-title">Dashboard</h2><div class="grid"><div class="card"><div class="muted">Registered students</div><div class="stat">{{ students_count }}</div></div><div class="card"><div class="muted">Total events</div><div class="stat">{{ events_count }}</div></div><div class="card"><div class="muted">Attendance records</div><div class="stat">{{ attendance_count }}</div></div></div><div class="card"><h2>Currently open events</h2>{% if opened %}<div class="table-wrap"><table><thead><tr><th>Event</th><th>Started at (IST)</th><th>Status</th></tr></thead><tbody>{% for e in opened %}<tr><td>{{ e["event_name"] }}</td><td>{{ e["start_time"] }}</td><td><span class="success">{{ e["status"] }}</span></td></tr>{% endfor %}</tbody></table></div>{% else %}<p class="empty">No events are currently open. Create an event when you are ready.</p>{% endif %}</div>'''
    return page('Dashboard',content,students_count=students_count,events_count=events_count,attendance_count=attendance_count,opened=opened)

@app.route('/students',methods=['GET','POST'])
@login_required
def students():
    if request.method=='POST':
        if session.get('role')!='admin': abort(403)
        name=request.form.get('name','').strip(); reg=request.form.get('register_number','').strip().upper(); year=request.form.get('academic_year','').strip()
        if not name or not reg or not year: flash('Please complete every student field.','error')
        else:
            token=uuid.uuid4().hex; con=db()
            try:
                con.execute('INSERT INTO students(name,register_number,academic_year,qr_token,created_at) VALUES(?,?,?,?,?)',(name,reg,year,token,now_ist())); con.commit()
                qrcode.make(token).save(os.path.join(QR_DIR,token+'.png')); flash('Student registered and QR code generated.','success')
            except sqlite3.IntegrityError: flash('That register number already exists.','error')
            finally: con.close()
        return redirect(url_for('students'))
    con=db(); rows=con.execute('SELECT * FROM students ORDER BY register_number').fetchall(); con.close()
    is_admin=session.get('role')=='admin'
    content=r'''<h2 class="page-title">Student records</h2>
    {% if is_admin %}<div class="card"><h2>Register one student</h2><form method="post"><label>Student name</label><input name="name" required><label>Register number</label><input name="register_number" required><label>Academic year</label><select name="academic_year" required><option value="">Choose year</option>{% for y in ['I Year','II Year','III Year','IV Year'] %}<option>{{ y }}</option>{% endfor %}</select><button>Register student</button></form></div>
    <div class="card"><h2>Import students from Excel or CSV</h2><p>Upload a spreadsheet instead of entering students one by one. This is ordinary spreadsheet import; machine learning is not needed.</p><div class="notice"><b>Required columns:</b> Name, Register Number, Academic Year.<br>Example academic year values: I Year, II Year, III Year, IV Year. Existing register numbers are skipped.</div><a class="btn" href="{{ url_for('student_template') }}">Download Excel template</a><form method="post" action="{{ url_for('import_students') }}" enctype="multipart/form-data"><label>Select .xlsx, .xls, or .csv file</label><input type="file" name="student_file" accept=".xlsx,.xls,.csv" required><br><button type="submit">Import student list</button></form></div>{% else %}<div class="card"><p>Only administrators can register or import students.</p></div>{% endif %}
    <div class="card"><h2>Registered students <span class="muted">({{ rows|length }})</span></h2>{% if rows %}<div class="table-wrap"><table><thead><tr><th>Name</th><th>Register number</th><th>Academic year</th><th>QR code</th><th>Print</th></tr></thead><tbody>{% for s in rows %}<tr><td>{{ s['name'] }}</td><td>{{ s['register_number'] }}</td><td>{{ s['academic_year'] }}</td><td><img class="qr" src="{{ url_for('static',filename='qrcodes/'+s['qr_token']+'.png') }}" alt="QR code"></td><td><button type="button" onclick="printQR('{{ url_for('static',filename='qrcodes/'+s['qr_token']+'.png') }}',{{ s['name']|tojson }},{{ s['register_number']|tojson }})">Print QR</button></td></tr>{% endfor %}</tbody></table></div>{% else %}<p class="empty">No students registered yet. Register one or import your spreadsheet.</p>{% endif %}</div>
    <script>function printQR(src,name,reg){const w=window.open('','_blank');w.document.write('<html><head><title>Student QR</title></head><body style="font-family:Arial;text-align:center;padding:20px"><h2>'+name+'</h2><p>'+reg+'</p><img src="'+src+'" style="width:230px;height:230px"><p>Event Attendance QR Code</p></body></html>');w.document.close();w.onload=()=>w.print();}</script>'''
    return page('Students',content,rows=rows,is_admin=is_admin)

@app.route('/students/template')
@admin_required
def student_template():
    df=pd.DataFrame(columns=['Name','Register Number','Academic Year'])
    df.loc[0]=['Example Student','DEMO001','III Year']
    out=io.BytesIO()
    with pd.ExcelWriter(out,engine='openpyxl') as writer: df.to_excel(writer,index=False,sheet_name='Students')
    out.seek(0)
    return send_file(out,as_attachment=True,download_name='student_import_template.xlsx',mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

def clean_col(value):
    return ''.join(ch for ch in str(value).strip().lower() if ch.isalnum())

@app.route('/students/import', methods=['POST'])
@admin_required
def import_students():
    """Import new students efficiently while preserving existing QR tokens."""

    upload = request.files.get('student_file')

    if not upload or not upload.filename:
        flash('Choose an Excel or CSV file first.', 'error')
        return redirect(url_for('students'))

    ext = os.path.splitext(upload.filename)[1].lower()

    try:
        # Read the uploaded file.
        if ext == '.csv':
            frame = pd.read_csv(upload, dtype=str, keep_default_na=False)
        elif ext in ('.xlsx', '.xls'):
            frame = pd.read_excel(upload, dtype=str, keep_default_na=False)
        else:
            flash('Please upload an .xlsx, .xls, or .csv file.', 'error')
            return redirect(url_for('students'))

        # Identify the required columns.
        colmap = {clean_col(c): c for c in frame.columns}

        aliases = {
            'name': ['name', 'studentname', 'fullname', 'nameofstudent'],
            'register_number': [
                'registernumber', 'registerno', 'regno',
                'rollno', 'rollnumber', 'studentid'
            ],
            'academic_year': [
                'academicyear', 'year', 'studyyear', 'currentyear'
            ]
        }

        chosen = {}

        for target, variants in aliases.items():
            for variant in variants:
                if variant in colmap:
                    chosen[target] = colmap[variant]
                    break

        if len(chosen) != 3:
            flash(
                'Excel headings must include Name, Register Number, '
                'and Academic Year. Download the template for an example.',
                'error'
            )
            return redirect(url_for('students'))

        year_alias = {
            '1': 'I Year',
            'iyear': 'I Year',
            'firstyear': 'I Year',
            '2': 'II Year',
            'iiyear': 'II Year',
            'secondyear': 'II Year',
            '3': 'III Year',
            'iiiyear': 'III Year',
            'thirdyear': 'III Year',
            '4': 'IV Year',
            'ivyear': 'IV Year',
            'fourthyear': 'IV Year'
        }

        added = skipped = invalid = 0
        new_qrs = []

        con = db()

        try:
            # Read existing register numbers once instead of querying
            # the database separately for every spreadsheet row.
            existing_rows = con.execute(
                'SELECT register_number FROM students'
            ).fetchall()

            existing_registers = {
                str(row['register_number']).strip().upper()
                for row in existing_rows
            }

            # Prepare all new records before inserting them.
            records = []
            seen_in_file = set()

            for _, row in frame.iterrows():
                name = str(row[chosen['name']]).strip()
                reg = str(row[chosen['register_number']]).strip().upper()
                year = str(row[chosen['academic_year']]).strip()

                if (
                    not name or not reg or not year
                    or any(v.lower() == 'nan' for v in (name, reg, year))
                ):
                    invalid += 1
                    continue

                year = year_alias.get(clean_col(year), year)

                # Skip students already in the database or duplicated
                # within this spreadsheet.
                if reg in existing_registers or reg in seen_in_file:
                    skipped += 1
                    continue

                seen_in_file.add(reg)

                token = uuid.uuid4().hex

                records.append((
                    name,
                    reg,
                    year,
                    token,
                    now_ist()
                ))

                new_qrs.append(token)

            # Insert records in one transaction.
            if records:
                con.executemany(
                    '''
                    INSERT INTO students
                    (name, register_number, academic_year, qr_token, created_at)
                    VALUES (?, ?, ?, ?, ?)
                    ''',
                    records
                )
                con.commit()
                added = len(records)

        finally:
            con.close()

        # Generate QR images only after the database transaction succeeds.
        qr_failures = 0

        for token in new_qrs:
            try:
                qr_path = os.path.join(QR_DIR, token + '.png')
                qrcode.make(token).save(qr_path)
            except Exception:
                qr_failures += 1
                app.logger.exception(
                    'Failed to generate QR image for token %s', token
                )

        message = (
            f'Import complete: {added} new student(s) added; '
            f'{skipped} existing/duplicate row(s) skipped; '
            f'{invalid} incomplete row(s) skipped.'
        )

        if qr_failures:
            message += (
                f' Warning: {qr_failures} QR image(s) could not be generated.'
            )

        flash(message, 'success' if not qr_failures else 'error')

    except Exception:
        app.logger.exception('Student spreadsheet import failed')
        flash(
            'Import failed. Check the terminal for details and verify '
            'the spreadsheet format and required column headings.',
            'error'
        )

    return redirect(url_for('students'))

@app.route('/events',methods=['GET','POST'])
@login_required
def events():
    if request.method=='POST':
        name=request.form.get('event_name','').strip()
        if not name: flash('Enter an event name.','error')
        else:
            con=db(); con.execute("INSERT INTO events(event_name,start_time,status) VALUES(?,?,'OPEN')",(name,now_ist())); con.commit(); con.close(); flash('Event created and started.','success')
        return redirect(url_for('events'))
    con=db(); rows=con.execute('''SELECT e.*,(SELECT COUNT(*) FROM attendance a WHERE a.event_id=e.id) AS present FROM events e ORDER BY e.id DESC''').fetchall(); con.close()
    content='''<h2 class="page-title">Event management</h2><div class="card"><h2>Create an event</h2><form method="post"><label>Event name</label><input name="event_name" placeholder="e.g. Annual Symposium" required><button>Create and start event</button></form><p class="muted">Start time is recorded automatically in Indian Standard Time.</p></div><div class="card"><h2>Event history</h2>{% if rows %}<div class="table-wrap"><table><thead><tr><th>Event</th><th>Started (IST)</th><th>Closed (IST)</th><th>Status</th><th>Present</th><th>Action</th></tr></thead><tbody>{% for e in rows %}<tr><td>{{ e['event_name'] }}</td><td>{{ e['start_time'] }}</td><td>{{ e['close_time'] or '—' }}</td><td>{{ e['status'] }}</td><td>{{ e['present'] }}</td><td>{% if e['status']=='OPEN' %}<form method="post" action="{{ url_for('close_event',event_id=e['id']) }}" onsubmit="return confirm('Close this event?')"><button class="danger">Close event</button></form>{% else %}Closed{% endif %}</td></tr>{% endfor %}</tbody></table></div>{% else %}<p class="empty">No events created yet.</p>{% endif %}</div>'''
    return page('Events',content,rows=rows)

@app.route('/events/<int:event_id>/close',methods=['POST'])
@login_required
def close_event(event_id):
    con=db(); event=con.execute('SELECT * FROM events WHERE id=?',(event_id,)).fetchone()
    if not event: con.close(); abort(404)
    if event['status']=='OPEN': con.execute("UPDATE events SET status='CLOSED',close_time=? WHERE id=?",(now_ist(),event_id)); con.commit(); flash('Event closed. Further scans are blocked.','success')
    else: flash('This event is already closed.','error')
    con.close(); return redirect(url_for('events'))

@app.route('/scanner')
@login_required
def scanner():
    con=db(); opened=con.execute("SELECT * FROM events WHERE status='OPEN' ORDER BY id DESC").fetchall(); con.close()
    content=r'''<h2 class="page-title">Scan attendance</h2><div class="card"><h2>Event scanner</h2>{% if opened %}<label>Select event</label><select id="event_id">{% for e in opened %}<option value="{{ e['id'] }}">{{ e['event_name'] }} — {{ e['start_time'] }}</option>{% endfor %}</select><p class="muted">Allow camera access when asked by the browser. On a phone, camera access generally requires HTTPS or localhost.</p><div id="reader" style="max-width:520px;margin-top:18px"></div><p id="result" aria-live="polite"></p><hr><h3>Manual token test</h3><label>QR token</label><input id="token" placeholder="Paste token only for testing"><button onclick="manualScan()">Record attendance</button>{% else %}<p class="empty">There are no open events. Create an event first.</p>{% endif %}</div>
    {% if opened %}<script src="https://unpkg.com/html5-qrcode"></script><script>
    let last='',lastAt=0;
    async function sendToken(token){let result=document.getElementById('result');try{let r=await fetch('{{ url_for('record_attendance') }}',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({token:token,event_id:document.getElementById('event_id').value})});let d=await r.json();result.textContent=d.message;result.className=d.success?'success':'error';}catch(e){result.textContent='Could not reach the server.';result.className='error';}}
    function manualScan(){let t=document.getElementById('token').value.trim();if(t)sendToken(t);else alert('Enter a token.');}
    function scanSuccess(text){let n=Date.now();if(text===last&&n-lastAt<2500)return;last=text;lastAt=n;sendToken(text);}
    if(typeof Html5QrcodeScanner!=='undefined'){new Html5QrcodeScanner('reader',{fps:10,qrbox:{width:250,height:250}},false).render(scanSuccess);}
    </script>{% endif %}'''
    return page('Scan attendance',content,opened=opened)

@app.route('/api/scan',methods=['POST'])
@login_required
def record_attendance():
    data=request.get_json(silent=True) or {}; token=str(data.get('token','')).strip()
    try: event_id=int(data.get('event_id'))
    except (TypeError,ValueError): return jsonify(success=False,message='Select a valid event.'),400
    con=db(); event=con.execute('SELECT * FROM events WHERE id=?',(event_id,)).fetchone()
    if not event: con.close(); return jsonify(success=False,message='Event not found.'),404
    if event['status']!='OPEN': con.close(); return jsonify(success=False,message='This event is closed. Attendance is not accepted.'),400
    student=con.execute('SELECT * FROM students WHERE qr_token=?',(token,)).fetchone()
    if not student: con.close(); return jsonify(success=False,message='QR code not recognized.'),404
    try:
        con.execute('INSERT INTO attendance(student_id,event_id,attendance_time) VALUES(?,?,?)',(student['id'],event_id,now_ist())); con.commit(); ok=True; message=f"Attendance recorded: {student['name']} ({student['register_number']})."
    except sqlite3.IntegrityError: ok=False; message=f"Duplicate attendance: {student['name']} is already marked for this event."
    finally: con.close()
    return jsonify(success=ok,message=message)

def report_rows():
    event_id=request.args.get('event_id','').strip(); date=request.args.get('date','').strip(); year=request.args.get('academic_year','').strip()
    q='''SELECT s.name AS student_name,s.register_number,s.academic_year,e.event_name,e.start_time AS event_start,e.close_time AS event_close,a.attendance_time FROM attendance a JOIN students s ON s.id=a.student_id JOIN events e ON e.id=a.event_id WHERE 1=1'''; params=[]
    if event_id: q+=' AND e.id=?'; params.append(event_id)
    if date: q+=' AND substr(a.attendance_time,1,10)=?'; params.append(date)
    if year: q+=' AND s.academic_year=?'; params.append(year)
    q+=' ORDER BY a.attendance_time DESC'; con=db(); rows=con.execute(q,params).fetchall(); con.close(); return rows

@app.route('/reports')
@login_required
def reports():
    con=db(); events_list=con.execute('SELECT * FROM events ORDER BY id DESC').fetchall(); con.close(); rows=report_rows()
    content='''<h2 class="page-title">Attendance reports</h2><div class="card"><h2>Filter records</h2><form method="get"><label>Event</label><select name="event_id"><option value="">All events</option>{% for e in events_list %}<option value="{{ e['id'] }}" {% if request.args.get('event_id')==e['id']|string %}selected{% endif %}>{{ e['event_name'] }} — {{ e['start_time'] }}</option>{% endfor %}</select><label>Attendance date</label><input type="date" name="date" value="{{ request.args.get('date','') }}"><label>Academic year</label><select name="academic_year"><option value="">All years</option>{% for y in ['I Year','II Year','III Year','IV Year'] %}<option value="{{ y }}" {% if request.args.get('academic_year')==y %}selected{% endif %}>{{ y }}</option>{% endfor %}</select><br><button>Apply filters</button><a class="btn" href="{{ url_for('export_excel',**request.args) }}">Download Excel</a><a class="btn" href="{{ url_for('export_pdf',**request.args) }}">Download PDF</a></form></div><div class="card"><h2>Results <span class="muted">({{ rows|length }} records)</span></h2>{% if rows %}<div class="table-wrap"><table><thead><tr><th>Student</th><th>Register number</th><th>Academic year</th><th>Event</th><th>Attendance time (IST)</th></tr></thead><tbody>{% for r in rows %}<tr><td>{{ r['student_name'] }}</td><td>{{ r['register_number'] }}</td><td>{{ r['academic_year'] }}</td><td>{{ r['event_name'] }}</td><td>{{ r['attendance_time'] }}</td></tr>{% endfor %}</tbody></table></div>{% else %}<p class="empty">No attendance records match these filters.</p>{% endif %}</div>'''
    return page('Reports',content,events_list=events_list,rows=rows)

@app.route('/export/excel')
@login_required
def export_excel():
    rows=report_rows(); cols=['student_name','register_number','academic_year','event_name','event_start','event_close','attendance_time']; df=pd.DataFrame([dict(r) for r in rows],columns=cols)
    df.rename(columns={'student_name':'Student Name','register_number':'Register Number','academic_year':'Academic Year','event_name':'Event Name','event_start':'Event Start (IST)','event_close':'Event Close (IST)','attendance_time':'Attendance Time (IST)'},inplace=True)
    out=io.BytesIO()
    with pd.ExcelWriter(out,engine='openpyxl') as writer: df.to_excel(writer,index=False,sheet_name='Attendance')
    out.seek(0); return send_file(out,as_attachment=True,download_name='attendance_report.xlsx',mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

@app.route('/export/pdf')
@login_required
def export_pdf():
    rows=report_rows(); out=io.BytesIO(); doc=SimpleDocTemplate(out,pagesize=landscape(A4),rightMargin=24,leftMargin=24,topMargin=24,bottomMargin=24); styles=getSampleStyleSheet(); story=[Paragraph('QR Code Event Attendance Report',styles['Title']),Spacer(1,12)]
    data=[['Student','Register No.','Year','Event','Event Start','Event Close','Attendance Time']]
    for r in rows: data.append([str(r['student_name']),str(r['register_number']),str(r['academic_year']),str(r['event_name']),str(r['event_start']),str(r['event_close'] or '-'),str(r['attendance_time'])])
    table=Table(data,repeatRows=1,colWidths=[100,85,55,105,95,95,110]); table.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#12345a')),('TEXTCOLOR',(0,0),(-1,0),colors.white),('GRID',(0,0),(-1,-1),.5,colors.grey),('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),('FONTSIZE',(0,0),(-1,-1),7),('VALIGN',(0,0),(-1,-1),'MIDDLE'),('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,colors.HexColor('#eef4fa')])]))
    story.append(table); doc.build(story); out.seek(0); return send_file(out,as_attachment=True,download_name='attendance_report.pdf',mimetype='application/pdf')

@app.errorhandler(403)
def forbidden(error):
    return page('Access denied','<div class="card"><h2>Access denied</h2><p>Your account does not have permission to perform this action.</p></div>'),403

if __name__=='__main__':
    # Local development only. Do not expose the Flask debugger to a public network.
    app.run(debug=True)

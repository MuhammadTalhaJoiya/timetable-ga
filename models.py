import sqlite3
import os
import datetime

_LOCAL_DB = os.path.join(os.path.dirname(__file__), 'database.db')
DB_PATH = '/tmp/database.db' if os.environ.get('VERCEL') else _LOCAL_DB

# Whitelist for both reads and writes
_ALLOWED_TABLES = frozenset({'courses', 'teachers', 'rooms', 'timeslots', 'assignments'})

# Maps table name → (INSERT sql, ordered list of form-field names)
_INSERT_MAP = {
    'courses': (
        'INSERT INTO courses (name, credit_hours) VALUES (?, ?)',
        ['name', 'credit_hours'],
    ),
    'rooms': (
        'INSERT INTO rooms (name, capacity) VALUES (?, ?)',
        ['name', 'capacity'],
    ),
    'timeslots': (
        'INSERT INTO timeslots (day, start_time, end_time) VALUES (?, ?, ?)',
        ['day', 'start_time', 'end_time'],
    ),
}


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    cur = conn.cursor()
    cur.executescript('''
        CREATE TABLE IF NOT EXISTS courses (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            name         TEXT    NOT NULL,
            credit_hours INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS teachers (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            name            TEXT    NOT NULL,
            available_slots TEXT    NOT NULL DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS rooms (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            name     TEXT    NOT NULL DEFAULT '',
            capacity INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS timeslots (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            day        TEXT    NOT NULL,
            start_time TEXT    NOT NULL,
            end_time   TEXT    NOT NULL
        );
        CREATE TABLE IF NOT EXISTS assignments (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id      TEXT    NOT NULL,
            course_id   INTEGER NOT NULL REFERENCES courses(id),
            teacher_id  INTEGER NOT NULL REFERENCES teachers(id),
            room_id     INTEGER NOT NULL REFERENCES rooms(id),
            timeslot_id INTEGER NOT NULL REFERENCES timeslots(id),
            fitness     REAL    NOT NULL,
            created_at  TEXT    DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS teacher_availability (
            teacher_id  INTEGER NOT NULL REFERENCES teachers(id),
            timeslot_id INTEGER NOT NULL REFERENCES timeslots(id),
            PRIMARY KEY (teacher_id, timeslot_id)
        );
    ''')
    cur.execute('SELECT COUNT(*) FROM courses')
    if cur.fetchone()[0] == 0:
        _seed(cur)
    else:
        # Migration: if the new table is empty but teachers already exist,
        # grant all existing teachers availability for every timeslot.
        cur.execute('SELECT COUNT(*) FROM teacher_availability')
        if cur.fetchone()[0] == 0:
            cur.execute('''
                INSERT OR IGNORE INTO teacher_availability (teacher_id, timeslot_id)
                SELECT t.id, ts.id FROM teachers t, timeslots ts
            ''')
    conn.commit()
    conn.close()


def _seed(cur):
    # Courses extracted from rich_university_dataset.csv
    cur.executemany(
        'INSERT INTO courses (name, credit_hours) VALUES (?, ?)',
        [
            ('Differential Equation',       3),
            ('Communication Skills',        2),
            ('Data Structure and Algorithm',2),
            ('Basic Electronics',           3),
            ('Evolutionary Computing',      3),
            ('CIS',                         2),
            ('Embedded Systems',            3),
            ('Data Science',                3),
            ('Discrete Structure',          3),
        ],
    )
    cur.executemany(
        'INSERT INTO teachers (name) VALUES (?)',
        [
            ('Miss Maria',),
            ('Sir Hassan Abbasi',),
            ('Sir Saleem',),
            ('Miss Amna Najeeb',),
            ('Miss Asma Sanam Larik',),
            ('Sir Ali Asghar',),
            ('Sir Talha Tariq',),
            ('Sir Asmatullah',),
            ('Sir Naseer',),
        ],
    )
    # Real classroom codes and capacities from the dataset
    cur.executemany(
        'INSERT INTO rooms (name, capacity) VALUES (?, ?)',
        [
            ('H2', 40), ('A1', 60), ('A2', 40), ('C2', 40),
            ('A3', 40), ('L1', 50), ('H1', 40), ('C3', 60),
            ('L2', 50), ('B3', 40), ('C1', 40), ('B1', 40),
            ('B2', 60),
        ],
    )
    # 20 timeslots sorted Mon→Fri, 08:30→10:00→11:30→13:30 within each day
    cur.executemany(
        'INSERT INTO timeslots (day, start_time, end_time) VALUES (?, ?, ?)',
        [
            ('Monday',    '08:30', '10:00'),
            ('Monday',    '10:00', '11:30'),
            ('Monday',    '11:30', '13:00'),
            ('Monday',    '13:30', '15:00'),
            ('Tuesday',   '08:30', '10:00'),
            ('Tuesday',   '10:00', '11:30'),
            ('Tuesday',   '11:30', '13:00'),
            ('Tuesday',   '13:30', '15:00'),
            ('Wednesday', '08:30', '10:00'),
            ('Wednesday', '10:00', '11:30'),
            ('Wednesday', '11:30', '13:00'),
            ('Wednesday', '13:30', '15:00'),
            ('Thursday',  '08:30', '10:00'),
            ('Thursday',  '10:00', '11:30'),
            ('Thursday',  '11:30', '13:00'),
            ('Thursday',  '13:30', '15:00'),
            ('Friday',    '08:30', '10:00'),
            ('Friday',    '10:00', '11:30'),
            ('Friday',    '11:30', '13:00'),
            ('Friday',    '13:30', '15:00'),
        ],
    )
    # Grant all seeded teachers availability for every timeslot by default.
    cur.execute('''
        INSERT OR IGNORE INTO teacher_availability (teacher_id, timeslot_id)
        SELECT t.id, ts.id FROM teachers t, timeslots ts
    ''')


# ── read helpers ──────────────────────────────────────────────────────────────

def get_all(table):
    """Return every row of `table` as a list of dicts."""
    if table not in _ALLOWED_TABLES:
        raise ValueError(f'Table not allowed: {table!r}')
    conn = get_db()
    rows = conn.execute(f'SELECT * FROM {table}').fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_last_assignments():
    """
    Return every row from the most recent GA run as a list of flat dicts,
    already joined to courses / teachers / rooms / timeslots.
    Returns an empty list when no GA run has been saved yet.
    """
    conn = get_db()
    rows = conn.execute('''
        SELECT
            c.name        AS course,
            t.name        AS teacher,
            r.id          AS room_id,
            r.name        AS room_name,
            r.capacity    AS room_capacity,
            ts.day        AS day,
            ts.start_time AS start_time,
            ts.end_time   AS end_time,
            a.fitness     AS fitness
        FROM assignments a
        JOIN courses   c  ON c.id  = a.course_id
        JOIN teachers  t  ON t.id  = a.teacher_id
        JOIN rooms     r  ON r.id  = a.room_id
        JOIN timeslots ts ON ts.id = a.timeslot_id
    ''').fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── write helpers ─────────────────────────────────────────────────────────────

def save_assignments(genes, fitness):
    """
    Replace the stored timetable with the latest GA result.
    All previous rows are deleted first so the table always holds one run.
    """
    run_id = datetime.datetime.utcnow().isoformat(timespec='seconds')
    conn = get_db()
    cur  = conn.cursor()
    cur.execute('DELETE FROM assignments')
    cur.executemany(
        '''INSERT INTO assignments
               (run_id, course_id, teacher_id, room_id, timeslot_id, fitness)
           VALUES (?, ?, ?, ?, ?, ?)''',
        [
            (
                run_id,
                g['course']['id'],
                g['teacher']['id'],
                g['room']['id'],
                g['timeslot']['id'],
                fitness,
            )
            for g in genes
        ],
    )
    conn.commit()
    conn.close()


def insert_record(table, form_data):
    """
    Insert one row into `table` using values taken from `form_data`.
    Teachers are handled separately (they get full availability by default).
    Returns the new row's id.
    """
    if table == 'teachers':
        return _insert_teacher(form_data)
    if table not in _INSERT_MAP:
        raise ValueError(f'Inserts not allowed on table: {table!r}')
    sql, fields = _INSERT_MAP[table]
    try:
        values = tuple(form_data[f] for f in fields)
    except KeyError as missing:
        raise ValueError(f'Missing field {missing} for table {table!r}') from missing
    conn = get_db()
    cur  = conn.cursor()
    cur.execute(sql, values)
    conn.commit()
    new_id = cur.lastrowid
    conn.close()
    return new_id


def _insert_teacher(form_data):
    name = (form_data.get('name') or '').strip()
    if not name:
        raise ValueError('Teacher name is required.')
    conn = get_db()
    cur  = conn.cursor()
    cur.execute('INSERT INTO teachers (name) VALUES (?)', (name,))
    teacher_id = cur.lastrowid
    # Default: available for every timeslot currently in the DB.
    cur.execute('''
        INSERT OR IGNORE INTO teacher_availability (teacher_id, timeslot_id)
        SELECT ?, id FROM timeslots
    ''', (teacher_id,))
    conn.commit()
    conn.close()
    return teacher_id


# ── availability helpers ───────────────────────────────────────────────────────

def get_teachers_by_timeslot():
    """Return {timeslot_id: [teacher_dict, ...]} for the GA engine."""
    conn = get_db()
    rows = conn.execute('''
        SELECT ta.timeslot_id, t.id, t.name
        FROM teacher_availability ta
        JOIN teachers t ON t.id = ta.teacher_id
    ''').fetchall()
    conn.close()
    result: dict = {}
    for r in rows:
        result.setdefault(r['timeslot_id'], []).append({'id': r['id'], 'name': r['name']})
    return result


def get_availability_by_teacher():
    """Return {teacher_id: set(timeslot_id)} for penalty checks in the GA."""
    conn = get_db()
    rows = conn.execute(
        'SELECT teacher_id, timeslot_id FROM teacher_availability'
    ).fetchall()
    conn.close()
    result: dict = {}
    for r in rows:
        result.setdefault(r['teacher_id'], set()).add(r['timeslot_id'])
    return result


def get_all_teacher_availability():
    """Return {teacher_id: [timeslot_id, ...]} for the admin template."""
    conn = get_db()
    rows = conn.execute(
        'SELECT teacher_id, timeslot_id FROM teacher_availability ORDER BY teacher_id'
    ).fetchall()
    conn.close()
    result: dict = {}
    for r in rows:
        result.setdefault(r['teacher_id'], []).append(r['timeslot_id'])
    return result


def set_teacher_availability(teacher_id, timeslot_ids):
    """Replace a teacher's availability with the given list of timeslot IDs."""
    conn = get_db()
    cur  = conn.cursor()
    cur.execute('DELETE FROM teacher_availability WHERE teacher_id = ?', (teacher_id,))
    cur.executemany(
        'INSERT INTO teacher_availability (teacher_id, timeslot_id) VALUES (?, ?)',
        [(teacher_id, tid) for tid in timeslot_ids],
    )
    conn.commit()
    conn.close()

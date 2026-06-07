import csv
import io

from flask import Flask, render_template, redirect, url_for, request, flash, Response
from models import (init_db, get_all, save_assignments, insert_record,
                    get_last_assignments, get_all_teacher_availability,
                    set_teacher_availability)
from ga_engine import GeneticAlgorithm

app = Flask(__name__)
app.secret_key = 'timetable-ga-dev-secret'

# On Vercel (serverless), __main__ never runs — init on first request instead.
init_db()

_DAY_ORDER = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']


def _day_sort_key(day: str) -> int:
    # B3/B4 fix: unknown days (e.g. 'Saturday' added via a direct DB edit) sort
    # after Friday rather than raising ValueError from list.index().
    try:
        return _DAY_ORDER.index(day)
    except ValueError:
        return len(_DAY_ORDER)


# ── GET / ─────────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    return render_template(
        'index.html',
        courses=get_all('courses'),
        teachers=get_all('teachers'),
        rooms=get_all('rooms'),
        timeslots=get_all('timeslots'),
        availability=get_all_teacher_availability(),
    )


# ── POST /generate ────────────────────────────────────────────────────────────

@app.route('/generate', methods=['POST'])
def generate():
    # B7 fix: catch ValueError raised by GeneticAlgorithm.__init__ when a
    # required table is empty and show a helpful flash instead of a 500.
    try:
        ga = GeneticAlgorithm()
        best, fitness_history = ga.run()
    except ValueError as exc:
        flash(str(exc), 'warning')
        return redirect(url_for('index'))

    best_fitness = max(fitness_history) if fitness_history else 0.0
    penalty      = int(round((1.0 / best_fitness) - 1)) if best_fitness > 0 else 999
    best_gen     = next(
        (i + 1 for i, f in enumerate(fitness_history) if f == best_fitness),
        len(fitness_history),
    )

    save_assignments(best, best_fitness)

    schedule = []
    for gene in best:
        schedule.append({
            'course':  gene['course']['name'],
            'credits': gene['course']['credit_hours'],
            'teacher': gene['teacher']['name'],
            'room':    f"{gene['room']['name']} (cap {gene['room']['capacity']})",
            'day':     gene['timeslot']['day'],
            'time':    f"{gene['timeslot']['start_time']} – {gene['timeslot']['end_time']}",
        })
    schedule.sort(key=lambda x: (_day_sort_key(x['day']), x['time']))

    return render_template(
        'result.html',
        schedule=schedule,
        fitness=round(best_fitness, 4),
        conflicts=penalty,
        fitness_history=fitness_history,
        best_gen=best_gen,
        total_gen=len(fitness_history),
    )


# ── GET /admin ────────────────────────────────────────────────────────────────

@app.route('/admin')
def admin():
    return render_template(
        'admin.html',
        courses=get_all('courses'),
        teachers=get_all('teachers'),
        rooms=get_all('rooms'),
        timeslots=get_all('timeslots'),
        availability=get_all_teacher_availability(),
    )


@app.route('/admin/availability', methods=['POST'])
def admin_availability():
    teacher_id  = request.form.get('teacher_id', type=int)
    timeslot_ids = list(map(int, request.form.getlist('timeslot_ids')))
    if not teacher_id:
        flash('Invalid teacher.', 'error')
        return redirect(url_for('admin'))
    set_teacher_availability(teacher_id, timeslot_ids)
    flash('Availability updated.', 'success')
    return redirect(url_for('admin'))


# ── GET /export ───────────────────────────────────────────────────────────────

@app.route('/export')
def export():
    rows = get_last_assignments()

    if not rows:
        flash('No timetable found. Run the genetic algorithm first.', 'warning')
        return redirect(url_for('index'))

    rows.sort(key=lambda r: (_day_sort_key(r['day']), r['start_time']))

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(['Course', 'Teacher', 'Room', 'Day', 'Time'])
    for r in rows:
        writer.writerow([
            r['course'],
            r['teacher'],
            f"{r['room_name']} (cap {r['room_capacity']})",
            r['day'],
            f"{r['start_time']} - {r['end_time']}",
        ])

    return Response(
        buf.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment; filename="timetable.csv"'},
    )


# ── POST /admin/add ───────────────────────────────────────────────────────────

@app.route('/admin/add', methods=['POST'])
def admin_add():
    table = request.form.get('table', '').strip()
    try:
        insert_record(table, request.form)
        # B5 fix: no HTML in flash messages — admin.html must not use | safe.
        flash(f'New record added to {table}.', 'success')
    except ValueError as exc:
        flash(str(exc), 'error')
    return redirect(url_for('admin'))


# ── entry point ───────────────────────────────────────────────────────────────

if __name__ == '__main__':
    init_db()
    app.run(debug=True)

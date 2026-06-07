"""
Standalone diagnostic test for ga_engine.py.
Bypasses SQLite entirely — injects test data directly into GeneticAlgorithm.
Dataset: 5 courses, 3 teachers, 2 rooms, 8 timeslots.
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ga_engine import GeneticAlgorithm, HARD, SOFT

# ── Test dataset ──────────────────────────────────────────────────────────────

COURSES = [{'id': i + 1, 'name': f'Course-{i + 1}', 'credit_hours': 3} for i in range(5)]

TEACHERS = [
    {'id': 1, 'name': 'Dr. Alpha', 'available_slots': '1,2,3,4,5,6,7,8'},
    {'id': 2, 'name': 'Dr. Beta',  'available_slots': '1,2,3,4,5,6,7,8'},
    {'id': 3, 'name': 'Dr. Gamma', 'available_slots': '1,2,3,4,5,6,7,8'},
]

ROOMS = [
    {'id': 1, 'capacity': 30},
    {'id': 2, 'capacity': 50},
]

TIMESLOTS = [
    {'id': 1, 'day': 'Monday',    'start_time': '08:00', 'end_time': '09:00'},
    {'id': 2, 'day': 'Monday',    'start_time': '09:00', 'end_time': '10:00'},
    {'id': 3, 'day': 'Tuesday',   'start_time': '08:00', 'end_time': '09:00'},
    {'id': 4, 'day': 'Tuesday',   'start_time': '09:00', 'end_time': '10:00'},
    {'id': 5, 'day': 'Wednesday', 'start_time': '08:00', 'end_time': '09:00'},
    {'id': 6, 'day': 'Wednesday', 'start_time': '09:00', 'end_time': '10:00'},
    {'id': 7, 'day': 'Thursday',  'start_time': '08:00', 'end_time': '09:00'},
    {'id': 8, 'day': 'Friday',    'start_time': '08:00', 'end_time': '09:00'},
]


# ── Helpers ───────────────────────────────────────────────────────────────────

def make_ga():
    """Construct GA with test data, bypassing the database."""
    ga = object.__new__(GeneticAlgorithm)
    ga.courses   = COURSES
    ga.teachers  = TEACHERS
    ga.rooms     = ROOMS
    ga.timeslots = TIMESLOTS
    return ga


SEP  = "=" * 62
SEP2 = "-" * 62

# Force UTF-8 output so box characters render on any terminal
import io, sys as _sys
_sys.stdout = io.TextIOWrapper(_sys.stdout.buffer, encoding='utf-8', errors='replace')


def print_chromosome(chrom):
    header = f"  {'#':<3} {'Course':<12} {'Teacher':<12} {'Room':<10} {'Day':<11} Time"
    print(header)
    print("  " + "-" * (len(header) - 2))
    for idx, g in enumerate(chrom, 1):
        print(
            f"  {idx:<3} {g['course']['name']:<12} {g['teacher']['name']:<12}"
            f" Room-{g['room']['id']:<6} {g['timeslot']['day']:<11}"
            f" {g['timeslot']['start_time']}-{g['timeslot']['end_time']}"
        )


def collect_violations(chrom):
    """Return list of (severity, label, description) for every violation."""
    issues = []
    n = len(chrom)
    for i in range(n):
        gi, ts_i = chrom[i], chrom[i]['timeslot']['id']
        for j in range(i + 1, n):
            gj, ts_j = chrom[j], chrom[j]['timeslot']['id']

            if ts_i == ts_j:
                if gi['teacher']['id'] == gj['teacher']['id']:
                    issues.append(('HARD', 'teacher-clash',
                        f"{gi['course']['name']} & {gj['course']['name']} → "
                        f"{gi['teacher']['name']} @ {gi['timeslot']['day']} {gi['timeslot']['start_time']}"))
                if gi['room']['id'] == gj['room']['id']:
                    issues.append(('HARD', 'room-clash',
                        f"{gi['course']['name']} & {gj['course']['name']} → "
                        f"Room-{gi['room']['id']} @ {gi['timeslot']['day']} {gi['timeslot']['start_time']}"))
                if gi['course']['id'] == gj['course']['id']:
                    issues.append(('HARD', 'course-overlap',
                        f"{gi['course']['name']} scheduled twice "
                        f"@ {gi['timeslot']['day']} {gi['timeslot']['start_time']}"))

            if (gi['teacher']['id'] == gj['teacher']['id']
                    and gi['timeslot']['day'] == gj['timeslot']['day']):
                if gi['timeslot']['start_time'] < gj['timeslot']['start_time']:
                    earlier, later = gi, gj
                else:
                    earlier, later = gj, gi
                if earlier['timeslot']['end_time'] == later['timeslot']['start_time']:
                    issues.append(('SOFT', 'back-to-back',
                        f"{earlier['course']['name']} → {later['course']['name']} "
                        f"({gi['teacher']['name']} on {gi['timeslot']['day']}, no gap)"))

    return issues


# ── Test 1: unit-verify the penalty function ──────────────────────────────────

def test_penalty_unit():
    print(SEP)
    print("TEST 1 — Unit verify _calc_penalty() with a known chromosome")
    print(SEP)

    ga = make_ga()

    # Chromosome crafted so we know the exact expected penalty:
    #   gene-0 & gene-1: same teacher (T1) + same room (R1) + same timeslot (TS1)
    #                    → HARD teacher-clash + HARD room-clash  = 20
    #   gene-2 & gene-4: same teacher (T2), Tuesday, consecutive slots
    #                    → SOFT back-to-back                     =  2
    #   Total expected                                            = 22
    known = [
        # gene-0: Course-1, Dr.Alpha, Room-1, Monday 08:00
        {'course': COURSES[0], 'teacher': TEACHERS[0], 'room': ROOMS[0], 'timeslot': TIMESLOTS[0]},
        # gene-1: Course-2, Dr.Alpha, Room-1, Monday 08:00  ← clashes with gene-0
        {'course': COURSES[1], 'teacher': TEACHERS[0], 'room': ROOMS[0], 'timeslot': TIMESLOTS[0]},
        # gene-2: Course-3, Dr.Beta,  Room-2, Tuesday 08:00
        {'course': COURSES[2], 'teacher': TEACHERS[1], 'room': ROOMS[1], 'timeslot': TIMESLOTS[2]},
        # gene-3: Course-4, Dr.Gamma, Room-1, Wednesday 08:00
        {'course': COURSES[3], 'teacher': TEACHERS[2], 'room': ROOMS[0], 'timeslot': TIMESLOTS[4]},
        # gene-4: Course-5, Dr.Beta,  Room-2, Tuesday 09:00  ← back-to-back with gene-2
        {'course': COURSES[4], 'teacher': TEACHERS[1], 'room': ROOMS[1], 'timeslot': TIMESLOTS[3]},
    ]

    expected = 2 * HARD + SOFT   # = 22
    actual   = ga._calc_penalty(known)
    fitness  = ga._fitness(known)
    issues   = collect_violations(known)

    print(f"\nKnown chromosome (deliberately broken):")
    print_chromosome(known)

    print(f"\nExpected penalty : {expected}")
    print(f"Actual penalty   : {actual}")
    print(f"Fitness score    : {fitness:.6f}  (expected {1/(1+expected):.6f})")

    print(f"\nViolations detected ({len(issues)}):")
    for sev, label, desc in issues:
        print(f"  [{sev:<4}] {label:<16} {desc}")

    passed = actual == expected
    print(f"\n{'✓ PASS' if passed else '✗ FAIL'}: penalty function "
          f"{'correct' if passed else f'wrong — got {actual}, expected {expected}'}")
    return passed


# ── Test 2: run the full GA and report results ────────────────────────────────

def test_ga_run(n_runs=5):
    print(f"\n{SEP}")
    print(f"TEST 2 — Full GA run  ×{n_runs}  (5 courses | 3 teachers | 2 rooms | 8 timeslots)")
    print(SEP)

    all_penalties, perfect_runs = [], 0

    for run in range(1, n_runs + 1):
        ga   = make_ga()
        best, history = ga.run()
        penalty = ga._calc_penalty(best)
        fitness = history[-1]
        all_penalties.append(penalty)
        if penalty == 0:
            perfect_runs += 1

        issues          = collect_violations(best)
        teacher_clashes = [v for v in issues if v[1] == 'teacher-clash']
        room_clashes    = [v for v in issues if v[1] == 'room-clash']
        soft_issues     = [v for v in issues if v[0] == 'SOFT']

        print(f"\n── Run {run} {'─' * 50}")
        print(f"  Best chromosome:")
        print_chromosome(best)

        # Fitness history at every 10th generation
        print(f"\n  Fitness history (gen / best_fitness):")
        sampled = list(range(0, len(history), 10)) + [len(history) - 1]
        for i in sorted(set(sampled)):
            marker = " ← final" if i == len(history) - 1 else ""
            print(f"    gen {i+1:>3}: {history[i]:.4f}{marker}")

        print(f"\n  Summary:")
        print(f"    Final fitness   : {fitness:.6f}")
        print(f"    Total penalty   : {penalty}")
        print(f"    Teacher clashes : {len(teacher_clashes)}")
        print(f"    Room clashes    : {len(room_clashes)}")
        print(f"    Back-to-back    : {len(soft_issues)}")

        if issues:
            print(f"\n  Violations in best result:")
            for sev, label, desc in issues:
                print(f"    [{sev:<4}] {label:<16} {desc}")
        else:
            print(f"\n  ✓ No constraint violations")

    # Aggregate
    print(f"\n{SEP}")
    print(f"AGGREGATE ({n_runs} runs)")
    print(SEP2)
    print(f"  Perfect schedules (penalty=0) : {perfect_runs}/{n_runs}")
    print(f"  Penalty values                : {all_penalties}")
    print(f"  Average penalty               : {sum(all_penalties)/len(all_penalties):.1f}")

    any_teacher = sum(1 for p in all_penalties if p > 0)
    return perfect_runs, all_penalties


# ── Mutation coverage check ───────────────────────────────────────────────────

def test_mutation_coverage():
    """
    Verify which gene fields mutation actually touches.
    Runs mutation 1000 times and counts what changed.
    """
    print(f"\n{SEP}")
    print("TEST 3 — Mutation coverage (what fields does _mutate() change?)")
    print(SEP)

    import copy as _copy
    ga = make_ga()

    changed = {'timeslot': 0, 'room': 0, 'teacher': 0, 'none': 0}
    TRIALS = 1_000

    for _ in range(TRIALS):
        chrom = ga._random_chromosome()
        original = _copy.deepcopy(chrom)
        mutated  = ga._mutate(_copy.deepcopy(chrom))

        for g_orig, g_mut in zip(original, mutated):
            if g_orig['timeslot']['id'] != g_mut['timeslot']['id']:
                changed['timeslot'] += 1
            if g_orig['room']['id'] != g_mut['room']['id']:
                changed['room'] += 1
            if g_orig['teacher']['id'] != g_mut['teacher']['id']:
                changed['teacher'] += 1

    total_changes = sum(v for k, v in changed.items() if k != 'none')
    print(f"\n  Over {TRIALS} chromosomes × {len(COURSES)} genes = "
          f"{TRIALS * len(COURSES)} gene evaluations:")
    for field, count in changed.items():
        if field == 'none':
            continue
        pct = (count / (TRIALS * len(COURSES))) * 100
        flag = "  ← NEVER MUTATED" if count == 0 else ""
        print(f"    {field:<12}: {count:>5} changes  ({pct:.1f}%){flag}")

    teacher_mutated = changed['teacher'] > 0
    print(f"\n  Teacher can be mutated: {'YES' if teacher_mutated else 'NO  ← BUG'}")
    return teacher_mutated


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == '__main__':
    unit_ok         = test_penalty_unit()
    perfect, penals = test_ga_run(n_runs=5)
    teacher_ok      = test_mutation_coverage()

    print(f"\n{SEP}")
    print("DIAGNOSIS")
    print(SEP)

    all_ok = True

    if not unit_ok:
        print("✗ _calc_penalty() is computing the wrong value — see Test 1.")
        all_ok = False

    if not teacher_ok:
        print("✗ _mutate() never changes the teacher field.")
        print("  → Teacher clashes can ONLY be resolved by timeslot reassignment.")
        print("  → Fix: add teacher to the mutation choices (3-way split).")
        all_ok = False

    if any(p > 0 for p in penals):
        hard_remain = any(p >= 10 for p in penals)
        if hard_remain:
            print(f"✗ Hard violations still present in {sum(1 for p in penals if p>0)}"
                  f"/{len(penals)} runs after 100 generations.")
            all_ok = False
        else:
            print(f"  Only soft violations remain (back-to-back) — acceptable.")

    if all_ok and perfect == len(penals):
        print("✓ All tests passed — fitness function and GA logic are correct.")
    elif all_ok:
        print(f"  GA converged perfectly in {perfect}/{len(penals)} runs.")
        print("  Remaining runs had only soft penalties — no hard violations.")

import random
import copy
from models import get_all

# ── GA hyper-parameters ───────────────────────────────────────────────────────
POPULATION_SIZE  = 30
GENERATIONS      = 100
TOURNAMENT_SIZE  = 3
MUTATION_RATE    = 0.10
ELITISM          = 2

# ── Penalty weights ───────────────────────────────────────────────────────────
HARD = 10   # teacher clash, room clash, same-course overlap
SOFT =  2   # back-to-back classes (same teacher, consecutive slots)


class GeneticAlgorithm:
    """
    Chromosome  : list of gene-dicts  [{course, teacher, room, timeslot}, ...]
                  one entry per course in the database.
    Fitness     : 1 / (1 + total_penalty)   →  1.0 = perfect schedule.
    Returns     : (best_chromosome, fitness_history)
                  fitness_history[i] = best fitness seen up to generation i.
    """

    def __init__(self):
        self.courses   = get_all('courses')
        self.teachers  = get_all('teachers')
        self.rooms     = get_all('rooms')
        self.timeslots = get_all('timeslots')

        # B2 fix: raise early so routes get a clean ValueError instead of a
        # cryptic IndexError buried inside random.choice() during population init.
        if not self.courses:
            raise ValueError('No courses found. Add at least one course before running the GA.')
        if not self.teachers:
            raise ValueError('No teachers found. Add at least one teacher before running the GA.')
        if not self.rooms:
            raise ValueError('No rooms found. Add at least one room before running the GA.')
        if not self.timeslots:
            raise ValueError('No timeslots found. Add at least one timeslot before running the GA.')

    # ── chromosome construction ───────────────────────────────────────────────

    def _random_gene(self, course):
        # Each gene represents one scheduled class: a course assigned to a
        # (teacher, room, timeslot) triple chosen uniformly at random.
        return {
            'course':   course,
            'teacher':  random.choice(self.teachers),
            'room':     random.choice(self.rooms),
            'timeslot': random.choice(self.timeslots),
        }

    def _random_chromosome(self):
        # A chromosome is a complete candidate timetable — one gene per course.
        # The initial population is fully random, providing genetic diversity for
        # the selection pressure to act on.
        return [self._random_gene(c) for c in self.courses]

    # ── fitness / penalty ─────────────────────────────────────────────────────

    def _calc_penalty(self, chromosome):
        penalty = 0
        n = len(chromosome)

        for i in range(n):
            gi  = chromosome[i]
            ts_i = gi['timeslot']['id']

            for j in range(i + 1, n):
                gj   = chromosome[j]
                ts_j = gj['timeslot']['id']

                # Hard constraints: two classes sharing a timeslot create a clash.
                # Each violation adds HARD=10 to the penalty so the fitness
                # function strongly penalises hard conflicts over soft ones.
                if ts_i == ts_j:
                    if gi['teacher']['id'] == gj['teacher']['id']:
                        penalty += HARD          # teacher clash

                    if gi['room']['id'] == gj['room']['id']:
                        penalty += HARD          # room clash

                    if gi['course']['id'] == gj['course']['id']:
                        penalty += HARD          # same course scheduled twice

                # Soft constraint: back-to-back (same teacher, same day, no gap).
                # Penalised with SOFT=2 — discouraged but not forbidden.
                if (gi['teacher']['id'] == gj['teacher']['id']
                        and gi['timeslot']['day'] == gj['timeslot']['day']):
                    if gi['timeslot']['start_time'] < gj['timeslot']['start_time']:
                        earlier, later = gi, gj
                    else:
                        earlier, later = gj, gi

                    if earlier['timeslot']['end_time'] == later['timeslot']['start_time']:
                        penalty += SOFT

        return penalty

    def _fitness(self, chromosome):
        # Fitness = 1 / (1 + penalty) maps any non-negative penalty to (0, 1].
        # A perfect schedule (penalty = 0) scores exactly 1.0; every constraint
        # violation drives the score closer to 0 without it ever going negative.
        return 1.0 / (1.0 + self._calc_penalty(chromosome))

    # ── GA operators ──────────────────────────────────────────────────────────

    def _tournament(self, population, fitnesses):
        # Tournament selection: pick TOURNAMENT_SIZE random candidates and return
        # the fittest. A small tournament (k=3) keeps selection pressure moderate —
        # weak chromosomes still occasionally reproduce, maintaining diversity.
        indices = random.sample(range(len(population)), TOURNAMENT_SIZE)
        winner  = max(indices, key=lambda i: fitnesses[i])
        return population[winner]

    def _crossover(self, p1, p2):
        # Single-point crossover: the child inherits the first `point` genes from
        # parent-1 and the remainder from parent-2, combining scheduling decisions
        # from two fit parents.
        # B1 fix: a 1-course chromosome has no valid cut point; return a copy of p1.
        if len(p1) <= 1:
            return list(p1)
        point = random.randint(1, len(p1) - 1)
        return p1[:point] + p2[point:]

    def _mutate(self, chromosome):
        # Per-gene mutation at MUTATION_RATE probability.
        # Equally likely to reassign timeslot, room, OR teacher so that all
        # three types of hard clash have a direct escape path.
        # (Restricting to timeslot/room only means teacher clashes can never
        # be fixed by diversity injection — only by lucky timeslot moves.)
        for gene in chromosome:
            if random.random() < MUTATION_RATE:
                r = random.random()
                if r < 1 / 3:
                    gene['timeslot'] = random.choice(self.timeslots)
                elif r < 2 / 3:
                    gene['room'] = random.choice(self.rooms)
                else:
                    gene['teacher'] = random.choice(self.teachers)
        return chromosome

    # ── main loop ─────────────────────────────────────────────────────────────

    def run(self):
        """
        Execute the GA and return:
            best_chromosome  – list of gene-dicts with the lowest penalty found
            fitness_history  – list of length GENERATIONS; entry i is the
                               running best fitness after generation i+1
        """
        # Initialise a random population — the starting gene pool.
        population = [self._random_chromosome() for _ in range(POPULATION_SIZE)]

        fitness_history: list[float] = []
        best_chrom = None
        best_fit   = -1.0

        for _gen in range(GENERATIONS):
            fitnesses = [self._fitness(c) for c in population]

            # Track the global best across all generations, not just the current one.
            gen_best_idx = max(range(POPULATION_SIZE), key=lambda i: fitnesses[i])
            gen_best_fit = fitnesses[gen_best_idx]

            if gen_best_fit > best_fit:
                best_fit   = gen_best_fit
                best_chrom = copy.deepcopy(population[gen_best_idx])

            fitness_history.append(round(best_fit, 4))

            # Early stopping: no need to continue once a perfect schedule is found.
            if best_fit >= 1.0:
                fitness_history.extend(
                    [1.0] * (GENERATIONS - len(fitness_history))
                )
                break

            # ── build next generation ─────────────────────────────────────────
            ranked = sorted(range(POPULATION_SIZE),
                            key=lambda i: fitnesses[i], reverse=True)

            # Elitism: copy the top-ELITISM chromosomes unchanged into the next
            # generation so the best solution found is never lost to crossover noise.
            next_gen = [copy.deepcopy(population[ranked[i]]) for i in range(ELITISM)]

            while len(next_gen) < POPULATION_SIZE:
                p1    = self._tournament(population, fitnesses)
                p2    = self._tournament(population, fitnesses)
                child = self._crossover(p1, p2)
                child = copy.deepcopy(child)     # own copy before mutating
                child = self._mutate(child)
                next_gen.append(child)

            population = next_gen

        return best_chrom, fitness_history

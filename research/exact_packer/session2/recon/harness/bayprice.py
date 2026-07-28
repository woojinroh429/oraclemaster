"""KILL-TEST for bay-schedule column generation (see REBUILD.md).

The design stands or falls on one question: can we, for ONE bay, search over complete
schedules -- which blocks it takes and when -- using the C++ engine as the only
feasibility authority, and do it fast enough to be a pricing subproblem?

Nothing here uses a capacity bound.  That is the entire point: bounding-box area was
measured INVALID on real solutions (prob_24 100.8%, prob_28 104.3%, prob_30 107.9%) because
blocks are polygons that nest, and every previous solver attempt rested on it.  Here a
transition is legal iff `feasible_scan` says a position exists, so the search can never
believe something that is not true.

Test 1 (tractability + optimisation power): fix the block set the incumbent gave this bay
and re-schedule exactly that set.  The incumbent is one feasible answer, so the search must
match it; the question is whether it BEATS it, and how fast.

RESULT: the from-scratch form of this pricing is DEAD.  prob_22 bay 0, 53 blocks, a set the
incumbent schedules at tardiness 0:

    beam   8, greedy pos/time   tardiness 92    14s     53/53
    beam  32, greedy pos/time   tardiness 78    58s     53/53
    beam  96, greedy pos/time   tardiness 79   171s     53/53
    beam  32, 2 entry times     tardiness 78   103s     53/53
    beam   8, 2 times x 2 pos   INCOMPLETE      27s     52/53

Twelve times the beam width buys 92 -> 79 and never approaches 0, and richer branching makes
it fail to complete at all.  The cause is RC1 again: schedule quality is decided by WHERE
each block goes, position does not appear in the objective, so the beam is ranking on a flat
signal and wanders.  The incumbent's 0 is the product of a tuned constructor plus polish,
not something a generic beam re-derives in seconds.  Cost also disqualifies it -- 27-171s
for ONE bay, against 2-4 bays times dozens of CG iterations.

What survives is the frame, not the pricing: the engine as sole feasibility authority (this
search never once believed something false, unlike every area-bound master), and the bay
schedule as the unit of decision.  The correction is to price by LOCAL MODIFICATION of
existing columns -- seed the pool with the incumbent's per-bay schedules (already at
tardiness 0), then generate new columns by tearing out one time window and refilling it,
so the position quality of the rest is preserved instead of being reinvented.  Note that
the only operator that moved anything all day (eject-and-insert, prob_29 -3.75%) also
worked by locally modifying a good solution; that may not be a coincidence.

    python3.12 harness/bayprice.py <prob> <bay|-1=most contended> <beam> <budget_s> [seed_s]
    env BP_K = entry times per block (default 1), BP_P = positions per time (default 1)
"""
import sys, os, json, time
HERE = os.path.dirname(os.path.abspath(__file__))
REC = os.path.dirname(HERE)
sys.path.insert(0, REC); os.chdir(REC)
import myalgorithm as M, utils
M._CPP_ENGINE_MODE = M.HAVE_OGC_FAST


def load(p):
    for c in ('data/train/prob_%d.json' % p, 'data/set1/prob_%d.json' % p):
        if os.path.exists(c):
            return json.load(open(c))
    raise SystemExit("prob_%d.json missing -- is data/ linked?" % p)


def incumbent(d, budget):
    sol = M.algorithm(d, timelimit=budget)
    ent = {}; ext = {}; bay = {}; oo = {}; xx = {}; yy = {}
    for t, ops in sol['operations'].items():
        for op in ops:
            if op['type'] == 'ENTRY':
                b = op['block_id']; ent[b] = int(t); bay[b] = op['bay_id']
                oo[b] = op['orient_idx']; xx[b] = op['x']; yy[b] = op['y']
            else:
                ext[op['block_id']] = int(t)
    return sol, ent, ext, bay, oo, xx, yy


class BaySearch:
    """Layered beam over per-bay schedules.  A state is a list of (block, orient, x, y,
    entry, exit); it is expanded by admitting one more block at the earliest entry time the
    engine will actually accept.  Widening the beam to infinity makes it exhaustive, so the
    same code answers 'is exact pricing tractable' and 'is heuristic pricing good enough'."""

    def __init__(self, d, j):
        self.d = d; self.j = j
        self.B = d['blocks']; self.n = len(self.B)
        self.E = M._ogc_fast_engine(d)
        self.pt = [b['processing_time'] for b in self.B]
        self.due = [b['due_date'] for b in self.B]
        self.rel = [b['release_time'] for b in self.B]
        self.w1 = float(d['weights']['w1'])
        self.calls = 0
        self.kmax = int(os.environ.get('BP_K','1')); self.pmax = int(os.environ.get('BP_P','1'))

    def _load(self, plc):
        self.E.clear_all()
        for (b, o, x, y, en, ex) in plc:
            self.E.add(self.j, b, o, float(x), float(y), en, ex)

    def _entry_options(self, plc, b, cap):
        """Times worth trying for b: its release, and each moment a resident leaves."""
        ts = {self.rel[b]}
        for (_c, _o, _x, _y, _en, ex) in plc:
            if ex > self.rel[b]:
                ts.add(ex)
        return sorted(ts)[:cap]

    def _place(self, plc, b, tcap, kmax=1, pmax=1):
        """Up to kmax (entry time, position) options the engine actually accepts.

        Branching on BOTH matters: taking a block at the first feasible instant, in the
        first feasible cell, is a greedy commitment that can wall off a more urgent block
        later -- which is exactly why the first version of this search lost to the
        incumbent by 92 tardiness on a set the incumbent schedules at 0.  The engine is
        still the only feasibility authority; we just stop pretending its first answer is
        the only one."""
        out = []
        for t in self._entry_options(plc, b, tcap):
            self.calls += 1
            r = self.E.feasible_scan(b, [self.j], int(t), int(t) + self.pt[b], 1)
            if not len(r):
                continue
            # spread the position choices instead of taking adjacent cells
            step = max(1, len(r) // pmax)
            for q in [r[i * step] for i in range(min(pmax, len(r)))]:
                out.append((b, int(q[1]), int(q[2]), int(q[3]), int(t), int(t) + self.pt[b]))
            if len(out) >= kmax * pmax:
                break
        return out

    def cost(self, plc):
        return self.w1 * sum(max(0, ex - self.due[b]) for (b, _o, _x, _y, _en, ex) in plc)

    def guide(self, plc):
        """Beam ranking.  Tardiness alone is FLAT for most of the horizon (the incumbent
        reaches 0 on prob_22's bay 0), so ranking by it alone leaves the beam with no signal
        and it picks arbitrarily.  Break ties on total waiting and on remaining due-date
        slack, which is what actually predicts whether the tail can still be seated."""
        wait = sum(en - self.rel[b] for (b, _o, _x, _y, en, _ex) in plc)
        risk = sum(max(0, self.pt[b] - (self.due[b] - en)) for (b, _o, _x, _y, en, _ex) in plc)
        return (self.cost(plc), risk, wait)

    def search(self, must, beam, budget, tcap=24):
        """Schedule every block in `must` into bay j, minimising tardiness."""
        must = list(must)
        t0 = time.time()
        states = [([], 0.0)]                      # (placements, cost)
        order = sorted(must, key=lambda b: (self.rel[b], self.due[b]))
        for depth, _ in enumerate(order):
            nxt = []
            for plc, _c in states:
                if time.time() - t0 > budget:
                    break
                done = {q[0] for q in plc}
                self._load(plc)
                for b in must:
                    if b in done:
                        continue
                    for got in self._place(plc, b, tcap, kmax=self.kmax, pmax=self.pmax):
                        np_ = plc + [got]
                        nxt.append((np_, self.cost(np_)))
                    # NOTE: _place only SCANS, it never adds -- so there is nothing to undo.
                    # (An E.remove(b) here corrupts the engine for every later sibling.)
            if not nxt:
                return None, time.time() - t0, depth
            # dominance: identical block SET -> keep only the cheapest representative
            bestby = {}
            for plc, c in nxt:
                k = (frozenset(q[0] for q in plc), tuple(sorted(q[4] for q in plc)))
                g = self.guide(plc)
                if k not in bestby or g < bestby[k][2]:
                    bestby[k] = (plc, c, g)
            nxt = sorted(bestby.values(), key=lambda s: s[2])
            nxt = [(a, b_) for (a, b_, _g) in nxt]
            states = nxt[:beam] if beam > 0 else nxt
            if time.time() - t0 > budget:
                return states[0][0], time.time() - t0, depth + 1
        return states[0][0], time.time() - t0, len(order)


if __name__ == '__main__':
    p = int(sys.argv[1]); jarg = int(sys.argv[2]); beam = int(sys.argv[3])
    budget = float(sys.argv[4]); seed_s = float(sys.argv[5]) if len(sys.argv) > 5 else 60.0
    d = load(p); m = len(d['bays'])
    sol, ent, ext, bay, oo, xx, yy = incumbent(d, seed_s)
    c0 = utils.check_feasibility(d, sol)
    counts = [sum(1 for b in bay if bay[b] == j) for j in range(m)]
    j = jarg if jarg >= 0 else max(range(m), key=lambda k: counts[k])
    S = [b for b in range(len(d['blocks'])) if bay[b] == j]
    w1 = float(d['weights']['w1'])
    inc_t = sum(max(0, ext[b] - d['blocks'][b]['due_date']) for b in S)
    print('prob_%d  bay %d of %d  |S|=%d  bay=%dx%d  incumbent obj=%d (Z1=%s total)'
          % (p, j, m, len(S), d['bays'][j]['width'], d['bays'][j]['height'],
             int(c0['objective']), c0['obj1']), flush=True)
    print('  incumbent tardiness inside this bay = %d  (w1*that = %d)' % (inc_t, w1 * inc_t), flush=True)
    bs = BaySearch(d, j)
    plc, el, depth = bs.search(S, beam, budget)
    if plc is None or len(plc) < len(S):
        print('  BEAM=%-5s placed %d/%d  -> INCOMPLETE at depth %d   %.1fs, %d oracle calls'
              % (beam or 'inf', 0 if plc is None else len(plc), len(S), depth, el, bs.calls), flush=True)
    else:
        t = sum(max(0, q[5] - d['blocks'][q[0]]['due_date']) for q in plc)
        print('  BEAM=%-5s placed %d/%d  tardiness %d vs incumbent %d  -> %s   %.1fs, %d oracle calls'
              % (beam or 'inf', len(plc), len(S), t, inc_t,
                 'BEATS it by %d' % (inc_t - t) if t < inc_t else
                 ('matches' if t == inc_t else 'worse by %d' % (t - inc_t)), el, bs.calls), flush=True)

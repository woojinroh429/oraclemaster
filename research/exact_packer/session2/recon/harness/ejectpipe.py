"""EJECTION-CHAIN pipeline: spend the budget on the one operator that measurably moves.

Why this operator and not another (all measured, see OVERNIGHT_PLAN.md):
  * single-block relocation to a better bay -- 0 fixable on prob_22/29/21/32
  * pairwise bay swap -- 443 of 443 improving candidates fail on exactly one side
  * stake-ordered bay rebuild -- seats 42 where the incumbent packs 52
  * eject-and-insert -- the only thing that moved anything: prob_29 -3.75% at 300s
The prize is real: reallocating the popular bay's seats by regret is worth -22% (p22) to
-56% (p24) of the objective, and it is unreachable by any small move.

Three things make the budget usable:

1. WINDOWED rescan.  After evicting victims V, block b can only newly fit where V's
   footprints were, so `feasible_scan_win` over those rectangles replaces a full-bay
   `feasible_scan`.  Measured 3.6-5.0x (prob_24 6.5 -> 1.8 ms, prob_22 0.74 -> 0.15 ms)
   with the same answer 461 times out of 462.  The one disagreement is benign: the full
   scan found a cell far from the victim, i.e. a placement that needed no eviction at all.
   remove/add cost 0.001-0.002 ms, so the scan was 100% of the cost.

2. TRUE-objective scoring.  Entry and exit times never change, so Z1 is constant by
   construction and the exact delta is w2*dZ2 + w3*dZ3, computed in closed form.  No proxy
   -- the trap that cost us prob_37 (construction won by 23%, instance lost by 20%) and
   prob_24 (_z3_improve took Z3 877->844 while pushing Z2 716->3216).

3. It does not stop when it converges.  The earlier version made 2 moves in 15s and then
   sat still for the rest of the budget.  Here a simulated-annealing acceptance plus
   restart-from-best keeps it exploring for the whole window, while the incumbent is
   retained as the floor so the result is never worse than the input.

RESULT: pouring budget into this operator does NOT pay, and the reason is arithmetic, not
search.  prob_29 at 90s:

    K=3   47,790 attempts, 57,287 scans, 2 accepted   ->  -3.67%
    K=6   32,461 attempts, 39,697 scans, 2 accepted   ->  -3.67%

Identical to the last digit.  Raising K, adding the slack-shift reseat, annealing for tens
of thousands of attempts: all of it finds the same two moves and nothing else.  The
neighbourhood is exhausted after two moves, so 80% of the budget here would be wasted.

Why -- the exchange rate.  Relocating one block to its preferred bay is worth
w3*gap/w1 tardiness units, and freeing a slot in the popular bay costs (median resident
processing time - free slack) units:

    prob_22  prize 2.1  cost  7.2   underwater  3.4x
    prob_29  prize 1.0  cost  8.3   underwater  8.5x
    prob_24  prize 0.9  cost 11.0   underwater 12.3x
    prob_21  prize 0.8  cost 16.0   underwater 20.9x
    prob_30  prize 1.0  cost  8.4   underwater  8.5x

w1 dwarfs w3, so the whole preference prize per block is 1-2 tardiness units while the
schedule disturbance needed to collect it costs 7-16.  The earlier "reallocation is worth
-22% to -56%" bound was computed by permuting bay seats WITHOUT charging for the
disturbance; once charged, it disappears.  Two accepted moves out of 47,790 attempts is
the correct answer, not a search failure.

Kept because the machinery is sound and correct-by-construction (times fixed -> Z1 fixed ->
exact w2*dZ2 + w3*dZ3 delta, engine as sole feasibility authority), and because the
measurement above should stop anyone re-running this experiment.

    python3.12 harness/ejectpipe.py <probs> <seed_s> <eject_s> [K] [T0]
"""
import sys, os, json, math, time, random, itertools
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


class Ejector:
    def __init__(self, d, sol, seed=12345):
        self.d = d; self.B = d['blocks']; self.n = len(self.B); self.m = len(d['bays'])
        w = d['weights']
        self.w2 = float(w.get('w2', 0)); self.w3 = float(w.get('w3', 0))
        self.rng = random.Random(seed)
        self.ent = {}; self.ext = {}
        self.bay = {}; self.ori = {}; self.px = {}; self.py = {}
        for t, ops in sol['operations'].items():
            for op in ops:
                b = op['block_id']
                if op['type'] == 'ENTRY':
                    self.ent[b] = int(t); self.bay[b] = op['bay_id']
                    self.ori[b] = op['orient_idx']; self.px[b] = op['x']; self.py[b] = op['y']
                else:
                    self.ext[b] = int(t)
        self.pref = [self.B[b]['bay_preferences'] for b in range(self.n)]
        self.mxp = [max(self.pref[b]) for b in range(self.n)]
        self.wl = [float(self.B[b].get('workload', 0.0)) for b in range(self.n)]
        ar = [d['bays'][j]['width'] * d['bays'][j]['height'] for j in range(self.m)]
        av = sum(ar) / self.m
        self.u = [av / a if a else 0.0 for a in ar]
        self.ewh = {}
        for b in range(self.n):
            ww = hh = 0
            for oi in range(len(self.B[b]['shape'])):
                q = M._orient_bbox(self.B[b], oi)
                ww = max(ww, q[2] - q[0]); hh = max(hh, q[3] - q[1])
            self.ewh[b] = (int(ww) + 1, int(hh) + 1)
        # time-overlap neighbour lists, built once
        self.ov = {b: [c for c in range(self.n) if c != b
                       and not (self.ext[c] <= self.ent[b] or self.ext[b] <= self.ent[c])]
                   for b in range(self.n)}
        self.E = M._ogc_fast_engine(d)
        self.load = [0.0] * self.m
        self.reload()
        self.attempts = 0; self.scans = 0; self.accepted = 0

    def reload(self):
        self.E.clear_all()
        self.load = [0.0] * self.m
        for b in range(self.n):
            self.E.add(self.bay[b], b, int(self.ori[b]), float(self.px[b]), float(self.py[b]),
                       self.ent[b], self.ext[b])
            self.load[self.bay[b]] += self.wl[b]

    def snapshot(self):
        return (dict(self.bay), dict(self.ori), dict(self.px), dict(self.py))

    def restore(self, s):
        self.bay, self.ori, self.px, self.py = dict(s[0]), dict(s[1]), dict(s[2]), dict(s[3])
        self.reload()

    def _undo(self, touched, placed):
        """Put back only what this attempt moved.  restore() rebuilds the whole engine
        (clear_all + n adds); at n=150 that cost more per REJECTED attempt than the scan
        the attempt existed to do, and most attempts are rejected."""
        for c in placed:
            self.E.remove(c)
        for (c, ob, oo_, ox, oy, oen, oex) in touched:
            self.ent[c], self.ext[c] = oen, oex
            self.E.add(ob, c, int(oo_), float(ox), float(oy), oen, oex)
            self.bay[c], self.ori[c], self.px[c], self.py[c] = ob, oo_, ox, oy

    def obj2(self, ld):
        v = [self.u[j] * ld[j] for j in range(self.m)]
        return math.floor(max(v) - min(v)) if self.m >= 2 else 0.0

    def z3(self):
        return sum(self.mxp[b] - self.pref[b][self.bay[b]] for b in range(self.n))

    def score(self):
        return self.w2 * self.obj2(self.load) + self.w3 * self.z3()

    def _rect_of(self, c):
        q = M._orient_bbox(self.B[c], self.ori[c])
        return (self.px[c] + q[0], self.py[c] + q[1], self.px[c] + q[2], self.py[c] + q[3])

    def _fit_window(self, b, j, victims):
        """Where can b go now that `victims` are gone?  Only near their footprints."""
        bw, bh = self.ewh[b]
        rects = []
        for v in victims:
            x0, y0, x1, y1 = self._rect_of(v)
            rects += [int(x0) - bw, int(x1), int(y0) - bh, int(y1)]
        self.scans += 1
        r = self.E.feasible_scan_win(b, j, self.ent[b], self.ext[b], 1, rects)
        return (int(r[0][0]), int(r[0][1]), int(r[0][2])) if len(r) else None

    def _fit_any(self, c, bays, allow_shift=True):
        """Re-seat an evicted block.  If nothing takes it at its own window, let it WAIT --
        but only inside its zero-tardiness slack, so Z1 stays fixed by construction and the
        exact objective delta remains w2*dZ2 + w3*dZ3.  Blocks carry 0-7 units of slack
        here, small but not nothing, and it is free."""
        self.scans += 1
        r = self.E.feasible_scan(c, list(bays), self.ent[c], self.ext[c], 1)
        if len(r):
            q = max(r, key=lambda z: self.pref[c][int(z[0])])
            return (int(q[0]), int(q[1]), int(q[2]), int(q[3]), self.ent[c], self.ext[c])
        if not allow_shift:
            return None
        pt = self.B[c]['processing_time']; due = self.B[c]['due_date']
        for t in range(self.ent[c] + 1, int(due) - int(pt) + 1):
            self.scans += 1
            r = self.E.feasible_scan(c, list(bays), t, t + pt, 1)
            if len(r):
                q = max(r, key=lambda z: self.pref[c][int(z[0])])
                return (int(q[0]), int(q[1]), int(q[2]), int(q[3]), t, t + pt)
        return None

    def attempt(self, b, victims):
        """One ejection attempt with an explicit (outsider, victim set).
        Returns (delta, undo_token) if it lands, else None -- state already rolled back."""
        self.attempts += 1
        j = max(range(self.m), key=lambda k: self.pref[b][k])
        if j == self.bay[b] or not victims:
            return None
        ld0 = list(self.load); s0 = self.score()
        touched = [(c, self.bay[c], self.ori[c], self.px[c], self.py[c], self.ent[c], self.ext[c])
                   for c in list(victims) + [b]]
        for v in victims:
            self.E.remove(v)
        self.E.remove(b)
        got = self._fit_window(b, j, victims)
        if got is None:
            self._undo(touched, []); self.load = ld0; return None
        self.E.add(j, b, got[0], float(got[1]), float(got[2]), self.ent[b], self.ext[b])
        placed = [b]
        self.load[self.bay[b]] -= self.wl[b]; self.load[j] += self.wl[b]
        self.bay[b], self.ori[b], self.px[b], self.py[b] = j, got[0], got[1], got[2]
        ok = True
        for v in victims:
            alt = sorted((t for t in range(self.m) if t != j), key=lambda t: -self.pref[v][t])
            g = self._fit_any(v, alt)
            if g is None:
                ok = False; break
            self.ent[v], self.ext[v] = g[4], g[5]
            self.E.add(g[0], v, g[1], float(g[2]), float(g[3]), g[4], g[5])
            placed.append(v)
            self.load[j] -= self.wl[v]; self.load[g[0]] += self.wl[v]
            self.bay[v], self.ori[v], self.px[v], self.py[v] = g[0], g[1], g[2], g[3]
        if not ok:
            self._undo(touched, placed); self.load = ld0; return None
        return self.score() - s0, (touched, placed, ld0)

    def undo(self, tok):
        touched, placed, ld0 = tok
        self._undo(touched, placed); self.load = ld0

    def outsiders(self):
        return sorted((b for b in range(self.n) if self.mxp[b] - self.pref[b][self.bay[b]] > 0),
                      key=lambda b: -(self.mxp[b] - self.pref[b][self.bay[b]]))

    def victim_pool(self, b, j, cap=12):
        occ = [c for c in self.ov[b] if self.bay[c] == j]
        occ.sort(key=lambda c: (self.pref[c][j] - max(self.pref[c][t] for t in range(self.m) if t != j)))
        return occ[:cap]

    def try_move(self, K):
        """Randomised attempt, for the annealing phase."""
        outs = self.outsiders()
        if not outs:
            return None
        b = self.rng.choices(outs, weights=[self.mxp[x] - self.pref[x][self.bay[x]] for x in outs])[0]
        j = max(range(self.m), key=lambda k: self.pref[b][k])
        pool = self.victim_pool(b, j)
        if not pool:
            return None
        k = self.rng.randint(1, min(K, len(pool)))
        return self.attempt(b, self.rng.sample(pool, k))


def run(p, seed_s, eject_s, K, T0):
    d = load(p)
    sol = M.algorithm(d, timelimit=seed_s)
    c0 = utils.check_feasibility(d, sol); o0 = int(c0['objective'])
    ej = Ejector(d, sol)
    best_s = ej.snapshot(); best_score = ej.score(); cur = best_score
    t0 = time.time()
    # PHASE 1 -- systematic first-improvement sweep.  The randomised phase alone reached
    # only -1.78% on prob_29 where the deterministic sweep had found -3.75%: annealing
    # samples victim sets, so it keeps missing the certain improving moves.  Take those
    # first, then spend what is left exploring.
    sweep_dl = t0 + eject_s * 0.35
    improved = True
    while improved and time.time() < sweep_dl:
        improved = False
        for b in ej.outsiders():
            if time.time() > sweep_dl:
                break
            j = max(range(ej.m), key=lambda k: ej.pref[b][k])
            pool = ej.victim_pool(b, j)
            hit = False
            for k in range(1, K + 1):
                if hit:
                    break
                for combo in itertools.combinations(pool, k):
                    r = ej.attempt(b, list(combo))
                    if r is None:
                        continue
                    delta, tok = r
                    if delta < -1e-9:
                        cur += delta; ej.accepted += 1; improved = True; hit = True
                        if cur < best_score - 1e-9:
                            best_score = cur; best_s = ej.snapshot()
                        break
                    ej.undo(tok)
    ej.restore(best_s); cur = best_score
    # PHASE 2 -- anneal, restarting from the best so it never drifts away for good
    last = time.time()
    while time.time() - t0 < eject_s:
        r = ej.try_move(K)
        if r is None:
            continue
        delta, tok = r
        frac = 1.0 - (time.time() - t0) / eject_s
        T = max(1e-9, T0 * frac * max(1.0, abs(best_score)) * 1e-4)
        if delta < 0 or ej.rng.random() < math.exp(-delta / T):
            cur += delta; ej.accepted += 1
            if cur < best_score - 1e-9:
                best_score = cur; best_s = ej.snapshot()
        else:
            ej.undo(tok)
        if time.time() - last > eject_s / 4.0:
            ej.restore(best_s); cur = best_score; last = time.time()
    ej.restore(best_s)
    recs = [{"block_id": b, "bay_id": ej.bay[b], "x": ej.px[b], "y": ej.py[b],
             "orient_idx": ej.ori[b], "entry_time": ej.ent[b], "exit_time": ej.ext[b]}
            for b in range(ej.n)]
    s2 = M._build_operations(recs)
    c2 = utils.check_feasibility(d, s2)
    o2 = int(c2['objective']) if c2.get('feasible') else -1
    el = time.time() - t0
    print('p%-3d base=%-10d Z1=%-6s Z2=%-6s Z3=%-7s -> eject=%-10d Z1=%-6s Z2=%-6s Z3=%-7s %+.2f%%'
          % (p, o0, c0['obj1'], c0['obj2'], c0['obj3'], o2, c2.get('obj1'), c2.get('obj2'),
             c2.get('obj3'), 100.0 * (o2 - o0) / o0 if o2 > 0 else 0), flush=True)
    print('     %s attempts, %s scans, %d accepted in %.0fs  (%.0f attempts/s)'
          % (format(ej.attempts, ','), format(ej.scans, ','), ej.accepted, el, ej.attempts / max(1e-9, el)),
          flush=True)


if __name__ == '__main__':
    probs = [int(x) for x in sys.argv[1].split(',')]
    seed_s = float(sys.argv[2]); eject_s = float(sys.argv[3])
    K = int(sys.argv[4]) if len(sys.argv) > 4 else 3
    T0 = float(sys.argv[5]) if len(sys.argv) > 5 else 2.0
    for p in probs:
        run(p, seed_s, eject_s, K, T0)

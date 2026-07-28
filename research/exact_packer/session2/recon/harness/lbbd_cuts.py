"""LBBD with REAL feasibility cuts, not a global capacity fudge.

Where the previous rounds stand (all measured):
  * master over incumbent windows RUNS everywhere and claims big allocation gains --
    prob_22 Z3 1930 -> 1538, prob_29 Z3 1175 -> 467
  * not one of them survives realisation.  prob_22 realises to Z3 2186 (7 spills),
    prob_29 to Z3 1227 (12 spills) -- both WORSE than the incumbent they started from.
The area-capacity row is simply far too optimistic about what a bay can hold, and the
existing feedback (scale every bay's capacity by 0.93 and re-solve) is a blunt instrument:
it makes the master more pessimistic everywhere instead of telling it the one thing it got
wrong.

So give it the textbook logic-based Benders feasibility cut instead.  When the realiser
finds that block b cannot enter bay j because blocks S are already there across its window,
that is a proof that {b} u S cannot share bay j simultaneously, and

    x[b][j] + sum_{c in S} x[c][j] <= |S|

is valid for every feasible assignment.  Accumulated over rounds the master LEARNS each
bay's true packing limit in the only currency that matters -- which block combinations are
actually impossible -- rather than a scalar shrink factor."""
import sys, os, json, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import myalgorithm as M, utils
M._CPP_ENGINE_MODE = M.HAVE_OGC_FAST
from ortools.sat.python import cp_model


def load_prob(p):
    for c in ('data/train/prob_%d.json' % p, 'data/set1/prob_%d.json' % p):
        if os.path.exists(c):
            return json.load(open(c))
    raise SystemExit("prob_%d missing" % p)


def solve(d, sol, tl_master, rounds, budget):
    B = d['blocks']; n = len(B); bays = d['bays']; m = len(bays); w = d['weights']
    w1 = float(w['w1']); w3 = float(w['w3'])
    ent = {}; ext = {}; bay = {}
    for t, ops in sol['operations'].items():
        for op in ops:
            if op['type'] == 'ENTRY':
                ent[op['block_id']] = int(t); bay[op['block_id']] = op['bay_id']
            else:
                ext[op['block_id']] = int(t)
    pref = [B[b]['bay_preferences'] for b in range(n)]
    mxp = [max(pref[b]) for b in range(n)]
    areas = []
    for b in range(n):
        best = None
        for oi in range(len(B[b]['shape'])):
            bb = M._orient_bbox(B[b], oi); a = (bb[2] - bb[0]) * (bb[3] - bb[1])
            if best is None or a < best:
                best = a
        areas.append(int(round(best)))
    cap = [bays[j]['width'] * bays[j]['height'] for j in range(m)]
    SC = 1000; avg = sum(cap) / m
    U = [int(round(SC * avg / cap[j])) for j in range(m)]
    cuts = []                                   # (bay, frozenset(blocks)) -> at most |S|-1
    base_obj = int(utils.check_feasibility(d, sol)['objective'])
    best = (base_obj, None, 'incumbent', 0)
    t0 = time.time()
    for rnd in range(rounds):
        if time.time() - t0 > budget:
            break
        mdl = cp_model.CpModel()
        x = [[mdl.NewBoolVar("x%d_%d" % (b, j)) for j in range(m)] for b in range(n)]
        for b in range(n):
            mdl.Add(sum(x[b]) == 1)
        ldv = [mdl.NewIntVar(0, 10 ** 7, "l%d" % j) for j in range(m)]
        for j in range(m):
            mdl.Add(ldv[j] == sum(x[b][j] * int(B[b]['workload']) for b in range(n)))
        Mv = mdl.NewIntVar(0, 10 ** 12, "M")
        for j in range(m):
            for k in range(m):
                if j != k:
                    mdl.Add(Mv >= U[j] * ldv[j] - U[k] * ldv[k])
        for j in range(m):
            for t in sorted(set(ent.values())):
                pres = [b for b in range(n) if ent[b] <= t < ext[b]]
                if pres:
                    mdl.Add(sum(x[b][j] * areas[b] for b in pres) <= cap[j])
        for (j, S) in cuts:                     # the learned no-goods
            mdl.Add(sum(x[b][j] for b in S) <= len(S) - 1)
        Z3 = sum(x[b][j] * (mxp[b] - pref[b][j]) for b in range(n) for j in range(m))
        mdl.Minimize(w['w2'] * Mv + w['w3'] * SC * Z3)
        for b in range(n):
            for j in range(m):
                mdl.AddHint(x[b][j], 1 if bay[b] == j else 0)
        slv = cp_model.CpSolver()
        slv.parameters.max_time_in_seconds = tl_master
        slv.parameters.num_search_workers = 4
        st = slv.Solve(mdl)
        if st not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            return best, cuts, 'master infeasible at round %d' % rnd
        asg = [next(j for j in range(m) if slv.Value(x[b][j]) == 1) for b in range(n)]
        mz3 = sum(mxp[b] - pref[b][asg[b]] for b in range(n))
        # ---- subproblem: pack each bay at the incumbent's own times ----
        E = M._ogc_fast_engine(d); E.clear_all()
        out = {}; newcuts = 0; spill = 0
        placed_in = {j: [] for j in range(m)}
        for b in sorted(range(n), key=lambda b: (ent[b], -B[b]['processing_time'])):
            j = asg[b]
            r = E.feasible_scan(b, [j], ent[b], ext[b], 1)
            if len(r):
                E.add(j, b, int(r[0][1]), float(r[0][2]), float(r[0][3]), ent[b], ext[b])
                out[b] = (j, int(r[0][1]), int(r[0][2]), int(r[0][3]), ent[b], ext[b])
                placed_in[j].append(b)
                continue
            # PROOF of infeasibility: b plus the residents of j overlapping its window
            S = [c for c in placed_in[j] if not (ext[c] <= ent[b] or ext[b] <= ent[c])]
            if S:
                cuts.append((j, frozenset(S + [b]))); newcuts += 1
            alt = sorted((k for k in range(m) if k != j), key=lambda k: -pref[b][k])
            ra = E.feasible_scan(b, alt, ent[b], ext[b], 1)
            if not len(ra):
                out = None
                break
            q = max(ra, key=lambda z: pref[b][int(z[0])])
            E.add(int(q[0]), b, int(q[1]), float(q[2]), float(q[3]), ent[b], ext[b])
            out[b] = (int(q[0]), int(q[1]), int(q[2]), int(q[3]), ent[b], ext[b])
            placed_in[int(q[0])].append(b); spill += 1
        if out is not None:
            recs = [{"block_id": b, "bay_id": out[b][0], "x": out[b][2], "y": out[b][3],
                     "orient_idx": out[b][1], "entry_time": out[b][4], "exit_time": out[b][5]}
                    for b in range(n)]
            s2 = M._build_operations(recs)
            c2 = utils.check_feasibility(d, s2)
            if c2.get('feasible'):
                o2 = int(c2['objective'])
                print('     r%-2d masterZ3=%-6d spill=%-3d newcuts=%-4d cuts=%-5d realised obj=%-10d Z3=%s'
                      % (rnd, mz3, spill, newcuts, len(cuts), o2, c2.get('obj3')), flush=True)
                if o2 < best[0]:
                    best = (o2, s2, 'round%d' % rnd, len(cuts))
            else:
                print('     r%-2d masterZ3=%-6d spill=%-3d newcuts=%-4d cuts=%-5d INFEASIBLE realisation'
                      % (rnd, mz3, spill, newcuts, len(cuts)), flush=True)
        else:
            print('     r%-2d masterZ3=%-6d newcuts=%-4d cuts=%-5d UNPLACEABLE'
                  % (rnd, mz3, newcuts, len(cuts)), flush=True)
        if newcuts == 0 and spill == 0:
            print('     r%-2d assignment fully realisable -> converged' % rnd, flush=True)
            break
    return best, cuts, ''


for p in (int(x) for x in sys.argv[1].split(',')):
    d = load_prob(p)
    sol = M.algorithm(d, timelimit=float(sys.argv[2]))
    c0 = utils.check_feasibility(d, sol); o0 = int(c0['objective'])
    print('p%-3d base=%-10d Z1=%-6s Z2=%-6s Z3=%-7s' % (p, o0, c0['obj1'], c0['obj2'], c0['obj3']), flush=True)
    t0 = time.time()
    best, cuts, msg = solve(d, sol, float(sys.argv[3]), int(sys.argv[4]), float(sys.argv[5]))
    if best[1] is None:
        print('p%-3d -> NO GAIN after %d cuts  %s  (%.0fs)' % (p, len(cuts), msg, time.time() - t0), flush=True)
    else:
        c2 = utils.check_feasibility(d, best[1])
        print('p%-3d -> LBBD=%-10d Z1=%-6s Z2=%-6s Z3=%-7s %+.2f%%  via %s, %d cuts  (%.0fs)'
              % (p, best[0], c2.get('obj1'), c2.get('obj2'), c2.get('obj3'),
                 100.0 * (best[0] - o0) / o0, best[2], best[3], time.time() - t0), flush=True)

"""z3free in compose.py is a loose UPPER bound: it counts every misplaced block that still
has slack, whether or not a preferred bay could physically hold it.  This measures the
REACHABLE part -- for each misplaced block, actually remove it from the engine and scan
every strictly-more-preferred bay over every candidate entry time inside its
ZERO-TARDINESS window [release, due-pt].  Reports what a perfect single-block
delay-for-preference operator could recover, which is the ceiling on this whole idea."""
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
    raise SystemExit("prob_%d.json missing" % p)

for p in (int(x) for x in sys.argv[1].split(',')):
    d = load(p); B = d['blocks']; n = len(B); m = len(d['bays']); w = d['weights']
    sol = M.algorithm(d, timelimit=float(sys.argv[2]))
    c = utils.check_feasibility(d, sol)
    obj = float(c['objective'])
    ent = {}; ext = {}; bay = {}; xx = {}; yy = {}; oo = {}
    for t, ops in sol['operations'].items():
        for op in ops:
            if op['type'] == 'ENTRY':
                ent[op['block_id']] = int(t); bay[op['block_id']] = op['bay_id']
                xx[op['block_id']] = op['x']; yy[op['block_id']] = op['y']; oo[op['block_id']] = op['orient_idx']
            else:
                ext[op['block_id']] = int(t)
    E = M._ogc_fast_engine(d); E.clear_all()
    for b in range(n):
        E.add(bay[b], b, int(oo[b]), float(xx[b]), float(yy[b]), ent[b], ext[b])
    # candidate entry times: every block exit in the target bay is when space frees up
    exits = sorted(set(ext.values()))
    gain_free = 0.0; nfix = 0; nmis = 0; t0 = time.time()
    for b in range(n):
        pv = B[b]['bay_preferences']; mx = max(pv)
        if mx - pv[bay[b]] <= 0:
            continue
        nmis += 1
        pt = B[b]['processing_time']; rel = B[b]['release_time']; due = B[b]['due_date']
        tgts = [j for j in range(m) if pv[j] > pv[bay[b]]]
        E.remove(b)
        best = 0.0
        cands = [e for e in exits if rel <= e <= due - pt]
        if rel <= due - pt:
            cands = sorted(set(cands + [rel, ent[b]]))
        if len(cands) > 60:                      # keep the probe bounded
            step = len(cands) / 60.0
            cands = [cands[int(i * step)] for i in range(60)]
        for t in cands:
            arr = E.feasible_scan(b, tgts, int(t), int(t) + pt, 1)
            if len(arr):
                g = max(pv[int(r[0])] for r in arr) - pv[bay[b]]
                if g > best:
                    best = g
        E.add(bay[b], b, int(oo[b]), float(xx[b]), float(yy[b]), ent[b], ext[b])
        if best > 0:
            nfix += 1; gain_free += best
    print('p%-3d n=%-4d obj=%-11d Z3share=%4.1f%% | misplaced %3d  '
          'SINGLE-MOVE fixable at ZERO tardiness %3d  gain=%.0f pts = %.2f%% of obj  (%.0fs)'
          % (p, n, int(obj), 100.0 * w['w3'] * float(c['obj3']) / obj, nmis, nfix,
             gain_free, 100.0 * w['w3'] * gain_free / obj, time.time() - t0), flush=True)

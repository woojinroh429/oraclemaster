"""EJECT-AND-INSERT for the preference-dominated low-density class.

Why this shape and not something simpler (all measured, do not re-derive):
  * single-block move to a better bay -- 0 fixable on p22/p29/p21/p32.  The popular bay
    has 0 feasible cells at the block's own entry time and blocks carry 0-7 units of
    slack, so waiting does not open it either.
  * pairwise bay swap -- of 443 improving candidates on p22 every one fails on exactly
    one side: the partner's window does not overlap, so evicting it frees nothing.
  * full bay rebuild in stake order -- seats only 42 blocks in p22's bay0 where the
    incumbent packs 52.  Stake ordering ignores geometry, so it packs strictly worse.

What is left is the asymmetric move: to seat an outsider, evict the occupants that
actually stand in its way -- the ones whose window OVERLAPS it -- choosing the ones with
the least stake in the bay, and let them land in any bay that will take them.  Entry and
exit times never change, so Z1 is fixed by construction; Z2 and Z3 are scored exactly and
a move is accepted only if the true objective strictly improves."""
import sys, os, json, math, time, itertools
HERE = os.path.dirname(os.path.abspath(__file__))
REC = os.path.dirname(HERE)
sys.path.insert(0, REC); os.chdir(REC)
import myalgorithm as M, utils
M._CPP_ENGINE_MODE = M.HAVE_OGC_FAST


def load(p):
    for c in ('data/train/prob_%d.json' % p, 'data/set1/prob_%d.json' % p):
        if os.path.exists(c):
            return json.load(open(c))
    raise SystemExit("prob_%d missing" % p)


def eject_insert(d, sol, budget, maxk=2):
    B = d['blocks']; n = len(B); m = len(d['bays']); w = d['weights']
    w2 = float(w.get('w2', 0)); w3 = float(w.get('w3', 0))
    ent = {}; ext = {}; bay = {}; xx = {}; yy = {}; oo = {}
    for t, ops in sol['operations'].items():
        for op in ops:
            if op['type'] == 'ENTRY':
                b = op['block_id']; ent[b] = int(t); bay[b] = op['bay_id']
                xx[b] = op['x']; yy[b] = op['y']; oo[b] = op['orient_idx']
            else:
                ext[op['block_id']] = int(t)
    pref = [B[b]['bay_preferences'] for b in range(n)]
    mxp = [max(pref[b]) for b in range(n)]
    wl = [float(B[b].get('workload', 0.0)) for b in range(n)]
    ar = [d['bays'][j]['width'] * d['bays'][j]['height'] for j in range(m)]
    av = sum(ar) / m
    u = [av / a if a else 0.0 for a in ar]
    load = [0.0] * m
    for b in range(n):
        load[bay[b]] += wl[b]

    def o2(ld):
        v = [u[j] * ld[j] for j in range(m)]
        return math.floor(max(v) - min(v)) if m >= 2 else 0.0

    E = M._ogc_fast_engine(d); E.clear_all()
    for b in range(n):
        E.add(bay[b], b, int(oo[b]), float(xx[b]), float(yy[b]), ent[b], ext[b])

    def seat(b, bays_pref):
        r = E.feasible_scan(b, list(bays_pref), ent[b], ext[b], 1)
        if not len(r):
            return None
        best = max(r, key=lambda q: pref[b][int(q[0])])
        return int(best[0]), int(best[1]), int(best[2]), int(best[3])

    t0 = time.time(); nacc = 0
    improved = True
    while improved and time.time() - t0 < budget:
        improved = False
        outs = sorted((b for b in range(n) if mxp[b] - pref[b][bay[b]] > 0),
                      key=lambda b: -(mxp[b] - pref[b][bay[b]]))
        for b in outs:
            if time.time() - t0 > budget:
                break
            jstar = max(range(m), key=lambda j: pref[b][j])
            if jstar == bay[b]:
                continue
            occ = [c for c in range(n) if bay[c] == jstar and c != b
                   and not (ext[c] <= ent[b] or ext[b] <= ent[c])]
            # least stake in jstar first: they are the cheapest to displace
            occ.sort(key=lambda c: (pref[c][jstar] - max(pref[c][k] for k in range(m) if k != jstar)))
            occ = occ[:12]
            hit = False
            for k in range(1, maxk + 1):
                if hit or time.time() - t0 > budget:
                    break
                for combo in itertools.combinations(occ, k):
                    old = {c: (bay[c], oo[c], xx[c], yy[c]) for c in combo}
                    for c in combo:
                        E.remove(c)
                    E.remove(b)
                    got = seat(b, [jstar])
                    if got is None:
                        E.add(bay[b], b, int(oo[b]), float(xx[b]), float(yy[b]), ent[b], ext[b])
                        for c in combo:
                            E.add(old[c][0], c, old[c][1], float(old[c][2]), float(old[c][3]), ent[c], ext[c])
                        continue
                    E.add(got[0], b, got[1], float(got[2]), float(got[3]), ent[b], ext[b])
                    placed = {}
                    ok = True
                    for c in combo:
                        alts = sorted((j for j in range(m) if j != jstar), key=lambda j: -pref[c][j])
                        g = seat(c, alts)
                        if g is None:
                            ok = False
                            break
                        E.add(g[0], c, g[1], float(g[2]), float(g[3]), ent[c], ext[c])
                        placed[c] = g
                    if ok:
                        ld = load[:]
                        ld[bay[b]] -= wl[b]; ld[jstar] += wl[b]
                        d3 = -(mxp[b] - pref[b][bay[b]])
                        for c in combo:
                            ld[jstar] -= wl[c]; ld[placed[c][0]] += wl[c]
                            d3 += (mxp[c] - pref[c][placed[c][0]]) - (mxp[c] - pref[c][jstar])
                        if w3 * d3 + w2 * (o2(ld) - o2(load)) < -1e-9:
                            load = ld
                            bay[b], oo[b], xx[b], yy[b] = got
                            for c in combo:
                                bay[c], oo[c], xx[c], yy[c] = placed[c]
                            nacc += 1; improved = True; hit = True
                            break
                    for c in placed:
                        E.remove(c)
                    E.remove(b)
                    E.add(old and bay[b] or bay[b], b, int(oo[b]), float(xx[b]), float(yy[b]), ent[b], ext[b])
                    for c in combo:
                        E.add(old[c][0], c, old[c][1], float(old[c][2]), float(old[c][3]), ent[c], ext[c])
    recs = [{"block_id": b, "bay_id": bay[b], "x": xx[b], "y": yy[b], "orient_idx": oo[b],
             "entry_time": ent[b], "exit_time": ext[b]} for b in range(n)]
    return M._build_operations(recs), nacc


for p in (int(x) for x in sys.argv[1].split(',')):
    d = load(p)
    sol = M.algorithm(d, timelimit=float(sys.argv[2]))
    c0 = utils.check_feasibility(d, sol); o0 = int(c0['objective'])
    t0 = time.time()
    s2, nacc = eject_insert(d, sol, float(sys.argv[3]) if len(sys.argv) > 3 else 30.0)
    c2 = utils.check_feasibility(d, s2)
    o2 = int(c2['objective']) if c2.get('feasible') else -1
    print('p%-3d base=%-10d Z1=%-6s Z2=%-6s Z3=%-7s -> eject=%-10d Z1=%-6s Z2=%-6s Z3=%-7s '
          '%+.2f%%  moves=%d  (%.0fs)'
          % (p, o0, c0['obj1'], c0['obj2'], c0['obj3'], o2, c2.get('obj1'), c2.get('obj2'),
             c2.get('obj3'), 100.0 * (o2 - o0) / o0 if o2 > 0 else 0, nacc, time.time() - t0), flush=True)

"""Is the mid-band gap a CONSTRUCTION-diversity gap?  One prefbkt build costs ~5s and
lands within 8% of what the whole 300s pipeline reaches, and the spread ACROSS modes is
44% -- so the question is whether perturbing the dispatch order alone reaches lower than
any named mode does."""
import sys, os, json, time, random
sys.path.insert(0, '.')
import myalgorithm as M, utils
M._CPP_ENGINE_MODE = M.HAVE_OGC_FAST

p = int(sys.argv[1]); budget = float(sys.argv[2]); mode = sys.argv[3] if len(sys.argv) > 3 else "prefbkt"
d = json.load(open('data/train/prob_%d.json' % p)); n = len(d['blocks'])
B = d['blocks']
due = [b['due_date'] for b in B]; rel = [b['release_time'] for b in B]
ar, _bc, _sc = M._footprint_areas(d)


def rof(v, rv):
    o = sorted(range(n), key=lambda i: v[i], reverse=rv); r = [0.0] * n
    for i, b in enumerate(o): r[b] = i / max(1, n - 1)
    return r


rd = rof(due, False); ra = rof(ar, True)
base = [rd[b] + ra[b] for b in range(n)]
rng = random.Random(12345)
t0 = time.time(); best = None; k = 0
while time.time() - t0 < budget:
    if k == 0:
        order = "rank"
    else:
        eps = 0.05 + 0.25 * rng.random()
        order = sorted(range(n), key=lambda b: (base[b] + rng.gauss(0, eps), due[b]))
    r = M._smallright_construct(d, time.time() + 60, step=1, mode=mode, order=order)
    k += 1
    if not r or len(r) != n:
        continue
    c = utils.check_feasibility(d, M._build_operations([r[b] for b in range(n)]))
    if not c.get('feasible'):
        continue
    o = int(c['objective'])
    if best is None or o < best[0]:
        best = (o, k, c.get('obj1'), c.get('obj2'), c.get('obj3'))
        print('  k=%-3d obj=%-11d Z1=%-7s Z2=%-6s Z3=%-8s t=%.0fs' % (k, o, c.get('obj1'), c.get('obj2'), c.get('obj3'), time.time() - t0), flush=True)
print('BEST p%d %s builds=%d obj=%d (first build %s)' % (p, mode, k, best[0] if best else -1, 'k=%d' % best[1] if best else '-'), flush=True)

import sys, json, time, os
sys.path.insert(0, '.')
import myalgorithm as M, utils
M._CPP_ENGINE_MODE = M.HAVE_OGC_FAST
for p in (36, 34, 24, 28, 32, 30):
    d = json.load(open('data/train/prob_%d.json' % p)); n = len(d['blocks'])
    row = {}
    for m in ('bigleft', 'coreperi', 'prefbkt', 'prefbkt5'):
        r = M._smallright_construct(d, time.time() + 400, step=1, mode=m)
        if not r or len(r) != n:
            row[m] = -1; continue
        c = utils.check_feasibility(d, M._build_operations([r[b] for b in range(n)]))
        row[m] = (int(c['objective']) if c.get('feasible') else -1, c.get('obj1'), c.get('obj2'), c.get('obj3'))
    base = min([v[0] for k, v in row.items() if k in ('bigleft', 'coreperi') and v != -1 and v[0] > 0] or [0])
    bk = min([v[0] for k, v in row.items() if k.startswith('prefbkt') and v != -1 and v[0] > 0] or [0])
    g = ('%+.1f%%' % (100.0 * (bk - base) / base)) if base and bk else 'n/a'
    print('p%-3d phys=%.3f base=%-11d prefbkt=%-11d %s  %s'
          % (p, M._demand_ratio_phys(d), base, bk, g,
             ' '.join('%s=%s' % (k, v[0] if v != -1 else 'FAIL') for k, v in row.items())), flush=True)

"""_z3_improve is the last post-pass and gets whatever wall time is left (often a few
seconds).  On prob_37 the pooled worker best was 4,158,580 and the returned answer
3,941,154 (-5.2%) -- the hint-beam FAILS standalone at 250 blocks in 100s, so that
-5.2% is very likely this pass.  A single cheap pass worth 5% is the strongest per-step
gain measured anywhere in the pipeline.  Does it have headroom left, i.e. does re-running
it keep finding moves?"""
import sys, os, json, time
sys.path.insert(0, '.')
import myalgorithm as M, utils
M._CPP_ENGINE_MODE = M.HAVE_OGC_FAST

p = int(sys.argv[1]); base = float(sys.argv[2]); passes = int(sys.argv[3])
per = float(sys.argv[4]) if len(sys.argv) > 4 else 10.0
d = json.load(open('data/train/prob_%d.json' % p))
sol = M.algorithm(d, timelimit=base)
c = utils.check_feasibility(d, sol); cur = int(c['objective'])
print('p%d base(%.0fs) obj=%d Z1=%s Z2=%s Z3=%s' % (p, base, cur, c.get('obj1'), c.get('obj2'), c.get('obj3')), flush=True)
for it in range(passes):
    t0 = time.time()
    imp = M._z3_improve(d, sol, per)
    dt = time.time() - t0
    if imp is None:
        print('  pass%d none t=%.1fs' % (it + 1, dt), flush=True); break
    c2 = utils.check_feasibility(d, imp)
    if not c2.get('feasible'):
        print('  pass%d INFEASIBLE t=%.1fs' % (it + 1, dt), flush=True); break
    o2 = int(c2['objective'])
    print('  pass%d obj=%-11d Z1=%-7s Z2=%-6s Z3=%-8s %+.3f%% t=%.1fs'
          % (it + 1, o2, c2.get('obj1'), c2.get('obj2'), c2.get('obj3'), 100.0 * (o2 - cur) / cur, dt), flush=True)
    if o2 < cur:
        cur = o2; sol = imp
    else:
        print('  (no further gain -> converged)', flush=True); break
print('p%d FINAL obj=%d' % (p, cur), flush=True)

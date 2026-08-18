import sys, os, json, time
sys.path.insert(0, '.')
os.environ["OGCWIN"] = "1"
import myalgorithm as M, utils
M._CPP_ENGINE_MODE = M.HAVE_OGC_FAST
for p in (int(x) for x in sys.argv[1].split(",")):
    d = json.load(open('data/train/prob_%d.json' % p))
    b = float(sys.argv[2]) if len(sys.argv) > 2 else 300.0
    s = M.algorithm(d, timelimit=b)
    c = utils.check_feasibility(d, s)
    print('p%-3d dr=%.3f obj=%d' % (p, M._demand_ratio_phys(d), int(c['objective'])), flush=True)
    for wid, tag, o in getattr(M, "_LAST_DBGWIN", []):
        print('     W%d %-10s %d' % (wid, tag, int(o)), flush=True)

"""The hint-beam post-pass runs ONCE and was worth -5.2% on prob_37 (4,158,580 ->
3,941,154) and -0.36% on prob_35 in the attribution traces.  A single pass that large is
the biggest per-step gain measured anywhere in the pipeline, and nothing feeds its own
output back in.  Question: does it compound, or is one pass the whole basin?"""
import sys, os, json, time
sys.path.insert(0, '.')
import myalgorithm as M, utils
M._CPP_ENGINE_MODE = M.HAVE_OGC_FAST

p = int(sys.argv[1]); base_budget = float(sys.argv[2]); passes = int(sys.argv[3])
d = json.load(open('data/train/prob_%d.json' % p)); n = len(d['blocks'])
w3 = float(d["weights"]["w3"])

sol = M.algorithm(d, timelimit=base_budget)
c = utils.check_feasibility(d, sol)
cur = int(c['objective'])
print('p%d base(%.0fs) obj=%d Z1=%s Z2=%s Z3=%s' % (p, base_budget, cur, c.get('obj1'), c.get('obj2'), c.get('obj3')), flush=True)

for it in range(passes):
    bay = [-1] * n; ent = [0] * n
    for t, ops in sol["operations"].items():
        for o in ops:
            if o["type"] == "ENTRY":
                bay[o["block_id"]] = o["bay_id"]; ent[o["block_id"]] = int(t)
    order = sorted(range(n), key=lambda b: (ent[b], b))
    t0 = time.time()
    g = M._contact_beam(d, 100.0, B=32, K=4, pos_lam=0.15, order="edd_tri2",
                        fut_beta=1.5, anchor_bays=bay, anchor_order=order, stay_w=2.0 * w3)
    if not g or len(g) != n:
        print('  pass%d FAIL t=%.0fs' % (it + 1, time.time() - t0), flush=True); break
    ops2 = {}
    for b, a in g.items():
        ops2.setdefault(a["entry_time"], []).append(
            {"type": "ENTRY", "block_id": b, "bay_id": a["bay_id"],
             "x": a["x"], "y": a["y"], "orient_idx": a["orient_idx"]})
        ops2.setdefault(a["exit_time"], []).append({"type": "EXIT", "block_id": b, "bay_id": a["bay_id"]})
    s2 = {"operations": {str(k): sorted(ops2[k], key=lambda o: 0 if o["type"] == "EXIT" else 1)
                         for k in sorted(ops2)}}
    c2 = utils.check_feasibility(d, s2)
    if not c2.get("feasible"):
        print('  pass%d INFEASIBLE t=%.0fs' % (it + 1, time.time() - t0), flush=True); break
    o2 = int(c2['objective'])
    print('  pass%d obj=%-11d Z1=%-7s Z2=%-6s Z3=%-8s %+.2f%% t=%.0fs'
          % (it + 1, o2, c2.get('obj1'), c2.get('obj2'), c2.get('obj3'),
             100.0 * (o2 - cur) / cur, time.time() - t0), flush=True)
    if o2 < cur:
        cur = o2; sol = s2
    else:
        print('  (kept previous; anchor unchanged -> stop)', flush=True); break
print('p%d FINAL obj=%d' % (p, cur), flush=True)

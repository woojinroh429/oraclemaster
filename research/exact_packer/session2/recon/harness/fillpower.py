"""HOW LONG DOES A SECOND ROUND HAVE TO BE TO BEAT A GIVEN INCUMBENT?

The freeround queue is trying to answer this by waiting for prob_1 to hand it a bad round-0 draw,
and prob_1 has returned 438,791 -- its p25 -- three times running.  A run whose round 0 lands well
cannot say anything about a mechanism that only fires when round 0 lands badly, so four replicates
of that are four uninformative cells.

This asks the question directly.  Round 0 is given a SHORT budget so its incumbent is deliberately
poor, then a second round of a known length runs against it, and the pair is recorded.  Sweeping
the second round's length over the values the queues actually produce -- 24 s and 31 s from
variant C, 67-76 s from variant B -- prices the mechanism instead of the draw:

    if a 31 s round beats a 500k incumbent and a 24 s round does not, the free round is worth
    having on instances that discard 40 s and not on ones that discard 24;

    if neither does at any incumbent quality, the tail cut needs B's 76 s and therefore needs
    round 0 to pay for it, and variant C is neutral by construction rather than by measurement.

Reads OGC_WSTAT lines from the child rather than parsing objectives, because FILL prints exactly
what is wanted: the round's budget, whether it moved, and the incumbent it moved from.
"""
import os, subprocess, sys, re

HERE = os.path.dirname(os.path.abspath(__file__))
RECON = os.path.dirname(HERE)
PY = "/usr/bin/python3.12"


def one(prob, limit, env):
    e = dict(os.environ); e.update(env); e["OGC_WSTAT"] = "1"
    p = subprocess.run([PY, os.path.join(HERE, "run1.py"), "myalgorithm", str(prob), str(limit),
                        "[fillpower]", "--data", "data/stage2"],
                       cwd=RECON, env=e, capture_output=True, text=True, timeout=limit * 4 + 120)
    out = p.stdout + p.stderr
    ws = re.search(r"WSTAT round=0 n=\d+ ([\d\s]+?)\s+spread", out)
    r0 = min(int(x) for x in ws.group(1).split()) if ws else None
    fl = re.search(r"FILL round=\d+ budget=(\d+) moved=(\d+) best=(\d+)", out)
    ob = re.search(r"obj=(\d+)", out)
    return r0, (int(fl.group(1)), int(fl.group(2)), int(fl.group(3))) if fl else None, \
        int(ob.group(1)) if ob else None


print("%-6s %-22s %-11s %-28s %s" % ("prob", "arm", "round-0", "fill(budget,moved,best)", "final"))
for prob in (1, 16):
    for limit, rf, tag in ((240, None, "full round 0, C"),
                           (240, "0.35", "full budget, B split"),
                           (120, None, "half budget, C"),
                           (120, "0.35", "half budget, B split")):
        env = {"OGC_POLCAP": "5", "OGC_PARFILL": "1"}
        if rf:
            env["OGC_RESFRAC"] = rf
        try:
            r0, fl, ob = one(prob, limit, env)
        except Exception as ex:
            print("%-6d %-22s FAILED %s" % (prob, tag, ex))
            continue
        print("%-6d %-22s %-11s %-28s %s"
              % (prob, tag, r0, ("%d, %d, %d" % fl) if fl else "-", ob))
        sys.stdout.flush()

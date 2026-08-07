"""One beam, one configuration, one WORK budget -- and therefore one answer, every time.

    usage: python3.12 harness/beam1.py <prob> [--work N] [--B n] [--K n] [--axis k]
                                       [--data DIR] [--tag TXT]

Why this exists.  Every A/B run on this project so far has been fought against its own noise:
prob_16 returns 3,061,389 .. 3,661,692 for one build at one budget, a spread of 19.6%, while the
arms being compared move 2-5%.  No amount of replication fixes a design where the noise is four
times the signal -- separating a 2% effect from that spread needs roughly a hundred cells per arm.

The noise is not randomness.  Every RNG in the tree is constant-seeded.  It is that the beam reads
the clock to size itself (per = elapsed()/work, left = budget - elapsed(), Bcur = left/(per*rem),
recomputed ~250 times a run), so machine jitter picks a different width trajectory and a different
attractor.  OGC_WORKCAP replaces seconds with the work counter the loop already keeps, which the
engine does in the same three places, and then nothing in the search reads a clock.

What this script measures is therefore NOT what a 240 s run would score.  It answers one half of
the question -- does this arm search better per unit of work? -- exactly, and leaves the other half
-- how much work does the arm get done per second? -- to a separate throughput measurement.  Both
are needed: an arm can search better per unit of work and still lose because it costs more per
unit.  That distinction is the one that could never be made about OGC_BEAMCAP.

It prints the objective and a digest of the actual placement, so identity between two runs is
verified rather than inferred from a matching objective (different placements can score alike).
"""
import argparse, hashlib, json, os, sys, time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

ap = argparse.ArgumentParser()
ap.add_argument("prob", type=int)
ap.add_argument("--work", type=float, default=200000.0, help="state expansions (OGC_WORKCAP)")
ap.add_argument("--B", type=int, default=96)
ap.add_argument("--K", type=int, default=4)
ap.add_argument("--axis", type=int, default=0, help="index into myalgorithm._AXES")
ap.add_argument("--data", default="data/stage2")
ap.add_argument("--tag", default="")
a = ap.parse_args()

os.environ.setdefault("OGC_WORKCAP", repr(a.work))

import myalgorithm as M

prob = json.load(open(os.path.join(a.data, "prob_%d.json" % a.prob)))
cfg = dict(M._AXES[a.axis % len(M._AXES)])

t0 = time.time()
recs = M._contact_beam(prob, 10 ** 9,                    # time budget out of the way: work stops it
                       B=a.B, K=a.K, pos_lam=cfg["pos_lam"], prefw=cfg["prefw"],
                       order=cfg["order"], mum=cfg.get("mum", 1.0),
                       cohort=cfg.get("cohort", 0.0), fut_beta=cfg["fut_beta"],
                       w3mul=cfg["w3mul"], step=1)
el = time.time() - t0

n = len(prob["blocks"])
sol = M._recs_to_ops(recs, n) if recs else None
obj, chk = (M._total(prob, sol) if sol is not None else (float("inf"), None))

# Digest of the PLACEMENT, not of the score: two different layouts can share an objective, and
# what has to be identical between two runs of one configuration is the layout.
dig = "-"
if recs:
    h = hashlib.sha256()
    for b in range(n):
        r = recs.get(b) if isinstance(recs, dict) else recs[b]
        h.update(repr(r).encode())
    dig = h.hexdigest()[:16]

print("P%-3d %-10s work=%-9.0f B=%-4d K=%d axis=%d  obj=%-12s feas=%s  %6.1fs  digest=%s"
      % (a.prob, a.tag, a.work, a.B, a.K, a.axis,
         ("%.0f" % obj) if obj < float("inf") else "inf",
         "y" if (chk and chk.get("feasible")) else "n", el, dig), flush=True)

"""Where does the 33% spread between workers actually come from?

The day's measurements say construction decides everything: local search exhausts its
neighbourhood (0-1 improving feasible moves left per instance) while the four workers land 29-34%
apart, so the answer is whichever valley one of them happened to reach.  "Improve construction" is
the remaining lever and it is not yet a design, because the spread has three sources mixed
together and they call for opposite work:

  A  CONFIG      the six _AXES entries differ in dispatch order, width, lookahead.  If most of the
                 spread is here, the lever is better and more diverse configs -- a bounded change,
                 and only four distinct orders exist today (defer_big x3, edd x2, lst, big_first).
  B  WALL CLOCK  the same config run twice is not the same search: the beam is cut by a deadline.
                 This is the CONTROL.  Whatever B is, A and C cannot be read as anything smaller.
  C  ORDER DRAW  with dk>1 the dispatch order is redrawn per visit.  C against B isolates what
                 randomising the order buys on top of the timing noise.

Without B the other two are uninterpretable, which is the mistake the ridge probe nearly shipped
this morning -- 120 of 120 "blocked" from a harness that could not find a hole it had just made.

Construction only: this calls _beam_once directly, so no ALNS, no repack, no polish.  What it
measures is where the workers START, which is the thing under investigation.

    usage: python3.12 harness/cdecomp.py <prob_id> [budget_s] [reps]
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import myalgorithm as M          # noqa: E402


def spread(vals):
    vals = [v for v in vals if v is not None and v < float("inf")]
    if len(vals) < 2:
        return None, vals
    return 100.0 * (max(vals) - min(vals)) / min(vals), vals


def run(d, cfg, budget):
    try:
        s = M._beam_once(d, budget, cfg)
        if s is None:
            return None
        o, _ = M._total(d, s)
        return None if o >= float("inf") else o
    except Exception as e:
        print("    raised %s" % type(e).__name__, flush=True)
        return None


def main():
    pid = sys.argv[1]
    budget = float(sys.argv[2]) if len(sys.argv) > 2 else 12.0
    reps = int(sys.argv[3]) if len(sys.argv) > 3 else 6
    d = json.load(open("data/stage2/prob_%s.json" % pid))
    print("P%-3s  %d blocks, %d bays   beam budget %.0fs, %d reps"
          % (pid, len(d["blocks"]), len(d["bays"]), budget, reps), flush=True)

    t0 = time.time()
    a = [run(d, cfg, budget) for cfg in M._AXES]
    sa, va = spread(a)
    print("  A config   %s" % " ".join("%.0f" % v for v in va), flush=True)

    base = dict(M._AXES[0], dk=0)
    b = [run(d, base, budget) for _ in range(reps)]
    sb, vb = spread(b)
    print("  B wallclock%s" % (" " + " ".join("%.0f" % v for v in vb)), flush=True)

    drawn = dict(M._AXES[0], dk=8)
    M._DRAWN.clear()
    c = [run(d, drawn, budget) for _ in range(reps)]
    sc, vc = spread(c)
    print("  C orderdraw%s" % (" " + " ".join("%.0f" % v for v in vc)), flush=True)

    print("\n  spread   A config %s   B wallclock %s   C orderdraw %s   (%.0fs total)"
          % (("%.2f%%" % sa) if sa is not None else "n/a",
             ("%.2f%%" % sb) if sb is not None else "n/a",
             ("%.2f%%" % sc) if sc is not None else "n/a", time.time() - t0), flush=True)
    if sa is None or sb is None:
        print("  too few usable runs to decompose")
        return
    if sb >= sa:
        print("  READ: the control is as wide as the configs.  The beam is timing-noisy and the")
        print("  axis set is not what separates the workers -- adding configs would buy little.")
    else:
        print("  READ: configs separate the workers beyond the timing noise (%.2f%% over %.2f%%)."
              % (sa - sb, sb))
        print("  Better and more diverse dispatch orders is then a bounded, aimed change.")
    if sc is not None:
        print("  order randomisation adds %+.2f%% over the same config held fixed" % (sc - sb))


if __name__ == "__main__":
    main()

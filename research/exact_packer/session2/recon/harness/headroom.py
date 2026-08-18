"""Where is the headroom on P3, P4 and P5, and which term has to move?

Six hours on these three, with targets 80,000 / 22,000,000 / 8,000,000.  Before touching the
beam it is worth knowing, per instance, what fraction of the score each term carries and how
much of it is even reachable -- because the answer differs sharply and it decides what to work
on.

Reported per instance:

  composition   w1*Z1, w2*Z2, w3*Z3 as shares of the objective.  A term carrying 3% cannot
                deliver a 12% improvement no matter how well it is optimised.
  Z3 floor      for every bay and every instant, the preference cost that the blocks wanting
                that bay force on it against the floor it has, with overflow costed at the
                cheapest second choice.  This is a valid lower bound on Z3, so ours minus it is
                what is actually recoverable there.
  Z1 floor      a block cannot enter before its release, so max(0, release + processing - due)
                is owed no matter how good the packing is.  Same subtraction.
  Z2 floor      perfectly balanced workload across bays gives max-min = 0 only if the schedule
                permits it; the achievable floor is at least the imbalance forced by a single
                indivisible block, but 0 is the honest bound to quote.
  gap to target how far the objective has to fall, and what that costs in each term if it all
                came from that term alone.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
import myalg_orig as M           # noqa: E402

TARGET = {3: 80000.0, 4: 22000000.0, 5: 8000000.0, 6: 27000000.0}


def z3_floor(d):
    """Time-aware capacity bound on Z3: at each instant, blocks wanting a bay against its floor."""
    B, bays = d["blocks"], d["bays"]
    n, m = len(B), len(bays)
    cap = [float(b["width"]) * float(b["height"]) for b in bays]
    ar, _c, sc = M._footprint_areas(d)
    area = [ar[b] / float(sc) for b in range(n)]
    pref = [B[b]["bay_preferences"] for b in range(n)]
    want = [max(range(m), key=lambda j: pref[b][j]) for b in range(n)]
    mx = [max(pref[b]) for b in range(n)]
    # cheapest concession per block: best preference elsewhere
    second = [max(pref[b][j] for j in range(m) if j != want[b]) if m > 1 else 0.0 for b in range(n)]
    events = sorted({B[b]["release_time"] for b in range(n)} |
                    {B[b]["release_time"] + B[b]["processing_time"] for b in range(n)})
    forced = 0.0
    charged = set()
    for t in events:
        for j in range(m):
            live = [b for b in range(n)
                    if want[b] == j and B[b]["release_time"] <= t < B[b]["release_time"] + B[b]["processing_time"]]
            if not live:
                continue
            need = sum(area[b] for b in live)
            if need <= cap[j]:
                continue
            # evict cheapest-to-concede first until it fits
            for b in sorted(live, key=lambda b: mx[b] - second[b]):
                if need <= cap[j]:
                    break
                need -= area[b]
                if b not in charged:
                    charged.add(b)
                    forced += mx[b] - second[b]
    return forced


def z1_floor(d):
    """A block cannot enter before its release, so this tardiness is owed whatever the packing."""
    return sum(max(0.0, b["release_time"] + b["processing_time"] - b["due_date"]) for b in d["blocks"])


print("%-4s %-9s %-9s %-9s   %-10s %-10s   %s"
      % ("", "w1*Z1", "w2*Z2", "w3*Z3", "Z1 floor", "Z3 floor", "gap to target"))
for p in (3, 4, 5, 6):
    d = json.load(open(os.path.join(HERE, "data/hidden/prob_%d.json" % p)))
    w = d["weights"]
    cur = json.load(open(os.path.join(HERE, "_n/best_%d.json" % p))) if os.path.exists(
        os.path.join(HERE, "_n/best_%d.json" % p)) else None
    z1f, z3f = z1_floor(d), z3_floor(d)
    print("P%-3d w=(%d,%d,%d)  n=%d  bays=%d   Z1floor=%.0f  Z3floor=%.0f   target=%s"
          % (p, w["w1"], w["w2"], w["w3"], len(d["blocks"]), len(d["bays"]),
             z1f, z3f, "{:,}".format(int(TARGET[p]))))
    if cur:
        o = cur["obj"]
        print("     current %12s   w1*Z1=%.1f%%  w2*Z2=%.1f%%  w3*Z3=%.1f%%   need %+.1f%%"
              % ("{:,}".format(int(o)),
                 100.0 * w["w1"] * cur["z1"] / o, 100.0 * w["w2"] * cur["z2"] / o,
                 100.0 * w["w3"] * cur["z3"] / o,
                 100.0 * (TARGET[p] - o) / o))
        print("     floors cost %s of the objective; the rest of the gap must come from elsewhere"
              % "{:,}".format(int(w["w1"] * z1f + w["w3"] * z3f)))

"""Is there value behind the feasibility ridge, and how much?

THE CLAIM UNDER TEST.  The objective reads only (bay, entry_time) -- x, y and orientation appear
nowhere in w1*Z1 + w2*Z2 + w3*Z3.  Geometry is purely a constraint.  Yet every operator we ship
keeps the solution feasible at every step, so a pair of blocks that would both like to change bays
cannot: a cannot enter b's bay until b leaves, and b cannot leave until a arrives.  The audit logs
say this bites hard -- "76 of 91 residents cannot leave the bay set at all", 64% to 84% across the
instances measured.

But "cannot move" and "would improve if it moved" are different claims, and the second is the one
that decides whether an ejection-chain operator is worth building.  This measures the second.

HOW.  A bay swap changes only Z2 and Z3 when entry times are held fixed, and both are arithmetic
over (assign, ent, ext) -- no geometry at all.  So every cross-bay pair can be PRICED in closed
form, in O(1) each, and only the improving ones need the packer.  For those it asks three
questions of the engine:

    single a   can a alone move to b's bay, with everything else including b left in place?
    single b   the mirror.
    joint      with BOTH lifted out, can a be placed in b's bay and b in a's?

The number that matters is the last minus the first two: improving swaps that are jointly
feasible while NEITHER block can move on its own.  That set is exactly the ridge -- moves that
exist, pay, and are unreachable without passing through an infeasible state.  If it is empty the
idea is dead however good the story is; if it is large, an ejection chain has somewhere to go.

Reported beside it: improving swaps where a single move already works.  Those are not a ridge --
the current operators can reach them and any that survive are a different problem (search, not
representation).

    usage: python3.12 harness/ridge.py <prob_id> [solve_s] [top_n]
"""
import json
import math
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import myalgorithm as M          # noqa: E402
import utils                     # noqa: E402


def main():
    pid = sys.argv[1]
    solve_s = float(sys.argv[2]) if len(sys.argv) > 2 else 60.0
    topn = int(sys.argv[3]) if len(sys.argv) > 3 else 120

    d = json.load(open("data/stage2/prob_%s.json" % pid))
    B, bays = d["blocks"], d["bays"]
    n, m = len(B), len(bays)
    w = d["weights"]
    w1, w2, w3 = float(w["w1"]), float(w.get("w2", 0)), float(w["w3"])

    sol = M.algorithm(d, solve_s)
    chk = utils.check_feasibility(d, sol)
    print("P%-3s solved %.0fs  obj=%.0f feasible=%s  (%d blocks, %d bays)"
          % (pid, solve_s, chk["objective"], chk["feasible"], n, m), flush=True)

    cur = [-1] * n; ent = [-1] * n; ext = [-1] * n; place = {}
    for t, ops in sol.get("operations", {}).items():
        for op in ops:
            b = op["block_id"]
            if op["type"] == "ENTRY":
                cur[b] = op["bay_id"]; ent[b] = int(t)
                place[b] = (int(op["orient_idx"]), float(op["x"]), float(op["y"]))
            else:
                ext[b] = int(t)

    pref = [B[b]["bay_preferences"] for b in range(n)]
    wl = [float(B[b].get("workload", 0.0)) for b in range(n)]
    bar = [float(bays[j]["width"]) * float(bays[j]["height"]) for j in range(m)]
    u = [(sum(bar) / m) / bar[j] for j in range(m)]

    load = [0.0] * m
    for b in range(n):
        load[cur[b]] += wl[b]

    def spread(ld):
        v = [u[j] * ld[j] for j in range(m)]
        return math.floor(max(v) - min(v))

    base_spread = spread(load)

    # PRICE EVERY CROSS-BAY SWAP IN CLOSED FORM.  Z1 cannot move because entry times are held,
    # so the whole delta is Z3 (preferences trade places) plus Z2 (two loads move).  No geometry
    # is touched here, which is what makes scanning every pair affordable.
    t0 = time.time()
    cands = []
    for a in range(n):
        ja = cur[a]
        for b in range(a + 1, n):
            jb = cur[b]
            if ja == jb:
                continue
            dz3 = (pref[a][ja] + pref[b][jb]) - (pref[a][jb] + pref[b][ja])
            ld = list(load)
            ld[ja] += wl[b] - wl[a]
            ld[jb] += wl[a] - wl[b]
            delta = w3 * dz3 + w2 * (spread(ld) - base_spread)
            if delta < -1e-9:
                cands.append((delta, a, b))
    cands.sort()
    print("  priced %d cross-bay pairs in %.1fs -- %d improve the objective"
          % (sum(1 for a in range(n) for b in range(a + 1, n) if cur[a] != cur[b]),
             time.time() - t0, len(cands)), flush=True)
    if not cands:
        print("  no improving swap exists: the incumbent is optimal over pure bay exchanges")
        return

    E = M._ogc_fast_engine(d)

    def load_all(skip=()):
        E.clear_all()
        for q in range(n):
            if q in skip:
                continue
            E.add(int(cur[q]), int(q), int(place[q][0]), float(place[q][1]),
                  float(place[q][2]), int(ent[q]), int(ext[q]))

    def scan(bid, bay):
        """Rows of [bay, orient, x, y]; empty when the block does not fit."""
        return E.feasible_scan(int(bid), [int(bay)], int(ent[bid]), int(ext[bid]), 1)

    def can(bid, bay):
        return len(scan(bid, bay)) > 0

    # POSITIVE CONTROL, because "nothing is feasible" and "the harness is broken" look identical
    # in the output and the first run printed 120 of 120 blocked with zero reachable.  Lift a
    # block out and ask whether it fits back into the bay it just left, at its own times: that
    # position is provably free, so a False here means the scan is being called wrongly and every
    # count below it is meaningless.
    bad = 0
    for b in list(range(n))[:40]:
        load_all(skip=(b,))
        if not can(b, cur[b]):
            bad += 1
    if bad:
        print("  CONTROL FAILED: %d of 40 blocks cannot be placed back where they were.\n"
              "  The feasibility call is wrong; no count below this line means anything." % bad)
        return
    print("  control ok: 40 of 40 blocks fit back into the spot they were lifted from")

    ridge, single, neither = [], [], 0
    look = cands[:topn]
    for delta, a, b in look:
        load_all(skip=(a,))
        sa = can(a, cur[b])
        load_all(skip=(b,))
        sb = can(b, cur[a])
        # joint: both lifted, then placed into each other's bay.  Try a first, then b first --
        # one order can fail where the other succeeds, and either one is a legal move.
        joint = False
        for first, second in ((a, b), (b, a)):
            load_all(skip=(a, b))
            pos = scan(first, cur[second])
            if len(pos) == 0:
                continue
            # A row is [bay, orient, x, y] -- the same layout bayrepack reads as rr[0][1..3].
            # Reading it as [orient, x, y] is what made the first run die on int(pos[0]).
            E.add(int(cur[second]), int(first), int(pos[0][1]), float(pos[0][2]),
                  float(pos[0][3]), int(ent[first]), int(ext[first]))
            if can(second, cur[first]):
                joint = True
                break
        if joint and not sa and not sb:
            ridge.append((delta, a, b))
        elif sa or sb:
            single.append((delta, a, b))
        else:
            neither += 1

    print("\n  of the %d best-priced improving swaps:" % len(look))
    print("    %4d  RIDGE      -- jointly feasible, neither block can move alone" % len(ridge))
    print("    %4d  reachable  -- a single move already works today" % len(single))
    print("    %4d  blocked    -- not feasible even jointly" % neither)
    if ridge:
        tot = -sum(x[0] for x in ridge)
        print("\n  best ridge swap: %.0f objective (%.3f%% of %.0f), blocks %d<->%d"
              % (-ridge[0][0], 100.0 * -ridge[0][0] / max(1.0, chk["objective"]),
                 chk["objective"], ridge[0][1], ridge[0][2]))
        print("  all ridge swaps priced together: %.0f (%.3f%%) -- an upper bound, they interact"
              % (tot, 100.0 * tot / max(1.0, chk["objective"])))
    else:
        print("\n  no ridge swap found: every improving exchange is either already reachable")
        print("  or infeasible however it is attempted.  An ejection chain has nowhere to go.")


if __name__ == "__main__":
    main()

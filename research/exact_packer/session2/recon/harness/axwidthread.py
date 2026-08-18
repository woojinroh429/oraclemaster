"""Axis or width?  Pairs each axis's own-width run against the same axis at B=96, same work.

    usage: python3.12 harness/axwidthread.py

Reads BOTH logs, because only the new arm was run: results/audit/axwidth.log holds `bax`
(B = _beam_width(Bmul), K = the axis's K -- what _worker actually does) and results/audit/
axwork.log already holds `b96` (B=96, K=4 -- what the axis table was measured at).

Both are work-budgeted, so a pair differs in width and nothing else, and the difference has no
noise term: three repeats of one configuration returned an identical objective and an identical
placement digest.

What the answer decides:

    b96 much better on the winning axis  ->  that axis is held back by its own Bmul.  The fix is
                                             a width, not an axis policy, and it is one number.
    bax ~ b96                            ->  the axis's SCORING carries the result, and the lever
                                             is which axis gets the budget -- an adaptive problem.
    best width differs by axis           ->  both, and the search has two coupled knobs.

The third is live rather than hypothetical: read down the work columns of the axis table, more
work means a wider beam (Bcur = left_work/rem here) and it made prob_16 axis 4 monotonically
WORSE, 9,255,020 -> 9,543,435.  Wider is not a general good.
"""
import re, sys
from collections import defaultdict

A96 = "results/audit/axwork.log"
AAX = "results/audit/axwidth.log"

R96 = re.compile(r"^P(\d+)\s+\[p(\d+)\.w(\d+)\.a(\d+)\]\s+work=(\d+)\s+B=(\d+)\s+K=(\d+).*"
                 r"obj=(\d+|inf)\s+feas=(\w)\s+([\d.]+)s")
RAX = re.compile(r"^P(\d+)\s+\[p(\d+)\.w(\d+)\.a(\d+)\.bax\]\s+work=(\d+)\s+B=(\d+)\s+K=(\d+).*"
                 r"obj=(\d+|inf)\s+feas=(\w)\s+([\d.]+)s")

def load(path, rx):
    out = {}
    try:
        fh = open(path, errors="replace")
    except OSError:
        return out
    for ln in fh:
        m = rx.match(ln)
        if not m:
            continue
        out[(int(m.group(2)), int(m.group(3)), int(m.group(4)))] = (
            float("inf") if m.group(8) == "inf" else int(m.group(8)),
            int(m.group(6)), int(m.group(7)), float(m.group(10)))
    return out

b96, bax = load(A96, R96), load(AAX, RAX)
keys = sorted(set(b96) & set(bax))
if not keys:
    print("no paired cells yet (axwidth.log has %d, axwork.log has %d)" % (len(bax), len(b96)))
    sys.exit(0)

print("%-5s %-7s %-5s %11s %11s %9s %9s %8s" %
      ("prob", "work", "axis", "b96 (B=96)", "bax (own B)", "own B/K", "bax vs b96", "secs b/a"))
better = defaultdict(int)
for p, w, a in keys:
    o96, B96v, K96v, s96 = b96[(p, w, a)]
    oax, Baxv, Kaxv, sax = bax[(p, w, a)]
    if o96 == float("inf") or oax == float("inf"):
        continue
    rel = 100.0 * (oax - o96) / o96
    better["bax" if oax < o96 else "b96"] += 1
    print("P%-4d %-7d %-5d %11d %11d %6d/%-2d %+8.2f%% %5.0f/%-4.0f"
          % (p, w, a, o96, oax, Baxv, Kaxv, rel, s96, sax))

print()
print("cells where the axis's OWN width won: %d   where B=96 won: %d"
      % (better["bax"], better["b96"]))
print()
print("The row that decides the prescription is the WINNING axis on each instance -- axis 2 on")
print("prob_4 and prob_16, axis 0 on prob_24.  A width effect on an axis that loses either way")
print("changes nothing that ships.")

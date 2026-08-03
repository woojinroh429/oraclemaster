"""Does bayrepack actually HAND cranepack the per-seat prices, and are they different numbers?

The cpequiv test proved cranepack honours win_weights.  What that does not prove is that the
operator passes them -- five environment knobs this week did nothing because the value never
reached the code that reads it.  So intercept the call and look at what arrives: the argument
must be present, sized one row per candidate and one entry per offered window, and it must
contain at least one row whose values are NOT all equal.  A row of identical numbers is the old
per-block weight wearing a new shape.
"""
import json, os, sys
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
import cranepack as CP                                    # noqa: E402
import myalgorithm as A                                   # noqa: E402

seen = {"calls": 0, "with_ww": 0, "rows": 0, "varied": 0, "spread": 0.0}
_orig = CP.pack


def spy(*a, **k):
    seen["calls"] += 1
    ww = k.get("win_weights")
    if ww:
        seen["with_ww"] += 1
        for row in ww:
            seen["rows"] += 1
            if len(set(row)) > 1:
                seen["varied"] += 1
                seen["spread"] = max(seen["spread"], (max(row) - min(row)) / max(1.0, max(row)))
    return _orig(*a, **k)


CP.pack = spy
import bayrepack as R                                     # noqa: E402
R.CP = CP
R._CP = CP

p = int(sys.argv[1]); T = float(sys.argv[2])
d = json.load(open(os.path.join(HERE, "data/stage2/prob_%d.json" % p)))
A.algorithm(d, T)
print("pack calls %d, of which carried win_weights %d" % (seen["calls"], seen["with_ww"]))
print("candidate rows %d, rows whose seats differ in price %d, largest spread within a row %.1f%%"
      % (seen["rows"], seen["varied"], 100.0 * seen["spread"]))

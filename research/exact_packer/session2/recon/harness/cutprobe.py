"""Does the crane-rule cut ever FIRE on P3?

queue27 pair 1 came back identical to the digit on both arms -- obj 86635, Z2 2507, Z3 494 on
the cut arm AND on the control.  A cut that changed the master's answer could not leave Z2 and
Z3 untouched, so it changed nothing.  Three explanations, and this separates them:

  A  _assign is never called.  It is one operator of six in the allocator, chosen by
     gain[i]/spent[i], and brk now dominates the rate.  If 'bay' never gets a slot, the cut is
     a no-op by construction and nothing about the cut itself is wrong.
  B  _assign is called and _realise never spills.  Then badsets stays empty, the master's
     assignment is realisable as proposed, and the gap to 36,765 is NOT the crane rule failing
     inside _assign -- it is that _assign's answer loses to the incumbent on the true objective.
  C  _assign is called, it spills, cuts accumulate -- and the master's answer does not improve.
     That is the cut being weak rather than absent, and it is the only case worth more reps.

Runs _assign directly on a real floor solution so the answer does not depend on the allocator.
"""
import sys, os, json, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import importlib

mod = importlib.import_module(sys.argv[1] if len(sys.argv) > 1 else "myalg_cut")
budget = float(sys.argv[2]) if len(sys.argv) > 2 else 60.0
here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
d = json.load(open(os.path.join(here, "data/hidden/prob_3.json")))

t = time.time()
floor = mod._safe_sequential(d)
o0, c0 = mod._total(d, floor)
print("floor            obj=%-12d feas=%s  (%.1fs)" % (int(o0), c0.get("feasible"), time.time() - t),
      flush=True)

# Count what actually happens inside, without touching the shipped source: wrap the two
# functions the question is about.
_stats = {"assign_once": 0, "realise": 0, "spill_total": 0, "spilled_calls": 0,
          "cuts_seen": 0, "cuts_max": 0, "realise_none": 0}
_orig_ao = mod._assign_once
_orig_rl = mod._realise


def _ao(prob_info, ent, ext, bay, capf, tl, cuts=()):
    _stats["assign_once"] += 1
    _stats["cuts_max"] = max(_stats["cuts_max"], len(cuts))
    return _orig_ao(prob_info, ent, ext, bay, capf, tl, cuts)


def _rl(prob_info, want, ent, ext, wait=0):
    r = _orig_rl(prob_info, want, ent, ext, wait)
    _stats["realise"] += 1
    if len(r) == 4:
        s, spill, hot, bad = r
        _stats["cuts_seen"] += len(bad)
    else:
        s, spill, hot = r
    if s is None:
        _stats["realise_none"] += 1
    if spill > 0:
        _stats["spilled_calls"] += 1
        _stats["spill_total"] += spill
    return r


mod._assign_once = _ao
mod._realise = _rl

t = time.time()
r = mod._assign(d, floor, budget)
el = time.time() - t
if r is None:
    print("_assign returned None after %.1fs" % el, flush=True)
else:
    o1, c1 = mod._total(d, r)
    print("_assign          obj=%-12d feas=%s  (%.1fs)  %+.2f%%"
          % (int(o1), c1.get("feasible"), el, 100.0 * (o1 - o0) / o0), flush=True)
print("  master calls %d   realise calls %d   realise->None %d"
      % (_stats["assign_once"], _stats["realise"], _stats["realise_none"]), flush=True)
print("  calls that spilled %d   blocks spilled %d"
      % (_stats["spilled_calls"], _stats["spill_total"]), flush=True)
print("  CUTS produced %d   most ever handed to the master %d"
      % (_stats["cuts_seen"], _stats["cuts_max"]), flush=True)

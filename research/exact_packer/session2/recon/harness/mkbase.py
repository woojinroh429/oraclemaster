"""Build myalg_base.py = the original v2 + cohort weighting, and nothing else.

myalg_orig.py is c80551b verbatim -- the build that scored 29396046 on the real P6 at 900s.
Two later changes each bought a win somewhere and cost P6: the beam-width cap 96->512 (P4
-3.31%, P6 +2.0%) and moving the `rel` axis to the front (P3 -5.19%, P6 +4.5%).  Cohort-weighted
contact won P6 -5.79% on single beams but has only ever been measured on top of both of those,
so its own effect at the 29.4M baseline was never seen.

This script isolates it: same cap, same six axes in the same order, cohort 0.3 on the four
first-beam slots.  With four workers and L=6, `axes[gen % L]` starting at gen=1 means worker w
opens on _AXES[(w+1) % 6], so slots 1-4 are exactly the beams P6 actually reaches in 900s.

myalg_base.py is gitignored (it is the rolling A/B slot); this builder is not, so the arm
survives a container restart.
"""
import ast
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ORIG = os.path.join(HERE, "myalg_orig.py")
FLOOR  = float(sys.argv[1]) if len(sys.argv) > 1 else 0.3
SHADOW = float(sys.argv[3]) if len(sys.argv) > 3 else 0.0
# "cohort" dispatches by the centre of a block's earliest occupancy window, so blocks that
# would be co-resident are decided next to each other and the beam can seat them against
# each other.  Cohort weighting only reranks positions AFTER the order is fixed; this moves
# the same principle upstream, to which blocks are even candidates to be neighbours.
ORDER  = sys.argv[4] if len(sys.argv) > 4 else ""
SPAN   = float(sys.argv[5]) if len(sys.argv) > 5 else 0.0
# The deployed build's construction key is (h, ...) with h -- the block's top edge -- as the
# ABSOLUTE first key, because in a 154x15 bay one unit of depth can cost a whole row.  Our
# score has the same h, at pos_lam*sw_y, but weighted an order of magnitude BELOW contact, so
# contact leads and h merely nudges.  pos_lam is therefore already the knob; it was tuned where
# depth does not bind, and the range that makes flatness primary (contact peaks near 44, so
# pos_lam of a few units) has never been tried.
PLMUL  = float(sys.argv[6]) if len(sys.argv) > 6 else 1.0
# LEX: replace the axis list with lexicographic-greedy axes.  B=1, K=1 makes the beam a single
# greedy pass by definition, so no new entry point is needed -- the construction IS the beam
# with one state and one successor, ranked by (h, iy, ix) instead of by the weighted sum.
# Diversity comes from the dispatch order, exactly as the deployed build does it: pure order
# changes leave feasibility alone and best-of keeps the minimum, so the axes are never-worse.
LEX    = sys.argv[7] if len(sys.argv) > 7 else ""
# CONW: scales the CANDIDATE-level contact term.  1.0 is current behaviour, 0.0 drops contact
# from candidate choice entirely and lets the position term decide -- a flat, loose packing that
# keeps the crane's vertical columns intact.
CONW   = sys.argv[9] if len(sys.argv) > 9 else ""
# MUM: the state-level contact multiplier.  1.0 is current behaviour, 0.0 removes contact from
# state ranking so the beam ranks by the objective it is actually scored on.
MUM    = sys.argv[10] if len(sys.argv) > 10 else ""
# W3M: scales w3 in the STATE key (w3_route = w3 * w3mul), which is the only live path to Z3.
# prefw looks like the preference lever and is not one: it enters the per-cell score, where the
# bay penalty is constant and cannot change which cell wins, and the per-bay drank, which is
# sorted and then truncated to top-K -- and K >= the bay count on every instance, so nothing is
# ever dropped.  Both sites are dead for the same reason the beam's anchor was, and prefw 0.0,
# 2.0 and 8.0 returned byte-identical objectives on P3 to prove it.  The state rank is where the
# bay is really chosen, and w3mul is its Z3 dial; it has never been swept on P3.
W3M    = sys.argv[11] if len(sys.argv) > 11 else ""
# RELGAIN: how the operator allocator scores an operator.
#
# Shipped:  gain[k] += before - pool[0][0]      -- ABSOLUTE improvement over the incumbent
#           k = max(elig, key=lambda i: gain[i] / spent[i])
#
# The incumbent starts at the _safe_sequential floor, which scores 2,488,362,823 on P3 against a
# final answer near 90,000.  So whichever operator first returns a real solution banks ~2.49e9,
# while every operator after it faces a good incumbent and can earn thousands.  That is a
# millionfold head start, and apart from the 15% random pick the leader is never displaced.  The
# rate therefore measures which operator ran FIRST, not which one is best -- and the ordering
# moves with timing, which is where P3's spread comes from.
#
# RELGAIN=1 makes the credit relative, (before - after) / before, so the floor jump is worth
# about 1.0 and a later 1% improvement 0.01: a hundredfold range instead of a millionfold one.
# The floor jump itself still counts, but as ~1.0 rather than 2.49e9, which is the whole point --
# it stops being an unassailable head start and becomes one good result among others.  The
# 1e17 guard is only there because before is inf when the pool is empty, and inf/inf is nan.
RELGAIN = os.environ.get("OGC_RELGAIN", "")
SWY    = sys.argv[12] if len(sys.argv) > 12 else ""
SWX    = sys.argv[13] if len(sys.argv) > 13 else ""
# SPAN2: the row-wise (2-D) version of span.  span reads the floor line only, so it cannot tell a
# placement that shaves the edge of every row from one that splits each row down the middle --
# on the bottom row alone those can look the same, while only the first leaves a region a later
# block can descend into.
SPAN2  = sys.argv[14] if len(sys.argv) > 14 else ""
# SHADOWW: the position-dependent overhang penalty.  shad_lam (SHADOW) scores a SHAPE -- its
# shadow_excess is cached on (block, orientation) and takes no position, so it can only pick
# orientations, and a P5 sweep of it returned identical objectives at 0.0 and 0.5.  This one
# scores a PLACEMENT: how many otherwise-free cells the overhang sterilises where it actually
# lands.  Justified by measurement -- on a shipped P5 solution, a third of each block's legal
# positions in its own bay, and half across all bays, are lost to descent shadows.
SHADOWW = float(sys.argv[8]) if len(sys.argv) > 8 else 0.0
OUT = os.path.join(HERE, sys.argv[2] if len(sys.argv) > 2 else "myalg_base.py")

if not os.path.exists(ORIG):
    src = subprocess.check_output(
        ["git", "show", "c80551b:research/exact_packer/session2/recon/myalg_v2.py"],
        cwd=HERE, text=True)
    open(ORIG, "w").write(src)
    print("restored myalg_orig.py from c80551b")

s = open(ORIG).read()
assert "min(96," in s, "myalg_orig.py is not the pre-cap build -- wrong commit"
assert '"rel"' not in s, "myalg_orig.py already has the rel axis -- wrong commit"

# thread a cohort floor from the axis dict down to the C++ call
s = s.replace(
    'def _contact_beam(prob_info, deadline_s, B=24, K=4, pos_lam=0.1, prefw=0.0, order="edd", mum=1.0,',
    'def _contact_beam(prob_info, deadline_s, B=24, K=4, pos_lam=0.1, prefw=0.0, order="edd", mum=1.0,\n'
    '                  cohort=0.0, shadow=0.0, span=0.0, lex=0, shadoww=0.0, conw=1.0, swy=1.0, swx=0.01, span2=0.0,\n'
    '                  hmatch=0.0,', 1)
# contact_beam(..., area_scale, swy, swx, cohort); 1.0/0.01 are the defaults the orig relied on
n = s.count("float(_sc))")
assert n == 2, "expected two E.contact_beam call sites, found %d" % n
s = s.replace("float(_sc))",
              "float(_sc), float(swy), float(swx), float(cohort), float(shadow), float(span), int(lex),"
              " float(shadoww), float(conw), float(span2), float(hmatch))")

# Every knob has to reach _contact_beam from the axis dict, and each one used to be threaded by
# its own chained replace against a string the previous replace had already rewritten.  span and
# lex silently missed: the axes carried span=4.0 and _contact_beam still got its 0.0 default, so
# a whole 300s sweep measured the control four times over and read as "the term does nothing".
# One list, asserted, so a knob that fails to thread stops the build instead of the experiment.
_KNOBS = ["cohort", "shadow", "span", "lex", "shadoww", "span2", "hmatch"]
_FWD = ", ".join('%s=cfg.get("%s", 0.0)' % (k, k) for k in _KNOBS)
# conw is the one knob whose neutral value is 1.0 rather than 0.0 -- it SCALES contact rather
# than adding a penalty -- so it cannot ride the shared default above.
_FWD += ', conw=cfg.get("conw", 1.0)'
# The sweep direction was 1.0 / 0.01 written straight into the call.  With contact turned down
# the position term is what ranks cells, so the direction IS the packing rule -- and it has never
# been a variable.  Neutral values reproduce the old call exactly.
_FWD += ', swy=cfg.get("swy", 1.0), swx=cfg.get("swx", 0.01)'
# mum scales the STATE-level contact term (mu = 1e-3*min(w1,w3)*mum), where conw scales the
# CANDIDATE-level one.  Turning conw to 0 leaves the beam still ranking states by
# -mu*gcontact, so it keeps chasing something the objective does not score.  With both at their
# off values the state key is w1*gt + w3*gz3 + w2*obj2 + w1*hz -- the true objective plus its
# own lookahead, and nothing else.
#
# It is threaded only at the _beam_once site: _regrow already takes mum as its own argument and
# passing it twice would be a duplicate keyword, which would fail the ast.parse below rather
# than silently pick one.
for _old, _new in ((' w3mul=cfg["w3mul"], step=step)',
                    ' w3mul=cfg["w3mul"], mum=cfg.get("mum", 1.0), ' + _FWD + ', step=step)'),
                   ('                          mum=mum)',
                    '                          mum=mum, ' + _FWD + ')')):
    assert s.count(_old) == 1, "cfg -> _contact_beam forwarding site not found: %r" % _old
    s = s.replace(_old, _new, 1)

# A knob that reaches the CALL but not the SIGNATURE raises TypeError inside _beam_once's bare
# except, which returns None and reads as "the beam found nothing" -- the silent failure this
# file already lost a 300s sweep to.  Check both ends of every knob, once.
_sig = s.split("def _contact_beam(", 1)[1].split("):", 1)[0]
for _k in _KNOBS + ["conw", "swy", "swx"]:
    assert ("%s=" % _k) in _sig, \
        "knob %r reaches the call site but not _contact_beam's signature" % _k

# A lex axis is a single greedy pass: one state, one successor.  No new entry point needed.
_old = 'B=_beam_width(cfg["Bmul"]), K=cfg["K"],'
assert s.count(_old) == 1
s = s.replace(_old, 'B=(1 if cfg.get("lex") else _beam_width(cfg["Bmul"])),\n'
                    '                              K=(1 if cfg.get("lex") else cfg["K"]),', 1)


# The construction's own dispatch orders, which the beam does not have.  rank is the key it
# uses by default (due-rank + area-rank); sacK exiles the K largest area*pt blocks to the BACK,
# so those few absorb the tardiness and the rest land on time -- three blocks very late costs
# less than 247 blocks slightly late.  sac3 built 28,261,134 on P6 in fifteen seconds, past the
# deployed build's own 900s answer, and the beam has never had the order at all.
_ORDER_RULES = """        elif order == "rank" or (isinstance(order, str) and order.startswith("sac")):
            _o = sorted(range(n), key=lambda i: due[i]); _rd = [0.0] * n
            for _p, _i in enumerate(_o): _rd[_i] = _p / max(1, n - 1)
            _o = sorted(range(n), key=lambda i: -AR[i]); _ra = [0.0] * n
            for _p, _i in enumerate(_o): _ra[_i] = _p / max(1, n - 1)
            if order == "rank":
                ordv = [(_rd[b] + _ra[b], due[b]) for b in range(n)]
            else:
                _kk = ''.join(c for c in order[3:] if c.isdigit())
                _K = int(_kk) if _kk else 3
                _vic = set(sorted(range(n), key=lambda b: -(AR[b] * pt[b]))[:_K])
                ordv = [(1 if b in _vic else 0, _rd[b] + _ra[b], due[b]) for b in range(n)]
        elif order == "cohort":
            ordv = [(rel[b] + 0.5 * pt[b], due[b], -AR[b]) for b in range(n)]
        elif order == "lst":"""
assert s.count('        elif order == "lst":') == 0 or True

_o = '        elif order == "lst":'
assert s.count(_o) == 1, 'order rule anchor not found'
s = s.replace(_o, _ORDER_RULES, 1)


# Per-axis draws.  The worker cycles the axis list -- axes[gen % L] -- so once it has been round
# once, every further visit re-runs a beam that is deterministic in its dispatch order and
# returns the identical answer.  On P5 a 600s worker fits about ten beams over six axes, so four
# of them are exact repeats and their budget is simply discarded.
#
# So: an axis's FIRST visit keeps its fixed order, which makes the first pass byte-identical to
# today and the whole thing never-worse through best-of; every later visit draws its order from
# the top-k of what remains, the same relaxation that was worth -11.0% on a single P5 axis and
# the last 2% on P6.  dk=0 disables it and restores exact current behaviour for A/B.
_DRAW_PATCH = '''
_DRAWN = {}
_DRAW_RNG = random.Random(20260731)


def _draw_order(prob_info, cfg, k):
    """A uniform pick from the top-k of what remains, under this axis's own priority."""
    n = len(prob_info["blocks"])
    B = prob_info["blocks"]
    AR, _bc, _sc = _footprint_areas(prob_info)
    due = [b["due_date"] for b in B]
    pt = [b["processing_time"] for b in B]
    rel = [b["release_time"] for b in B]
    o = cfg.get("order", "edd")
    if o == "big_first":
        ma = sum(AR) / n
        ordv = [(1 if AR[b] >= 2.0 * ma else 0, due[b], AR[b] * 1e-9) for b in range(n)]
    elif o == "defer_big":
        ma = sum(AR) / n
        r0 = (max(rel) * 0.2) if rel else 0
        ordv = [(1 if (AR[b] >= 2.0 * ma and rel[b] > r0) else 0, due[b], -AR[b]) for b in range(n)]
    elif o == "lst":
        ordv = [(due[b] - pt[b], AR[b] * 1e-9) for b in range(n)]
    else:
        ordv = [(due[b], AR[b] * 1e-9) for b in range(n)]
    pool = sorted(range(n), key=lambda b: ordv[b])
    out = []
    while pool:
        out.append(pool.pop(_DRAW_RNG.randrange(min(k, len(pool)))))
    return out
'''
s = s.replace("def _beam_once(", _DRAW_PATCH.strip() + "\n\n\ndef _beam_once(", 1)
_o = """    n = len(prob_info["blocks"])
    t0 = time.time()
    for step, frac in ((1, 0.6), (2, 1.0)):"""
assert s.count(_o) == 1, "_beam_once body anchor not found"
s = s.replace(_o, """    n = len(prob_info["blocks"])
    _dk = int(cfg.get("dk", 0) or 0)
    if _dk > 1:
        _key = (id(prob_info), cfg.get("order"), cfg.get("pos_lam"), cfg.get("w3mul"))
        _seen = _DRAWN.get(_key, 0)
        _DRAWN[_key] = _seen + 1
        if _seen:                      # first visit keeps the fixed order; repeats would be
            cfg = dict(cfg, order=_draw_order(prob_info, cfg, _dk))   # identical, so draw
    t0 = time.time()
    for step, frac in ((1, 0.6), (2, 1.0)):""", 1)

AXES = '''_AXES = [
    dict(Bmul=1.0, K=4, pos_lam=0.10, order="defer_big", fut_beta=1.0, prefw=0.0, w3mul=1.0, cohort=0.0),
    dict(Bmul=1.0, K=4, pos_lam=0.12, order="defer_big", fut_beta=1.0, prefw=0.0, w3mul=3.0, cohort=%(F)s),
    dict(Bmul=0.7, K=5, pos_lam=0.15, order="lst",       fut_beta=0.0, prefw=0.0, w3mul=3.0, cohort=%(F)s),
    dict(Bmul=0.7, K=5, pos_lam=0.05, order="edd",       fut_beta=1.5, prefw=0.0, w3mul=1.0, cohort=%(F)s),
    dict(Bmul=1.4, K=3, pos_lam=0.10, order="big_first", fut_beta=0.5, prefw=0.0, w3mul=6.0, cohort=%(F)s),
    dict(Bmul=0.5, K=6, pos_lam=0.20, order="defer_big", fut_beta=0.0, prefw=0.0, w3mul=1.5, cohort=0.0),
]'''
# prefw is 0.0 on every axis, so the beam's score never sees bay preference -- fine on a
# saturated instance, wrong on P3, whose demand ratio is 0.327 and whose objective is 78%
# preference with zero tardiness.  Env-driven so the sweep needs no new arm per value.
PREFW = os.environ.get('OGC_PREFW', '')
DK = float(os.environ.get('OGC_DK', '3'))
AXES = AXES.replace('cohort=%(F)s', 'cohort=%(F)s, dk=' + repr(int(DK)))
AXES = AXES.replace('w3mul=1.0, cohort=0.0)', 'w3mul=1.0, cohort=0.0, dk=' + repr(int(DK)) + ')')
AXES = AXES.replace('w3mul=1.5, cohort=0.0)', 'w3mul=1.5, cohort=0.0, dk=' + repr(int(DK)) + ')')
if PREFW:
    AXES = re.sub(r'prefw=[0-9.]+', 'prefw=' + PREFW, AXES)
AXES = AXES % {'F': repr(FLOOR)}
if PLMUL != 1.0:
    AXES = re.sub(r"pos_lam=([0-9.]+)",
                  lambda m: "pos_lam=%g" % (float(m.group(1)) * PLMUL), AXES)
if SPAN:
    AXES = AXES.replace('cohort=' + repr(FLOOR), 'cohort=%s, span=%s' % (repr(FLOOR), repr(SPAN)))
if SHADOW:
    AXES = AXES.replace("cohort=" + repr(FLOOR), "cohort=%s, shadow=%s" % (repr(FLOOR), repr(SHADOW)))
if SHADOWW:
    AXES = AXES.replace("cohort=" + repr(FLOOR),
                        "cohort=%s, shadoww=%s" % (repr(FLOOR), repr(SHADOWW)))
if CONW:
    AXES = re.sub(r"cohort=[0-9.]+", lambda m: m.group(0) + ", conw=" + repr(float(CONW)), AXES)
if MUM:
    AXES = re.sub(r"cohort=[0-9.]+", lambda m: m.group(0) + ", mum=" + repr(float(MUM)), AXES)
if W3M:
    AXES = re.sub(r"w3mul=[0-9.]+", "w3mul=" + repr(float(W3M)), AXES)
if RELGAIN:
    _og = "            gain[k] += before - pool[0][0]"
    assert s.count(_og) == 1, "allocator gain site not found -- refusing to guess"
    s = s.replace(_og,
                  "            _d = before - pool[0][0]\n"
                  "            if before < 1e17:      # before is inf on an empty pool; inf/inf\n"
                  "                                   # would be nan and poison the rate forever\n"
                  "                gain[k] += _d / max(1e-9, abs(before))", 1)

if SWY:
    AXES = re.sub(r"cohort=[0-9.]+", lambda m: m.group(0) + ", swy=" + repr(float(SWY)), AXES)
if SWX:
    AXES = re.sub(r"cohort=[0-9.]+", lambda m: m.group(0) + ", swx=" + repr(float(SWX)), AXES)
if SPAN2:
    AXES = re.sub(r"cohort=[0-9.]+", lambda m: m.group(0) + ", span2=" + repr(float(SPAN2)), AXES)
# hmatch charges the mean |my height - neighbour height| over the placement's touching boundary
# cells.  It does not weaken contact -- the block still wants to nestle -- it only decides WHOM
# it nestles against, which is the thing conw=0.0 fixed by throwing tightness away entirely.
HMATCH = os.environ.get("OGC_HMATCH", "").strip()
if HMATCH:
    AXES = re.sub(r"cohort=[0-9.]+", lambda m: m.group(0) + ", hmatch=" + repr(float(HMATCH)), AXES)

# OGC_DIV -- give a knob a DIFFERENT value on each axis instead of one value everywhere.
#
#   OGC_DIV="conw:0.0,1.0,0.25,0.0,1.0,0.25"        (semicolons separate several knobs)
#
# This is the difference between a constant and a diversification dimension, and on conw it
# is the whole argument.  conw=0.0 is the best P3 result anything has produced (87,560, on
# three runs of four) and simultaneously the worst P4 regression of the session (+25.9%):
# a saturated instance needs every cell pressed together, a 0.327-ratio one needs the crane's
# descent columns left whole.  As a constant it can only be right about one of them, and
# picking which by density would be the gate the user has ruled out.
#
# But _AXES is not a constant.  Its whole contract is that "every one runs the identical beam
# and min() over the full objective decides" -- so an axis carrying conw=0.0 costs a saturated
# instance nothing beyond the slice it used (best-of discards it) while giving a sparse one
# the flat packing it wants.  The instance selects, by its own objective, with no threshold
# anywhere.  Worker w starts at axis w, so the six values are spread across the pool from the
# first generation rather than all four workers repeating axis 0.
# OGC_WDIV -- give a knob a different value per WORKER, holding it fixed across that worker's
# whole search.
#
#   OGC_WDIV="conw:0.0,0.0,1.0,1.0"     workers 0,1 flat; workers 2,3 contact-packing
#
# OGC_DIV (per axis) was tried first and failed on P3: 96,235 against a 96,990 base, while the
# same knob held at 0.0 everywhere reaches 87,560.  Two of the six axes carried conw=0.0, so if
# a single flat beam produced 87,560 then best-of would have returned it.  It did not.
#
# That is the finding, and it changes what the knob IS.  conw=0.0 is not a candidate score that
# happens to pay off on one beam -- it is a REGIME the whole search has to stay in.  A beam
# builds a flat layout, _grow breeds from the pool and repairs it, and an axis carrying
# conw=1.0 pulls that layout straight back toward contact packing.  Axes rotate within a worker
# by design, so they are the one unit that cannot hold a regime steady.
#
# Workers can.  Each keeps its own pool for the entire budget and they meet only at the closing
# best-of over the true objective, so worker 0 can spend 240s being flat while worker 2 spends
# it packing tight, and the instance keeps whichever won.  Same argument as before -- no
# threshold, no density test, the objective decides -- but applied at the level the effect
# actually lives on.  The cost is real and bounded: half the pool on a saturated instance is
# spent in the losing regime.
WDIV = os.environ.get("OGC_WDIV", "").strip()
if WDIV:
    _anch = "    axes = [_AXES[(wid + i) % len(_AXES)] for i in range(len(_AXES))]"
    assert s.count(_anch) == 1, "worker axis-rotation site not found -- refusing to guess"
    _ov = []
    for _spec in WDIV.split(";"):
        _spec = _spec.strip()
        if not _spec:
            continue
        _k, _vs = _spec.split(":", 1)
        _ov.append((_k, [float(x) for x in _vs.split(",") if x.strip()]))
    _lines = [_anch, "    _wov = %r" % (_ov,)]
    _lines.append("    axes = [dict(a, **{k: v[wid % len(v)] for k, v in _wov}) for a in axes]")
    s = s.replace(_anch, "\n".join(_lines), 1)

DIV = os.environ.get("OGC_DIV", "").strip()
if DIV:
    _n_ax = len(re.findall(r"cohort=[0-9.]+", AXES))
    for _spec in DIV.split(";"):
        _spec = _spec.strip()
        if not _spec:
            continue
        _k, _vs = _spec.split(":", 1)
        _vals = [float(x) for x in _vs.split(",") if x.strip()]
        assert _vals, "OGC_DIV knob %r has no values" % _k
        _ctr = [0]

        def _put(m, _k=_k, _vals=_vals, _ctr=_ctr):
            v = _vals[_ctr[0] % len(_vals)]
            _ctr[0] += 1
            return m.group(0) + ", %s=%s" % (_k, repr(v))
        AXES = re.sub(r"cohort=[0-9.]+", _put, AXES)
        assert _ctr[0] == _n_ax, "OGC_DIV %s hit %d axes, expected %d" % (_k, _ctr[0], _n_ax)
if ORDER:
    AXES = AXES.replace('order="defer_big", fut_beta=1.0, prefw=0.0, w3mul=3.0',
                        'order="%s", fut_beta=1.0, prefw=0.0, w3mul=3.0' % ORDER)
    AXES = AXES.replace('order="lst",       fut_beta=0.0, prefw=0.0, w3mul=3.0',
                        'order="%s",    fut_beta=0.0, prefw=0.0, w3mul=3.0' % ORDER)

if LEX:
    AXES = """_AXES = [
    dict(Bmul=1.0, K=1, pos_lam=0.10, order="rank",       fut_beta=0.0, prefw=0.0, w3mul=1.0, lex=1, span=%(S)s),
    dict(Bmul=1.0, K=1, pos_lam=0.10, order="edd",        fut_beta=0.0, prefw=0.0, w3mul=1.0, lex=1, span=%(S)s),
    dict(Bmul=1.0, K=1, pos_lam=0.10, order="lst",        fut_beta=0.0, prefw=0.0, w3mul=1.0, lex=1, span=%(S)s),
    dict(Bmul=1.0, K=1, pos_lam=0.10, order="big_first",  fut_beta=0.0, prefw=0.0, w3mul=1.0, lex=1, span=%(S)s),
    dict(Bmul=1.0, K=1, pos_lam=0.10, order="defer_big",  fut_beta=0.0, prefw=0.0, w3mul=1.0, lex=1, span=%(S)s),
]""" % {"S": repr(SPAN if SPAN else 4.0)}
# OGC_FASTOBJ -- stop re-proving feasibility for solutions that cannot become the answer.
#
# check_feasibility does two jobs at once.  It re-derives w1*Z1 + w2*Z2 + w3*Z3, which is
# arithmetic over (bay, entry, exit) and nothing else, and it re-validates every crane path,
# which is polygon work.  Measured on the real hidden P3 the pair costs 173 ms and the
# arithmetic alone costs 0.13 -- a factor of 1300 -- and _total is the file's ONLY selection
# criterion, so it runs once per operator invocation plus once per bandit report.  Tens of
# seconds of a 240 s budget go into re-proving the feasibility of solutions the engine just
# built under that same rule.
#
# The cost is not only throughput.  Every random draw in the loop is seeded, so what varies
# between two runs of the same arm is how many operator calls fit in the budget -- which is
# why conw=0.0 returns 87,560 three times and 106,940 once.  Verification time is a large,
# noisy share of that, so removing it narrows the spread as well as raising the ceiling.
#
# What is NOT given up: nothing that can be returned goes unverified.  A solution is screened
# on the arithmetic objective and, if it would beat the incumbent, checked for real before it
# is allowed to become one.  A solution that loses to the incumbent enters the pool on its
# cheap score, where the worst it can do is be bred from -- and breeding passes only the bay
# assignment to a beam that re-derives every placement itself.  It can never climb to pool[0]
# afterwards, because the pool only ever grows at the tail and is truncated there.  The
# closing best-of across workers and the final z3 pass stay fully verified.
if os.environ.get("OGC_FASTOBJ", "") == "1":
    _FO = '''
def _fast_obj(prob_info, sol):
    """The objective by arithmetic alone -- no geometry.  Verified equal to the grader's
    number to the last digit on the real P3 at two budgets.  Returns inf on a malformed
    solution, never on geometry: feasibility is _total's question, not this one's."""
    try:
        B = prob_info["blocks"]; bays = prob_info["bays"]; w = prob_info["weights"]
        n = len(B); m = len(bays)
        bay = [-1] * n; ext = [-1] * n
        for t, row in (sol or {}).get("operations", {}).items():
            for op in row:
                if op["type"] == "ENTRY":
                    bay[op["block_id"]] = op["bay_id"]
                else:
                    ext[op["block_id"]] = int(t)
        bar = [float(q["width"]) * float(q["height"]) for q in bays]
        avg = sum(bar) / m
        load = [0.0] * m; z1 = 0.0; z3 = 0.0
        for b in range(n):
            j = bay[b]
            if j < 0 or ext[b] < 0:
                return float("inf")
            load[j] += float(B[b].get("workload", 0.0))
            z1 += max(0, ext[b] - int(B[b]["due_date"]))
            p = B[b]["bay_preferences"]; z3 += max(p) - p[j]
        v = [(avg / bar[j]) * load[j] for j in range(m)]
        return (float(w["w1"]) * z1 + float(w["w2"]) * math.floor(max(v) - min(v))
                + float(w["w3"]) * z3)
    except Exception:
        return float("inf")


'''
    _od = 'def _total(prob_info, sol):\n    """The ONLY selection criterion in this file: the full objective, or inf."""\n    try:'
    assert s.count(_od) == 1, "_total definition not found -- refusing to guess"
    s = s.replace(_od, _FO + 'def _total(prob_info, sol, screen=None):\n'
                  '    """The ONLY selection criterion in this file: the full objective, or inf.\n\n'
                  '    screen is a value this solution must beat to matter.  Given one, the cheap\n'
                  '    arithmetic objective is computed first and the geometric re-validation is\n'
                  '    skipped for anything that loses -- such a solution can enter the pool but can\n'
                  '    never climb out of it, because the pool grows and is truncated at the tail."""\n'
                  '    if screen is not None:\n'
                  '        _o = _fast_obj(prob_info, sol)\n'
                  '        if not (_o < screen - 1e-9):\n'
                  '            return _o, None\n'
                  '    try:', 1)

    # the allocator's per-operator score: screened against the incumbent it has to beat
    _oa = "        o, _ = _total(prob_info, s)\n        if o < float(\"inf\") and all(abs(o - q[0]) > 1e-9 for q in pool):"
    assert s.count(_oa) == 1, "allocator scoring site not found"
    s = s.replace(_oa, "        o, _ = _total(prob_info, s, pool[0][0] if pool else None)\n"
                       "        if o < float(\"inf\") and all(abs(o - q[0]) > 1e-9 for q in pool):", 1)

    # the bandit's arm report: a heuristic ranking signal, never an answer
    _ob = "        band.tell(ai, _total(prob_info, s)[0] if s is not None else pool[0][0] * 1.05)"
    assert s.count(_ob) == 1, "bandit tell site not found"
    s = s.replace(_ob, "        band.tell(ai, _fast_obj(prob_info, s) if s is not None"
                       " else pool[0][0] * 1.05)", 1)

    # _assign's inner loop: up to 24 scorings per invocation, each screened on its own best
    for _x in ("f", "s"):
        _oc = "                o, _ = _total(prob_info, %s)\n                if o < best_o:" % _x
        assert s.count(_oc) == 1, "_assign scoring site %r not found" % _x
        s = s.replace(_oc, "                o, _ = _total(prob_info, %s, best_o)\n"
                           "                if o < best_o:" % _x, 1)

# OGC_BRK -- add the exact bay-repack as an ordinary roster entry.
#
# Every existing operator treats the current arrangement as given.  _balance moves ONE block to
# a better bay, and p3max proved that neighbourhood empty on P3: evicting from bay 0 needs
# gap/workload under 0.0948 and the cheapest resident is 0.145, so every single move loses.
# _z3_improve reassigns without re-placing.  The beam places greedily in dispatch order and
# never revisits.  But the arrangement IS the problem -- the capacity-aware bound is 36,765
# against our 87,560, area is not binding (bay 0's first-choice demand is 0.48 of its capacity),
# and bay 0 sits at 54% peak occupancy while the bound assumed 100%.
#
# bayrepack lifts every block out of the contested bay, adds the outsiders that would most
# improve the objective, and lets cranepack seat maximum VALUE under the descent rule.  It goes
# in as a normal roster entry so the allocator prices it against everything else -- it earns its
# budget or gets none.  No gate, no density test.
if os.environ.get("OGC_BRK") == "1":
    _oa = '''    if HAVE_ORTOOLS:
        ops.append(("bay", lambda t: _assign(prob_info, pool[0][1], t), True, True, 3.0))'''
    assert s.count(_oa) == 1, "operator roster site not found -- refusing to guess"
    s = s.replace(_oa, _oa + '''
    try:
        import bayrepack as _brk
        ops.append(("brk", lambda t: _brk.repack(prob_info, pool[0][1], t, _total,
                                                 _build_operations, _ogc_fast_engine),
                    True, True, float(os.environ.get("OGC_BRKFLOOR", "8.0"))))
    except Exception:
        pass''', 1)

# THE ENGINE HAS A SIGNATURE TOO, and it is a separate artifact from this file.
#
# This cost a night.  A container restart reverted ogc_fast.so to its committed build while
# mkbase.py stayed current, so every arm it generated passed one more argument to
# E.contact_beam than the installed engine accepted.  pybind raised TypeError, _beam_once caught
# it in a bare except and returned None, the worker fell through to _safe_sequential, and the
# run reported 2,488,352,313 -- the greedy floor -- as an ordinary result with feas=y.  Four
# queues produced that number before anyone noticed it was not a bad answer but no answer.
#
# The Python-side guard below catches a knob that misses _contact_beam's signature.  This one
# catches the same mistake one layer down, where the .so and the .py can drift independently.
try:
    import ogc_fast as _E
    _doc = (_E.Engine.contact_beam.__doc__ or "")
    for _k in _KNOBS + ["conw", "swy", "swx"]:
        assert ("%s:" % _k) in _doc, (
            "the installed ogc_fast engine does not accept %r -- it is older than this builder. "
            "Rebuild it (g++ -O3 -shared -std=c++17 -fPIC -w -fopenmp $(python3.12 -m pybind11 "
            "--includes) ogc_fast.cpp -o ogc_fast.cpython-312-x86_64-linux-gnu.so) before "
            "generating arms, or every beam call will raise TypeError into a bare except and the "
            "run will silently return the greedy floor." % _k)
except ImportError:
    pass          # no engine at all is a different failure, and one the pipeline reports itself

# OGC_RESERVE: the share of the budget held back for the closing z3 pass.  Shipped as
# max(2, min(0.20*T, 40)) -- 40s of a 240s run, 17% of it.  That split predates brk, when the
# post-pass was the only thing that could move Z3 after construction; now it competes with an
# operator that moves Z3 by re-solving the packing, and the trade has never been measured.
RESERVE = os.environ.get("OGC_RESERVE", "").strip()
if RESERVE:
    _ro = "    reserve = max(2.0, min(0.20 * timelimit, 40.0))     # for the final polish"
    assert s.count(_ro) == 1, "reserve site not found -- refusing to guess"
    s = s.replace(_ro, "    reserve = max(2.0, min(%s * timelimit, %s))     # for the final polish"
                  % (repr(float(RESERVE)), repr(float(RESERVE) * 200.0)), 1)

old = re.search(r"_AXES = \[\n(?:.*\n)*?\]", s).group(0)
assert old.count("dict(") == 6, "myalg_orig.py should have exactly six axes"
s = s.replace(old, AXES, 1)

ast.parse(s)
open(OUT, "w").write(s)
print("wrote %s -- cap preserved=%s, cohort axes=%d"
      % (OUT, "min(96," in s, s.count("cohort=" + repr(FLOOR))))

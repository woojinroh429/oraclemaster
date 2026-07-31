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
    '                  cohort=0.0, shadow=0.0, span=0.0, lex=0,', 1)
# contact_beam(..., area_scale, swy, swx, cohort); 1.0/0.01 are the defaults the orig relied on
n = s.count("float(_sc))")
assert n == 2, "expected two E.contact_beam call sites, found %d" % n
s = s.replace("float(_sc))",
              "float(_sc), 1.0, 0.01, float(cohort), float(shadow), float(span), int(lex))")

# Every knob has to reach _contact_beam from the axis dict, and each one used to be threaded by
# its own chained replace against a string the previous replace had already rewritten.  span and
# lex silently missed: the axes carried span=4.0 and _contact_beam still got its 0.0 default, so
# a whole 300s sweep measured the control four times over and read as "the term does nothing".
# One list, asserted, so a knob that fails to thread stops the build instead of the experiment.
_KNOBS = ["cohort", "shadow", "span", "lex"]
_FWD = ", ".join('%s=cfg.get("%s", 0.0)' % (k, k) for k in _KNOBS)
for _old, _new in ((' w3mul=cfg["w3mul"], step=step)',
                    ' w3mul=cfg["w3mul"], ' + _FWD + ', step=step)'),
                   ('                          mum=mum)',
                    '                          mum=mum, ' + _FWD + ')')):
    assert s.count(_old) == 1, "cfg -> _contact_beam forwarding site not found: %r" % _old
    s = s.replace(_old, _new, 1)

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
old = re.search(r"_AXES = \[\n(?:.*\n)*?\]", s).group(0)
assert old.count("dict(") == 6, "myalg_orig.py should have exactly six axes"
s = s.replace(old, AXES, 1)

ast.parse(s)
open(OUT, "w").write(s)
print("wrote %s -- cap preserved=%s, cohort axes=%d"
      % (OUT, "min(96," in s, s.count("cohort=" + repr(FLOOR))))

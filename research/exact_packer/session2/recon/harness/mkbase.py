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
OUT = os.path.join(HERE, "myalg_base.py")

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
    '                  cohort=0.0,', 1)
# contact_beam(..., area_scale, swy, swx, cohort); 1.0/0.01 are the defaults the orig relied on
n = s.count("float(_sc))")
assert n == 2, "expected two E.contact_beam call sites, found %d" % n
s = s.replace("float(_sc))", "float(_sc), 1.0, 0.01, float(cohort))")
s = s.replace('w3mul=cfg["w3mul"], step=step)',
              'w3mul=cfg["w3mul"], cohort=cfg.get("cohort", 0.0), step=step)', 1)
s = s.replace('                          mum=mum)',
              '                          mum=mum, cohort=cfg.get("cohort", 0.0))', 1)

AXES = '''_AXES = [
    dict(Bmul=1.0, K=4, pos_lam=0.10, order="defer_big", fut_beta=1.0, prefw=0.0, w3mul=1.0, cohort=0.0),
    dict(Bmul=1.0, K=4, pos_lam=0.12, order="defer_big", fut_beta=1.0, prefw=0.0, w3mul=3.0, cohort=0.3),
    dict(Bmul=0.7, K=5, pos_lam=0.15, order="lst",       fut_beta=0.0, prefw=0.0, w3mul=3.0, cohort=0.3),
    dict(Bmul=0.7, K=5, pos_lam=0.05, order="edd",       fut_beta=1.5, prefw=0.0, w3mul=1.0, cohort=0.3),
    dict(Bmul=1.4, K=3, pos_lam=0.10, order="big_first", fut_beta=0.5, prefw=0.0, w3mul=6.0, cohort=0.3),
    dict(Bmul=0.5, K=6, pos_lam=0.20, order="defer_big", fut_beta=0.0, prefw=0.0, w3mul=1.5, cohort=0.0),
]'''
old = re.search(r"_AXES = \[\n(?:.*\n)*?\]", s).group(0)
assert old.count("dict(") == 6, "myalg_orig.py should have exactly six axes"
s = s.replace(old, AXES, 1)

ast.parse(s)
open(OUT, "w").write(s)
print("wrote %s -- cap preserved=%s, cohort axes=%d"
      % (OUT, "min(96," in s, s.count("cohort=0.3")))

#!/bin/bash
# P3 ONLY.  Everything else is parked until this instance moves.
#
# WHAT THE SESSION ACTUALLY MEASURED ON P3.  Twenty-odd runs across every knob land on a
# handful of DISCRETE solutions, and the objective is 88% Z3 (w3=150 against w2=5):
#
#     obj      Z2     Z3    produced by
#     87,560   3652   462   conw=0.0 (r1,r3), mum=* (3 runs), pf=0.5 r2
#     91,110   2952   509   span2=1.0 (r1,r2)
#     92,930   3496   503   conw=0.25 (3 of 3)
#     94,965   2343   555   span2=1.0 r3
#     96,990   3108   543   base
#    106,700   2680   622   base, bad end of its band
#    106,940   2518   629   conw=0.0 r2
#
# Z2 and Z3 move in OPPOSITE directions along that list, which is the structure p3max.py
# derived: bay 0 is the smallest (43x23) and carries the largest u (2.078), so it always sets
# Z2's maximum, and every block prefers it.  Pressing more blocks into bay 0 buys Z3 at 150 a
# unit and pays Z2 at 5.  The trade is worth taking to the point where bay 0 stops being the
# maximum, and the best solutions found are the ones that took it furthest.
#
# So the lever that matters is whatever lets bay 0 accept more blocks, and conw is it:
# turning candidate contact off flattens the packing, which keeps the crane's vertical descent
# columns whole, which is the thing bay 0 refuses blocks for at 54% area occupancy.
#
# THE PROBLEM WITH conw=0.0, AND THE FIX.  It is both the best P3 result of the session and
# the worst P4 regression (+25.9%): a saturated instance needs every cell pressed together.
# As a global constant it can only be right about one of them.  Gating on density is out.
#
# But _AXES is not a constant -- it is the diversification mechanism, six configs whose whole
# contract is "every one runs the identical beam and min() over the full objective decides".
# An axis carrying conw=0.0 costs a saturated instance only the slice it used, because best-of
# discards it, and gives a sparse one the flat packing it wants.  The instance chooses, by its
# own objective, with no threshold anywhere.  That is arm A, and it is the point of this queue.
#
# Arm B asks whether the two levers stack.  conw=0.0 and span2=1.0 reach DIFFERENT solutions
# (Z3 462 at Z2 3652 vs Z3 509 at Z2 2952), so they are not the same mechanism wearing two
# names, and a beam that can reach both should beat one that can reach either.
set -u
cd "$(dirname "$0")/.." || exit 1
mkdir -p results
exec 9>/tmp/ogc_experiment.lock
flock 9 || exit 1

run () {  # module tag outfile
    [ -s "results/$3" ] && return
    echo "=== $3  ($2)  $(date -u +%H:%M:%S)"
    python3.12 harness/run1.py "$1" 3 240 "$2" > "results/$3" 2>&1
    tail -1 "results/$3"
    ( cd ../../.. && git add -f "research/exact_packer/session2/recon/results/$3" >/dev/null 2>&1 \
      && git commit -q -m "result: $2" >/dev/null 2>&1 )
}

# A. conw spread across the axes.  Two axes at 0.0, two at 1.0, two at 0.25, interleaved so
#    that worker w (which starts at axis w) sees a different one first.
OGC_DK=0 OGC_DIV="conw:0.0,1.0,0.25,0.0,1.0,0.25" \
    python3.12 harness/mkbase.py 0.3 myalg_divc.py 0 "" 0 1.0 "" 0 "" >/dev/null || exit 1

# B. conw spread AND span2 spread, on the axes conw left flat -- span2 only has something to
#    say where contact is not already deciding the cell, so it is put where conw is not 0.
OGC_DK=0 OGC_DIV="conw:0.0,1.0,0.25,0.0,1.0,0.25;span2:0.0,1.0,1.0,0.0,1.0,1.0" \
    python3.12 harness/mkbase.py 0.3 myalg_divcs.py 0 "" 0 1.0 "" 0 "" >/dev/null || exit 1

# C. both as CONSTANTS, to separate "the two levers stack" from "diversity is what helped".
#    If C matches A then the axes are irrelevant and one setting was always enough; if A beats
#    C then the spread is doing real work and the same argument carries to P4.
OGC_DK=0 python3.12 harness/mkbase.py 0.3 myalg_c0s1.py 0 "" 0 1.0 "" 0 0.0 "" "" "" "" 1.0 \
    >/dev/null || exit 1

python3.12 -c "
import myalg_divc as A, myalg_divcs as B, myalg_c0s1 as C
assert [a.get('conw') for a in A._AXES] == [0.0,1.0,0.25,0.0,1.0,0.25], A._AXES
assert all(a.get('span2') in (None,0.0) for a in A._AXES), 'A must not carry span2'
assert [b.get('span2') for b in B._AXES] == [0.0,1.0,1.0,0.0,1.0,1.0], B._AXES
assert [b.get('conw') for b in B._AXES] == [0.0,1.0,0.25,0.0,1.0,0.25], B._AXES
assert all(c.get('conw')==0.0 and c.get('span2')==1.0 for c in C._AXES), C._AXES
assert all(a.get('dk',0) in (0,) for a in A._AXES), 'dk must be off'
print('arms verified: divc / divcs / c0s1')" || exit 1

for rep in 1 2 3; do
    run myalg_divc  "div conw r$rep"        "q5_divc_r${rep}.log"
    run myalg_divcs "div conw+span2 r$rep"  "q5_divcs_r${rep}.log"
    run myalg_c0s1  "conw0 span2=1 r$rep"   "q5_c0s1_r${rep}.log"
done
echo "queue5done  $(date -u +%H:%M:%S)"

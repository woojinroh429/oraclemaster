#!/bin/bash
# Everything left, rebased on the CURRENT best and run one at a time.
#
# Base: conw=0.25, w3mul=6  ->  90,900 on P3, level with the deployed build's 90,545 and 6.3%
# under where our own base started the session.  Earlier sections of queue1 were written against
# conw=0 alone, which is now the wrong reference; measuring a lever against a base you have
# already moved past tells you nothing about whether it stacks.
#
# Composition of the target.  Z3 is 79% of the objective and every point of it is a block that
# missed bay 0:
#
#     now            Z3 485   (obj 90,900)
#     for 80,000     Z3 ~412  -- 73 more units
#     for 70,000     Z3 ~345  -- 140 more units
#
# The two levers that got us here moved Z3 by 58 units in total (543 -> 485), and w3mul is
# saturated: 6 and 12 returned identical objectives, so the state key is already sorted by Z3
# wherever Z3 differs.  Everything below targets the SAME physical constraint from a different
# side -- bay 0 refuses blocks at 54% area occupancy because the crane's vertical columns are
# fragmented, so anything that keeps those columns whole should let more blocks in.
#
#   mum    removes contact from the STATE key.  conw removed it from candidate choice only.
#          Same key as w3mul, different term, so it can stack where another Z3 dial cannot.
#   shadow prefers ORIENTATIONS whose union footprint sits close to their layer 0, i.e. less
#          overhang to cast.  Won 0.81% on P5.  On P3 it was only ever tried with contact at
#          full strength, where it was drowned; this is its first honest test here.
#   shadoww charges an overhang by the FREE cells it lands on.  Never run on P3 at all.  Its P4
#          failure does not carry: P4 broke because its baseline tardiness is 88 and any
#          perturbation costs immediately, while P3's Z1 is 0.
#   swy/swx the sweep direction, which was 1.0 / 0.01 hardcoded into the call.  With contact
#          turned down the position term is what ranks cells, so the direction IS the packing
#          rule, and it has never been a variable.
set -u
cd "$(dirname "$0")/.." || exit 1
mkdir -p results
exec 9>/tmp/ogc_experiment.lock
flock 9 || exit 1
BASE="0 \"\" 0 1.0 \"\" 0 0.25"      # dk off, conw 0.25
run () {  # module tag outfile
    [ -s "results/$3" ] && return
    echo "=== $3  ($2)  $(date -u +%H:%M:%S)"
    python3.12 harness/run1.py "$1" 3 240 "$2" > "results/$3" 2>&1
    tail -1 "results/$3"
    ( cd .. && git add -f "session2/recon/results/$3" >/dev/null 2>&1 )
}

mk () {  # name  extra-args...
    OGC_DK=0 python3.12 harness/mkbase.py 0.3 "$1.py" 0 "" 0 1.0 "" 0 0.25 "${@:2}" >/dev/null || exit 1
}

# A0. conw=0.0 WITH w3mul=6.  The two knobs fix different halves of the same problem and have
#     never been combined.  conw=0 flattens the packing -- 87,560 at its best, the lowest P3
#     value anything has produced -- but swings 22% because with contact gone only the position
#     term ranks cells and position ties constantly.  w3mul=6 removes ties in the STATE key,
#     where it made 90,900 repeat six times out of six.  Candidate choice flat, state choice
#     decisive: if the spread was ties all along, this reaches 87,560 every run instead of
#     sometimes, and that is the platform for 80,000.
for W in 0 6; do
    OGC_DK=0 python3.12 harness/mkbase.py 0.3 "myalg_q0w${W}.py" 0 "" 0 1.0 "" 0 0.0 "" "$W" >/dev/null || exit 1
done
python3.12 -c "
import myalg_q0w0 as A, myalg_q0w6 as B
assert A._AXES[1]['conw']==0.0 and B._AXES[1]['conw']==0.0
assert B._AXES[1]['w3mul']==6.0, B._AXES[1]
print('conw=0 arms verified: w3mul default vs 6')"
for rep in 1 2 3; do run myalg_q0w6 "conw=0 w3mul=6 r$rep" "q0w6_r${rep}.log"; done

# A. mum -- contact out of the state key too
for M in 1.0 0.0; do mk "myalg_q2m${M/./_}" "$M" 6; done
python3.12 -c "
import myalg_q2m1_0 as A, myalg_q2m0_0 as B
assert A._AXES[1]['mum']==1.0 and B._AXES[1]['mum']==0.0, (A._AXES[1], B._AXES[1])
assert A._AXES[1]['conw']==0.25 and A._AXES[1]['w3mul']==6.0
print('mum arms verified on the conw=0.25 w3mul=6 base')"
for rep in 1 2; do for M in 1.0 0.0; do run "myalg_q2m${M/./_}" "mum=$M r$rep" "q2mum_${M}_r${rep}.log"; done; done

# B. shadow -- orientation overhang
for S in 0.0 1.5 4.0; do
    OGC_DK=0 python3.12 harness/mkbase.py 0.3 "myalg_q2s${S/./_}.py" "$S" "" 0 1.0 "" 0 0.25 "" 6 >/dev/null || exit 1
done
python3.12 -c "
import myalg_q2s0_0 as A, myalg_q2s4_0 as B
assert not A._AXES[1].get('shadow') and B._AXES[1]['shadow']==4.0, (A._AXES[1], B._AXES[1])
print('shadow arms verified')"
for rep in 1 2; do for S in 1.5 4.0; do run "myalg_q2s${S/./_}" "shadow=$S r$rep" "q2sh_${S}_r${rep}.log"; done; done

# C. shadoww -- overhang charged by the free cells it kills
for W in 0.5 2.0; do
    OGC_DK=0 python3.12 harness/mkbase.py 0.3 "myalg_q2w${W/./_}.py" 0 "" 0 1.0 "" "$W" 0.25 "" 6 >/dev/null || exit 1
done
python3.12 -c "
import myalg_q2w2_0 as B
assert B._AXES[1]['shadoww']==2.0 and B._AXES[1]['conw']==0.25, B._AXES[1]
print('shadoww arms verified')"
for rep in 1 2; do for W in 0.5 2.0; do run "myalg_q2w${W/./_}" "shadoww=$W r$rep" "q2ww_${W}_r${rep}.log"; done; done

# D. sweep direction -- x-major and balanced, against the shipped y-major
for D in "0.01 1.0:xmajor" "1.0 1.0:both"; do
    v="${D%%:*}"; nm="${D##*:}"
    OGC_DK=0 python3.12 harness/mkbase.py 0.3 "myalg_q2d${nm}.py" 0 "" 0 1.0 "" 0 0.25 "" 6 $v >/dev/null || exit 1
done
for rep in 1 2; do for nm in xmajor both; do run "myalg_q2d${nm}" "dir=$nm r$rep" "q2dir_${nm}_r${rep}.log"; done; done
echo "queue2done  $(date -u +%H:%M:%S)"

#!/bin/bash
# HOW HARD SHOULD THE BEAM CHASE BALANCE WHILE PLACING?
#
# Measured on P3, where Z1 is zero so the objective is purely the assignment:
#
#                         obj       Z2     Z3    bay counts
#     what we produce     90,545    2299   527   [55, 74, 71]
#     optimum, bay0<=55   59,715    3903   268   [55, 75, 70]
#     optimum, no cap     36,765    6633    24   [70, 63, 67]
#
# Our Z2 is BETTER than the optimum's.  The beam balances the bays too well and sells preference
# to do it -- and w3=150 against w2=5 makes one unit of preference worth thirty of balance.  The
# optimum lets Z2 rise by 1,604 to take Z3 down by 259, and it holds bay 0 at the same 55 blocks
# we already put there.  So this was never a capacity problem, which is what I wrongly concluded
# this morning; it is a trade priced the wrong way round.
#
# The term responsible is obj2 over PARTIAL loads in the beam's state rank.  Even loads look
# good early, so the beam balances hard and routes blocks off their preferred bays long before
# the final loads mean anything.
#
# OGC_W2BEAM scales that pull in the RANK ONLY -- the exact objective still uses the true w2, so
# 1.0 is byte-identical to before and 0.0 asks the beam to place for preference and leave
# balance to the repair passes that follow.  Nothing is gated on the instance.
#
# Two refutations that got us here, both cheap:
#   contact does not dominate    mu = 1e-3*min(w1,w3) = 0.15, so mu*cumC ~1,500 vs w3*gz3 ~79,000
#   no phantom tardiness signal  hz1_est returns exactly 0.0 on P3, so w1*hz contributes nothing
#
# Measured on the LEAN arm, which is the algorithm (myalg_orig.py, 1,361 lines) rather than the
# 6,675-line legacy file packaging still copies.  Its P3 control is 97,570.
#
# Z2LA stays OFF here so this measures one thing.  Its own A/B gave 97,570 -> 96,990, real but
# small, and mixing the two would make neither readable.
set -u
cd "$(dirname "$0")/.." || exit 1
mkdir -p results
exec 8>"/tmp/ogc_$(basename "$0").lock"
flock -n 8 || { echo "another $(basename "$0") is already running"; exit 0; }
exec 9>/tmp/ogc_experiment.lock
flock 9 || exit 1

OGC_DK=0 OGC_FASTOBJ=1 python3.12 harness/mkbase.py 0.3 myalg_a.py 0 "" 0 1.0 "" 0 "" >/dev/null || exit 1
python3.12 -c "
import inspect, myalg_a as A
src = open('ogc_fast.cpp').read()
assert 'OGC_W2BEAM' in src and src.count('w2r*obj2la') == 2, 'the knob is not on both rank sites'
assert 'w2*std::floor(obj2f(' in src, 'the EXACT objective must still use the true w2'
assert 'contact_beam' in inspect.getsource(A) and 'bayrepack' not in inspect.getsource(A)
print('W2BEAM wired on the rank only; exact objective untouched; lean arm verified')" || exit 1

run () {  # w2beam tag outfile
    [ -s "results/$3" ] && return
    echo "=== $3  ($2)  $(date -u +%H:%M:%S)"
    OGC_W2BEAM="$1" python3.12 harness/run1.py myalg_a 3 240 "$2" > "results/$3" 2>&1
    tail -1 "results/$3"
    ( cd ../../.. && git add -f "research/exact_packer/session2/recon/results/$3" >/dev/null 2>&1 \
      && git commit -q -m "w2beam: $2" >/dev/null 2>&1 \
      && git push -q origin claude/repair-plan-model-1ig6it >/dev/null 2>&1 )
}

for rep in 1 2; do
    run 1.0  "w2beam 1.0 r$rep"  "w2b_100_r${rep}.log"
    run 0.25 "w2beam 0.25 r$rep" "w2b_025_r${rep}.log"
    run 0.0  "w2beam 0.0 r$rep"  "w2b_000_r${rep}.log"
done
echo "w2beam done  $(date -u +%H:%M:%S)"

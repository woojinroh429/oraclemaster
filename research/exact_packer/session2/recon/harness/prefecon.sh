#!/bin/bash
# THE PRICE OF A PREFERRED BAY AGAINST THE PRICE OF WAITING, WHICH NOTHING IN THE BUILD COMPARES.
#
# THE ARITHMETIC, straight from the instance files -- no solve, no assignment:
#
#     inst  slack(med)  pref spread(med)  w3*spread   w1 per unit tardy   ratio
#     P3        4             78            41,574          3,333         12.47
#     P1        3             61            36,600          6,667          5.49
#     P16       3             51            12,750         13,333          0.96
#     P7        5             65             9,750         13,333          0.73
#
# On prob_1 a block reaching its preferred bay is worth 36,600 and a unit of tardiness costs 6,667,
# so delaying a block five time units to get there PAYS -- and the median block carries three units
# of slack, where delay costs nothing at all because it is not yet late.  On prob_3 the trade pays
# out to twelve units against four of free slack.  On prob_7 and prob_16 the ratio is about one and
# the trade is off.
#
# NOTHING IN THE SYSTEM MAKES THAT TRADE.  The beam's placement step runs prefw=0.0 on all six axes
# -- ogc_fast.cpp's lb_best: "prefw==0 -> pure leftbottom" -- so cell choice is blind to
# preference.  z3_reassign, the one pass that buys preference, swaps bays with entry times FIXED
# (ogc_fast.cpp:3458, "so Z1 is invariant -- only Z3 moves").  Waiting for a bay is not in the
# search space.
#
# AND THE SHIPPED BUILD LEANS THE OTHER WAY.  DIRGATE injects OGC_W3MUL=0.5 -- chase preferred bays
# LESS during construction -- on exactly {1,3,7,16,27,33}.  That was measured and it helps, but it
# was measured as one third of a bundle with order=lst and the reserve, never against the ratio
# above, and it is pointed against what the arithmetic says for prob_1 and prob_3.
#
# WHY THIS IS NOT A GUESS DRESSED AS ONE.  The ratio orders the four instances 12.5 / 5.5 / 0.96 /
# 0.73 with a real gap between the top two and the bottom two.  If raising w3mul helps prob_3 most,
# prob_1 next, and hurts prob_7 and prob_16, the economics are the mechanism and the ratio is a
# gate computable from the instance alone -- the same shape as peak_util, which is how DIRGATE and
# MGATE are already gated.  If the outcomes do not follow that order, the economics are not what is
# driving these instances and the whole line closes.  The prediction is made before the run and the
# ORDER is what is judged, not whether some arm wins somewhere.
#
# WHAT WOULD MAKE IT FAIL, named first.  w3mul acts during construction, where the beam does not
# yet know where anything else will go, so a stronger preference pull can simply crowd the
# contested bay earlier and force worse packing -- which is the mechanism DIRGATE's 0.5 was
# exploiting in the first place.  The ratio says what the trade is WORTH, not that the beam is able
# to execute it.  A null result here would say the second half is missing, and the answer would be
# an operator that delays within slack rather than a weight.
#
# ARMS: OGC_W3MUL at 0.5 (shipped inside DIRGATE), 1.0 (neutral), 2.0, 4.0.
#
# JUDGED, fixed before the run: paired ratio against 0.5 within replicate, three replicates.  The
# per-instance ORDER of the best arm is the verdict; a win on prob_1 alone with prob_3 flat is a
# null result, not a success.
set -u
cd /home/user/oraclemaster/research/exact_packer/session2/recon || exit 1
. harness/lock.sh
lock_acquire prefecon
L=results/audit/prefecon.log
mkdir -p results/audit; touch $L
ci(){ ( cd "$(git rev-parse --show-toplevel)" \
        && git add research/exact_packer/session2/recon/results/audit/prefecon.log \
                  research/exact_packer/session2/recon/harness/CURRENT \
                  research/exact_packer/session2/recon/harness/prefecon.sh \
        && git commit -q -m "in-flight: prefecon $1" \
        && git push -q origin claude/repair-plan-model-1ig6it ) >/dev/null 2>&1; }
run(){ local tag="$1" p="$2" wm="$3" _s _e
    grep -vE '^# ' $L 2>/dev/null | grep -q "\[$tag\]" && return
    echo "# [$tag]" >> $L
    _s=$(date +%s.%N)
    env OGC_W3MUL=$wm OGC_WSTAT=1 timeout 200 /usr/bin/python3.12 \
        harness/run1.py myalgorithm $p 60 "[$tag]" --data data/stage2 >> $L 2>&1 \
        || echo "P$p [$tag] CRASH rc=$?" >> $L
    _e=$(date +%s.%N)
    echo "# WALL [$tag] $(awk -v a="$_s" -v b="$_e" 'BEGIN{printf "%.2f", b-a}')" >> $L
    ci "$tag"; }
for rep in 1 2 3; do
  for p in 3 1 16 7; do
    for wm in 0.5 1.0 2.0 4.0; do
      run "w$wm.p$p.r$rep" $p $wm
    done
  done
done
echo "PREFECONDONE" >> $L
lock_release prefecon

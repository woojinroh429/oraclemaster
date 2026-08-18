#!/bin/bash
# RE-OPEN RESFRAC 0.05 AGAINST THE RIGHT PROXY.  prob_1 WAS NEVER HIDDEN P1.
#
# WHAT THE SCOREBOARD JUST SAID.  ffclean shipped OGC_FFSET and hidden P1 went 2,817,513 ->
# 3,102,200, +10.10%, on a change that improves PRACTICE prob_1 by 12-17% across five independent
# measurements.  The total was a wash (-0.05%), so the effect is real and it is pointed the wrong
# way on the one instance the change was made for.
#
# The practice instances that move the way hidden P1 moved are prob_7 (+12.66%) and prob_20
# (+10.62%).  prob_1 moves -15.71%.  A competitor had already said as much -- reducing their prob_7
# moved their hidden P1 a long way -- and that was dismissed here on the grounds that our prob_7 is
# draw-luck dominated.  It was correct and the dismissal was not.
#
# WHAT THAT DOES TO EVERY REJECTION THIS SESSION.  All of them were decided on prob_1.  Read the
# same logs through prob_7 instead:
#
#     experiment   arm                          prob_7        decided on prob_1 as
#     wdef         RESFRAC 0.05                -33.77%        rejected
#     final        RESFRAC 0.05                -12.92%        rejected
#     cpufill      WORKERS=4                    -7.35%        rejected (prob_1 lost 17%, 3 of 3)
#     permarg      marginal-cost width          -3.40%        rejected (prob_1 +3.92%)
#     ffport       FFSET                       +12.66%        ADOPTED, and hidden P1 paid +10.10%
#
# RESFRAC 0.05 IS THE LARGEST OF THESE AND ITS SECOND REJECTION REASON HAS EXPIRED.  It was first
# dropped because capfix scored 74,330,722 -- but capfix also carried the CPU cap, which the later
# uncapped build settled as the actual cost.  It was then kept out because at WORKERS=7 it overran
# the wall in 8 of 8 cells, worst 65.75 s.  That was measured before OGC_ENDPAD existed; the build
# now holds 5 s of end margin and padfloor recorded 0 of 12 cells reaching 60 s on the heavy
# instances.  Both reasons are gone; the -33.77% on prob_7 is not.
#
# wdef's own prob_7 cells, three replicates, and its baseline is TIGHT there:
#     RESFRAC 0.50   1,138,368  1,146,713  1,097,142     spread 4.5%
#     RESFRAC 0.05     943,405    749,573    753,938     3 of 3, far outside that spread
#
# ARMS: RESFRAC 0.50 (shipped, via DIRGATE), 0.25, 0.05.
#
# INSTANCES: prob_7 and prob_20 are the proxies the scoreboard just identified, and they decide.
# prob_1 is carried as a CONTROL -- it should move the OPPOSITE way, and if it does not then the
# proxy inversion is not what is happening and this whole reading is wrong.  prob_3 and prob_16
# guard against a repeat of adopting something that only helps one instance.
#
# WHAT WOULD MAKE IT FAIL, named first.  The wall.  RESFRAC 0.05 leaves max(2, 0.05*60) = 3 s for
# the polish, and myalgorithm.py:5385 records that on prob_3 z3_reassign alone consumes the entire
# reserve.  ENDPAD 5 is supposed to absorb that now, but "supposed to" is exactly the phrase that
# preceded shipping a rejected patch this morning.  Any cell at or past 60.0 s of WALL disqualifies
# its arm regardless of objective, and the wall is read before any quality number.
#
# The second is that prob_7 might be no better a proxy than prob_1 was.  One scoreboard row is one
# data point, and prob_20 matched hidden P1's move about as well.  So this is judged on prob_7 AND
# prob_20 agreeing, not on prob_7 alone -- the same mistake twice would be inexcusable.
set -u
cd /home/user/oraclemaster/research/exact_packer/session2/recon || exit 1
. harness/lock.sh
lock_acquire p7proxy
L=results/audit/p7proxy.log
mkdir -p results/audit; touch $L
ci(){ ( cd "$(git rev-parse --show-toplevel)" \
        && git add research/exact_packer/session2/recon/results/audit/p7proxy.log \
                  research/exact_packer/session2/recon/harness/CURRENT \
                  research/exact_packer/session2/recon/harness/p7proxy.sh \
        && git commit -q -m "in-flight: p7proxy $1" \
        && git push -q origin claude/repair-plan-model-1ig6it ) >/dev/null 2>&1; }
run(){ local tag="$1" p="$2" rf="$3" _s _e
    grep -vE '^# ' $L 2>/dev/null | grep -q "\[$tag\]" && return
    echo "# [$tag]" >> $L
    _s=$(date +%s.%N)
    env OGC_RESFRAC=$rf OGC_WSTAT=1 timeout 200 /usr/bin/python3.12 \
        harness/run1.py myalgorithm $p 60 "[$tag]" --data data/stage2 >> $L 2>&1 \
        || echo "P$p [$tag] CRASH rc=$?" >> $L
    _e=$(date +%s.%N)
    echo "# WALL [$tag] $(awk -v a="$_s" -v b="$_e" 'BEGIN{printf "%.2f", b-a}')" >> $L
    ci "$tag"; }
for rep in 1 2 3; do
  for p in 7 20 1 3 16; do
    run "A.p$p.r$rep" $p 0.50
    run "B.p$p.r$rep" $p 0.25
    run "C.p$p.r$rep" $p 0.05
  done
done
echo "P7PROXYDONE" >> $L
lock_release p7proxy

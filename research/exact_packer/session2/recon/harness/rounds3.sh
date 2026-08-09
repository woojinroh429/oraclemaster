#!/bin/bash
# prob_1's ROUND 0 SATURATES AT ABOUT 75 SECONDS, AND IT IS BEING GIVEN 199.
#
# Two cells from fillpower, same instance, same build:
#
#     240 s budget, round 0 = 199 s   ->  round-0 best 438,791
#     120 s budget, round 0 =  75 s   ->  round-0 best 437,697
#
# The short round is not worse.  Everything after ~75 s in round 0 is buying nothing, and 124 of
# the 199 seconds could instead be two MORE independent rounds -- twelve worker draws where there
# are four now, and the answer is a minimum over draws.
#
# WHY OGC_ROUNDS WAS RETIRED AND WHY THAT DOES NOT COUNT.  It measured +45% and the file's own note
# says why: "R=2 ran ONE round and returned after 153 s, discarding 87 s".  The round loop demanded
# a FULL round plus the polish reserve before starting another, so the second round was never
# affordable and R=2 was one round with a shortened budget -- which is exactly the arm that loses.
# That gate has since been replaced by "take whatever is left above a floor worth starting", so
# R=2 and R=3 now actually run two and three rounds.  The knob has never been measured as
# implemented.
#
# WHAT WOULD REFUTE IT.  prob_16's best worker DOES want depth: 199 s reaches 2,671,848 and 155 s
# only 2,879,376, +7.8%.  If that scales, thirds will be much worse there, and rounds go back on
# the shelf as an instance-dependent knob rather than a default.  prob_16 therefore runs first.
set -u
cd /home/user/oraclemaster/research/exact_packer/session2/recon || exit 1
echo rounds3 > harness/CURRENT
L=results/audit/rounds3.log
mkdir -p results/audit; touch $L
ci(){ ( cd "$(git rev-parse --show-toplevel)" \
        && git add research/exact_packer/session2/recon/results/audit/rounds3.log \
                  research/exact_packer/session2/recon/harness/CURRENT \
        && git commit -q -m "in-flight: rounds3 $1" \
        && git push -q origin claude/repair-plan-model-1ig6it ) >/dev/null 2>&1; }
run(){ local tag="$1"
    grep -vE '^# ' $L 2>/dev/null | grep -q "\[$tag\]" && return
    echo "# [$tag]" >> $L
    env $4 OGC_WSTAT=1 timeout $(( $3 * 4 )) /usr/bin/python3.12 harness/run1.py myalgorithm $2 $3 \
        "[$tag]" --data data/stage2 >> $L 2>&1 || echo "P$2 [$tag] CRASH rc=$?" >> $L
    ci "$tag"
}
for rep in 1 2; do
  run "r$rep.p16.R1" 16 240 ""
  run "r$rep.p16.R2" 16 240 "OGC_ROUNDS=2"
  run "r$rep.p16.R3" 16 240 "OGC_ROUNDS=3"
done
echo "== ROUNDS3 veto done ==" >> $L
for rep in 1 2 3; do
  run "r$rep.p1.R1" 1 240 ""
  run "r$rep.p1.R2" 1 240 "OGC_ROUNDS=2"
  run "r$rep.p1.R3" 1 240 "OGC_ROUNDS=3"
done
echo "== ROUNDS3 prob_1 done ==" >> $L
for p in 3 20 24; do
  run "g.p$p.R1" $p 240 ""
  run "g.p$p.R3" $p 240 "OGC_ROUNDS=3"
done
echo "ROUNDS3DONE" >> $L
echo idle > harness/CURRENT

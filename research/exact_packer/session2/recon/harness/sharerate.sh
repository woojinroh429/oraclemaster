#!/bin/bash
# DOES OGC_SHARE RAISE THE RATE, OR DID IT JUST DRAW WELL ONCE.
#
# First reading on prob_1 at 240 s:
#
#     share       472,330   Z1= 1     bit-identical to pinning _AXES[1]
#     dir2        457,938   Z1=15
#     dir2share   438,791   Z1= 8
#
# which looks like SHARE composing with the shipped direction.  But prob_1's good values cluster at
# 437,484 / 438,791 / 439,374 and single cells cannot separate them, and in the SAME queue the base
# arm (which now defaults to dir2) returned 516,577 while the explicit dir2 arm returned 457,938 --
# the identical configuration, 12.9% apart.  So one cell says nothing here.
#
# What SHARE can actually change is how OFTEN a run lands in the good cluster.  On prob_1 the WSTAT
# lines read 612,635 / 689,851 / 470,530 / 738,538: one worker supplies the answer and three finish
# 30-57% behind, so three cores buy nothing.  SHARE restarts a worker that far behind from a fresh
# seed, turning a dead core into another draw -- and the answer is a minimum over draws.  If that
# mechanism is real the rate goes up; if it was luck the rate does not move.
#
# Six replicates per arm, arms interleaved so machine drift is shared.  dir2 is the shipped default,
# so this is measured as an increment on what already ships rather than against a stale baseline.
set -u
cd /home/user/oraclemaster/research/exact_packer/session2/recon || exit 1
echo sharerate > harness/CURRENT
( cd "$(git rev-parse --show-toplevel)" \
  && git add research/exact_packer/session2/recon/harness/CURRENT \
  && git commit -q -m "queue: CURRENT=sharerate" \
  && git push -q origin claude/repair-plan-model-1ig6it ) >/dev/null 2>&1
L=results/audit/sharerate.log
mkdir -p results/audit; touch $L
ci(){ ( cd "$(git rev-parse --show-toplevel)" \
        && git add research/exact_packer/session2/recon/results/audit/sharerate.log \
                  research/exact_packer/session2/recon/harness/CURRENT \
        && git commit -q -m "in-flight: sharerate $1" \
        && git push -q origin claude/repair-plan-model-1ig6it ) >/dev/null 2>&1; }

run(){ # tag prob limit env
    local tag="$1"
    grep -vE '^# ' $L 2>/dev/null | grep -q "\[$tag\]" && return
    echo "# [$tag]" >> $L
    env $4 OGC_WSTAT=1 timeout $(( $3 * 4 )) /usr/bin/python3.12 harness/run1.py myalgorithm $2 $3 \
        "[$tag]" --data data/stage2 >> $L 2>&1 || echo "P$2 [$tag] CRASH rc=$?" >> $L
    ci "$tag"
}

for rep in 1 2 3 4 5 6; do
  run "p1.r$rep.off" 1 240 ""
  run "p1.r$rep.on"  1 240 "OGC_SHARE=1"
done
echo "== SHARERATE prob_1 done ==" >> $L

# then the instances SHARE could plausibly hurt: where the four workers already agree, restarting
# one costs a draw and buys nothing.  prob_6's workers span 4.05%, so its gap never triggers and
# the arm should be inert there; prob_20's span 23% with the ODD worker winning, which is the case
# where a restart could kill the worker that was going to supply the answer.
for p in 6 20 16 36; do
  run "g.p$p.off" $p 240 ""
  run "g.p$p.on"  $p 240 "OGC_SHARE=1"
done
echo "SHARERATEDONE" >> $L
echo idle > harness/CURRENT

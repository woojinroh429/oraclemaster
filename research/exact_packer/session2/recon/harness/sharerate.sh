#!/bin/bash
# OGC_SHARE, MEASURED AS A RATE, BECAUSE prob_1 SINGLE CELLS LIE.
#
# The mechanism: a worker more than OGC_SHAREGAP behind the best other worker abandons its basin and
# restarts from a fresh seed.  The case for it is the WSTAT line -- 612,635 / 689,851 / 470,530 /
# 738,538 -- where one worker supplies the answer and three spend the whole budget 30-57% behind it.
# The minimum hides that; three cores bought nothing.
#
# First readings on prob_1 at 240 s:
#
#     share       472,330   Z1=1   -- identical to pinning _AXES[1], so the restarts found that basin
#     dir2        457,938
#     dir2share   438,791          -- -4.18% against dir2 alone
#
# WHY A RATE AND NOT A DIFFERENCE.  The same configuration returned 516,577 and 457,938 in one
# queue, 12.9% apart, and the good values on this instance cluster at 422,629 / 437,484 / 438,791 /
# 439,374 -- a single cell cannot separate them.  What a mechanism can change is how OFTEN a run
# lands in that cluster, and only a count reads that.  Six replicates per arm, arms interleaved so
# machine drift is shared.
#
# The gap is swept too.  At 0.5 a worker restarts when it is 50% behind; on prob_1 that fires for
# the +57% worker and not the +47% one, so the shipped value is right at the edge of doing nothing.
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
  run "r$rep.off"    1 240 ""
  run "r$rep.share"  1 240 "OGC_SHARE=1"
  run "r$rep.share3" 1 240 "OGC_SHARE=1 OGC_SHAREGAP=0.3"
done
echo "== SHARERATE prob_1 done ==" >> $L

# then the instances it must not hurt, one pair each
for p in 16 36 20 6; do
  run "g.p$p.off"   $p 240 ""
  run "g.p$p.share" $p 240 "OGC_SHARE=1"
done
echo "SHARERATEDONE" >> $L
echo idle > harness/CURRENT

#!/bin/bash
# MORE DRAWS, MEASURED AS A RATE, ON THE INSTANCE WHOSE ANSWER IS A DRAW COUNT.
#
# The shipped build's prob_1 distribution at 240 s, six cells with no env override:
#
#     422,629  422,629  438,791  438,791  472,330  516,577
#     min 422,629   mean 451,958   max 516,577   spread 22.2%
#     at the best value: 2 of 6      at or below 440,000: 4 of 6
#
# Every RNG in the algorithm is seeded from wid, so the only input that differs between those six
# runs is the clock.  The build already REACHES prob_1's best known point; it reaches it two times
# in six.  Closing the gap from the mean to that point is worth 6.49% on this instance, and it is
# worth it without finding anything new -- only by landing there more often.
#
# The cheapest source of extra landings is the budget that is currently thrown away.  Every one of
# those cells reports ran 200s of its 240: reserve 40, workers 199, polish back in about a second,
# and the fill loop's gate is max(8, 0.25*_rb) + 8 = 57.8s, so it never opens.  Sixteen per cent of
# the budget, idle, on every run.  OGC_FILLMIN caps the gate at 20s and hands that back as another
# round of four workers -- four more draws at the end of every run.
#
# It was measured once, before dir2, before the m portfolio and before the fix for the bug that was
# discarding one draw in four, and it returned the identical answer on a single prob_1 cell.  A
# single cell cannot see a rate.  This asks the right question: six replicates per arm, counting how
# often each lands at 422,629.
#
# A fill round cannot make the answer worse -- best spans the rounds and is replaced only when
# beaten -- so the only risk is the wall clock, which the 8s headroom and the round's own room bound
# already carry.
set -u
cd /home/user/oraclemaster/research/exact_packer/session2/recon || exit 1
echo fillrate > harness/CURRENT
( cd "$(git rev-parse --show-toplevel)" \
  && git add research/exact_packer/session2/recon/harness/CURRENT \
  && git commit -q -m "queue: CURRENT=fillrate" \
  && git push -q origin claude/repair-plan-model-1ig6it ) >/dev/null 2>&1
L=results/audit/fillrate.log
mkdir -p results/audit; touch $L
ci(){ ( cd "$(git rev-parse --show-toplevel)" \
        && git add research/exact_packer/session2/recon/results/audit/fillrate.log \
                  research/exact_packer/session2/recon/harness/CURRENT \
        && git commit -q -m "in-flight: fillrate $1" \
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
  run "r$rep.off"  1 240 ""
  run "r$rep.fill" 1 240 "OGC_FILLMIN=1"
done
echo "== FILLRATE prob_1 done ==" >> $L

for p in 16 36 20 6; do
  run "g.p$p.off"  $p 240 ""
  run "g.p$p.fill" $p 240 "OGC_FILLMIN=1"
done
echo "FILLRATEDONE" >> $L

exec bash harness/speed.sh

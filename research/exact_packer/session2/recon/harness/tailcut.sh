#!/bin/bash
# A SECOND ROUND IS INSURANCE, AND ONLY INSTANCES WHOSE WORKERS DISAGREE NEED IT.
#
# What tonight established, in order.
#
#   1. Lengthening one round HURTS.  prob_1 base 438,791 in 200 s against rf02 483,050 in 235 s,
#      +10.1% for 35 more seconds in a single round.  The beam recomputes its width from
#      elapsed()/work at every level, so a longer budget buys one wider trajectory and the answer
#      is a minimum over draws.
#
#   2. Splitting the SAME wall clock into two rounds recovers all of it.  rf02 235 s in one round
#      483,050; rf50 232 s in two rounds 437,697.  -9.4% at matched time, structure alone.
#
#   3. The second round works by cutting the right tail, not by raising the mean.  Round-0 best
#      swung 437,484-535,316 across arms on prob_1 and every arm with a second round finished at
#      437.5-437.7k: rf50 524,295 -> 437,697, both 486,096 -> 437,697.  Over 49 recent runs prob_1's
#      round-0 best reads p25 438,791, median 438,791, p75 472,330, max 689,851 -- one run in four
#      leaves it at 472,330 or worse, and a build that stops there submits that number.  Scoring is
#      a single run.
#
#   4. It is not free everywhere.  prob_3's round-0 workers land within 10-11% of each other where
#      prob_1's span 63-79%, so there is no tail to cut, and shortening round 0 to buy the round
#      costs 2.3%.
#
#   5. prob_3's first veto was mis-attributed and had to be re-run.  RESFRAC=0.50 there showed no
#      FILL line at all: the tail polish is handed every remaining second and consumed the whole
#      120 s reserve, so the arm measured "starve round 0 and feed the polish", not "starve round 0
#      and run a second round".  OGC_POLCAP caps that pass -- and the pass does not want the time:
#      prob_3 returns 4,274,798 with a 39 s polish and 4,277,106 with a 5 s one, 0.05% apart, while
#      the round-0 seconds those arms differ in are worth 2.5%.
#
# WHAT THIS QUEUE DECIDES.  Whether OGC_RESFRAC returns as a default, alone, with the polish capped
# so the round it buys actually runs.  The hidden set is the reason to ask: the 7th entry is the
# only one that ever carried it and it is still the best P1 (2,685,759) and best P3 (5,569,691)
# recorded, against 3,185,928 and 5,886,815 in the 10th.  But the 7th also carried ORDER=lst and
# W3MUL=0.5 globally, which is what blew P2 +14.23% / P5 +19.03% / P8 +14.00%, so the reserve has
# never been priced on its own.
#
# READ IT AS A DISTRIBUTION.  Four replicates on prob_1 because the claim is about the tail, and
# the tail is invisible in one cell -- the arms differ by 0.3% at the median and by 10%+ at p75.
set -u
cd /home/user/oraclemaster/research/exact_packer/session2/recon || exit 1
echo tailcut > harness/CURRENT
( cd "$(git rev-parse --show-toplevel)" \
  && git add research/exact_packer/session2/recon/harness/CURRENT \
  && git commit -q -m "queue: CURRENT=tailcut" \
  && git push -q origin claude/repair-plan-model-1ig6it ) >/dev/null 2>&1
L=results/audit/tailcut.log
mkdir -p results/audit; touch $L
ci(){ ( cd "$(git rev-parse --show-toplevel)" \
        && git add research/exact_packer/session2/recon/results/audit/tailcut.log \
                  research/exact_packer/session2/recon/harness/CURRENT \
        && git commit -q -m "in-flight: tailcut $1" \
        && git push -q origin claude/repair-plan-model-1ig6it ) >/dev/null 2>&1; }

run(){ # tag prob limit env
    local tag="$1"
    grep -vE '^# ' $L 2>/dev/null | grep -q "\[$tag\]" && return
    echo "# [$tag]" >> $L
    env $4 OGC_WSTAT=1 timeout $(( $3 * 4 )) /usr/bin/python3.12 harness/run1.py myalgorithm $2 $3 \
        "[$tag]" --data data/stage2 >> $L 2>&1 || echo "P$2 [$tag] CRASH rc=$?" >> $L
    ci "$tag"
}

CUT="OGC_RESFRAC=0.35 OGC_POLCAP=5"

for rep in 1 2 3 4; do
  run "r$rep.p1.base" 1 240 ""
  run "r$rep.p1.cut"  1 240 "$CUT"
done
echo "== TAILCUT prob_1 done ==" >> $L

# the cost, on the instances whose workers agree and on the two large ones
for rep in 1 2; do
  for p in 3 16 20; do
    run "r$rep.p$p.base" $p 240 ""
    run "r$rep.p$p.cut"  $p 240 "$CUT"
  done
done
echo "TAILCUTDONE" >> $L
echo idle > harness/CURRENT

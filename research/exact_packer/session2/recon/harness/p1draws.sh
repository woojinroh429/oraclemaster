#!/bin/bash
# P1 IS A LOTTERY AND WE HAVE BEEN BUYING FEWER, BETTER TICKETS.
#
# THE MEASUREMENT THAT SAYS SO.  Twenty-four round-0 worker draws on prob_1, pooled over the
# brkcal queue:
#
#     min 422,629   p25 489,878   median 571,400   p75 722,186   max 866,567
#     P(a single worker draw <= 450,000) = 0.25
#
# The score is the MINIMUM over the draws, so with four of them P(some draw <= 450,000) is
# 1 - 0.75^4 = 68%, and with eight it is 90%.  Nothing about the median matters; the left tail and
# the COUNT are the whole score.  This is why brk lifting prob_1's median worker by 4.7% left the
# minimum at 422,629 in both arms, and why twelve branches of budget-shuffling closed as trades.
#
# The hidden P1 has read 2,685,759 / 3,009,531 / 3,185,928 / 3,051,204 across the 7th, 8th, 10th
# and 11th entries -- an 18.6% band with no monotone relationship to anything shipped in between.
# That is the same lottery seen from outside, and the 7th's 2,685,759 was a good ticket, not a
# better algorithm.
#
# WHAT THIS SWEEP DOES.  OGC_ROUNDS sets how many worker rounds the budget is cut into, so it buys
# draws directly: R rounds x 4 workers = 4R draws, each about 1/R as long.  Shorter draws are
# worse -- fillpower measured prob_1 at 486,096 from a 99 s round 0 against 438,791 from a 199 s
# one -- so this is a real trade and the question is which side of it 240 s sits on.
#
# It is read from WSTAT, i.e. from the DRAW DISTRIBUTION, not from the run objective.  Each run
# yields 4R samples, so four replicates of R=4 is 64 draws against the 24 that took the whole
# brkcal queue to collect.  The decision quantity is P(min over the run's draws <= T) and it is
# computed from the pooled distribution rather than from which run happened to win.
#
# WHAT WOULD REFUSE IT.  If the draw distribution degrades faster than the count grows -- if R=4's
# p25 is worse than R=1's median, say -- then long rounds are right and P1's band is irreducible
# by this lever.  Then the answer for P1 is that it cannot be improved by scheduling at all and
# the remaining lever is the beam's own left tail.
#
# prob_16 IS THE VETO, AND IT IS RUN FIRST.  It is the instance that needs depth: its best worker
# reaches 2,671,848 with a 199 s round and only 2,879,376 with 155 s, so cutting the budget into
# four rounds should hurt it badly.  If it does not, that finding was itself a draw.
set -u
cd /home/user/oraclemaster/research/exact_packer/session2/recon || exit 1
echo p1draws > harness/CURRENT
L=results/audit/p1draws.log
mkdir -p results/audit; touch $L
ci(){ ( cd "$(git rev-parse --show-toplevel)" \
        && git add research/exact_packer/session2/recon/results/audit/p1draws.log \
                  research/exact_packer/session2/recon/harness/CURRENT \
        && git commit -q -m "in-flight: p1draws $1" \
        && git push -q origin claude/repair-plan-model-1ig6it ) >/dev/null 2>&1; }

run(){ # tag prob limit env
    local tag="$1"
    grep -vE '^# ' $L 2>/dev/null | grep -q "\[$tag\]" && return
    echo "# [$tag]" >> $L
    env $4 OGC_WSTAT=1 timeout $(( $3 * 4 )) /usr/bin/python3.12 harness/run1.py myalgorithm $2 $3 \
        "[$tag]" --data data/stage2 >> $L 2>&1 || echo "P$2 [$tag] CRASH rc=$?" >> $L
    ci "$tag"
}

# The veto first: two replicates on the instance that is supposed to need one long round.
for rep in 1 2; do
  for R in 1 4; do
    run "r$rep.p16.R$R" 16 240 "OGC_ROUNDS=$R"
  done
done
echo "== P1DRAWS veto done ==" >> $L

for rep in 1 2 3 4; do
  for R in 1 2 3 4; do
    run "r$rep.p1.R$R" 1 240 "OGC_ROUNDS=$R"
  done
done
echo "== P1DRAWS prob_1 done ==" >> $L

for rep in 1 2; do
  for R in 1 3; do
    run "r$rep.p3.R$R" 3 240 "OGC_ROUNDS=$R"
    run "r$rep.p20.R$R" 20 240 "OGC_ROUNDS=$R"
  done
done
echo "P1DRAWSDONE" >> $L
echo idle > harness/CURRENT

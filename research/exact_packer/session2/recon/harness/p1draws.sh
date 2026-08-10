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
# AND IT CARRIES OGC_DRAWSTAT=1, WHICH IS FREE HERE.  Every draw then prints its wid, its axis
# and its objective, so the same cells that price the round count also answer which _AXES entry
# produces prob_1's good draws -- and the axis is documented as worth 32-210% against 0.0-12.6%
# for repeating one config, i.e. more than anything else in the run.  The instrumented _fresh is
# byte-for-byte the plain one when OGC_AXJIT is unset (_jit returns cfg untouched), so this costs
# one _total per draw and changes no decision.
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
    env $4 OGC_WSTAT=1 OGC_DRAWSTAT=1 timeout $(( $3 * 4 )) /usr/bin/python3.12 harness/run1.py myalgorithm $2 $3 \
        "[$tag]" --data data/stage2 >> $L 2>&1 || echo "P$2 [$tag] CRASH rc=$?" >> $L
    ci "$tag"
}

# AXIS FIRST.  A WSTAT draw is a min over ~12 constructions (opstat's beam try counts on prob_1
# read 12/8/11/8) and `axes[gen[0] % 6]` rotates the axis on each, so each axis gets about two.
# P(worker draw <= 450,000) = 0.16 then implies a single construction clears it about 1.5% of the
# time.  If ONE axis holds most of that mass, pinning converts two chances into twelve, and the
# file's own measurement says the axis is worth 32-210% against 0.0-12.6% for repeating one config
# -- an order of magnitude more than anything else touched tonight.
#
# OGC_AXIS pins EVERY worker to one _AXES entry, so these six cells also say what config A and
# config B are each worth on a single axis.  Two replicates because prob_1's spread is 105% and one
# cell has produced a wrong call three times tonight.
for rep in 1 2; do
  for A in 0 1 2 3 4 5; do
    run "r$rep.p1.ax$A" 1 240 "OGC_AXIS=$A"
  done
  run "r$rep.p1.rot" 1 240 ""
done
echo "== P1DRAWS axis done ==" >> $L

# Then the round sweep, at two replicates rather than four: the fill-round evidence (4% move rate
# over 53 samples) and the saturation reading (155 s and 228 s identical over 248) both point at
# R=1, so this is now confirmation rather than discovery.  R=2 is the cell that could still move --
# its rounds are about 120 s, which is above the 73 s the fill round proves is too short.
#
# WORKERS=4 IS PINNED BELOW.  The shipped default now gates to three workers at timelimit <= 240,
# so an unpinned 240 s run measures three draws per round.  Everything this sweep gets compared
# against was produced with four: the 24-draw distribution in p1lottery.md, the 248-sample
# saturation reading in shortdraws.md, and the four submitted entries themselves.  Mixing the two
# makes the draw-count question unanswerable.  The worker count is a separate and still
# unvalidated change and does not belong inside the experiment that would judge it.
for rep in 1 2; do
  for R in 1 2 3 4; do
    run "r$rep.p1.R$R" 1 240 "WORKERS=4 OGC_ROUNDS=$R"
  done
done
echo "== P1DRAWS rounds done ==" >> $L

# The veto last: prob_16 is supposed to need one long round.
for rep in 1 2; do
  for R in 1 4; do
    run "r$rep.p16.R$R" 16 240 "WORKERS=4 OGC_ROUNDS=$R"
  done
done
echo "P1DRAWSDONE" >> $L
echo idle > harness/CURRENT

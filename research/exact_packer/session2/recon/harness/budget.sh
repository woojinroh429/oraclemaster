#!/bin/bash
# THE ONLY LOSSLESS LEVER LEFT: 41.7% OF A WORKER'S SLICE GOES TO OPERATORS THAT RETURN NOTHING.
#
# WHY THIS AND NOT ANOTHER KNOB.  Everything tried today either replaced a draw or replaced a
# configuration, and both can lose.  FFSET is the clearest case -- it SWAPS the even workers' rung
# split, so where the even half is the answering half the original draw is gone: prob_1 gains
# -12.53% by exactly the mechanism that costs prob_2, prob_27 and prob_33 6.8-8.9%.  A change that
# only ADDS cannot do that.
#
# THE MEASUREMENT THIS RESTS ON, from OPSTAT on stage-2 prob_1, single worker:
#
#     RESFRAC 0.50, 27.8 s total     grow 5.1 + bay 5.0 + brk 1.5 = 11.6 s = 41.7%, gain 0
#     RESFRAC 0.05, 54.7 s total     grow 9.8 + bay 9.3 + brk 13.3 = 32.4 s = 59.2%, gain 0
#
# All three are tried=1 -- the compulsory first probe and nothing more -- and all three return
# zero.  Doubling the budget moved the waste from 41.7% to 59.2% and pushed beam, the operator that
# actually pays, from 42.2% of the clock down to 29.4%.
#
# WHERE THE TIME GOES.  `slot` opens every search operator at 20% of the budget, and `unt` runs
# each untried operator before selection by rate begins.  So the opening probes are a FRACTION of
# the clock and scale with it: a bigger budget buys a bigger sample of an operator already known to
# return nothing.  OGC_FIRSTCAP caps that compulsory first try at a fixed number of SECONDS
# instead, and whatever it does not take is left for selection to spend on what pays.
#
# WHY THIS IS LOSSLESS IN THE SENSE THAT MATTERS.  It removes no configuration and no draw.  The
# operators are all still in the roster and still selectable; they simply audition briefly rather
# than at 20% of the clock each.  If an operator is worth choosing, `max(gain/spent)` still chooses
# it -- and a shorter first try makes its RATE look better, not worse, when it does pay.
#
# AND THE PRICE LIST IS ALREADY MEASURED.  From every WSTAT draw logged, the expected minimum over
# k draws on prob_1: k=3 635,707, k=6 -5.9%, k=12 -11.0%.  Recovering 41.7% of the slice is roughly
# 1.7x the beam draws, so the order of magnitude to expect here is -4%.
#
# WHAT WOULD MAKE IT FAIL, named first, and it has already been observed once.  An operator that
# needs TIME before it earns anything will be judged on a probe too short to earn it, and the
# selection loop never returns to an operator that scored zero -- brk is the proven case:
# OGC_BRKFLOOR=25 took it from 0.4 s and gain 0 to 34 s and gain 62,222 on the same instance.  So a
# cap that is too tight does not merely waste less, it can amputate a real operator.  prob_3 and
# prob_16 are carried for that reason: brk pays there (P3 80,795 against 96,990 with it off) and
# they are where the amputation would show.
#
# THE PREVIOUS ATTEMPT AT THIS IS VOID, not negative.  The knob was first called OGC_PROBE, which
# was already the repair passes' opening slice -- a FRACTION clamped to [0.005, 0.50] -- so
# OGC_PROBE=2 silently meant "open every repair operator at 50% of the clock" ON TOP of the cap
# being tested.  results/audit/probe.log and gainfair.log's K arm were run that way and cannot be
# read.  The name was fixed to OGC_FIRSTCAP and never re-measured.  This is that re-measurement.
#
# ARMS: FIRSTCAP 0 (off, shipped), 1.0 s, 2.0 s, 4.0 s.
#
# JUDGED, fixed before the run: prob_1 decides the direction, prob_3 and prob_16 hold the veto --
# if either regresses by more than 1% the cap is amputating brk and the arm dies regardless of
# prob_1.  Three replicates, paired within replicate.
set -u
cd /home/user/oraclemaster/research/exact_packer/session2/recon || exit 1
. harness/lock.sh
lock_acquire budget
L=results/audit/budget.log
mkdir -p results/audit; touch $L
ci(){ ( cd "$(git rev-parse --show-toplevel)" \
        && git add research/exact_packer/session2/recon/results/audit/budget.log \
                  research/exact_packer/session2/recon/harness/CURRENT \
                  research/exact_packer/session2/recon/harness/budget.sh \
        && git commit -q -m "in-flight: budget $1" \
        && git push -q origin claude/repair-plan-model-1ig6it ) >/dev/null 2>&1; }
run(){ local tag="$1" p="$2" fc="$3" _s _e
    grep -vE '^# ' $L 2>/dev/null | grep -q "\[$tag\]" && return
    echo "# [$tag]" >> $L
    _s=$(date +%s.%N)
    env OGC_FIRSTCAP=$fc OGC_WSTAT=1 timeout 200 /usr/bin/python3.12 \
        harness/run1.py myalgorithm $p 60 "[$tag]" --data data/stage2 >> $L 2>&1 \
        || echo "P$p [$tag] CRASH rc=$?" >> $L
    _e=$(date +%s.%N)
    echo "# WALL [$tag] $(awk -v a="$_s" -v b="$_e" 'BEGIN{printf "%.2f", b-a}')" >> $L
    ci "$tag"; }
for rep in 1 2 3; do
  for p in 1 3 16; do
    run "A.p$p.r$rep" $p 0
    run "B.p$p.r$rep" $p 1.0
    run "C.p$p.r$rep" $p 2.0
    run "D.p$p.r$rep" $p 4.0
  done
done
echo "BUDGETDONE" >> $L
lock_release budget

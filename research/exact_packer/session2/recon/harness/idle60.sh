#!/bin/bash
# THE 60-SECOND RUN CANNOT REACH ITS LAST THIRD, AND RESFRAC 0.05 IS A BLUNT FIX FOR IT.
#
# rf7 exposed this in its "ran" column, not in its objectives: every RESFRAC 0.50 cell at
# WORKERS=7 returns at 33-36 s of a 60 s limit, every 0.05 cell returns at 57-58 s.  The arithmetic
# is in algorithm() and it is exact, not a tendency:
#
#     reserve  = 0.50 * 60                              = 30 s held for the polish
#     wbudget  = 60 - reserve - elapsed - 1             = 28 s, all of round 0
#     polish   = z3_reassign + fill                     returns in ~1 s on prob_1 and prob_3
#     fill gate: min(_rb, left-8) < OGC_FILLFLOOR       min(28, 18) = 18 < 40  ->  break
#
# 26 of 60 seconds, discarded, on every DIRGATE instance -- and DIRGATE only fires at
# timelimit <= 60, so this is precisely the band the hidden set is graded in.
#
# FILLFLOOR=40 WAS CHOSEN AT 240 s AND ITS OWN COMMENT SAYS SO: "Short budgets are untouched -- at
# 60 s the leftover is nowhere near 48 s and the gate was closed there anyway."  It was never meant
# to be reachable at 60 s.  That was fine while the reserve was 0.35 and nobody was counting the
# tail; it is not fine now that the tail is 43% of the graded budget.
#
# SO RESFRAC 0.05 MAY BE WINNING FOR A REASON THAT HAS NOTHING TO DO WITH THE POLISH.  Shrinking
# the reserve to 3 s does not buy better search -- it deletes the idle window by making round 0
# long enough to consume the clock.  If that is the whole mechanism, there is a strictly better
# change available: keep the polish's 30 s AND spend the leftover, by lowering the gate that is
# refusing the fill round.
#
# ARMS, all WORKERS=7, 60 s, paired within replicate:
#     A  stock                        RESFRAC 0.50                      the dirgate build
#     B  reserve                      RESFRAC 0.05                      what rf7 is measuring
#     C  gate                         RESFRAC 0.50 + FILLFLOOR 10       polish intact, tail spent
#     D  both                         RESFRAC 0.05 + FILLFLOOR 10       do they stack or overlap
#
# C IS THE ARM THAT MATTERS.  If C >= B the reserve revert was right for the wrong reason and the
# real defect is a threshold left over from a 240 s campaign -- a one-token change that costs the
# polish nothing.  If B > C then the reserve is buying something the extra draw is not, and 0.05
# goes in on its own evidence.
#
# WHAT WOULD MAKE IT FAIL, named first.  The module already measured short fill rounds and found
# them worthless -- "Eight rounds under 35 s, eight times nothing" (myalgorithm.py:5507), and C's
# fill round gets about 18 s.  That measurement was taken at 240 s where the incumbent came from a
# 47 s round, and a short draw cannot beat a long one; here the incumbent comes from a 28 s round,
# so the fill draw is comparable rather than stunted.  That is the reason to expect C to behave
# differently and it is exactly the reason it might not.  The other failure mode is the wall: the
# gate keeps 8 s of headroom and hands `left` as the hard bound, so a fill round must not push
# past 60 s -- the "ran" column is checked on every C and D cell and any cell at 60 s or beyond
# voids the arm regardless of its objective.
#
# JUDGED, fixed before the run: prob_1 four replicates, prob_3 / prob_16 / prob_2 two each,
# paired ratio against A within replicate, median over replicates.  Nothing ships on prob_1 alone.
set -u
cd /home/user/oraclemaster/research/exact_packer/session2/recon || exit 1
while [ "$(cat harness/CURRENT 2>/dev/null)" != "idle" ]; do sleep 15; done
echo idle60 > harness/CURRENT
L=results/audit/idle60.log
mkdir -p results/audit; touch $L
ci(){ ( cd "$(git rev-parse --show-toplevel)" \
        && git add research/exact_packer/session2/recon/results/audit/idle60.log \
                  research/exact_packer/session2/recon/harness/CURRENT \
                  research/exact_packer/session2/recon/harness/idle60.sh \
        && git commit -q -m "in-flight: idle60 $1" \
        && git push -q origin claude/repair-plan-model-1ig6it ) >/dev/null 2>&1; }
# WALL TIME AT FULL PRECISION, BECAUSE AN OVERRUN IS DISQUALIFICATION AND run1.py PRINTS %.0f.
# rf7's cross-instance cells came back with "ran 60s" on a 60 s limit for P3, P16 and P13 -- which
# at one significant figure means anything from 59.5 to 60.5.  That is not a number a decision about
# the wall can be made from.  WALL is measured around the whole interpreter, so it includes ~0.3 s
# of startup the grader may or may not charge us: it OVER-estimates, which is the safe direction.
run(){ local tag="$1" p="$2" rf="$3" ff="$4"
    grep -vE '^# ' $L 2>/dev/null | grep -q "\[$tag\]" && return
    echo "# [$tag]" >> $L
    local _s _e
    _s=$(date +%s.%N)
    env WORKERS=7 OGC_RESFRAC=$rf OGC_FILLFLOOR=$ff timeout 200 /usr/bin/python3.12 \
        harness/run1.py myalgorithm $p 60 "[$tag]" --data data/stage2 >> $L 2>&1 \
        || echo "P$p [$tag] CRASH rc=$?" >> $L
    _e=$(date +%s.%N)
    echo "# WALL [$tag] $(awk -v a="$_s" -v b="$_e" 'BEGIN{printf "%.2f", b-a}')" >> $L
    ci "$tag"; }
for rep in 1 2 3 4; do
  run "A.p1.r$rep" 1 0.50 40
  run "B.p1.r$rep" 1 0.05 40
  run "C.p1.r$rep" 1 0.50 10
  run "D.p1.r$rep" 1 0.05 10
done
for rep in 1 2; do
  for p in 3 16 2; do
    run "A.p$p.r$rep" $p 0.50 40
    run "B.p$p.r$rep" $p 0.05 40
    run "C.p$p.r$rep" $p 0.50 10
    run "D.p$p.r$rep" $p 0.05 10
  done
done
echo "IDLE60DONE" >> $L
echo idle > harness/CURRENT

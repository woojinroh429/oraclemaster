#!/bin/bash
# THE 60-SECOND RUN CANNOT REACH ITS LAST THIRD, AND RESFRAC 0.05 IS A BLUNT FIX FOR IT.
#
# SUPERSEDES rf7, WHICH IS VOID.  rf7 ran from 01:45 to 02:05 and never once had the box to
# itself: m120 -- believed cut, actually alive -- held cores until 01:58:49, and idle60's first
# incarnation held them from 01:59 to 02:04.  All six of rf7's P1 replicates were contended.  The
# lock is fixed in harness/lock.sh; this run uses it.  rf7's arms are a strict subset of this
# one's, so nothing is lost by re-running rather than repairing.
#
# THE DEFECT, which is arithmetic in algorithm() and not a tendency -- it survives the void
# because a threshold comparison does not care how loaded the box was:
#
#     reserve  = 0.50 * 60                              = 30 s held for the polish
#     wbudget  = 60 - reserve - elapsed - 1             = 28 s, all of round 0
#     polish   = z3_reassign + fill                     returns in ~1 s on prob_1 and prob_3
#     fill gate: min(_rb, left-8) < OGC_FILLFLOOR       min(28, 18) = 18 < 40  ->  break
#
# 26 of 60 seconds, discarded -- and DIRGATE only fires at timelimit <= 60, so this is precisely
# the band the hidden set is graded in.
#
# FILLFLOOR=40 WAS CHOSEN AT 240 s AND ITS OWN COMMENT SAYS SO: "Short budgets are untouched -- at
# 60 s the leftover is nowhere near 48 s and the gate was closed there anyway" (myalgorithm.py:5517).
# It was never meant to be reachable at 60 s.  That was fine while nobody was counting the tail; it
# is not fine now that the tail is 43% of the graded budget.
#
# SO RESFRAC 0.05 MAY BE WINNING FOR A REASON THAT HAS NOTHING TO DO WITH THE POLISH.  Shrinking
# the reserve to 3 s does not buy better search -- it deletes the idle window by making round 0
# long enough to consume the clock.  If that is the whole mechanism there is a strictly better
# change available: keep the polish's 30 s AND spend the leftover, by lowering the gate.
#
# ARMS, all WORKERS=7, 60 s, paired within replicate:
#     A  stock        RESFRAC 0.50                   the dirgate build as it scored 72,188,856
#     B  reserve      RESFRAC 0.05                   what capfix shipped, what rf7 tried to judge
#     C  gate         RESFRAC 0.50 + FILLFLOOR 10    polish intact, tail spent
#     D  both         RESFRAC 0.05 + FILLFLOOR 10    do they stack or overlap
#
# C IS THE ARM THAT MATTERS.  If C >= B the reserve was never the point and the real defect is a
# threshold left over from a 240 s campaign -- a one-token change that costs the polish nothing.
#
# FILLFLOOR IS A GLOBAL DEFAULT, NOT A GATED ONE.  RESFRAC reaches only instances inside DIRGATE's
# band; lowering FILLFLOOR changes every instance at every budget.  That is why P2 and P13 are
# here on arms A and C: they sit outside the gate, they are Z1-dominated with Z3=0, and if the
# freed tail can hurt anything it will hurt something the gate never protected.  One replicate is
# not a quality measurement -- it is a check for harm and it is judged as one.
#
# WHAT WOULD MAKE IT FAIL, named first.  The module already measured short fill rounds and found
# them worthless -- "Eight rounds under 35 s, eight times nothing" (myalgorithm.py:5507) -- and C's
# fill round gets about 18 s.  That was taken at 240 s where the incumbent came from a 47 s round
# and a short draw cannot beat a long one; here the incumbent is itself a 28 s round, so the fill
# draw is comparable rather than stunted.  That is the reason to expect C to differ and it is
# exactly the reason it might not.
#
# THE WALL IS A HARD CONSTRAINT AND OUTRANKS EVERY OBJECTIVE HERE.  run1.py prints elapsed at
# %.0f, so rf7's "ran 60s" on a 60 s limit could not distinguish finishing in time from overrunning.
# Every cell now records WALL at full precision around the whole interpreter -- which includes
# ~0.3 s of startup the grader may not charge us, so it over-estimates, which is the safe
# direction.  ANY arm with a cell over 60.0 s is disqualified regardless of what it scored.
#
# JUDGED, fixed before the run: paired ratio against A within replicate, median over replicates.
# P1 four replicates, P3 and P16 two each.  Nothing ships on prob_1 alone -- P16 is carried
# specifically because it is the instance the reserve has hurt before.
set -u
cd /home/user/oraclemaster/research/exact_packer/session2/recon || exit 1
. harness/lock.sh
lock_acquire idle60
if [ "$(lock_box_busy)" -gt 0 ]; then
    echo "# ABORT: solver processes already running, box not quiet" >> results/audit/idle60.log
    lock_release idle60; exit 1
fi
L=results/audit/idle60.log
mkdir -p results/audit; touch $L
ci(){ ( cd "$(git rev-parse --show-toplevel)" \
        && git add research/exact_packer/session2/recon/results/audit/idle60.log \
                  research/exact_packer/session2/recon/harness/CURRENT \
                  research/exact_packer/session2/recon/harness/idle60.sh \
                  research/exact_packer/session2/recon/harness/lock.sh \
        && git commit -q -m "in-flight: idle60 $1" \
        && git push -q origin claude/repair-plan-model-1ig6it ) >/dev/null 2>&1; }
run(){ local tag="$1" p="$2" rf="$3" ff="$4" _s _e
    grep -vE '^# ' $L 2>/dev/null | grep -q "\[$tag\]" && return
    echo "# [$tag]" >> $L
    _s=$(date +%s.%N)
    env WORKERS=7 OGC_RESFRAC=$rf OGC_FILLFLOOR=$ff timeout 200 /usr/bin/python3.12 \
        harness/run1.py myalgorithm $p 60 "[$tag]" --data data/stage2 >> $L 2>&1 \
        || echo "P$p [$tag] CRASH rc=$?" >> $L
    _e=$(date +%s.%N)
    echo "# WALL [$tag] $(awk -v a="$_s" -v b="$_e" 'BEGIN{printf "%.2f", b-a}')" >> $L
    ci "$tag"; }
arms(){ local p="$1" rep="$2"
    run "A.p$p.r$rep" $p 0.50 40
    run "B.p$p.r$rep" $p 0.05 40
    run "C.p$p.r$rep" $p 0.50 10
    run "D.p$p.r$rep" $p 0.05 10; }
# Replicate-major so a run cut short still has breadth rather than four arms of prob_1 alone.
for rep in 1 2; do
  for p in 1 3 16; do arms $p $rep; done
done
for rep in 3 4; do arms 1 $rep; done
# FILLFLOOR is global: check it cannot hurt instances outside DIRGATE's band.
for p in 2 13; do
  run "A.p$p.r1" $p 0.50 40
  run "C.p$p.r1" $p 0.50 10
done
echo "IDLE60DONE" >> $L
lock_release idle60

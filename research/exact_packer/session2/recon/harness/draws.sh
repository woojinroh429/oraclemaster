#!/bin/bash
# HOW MANY DRAWS DOES THE ANSWER ACTUALLY COME FROM, AND DOES BUYING MORE OF THEM PAY?
#
# What forced this queue.  On prob_16 the four workers came back
#
#     ship   4357325  3281165  3999235  4289843     spread 32.8%
#     m1     3934380  3061389  4220237  3932023     spread 37.9%
#     mono   4322739  3380578  4550495  3683769     spread 34.6%
#     monoB  4074927  3295373  3787107  3936245     spread 30.2%
#
# and the reported answer is the MINIMUM of each row.  m1 wins the comparison on a single worker
# that landed at 3.06M while its other three sat above 3.9M -- its MEDIAN worker is the second
# worst of the four arms.  monoB has the best median worker and loses.  So on this instance the
# score is set by the luck of a 4-sample minimum drawn from a distribution 30-38% wide, not by
# which search is better.
#
# And the budget does not buy samples.  Bcur = min(Bmax, left/(per*rem)) is derived from the
# budget, so 240 s runs FOUR wider draws, not EIGHT.  That is the missing half of "why does a
# bigger budget sometimes lose" -- min-of-4 from a wide distribution is mostly luck, and widening
# each draw does not reduce that.
#
# The headroom is real and it is the size we need: every arm above scored 3.06-3.38M, while
# prob_16's recorded best at this budget is 2,795,643.  A better minimum EXISTS in the reachable
# set; nothing in the current design goes and gets more chances at it.
#
# STAGE 1 -- diagnosis, cheap.  OGC_OPSTAT=1 already prints tried/seconds/gain per operator; it
# has never been read for the beam's own call count.  `beam` tried=1 means a worker draws once and
# every later second goes to grow/repair around that single construction; tried=5 means the
# rotation is already resampling and the ceiling is elsewhere.  Nothing about the rest of this
# queue is worth reading until that number is known, so it runs first and on one instance.
#
# STAGE 2 -- the lever.  Three ways to turn budget into draws instead of width:
#
#     w4     WORKERS=4                     as shipped: 4 draws, axes 0-3, axes 4 and 5 never open
#     w6     WORKERS=6                     6 draws on 4 cores -- and the FIRST TIME axes 4 and 5
#                                          run at all, so it adds diversity as well as count
#     w8     WORKERS=8                     8 draws, each at half a core
#     b48    WORKERS=4 OGC_BCAP=48         half-width beams: each draw is cheaper, so the operator
#                                          loop can afford more of them within one worker
#
# w6/w8 oversubscribe 4 cores deliberately.  That is the trade being measured: each draw gets less
# CPU and is therefore effectively narrower, which is the same currency the mono ladder spent and
# lost with.  The difference is that these draws are INDEPENDENT -- different axes, different
# seeds -- so they sample the attractor set instead of re-walking one basin at two widths.
#
# Polish is OFF on every arm.  It gained exactly 0.00% on all four mono cells, matching the 804-run
# median, and leaving it on only adds a random 0-10% to whichever arm gets lucky.
#
# Read with:  python3.12 harness/beamside.py results/audit/draws.log w4
# and judge on the MEDIAN worker as well as the min -- an arm that moves the min but not the
# median bought a lucky draw, which is the exact failure this queue exists to stop rewarding.
set -u
cd "$(dirname "$0")/.." || exit 1
echo draws > harness/CURRENT
( cd "$(git rev-parse --show-toplevel)" \
  && git add research/exact_packer/session2/recon/harness/CURRENT \
  && git commit -q -m "queue: CURRENT=draws" \
  && git push -q origin claude/repair-plan-model-1ig6it ) >/dev/null 2>&1
L=results/audit/draws.log
mkdir -p results/audit; touch $L

run(){ # tag prob secs env
    local tag="$1"
    grep -vE '^# ' $L 2>/dev/null | grep -q "\[$tag\]" && return
    echo "# [$tag]" >> $L
    env $4 OGC_WSTAT=1 timeout $(( $3 * 5 )) /usr/bin/python3.12 harness/run1.py myalgorithm $2 $3 \
        "[$tag]" --data data/stage2 >> $L 2>&1 \
        || echo "P$2 [$tag] HANG-OR-CRASH rc=$?" >> $L
    ( cd "$(git rev-parse --show-toplevel)" \
      && git add research/exact_packer/session2/recon/results/audit/draws.log \
                research/exact_packer/session2/recon/harness/CURRENT \
      && git commit -q -m "in-flight: draws $tag" ) >/dev/null 2>&1
}

# ---- stage 1: how many beam draws does a worker take today? ----
for p in 16 4; do
    run "d60.$p"  $p  60 "OGC_OPSTAT=1"
    run "d240.$p" $p 240 "OGC_OPSTAT=1"
done
echo "DIAGDONE" >> $L

# ---- stage 2: buy draws instead of width ----
for rep in 1 2; do
    for p in 16 4 20 24; do
        run "r$rep.w4.$p"  $p 240 "WORKERS=4"
        run "r$rep.w6.$p"  $p 240 "WORKERS=6"
        run "r$rep.w8.$p"  $p 240 "WORKERS=8"
        run "r$rep.b48.$p" $p 240 "WORKERS=4 OGC_BCAP=48"
    done
    echo "REPDONE $rep" >> $L
done
echo "DRAWSDONE" >> $L
echo beamhard > harness/CURRENT
nohup bash harness/beamhard.sh >> results/beamhard.log 2>&1 < /dev/null &

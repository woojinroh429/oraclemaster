#!/bin/bash
# CAN THE POLISH REACH THE POINT OUR SOLUTIONS ALREADY BRACKET?
#
# prob_1, w1=6667 w2=3 w3=600, exchange w1/w3 = 11.1.  Our recorded solutions sit along a
# trade-off and never inside it:
#
#     obj 450,860   Z1= 5  Z2=6975  Z3=661     <- our best, low tardiness / high penalty
#     obj 470,530   Z1=19  Z2=7419  Z3=536     <- our lowest penalty, high tardiness
#     obj 516,577   Z1=13  Z2=4102  Z3=696     <- our lowest Z2
#
# Combining the components we already achieve separately -- Z1=5, Z3=536, Z2~6000 -- would score
# about 373,000, which is where a competitor reportedly is.  So the target is not a better
# algorithm; it is a point INSIDE our own frontier, and our search never lands there.
#
# The operator that walks that frontier already exists.  z3_reassign accepts a move when
# w1*dtardy + w3*dpen < 0, so at 11.1 it will pay up to 11 units of tardiness for 125 units of
# penalty.  Going from our best (Z1=5, Z3=661) to (Z1=16, Z3=536) is exactly such a trade and
# would score ~374,000.  Either the pass cannot find those moves, or geometry forbids them.
#
# That is a budget question and OGC_RESERVE sets the budget directly (reserve = max(2, OGC_RESERVE)
# when set, else min(20% of limit, 40 s)).  _z3_improve calls Engine::z3_reassign, whose body is
# hillclimb + ruin-recreate until its budget is gone, so it absorbs whatever it is handed.
#
#     r40    default reserve at 240 s -- 40 s of polish        (control)
#     r120   half the budget to the polish
#     r240   almost all of it: the beam gets one slice, the polish gets the rest
#     r400   600 s limit, 400 s polish -- past what could ship, to see the ceiling
#
# What each outcome means:
#     Z3 falls with budget      the moves exist and the polish is starved -> raise the reserve
#     Z3 flat, objective flat   the pass is at a local optimum -> it needs a different neighbourhood
#     objective worsens         the beam's time was worth more than the polish's -> frontier is real
#
# prob_1 only, because that is where the competitor number is and where Z3 is 73% of the score.
# prob_24 is second (Z3 36%) and prob_16 third (32.7%) as a check that any effect is not prob_1's
# alone.
set -u
cd "$(dirname "$0")/.." || exit 1
echo z3budget > harness/CURRENT
( cd "$(git rev-parse --show-toplevel)" \
  && git add research/exact_packer/session2/recon/harness/CURRENT \
  && git commit -q -m "queue: CURRENT=z3budget" \
  && git push -q origin claude/repair-plan-model-1ig6it ) >/dev/null 2>&1
L=results/audit/z3budget.log
mkdir -p results/audit; touch $L

run(){ # tag prob limit reserve
    local tag="$1"
    grep -vE '^# ' $L 2>/dev/null | grep -q "\[$tag\]" && return
    echo "# [$tag]" >> $L
    OGC_RESERVE=$4 OGC_WSTAT=1 timeout $(( $3 * 4 )) \
        /usr/bin/python3.12 harness/run1.py myalgorithm $2 $3 "[$tag]" --data data/stage2 \
        >> $L 2>&1 || echo "P$2 [$tag] CRASH rc=$?" >> $L
    ( cd "$(git rev-parse --show-toplevel)" \
      && git add research/exact_packer/session2/recon/results/audit/z3budget.log \
                research/exact_packer/session2/recon/harness/CURRENT \
      && git commit -q -m "in-flight: z3budget $tag" ) >/dev/null 2>&1
}

for rep in 1 2; do
  for p in 1 24 16; do
    run "r$rep.r40.$p"  $p 240 40
    run "r$rep.r120.$p" $p 240 120
    run "r$rep.r240.$p" $p 300 240
    run "r$rep.r400.$p" $p 600 400
  done
  echo "REPDONE $rep" >> $L
done
echo "Z3BUDGETDONE" >> $L
echo idle > harness/CURRENT

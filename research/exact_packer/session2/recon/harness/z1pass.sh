#!/bin/bash
# THE IMPROVEMENT PASS ONLY EVER CHASED Z3.  This measures the one that chases Z1.
#
# z3_reassign, the pass that runs at the end of every solve, opens its move loop with
#
#     if(cur_pen<=0) continue;                          // skip any block already in its best bay
#     for(int tb=0;tb<n_bays;tb++){
#         if(prefv(b,tb)<=prefv(b,cur_bay)) continue;   // only consider MORE-preferred bays
#
# so a block that is late where it already wants to be is never touched, and a move that trades a
# little preference for a lot of tardiness is never generated -- though the acceptance test,
# w1*dtardy + w3*dpen < 0, would take it.  w1*Z1 is 22-85% of the objective on the instances
# measured: 85.4% prob_20, 85.3% prob_6, 67.2% prob_16, 63.4% prob_24, 46.4% prob_4, 22.6% prob_1.
#
# Engine::ruin_tardy is the pass that aims there.  It is implemented, it is bound into the module,
# and myalgorithm has never called it.  Its own comment records why it was shelved: on the real P6,
# 102 of 102 rounds were rejected because "throughput is fixed and Z1 is conserved under
# rearrangement".  That is what a SATURATED yard does -- and prob_6 is 85% w1*Z1.  The instances
# this project is furthest behind on are the loose ones; prob_1 peaks at 59.3% of bay area.
# Shelved on the wrong instance type.
#
# First reading, prob_1 at 60 s, the budget the hidden set reportedly gives its early instances:
#
#     off  750,826   Z1=37  Z2=6649  Z3=807
#     on   650,892   Z1=18  Z2=3762  Z3=866      -13.3%, and Z1 halved
#
# WHAT THIS QUEUE HAS TO ESTABLISH BEFORE ANY OF IT SHIPS
#
#   1. replication -- one cell decides nothing, and prob_1's 60 s spread is not yet known
#   2. the Z1-heavy instances -- prob_20 and prob_6 are where the pass should matter MOST by the
#      share argument, and are exactly where its own comment says it does nothing.  If it fails
#      there the argument above is wrong even though the prob_1 number is right
#   3. both budgets -- 60 s is what matters, 240 s is what everything else was tuned at
#   4. no regression anywhere: scoring is per instance, so one bad instance is not paid for
#
# Arms are just the flag, on top of whatever else is default, so the reading is the pass alone.
set -u
cd "$(dirname "$0")/.." || exit 1
echo z1pass > harness/CURRENT
( cd "$(git rev-parse --show-toplevel)" \
  && git add research/exact_packer/session2/recon/harness/CURRENT \
  && git commit -q -m "queue: CURRENT=z1pass" \
  && git push -q origin claude/repair-plan-model-1ig6it ) >/dev/null 2>&1
L=results/audit/z1pass.log
mkdir -p results/audit; touch $L
ci(){ ( cd "$(git rev-parse --show-toplevel)" \
        && git add research/exact_packer/session2/recon/results/audit/z1pass.log \
                  research/exact_packer/session2/recon/harness/CURRENT \
        && git commit -q -m "in-flight: z1pass $1" \
        && git push -q origin claude/repair-plan-model-1ig6it ) >/dev/null 2>&1; }

run(){ # tag prob limit env
    local tag="$1"
    grep -vE '^# ' $L 2>/dev/null | grep -q "\[$tag\]" && return
    echo "# [$tag]" >> $L
    env $4 timeout $(( $3 * 5 )) /usr/bin/python3.12 harness/run1.py myalgorithm $2 $3 \
        "[$tag]" --data data/stage2 >> $L 2>&1 || echo "P$2 [$tag] CRASH rc=$?" >> $L
    ci "$tag"
}

# 60 s first and complete: it is the budget that matters and the cheap one.  prob_20 and prob_6 are
# the Z1-heavy pair the share argument predicts should gain most; prob_1 and prob_4 are where the
# baselines are most reproducible.
for rep in 1 2; do
  for BUD in 60 120 240; do
    for p in 1 20 6 4 24; do
      run "r$rep.b$BUD.p$p.off" $p $BUD "OGC_Z1PASS=0"
      run "r$rep.b$BUD.p$p.on"  $p $BUD "OGC_Z1PASS=1"
    done
    echo "== BUDGET $BUD rep $rep done ==" >> $L
  done
done
echo "Z1PASSDONE" >> $L
echo idle > harness/CURRENT

#!/bin/bash
# Three dispatch orders are implemented and none of them has ever been in the portfolio.
#
# THE CHAIN THAT LEADS HERE.  cdecomp: which valley construction reaches is decided by the axis
# config -- five instances, config spread 32% to 210% against a control of 0.0% to 12.6%.  bandit:
# the selection among the six existing configs already lands within ~1% of the best of them, so
# selection is not the failure.  What is left is the SET being chosen from.
#
# And the set is narrower than its six entries suggest.  _contact_beam accepts seven orders;
# _AXES uses edd (2 slots), lst (1), defer_big (3), big_first (1) -- and all three defer_big
# entries sort on due as their second key, so five of the six axes are effectively deadline-
# ordered.  rank, cohort and sacK exist in the code and have never been tried.
#
#   arm  base     shipped default, all six axes, bandit chooses
#   arm  edd      \
#   arm  lst       |  OGC_ORDER pins the order on every axis, leaving Bmul, K, pos_lam and w3mul
#   arm  rank      |  alone.  Changing an _AXES entry instead would move four things at once and
#   arm  cohort    |  the result could not be attributed to the order.
#   arm  sac3     /
#
# What decides the next step is not whether a new order beats `base` -- one order against a
# six-axis portfolio is not a fair fight and losing proves nothing.  It is whether a new order
# wins on some INSTANCE where the current set does badly.  A portfolio is paid for by the draws
# that win, so an order that is best on two of eight earns a slot even if it is last on the rest.
#
# Same instances, budget and rep-major layout as bandit, so the two logs compare directly.
set -u
cd "$(dirname "$0")/.." || exit 1
echo orders > harness/CURRENT
L=results/audit/orders.log
mkdir -p results/audit; touch $L

run(){ # rep arm prob env
    local tag="r$1.$2.$3"
    # SKIP ON A RESULT, NOT ON THE MARKER.  The marker is written BEFORE the run, so a queue
    # killed mid-cell leaves an orphan "# [tag]" line with no result -- and this test then
    # matched it on resume and skipped the cell forever.  Nine such orphans existed across
    # today's logs, including one this session was actively waiting on (w3grid r1.dn.26).
    # In a paired design a lost arm silently invalidates the whole instance.  Excluding the
    # marker lines makes the test key on evidence the run finished.
    grep -vE '^# ' $L 2>/dev/null | grep -q "\[$tag\]" && return
    echo "# [$tag]" >> $L
    env $4 OGC_WSTAT=1 timeout 300 /usr/bin/python3.12 harness/run1.py myalgorithm $3 60 \
        "[$tag]" --data data/stage2 >> $L 2>&1
    ( cd "$(git rev-parse --show-toplevel)" \
      && git add research/exact_packer/session2/recon/results/audit/orders.log \
      && git commit -q -m "in-flight: orders $tag" ) >/dev/null 2>&1
}

for rep in 1 2 3; do
    for p in 20 16 1 6; do
        run $rep base   $p ""
        for o in edd lst rank cohort sac3; do
            run $rep "$o" $p "OGC_ORDER=$o"
        done
    done
    echo "REPDONE $rep" >> $L
done
echo "ORDERSDONE" >> $L
echo idle > harness/CURRENT

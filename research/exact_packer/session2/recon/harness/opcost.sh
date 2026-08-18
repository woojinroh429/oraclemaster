#!/bin/bash
# WHERE DOES THE BUDGET ACTUALLY GO, AND WHAT DOES EACH OPERATOR EARN FOR IT?
#
# No new arms and no new code: OGC_OPSTAT=1 already prints tried/seconds/%budget/gain/gain-per-s
# per operator, and it has never been run across a set.  The two ad-hoc runs that exist are one
# instance at 60 s and they are startling enough to be worth doing properly:
#
#     op      seconds  %budget            gain          op      seconds  %budget    gain
#     beam      25.7    48.2%   1,847,214,537          grow       9.7    18.3%        0
#     grow       9.7    18.3%               0          bay       12.4    23.3%        0
#     bay       11.1    22.0%           4,682          bal        0.1     0.2%        0
#     pref       4.8     9.6%           2,699          pref       4.8     9.1%   25,589
#     bal        0.1     0.1%           4,674
#
# grow took 18% of the budget and returned nothing twice; bay took 22-23% and returned 4,682 and
# nothing.  Together that is 40% of every run, and with brk unregistered their share is larger
# still.  If it holds across instances it is a bigger block than brk was.
#
# Deliberately NOT an ablation.  Removing an operator changes the scheduler's behaviour for all
# the others -- slots are sized per operator and the repair passes' opening slice is budget/(2n) --
# so an ablation measures the removal, not the operator.  This measures the operator: what it cost
# and what the incumbent gained while it held the budget, inside the shipped configuration.
# Whatever looks dead here then gets an ablation of its own, which is how brk was handled.
#
# gain is credited only when pool[0] improves, so an operator that produces good-but-not-better
# solutions scores zero.  That is a real limitation of the metric and the reason a zero here buys
# an ablation rather than a deletion.
#
# Twelve instances at 240 s, the same stratified sample ortho and w3grid used, one run each --
# this is an accounting sweep, not a comparison, so replicates buy less than coverage.
set -u
cd "$(dirname "$0")/.." || exit 1
echo opcost > harness/CURRENT
L=results/audit/opcost.log
mkdir -p results/audit; touch $L

run(){ # prob
    local tag="op.$1"
    grep -vE '^# ' $L 2>/dev/null | grep -q "\[$tag\]" && return
    echo "# [$tag]" >> $L
    OGC_OPSTAT=1 OGC_WSTAT=1 timeout 960 /usr/bin/python3.12 harness/run1.py myalgorithm $1 240 \
        "[$tag]" --data data/stage2 >> $L 2>&1 \
        || echo "P$1 [$tag] HANG-OR-CRASH rc=$?" >> $L
    ( cd "$(git rev-parse --show-toplevel)" \
      && git add research/exact_packer/session2/recon/results/audit/opcost.log \
      && git commit -q -m "in-flight: opcost $tag" ) >/dev/null 2>&1
}

for p in 4 26 20 2 13 6 1 32 5 31 38 35; do
    run $p
done
echo "OPCOSTDONE" >> $L
echo idle > harness/CURRENT

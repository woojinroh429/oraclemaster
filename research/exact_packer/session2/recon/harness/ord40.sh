#!/bin/bash
# JUDGE defer_big THE WAY THIS REPOSITORY JUDGES THINGS: FORTY INSTANCES, SIGN COUNT.
#
# The order sweep closed unresolvable on one instance, but it left one candidate standing.  Over
# twelve pooled draws on stage2/prob_1, defer_big beat the shipped lst on every statistic:
#
#     min       647,639  vs  654,739     -1.1%
#     p25       669,670  vs  679,647     -1.5%
#     run mean  654,983  vs  677,317     -3.3%
#
# and it was the only arm besides big_first whose span stayed narrow (3.4%) while six of the eight
# spread across the whole range once a third draw landed.  1-3% is far below that instance's own
# 13-46% swing, which is why the sweep could not call it -- and it is exactly the size the tech
# report says the forty-instance sign count exists to resolve:
#
#   > all 40 finals instances, paired, at 180 s, judged by SIGN COUNTS OVER THE SET rather than per
#   > instance -- one instance answers the same question with about 3% of spread, and unchanged
#   > code moved 8.4% between two runs an hour apart.  No single pair can resolve an effect of this
#   > size.
#
# The report judged its own spot-pricing change this way and reported 20 wins to 9 losses at a mean
# of -0.74%.  That is the precedent for calling a 1-3% effect, and this session has now produced
# sixteen reversals by refusing to use it.
#
# WHAT IS BEING COMPARED.  Stock against OGC_ORDER=defer_big, nothing else touched, so the arm is
# one environment variable and config B keeps whatever the axis gives it.  Instances run 1..40 in
# order, so an interrupted queue still yields whole pairs and a partial sign count that means
# something.
#
# WHAT WOULD MAKE IT SHIP.  A clear majority of the forty going the same way, in the report's own
# terms.  Anything near even is a null and defer_big stays unshipped -- the point of using the set
# is that it can return that answer credibly, which no amount of replication on prob_1 could.
set -u
cd /home/user/oraclemaster/research/exact_packer/session2/recon || exit 1
echo ord40 > harness/CURRENT
L=results/audit/ord40.log
mkdir -p results/audit; touch $L
ci(){ ( cd "$(git rev-parse --show-toplevel)" \
        && git add research/exact_packer/session2/recon/results/audit/ord40.log \
                  research/exact_packer/session2/recon/harness/CURRENT \
                  research/exact_packer/session2/recon/harness/ord40.sh \
        && git commit -q -m "in-flight: ord40 $1" \
        && git push -q origin claude/repair-plan-model-1ig6it ) >/dev/null 2>&1; }

run(){ # tag prob env
    local tag="$1"
    grep -vE '^# ' $L 2>/dev/null | grep -q "\[$tag\]" && return
    echo "# [$tag]" >> $L
    env $3 OGC_WSTAT=1 timeout 460 /usr/bin/python3.12 harness/run1.py myalgorithm $2 180 \
        "[$tag]" --data data/stage2 >> $L 2>&1 || echo "P$2 [$tag] CRASH rc=$?" >> $L
}

for p in $(seq 1 40); do
  run "o.p$p.stock" $p "WORKERS=4"
  run "o.p$p.defer" $p "WORKERS=4 OGC_ORDER=defer_big"
  ci "p$p"
done
echo "ORD40DONE" >> $L
echo idle > harness/CURRENT

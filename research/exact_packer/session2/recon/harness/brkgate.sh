#!/bin/bash
# DOES THE INCUMBENT'S Z3 SHARE, READ WHEN brk IS ABOUT TO BE CALLED, MATCH THE FINAL RUN'S?
#
# The gate decides on pool[0] mid-run.  Every share quoted for it so far was computed from the
# FINISHED run's Z terms, and those are not the same number: early solutions are more tardy, so Z1
# holds a larger share of the objective than it will at the end and Z3 a smaller one.  The bias has
# a known direction and it is the dangerous direction -- it can only push an instance BELOW the
# threshold, i.e. it can only switch brk off where it should be on.
#
# So the gate cannot be adopted on the final-run shares.  This reads the real one.  BRK_DEBUG=1
# prints the share at each call site without gating anything (OGC_BRKZ3 stays 0), so these runs are
# ordinary brk-on runs and their objectives stay comparable to the brkcal cells.
#
# WHAT WOULD REFUSE THE GATE.  If prob_1 or prob_3 -- the two instances brk pays on -- report
# mid-run shares below 0.65, the threshold that fits the finished runs switches the operator off
# exactly where it earns, and either the threshold has to move or the gate reads the wrong thing.
# If prob_16/24/20 report shares ABOVE 0.65, it fails to switch it off where it costs, which is
# the same verdict from the other side.
#
# Five cells, one each.  The share is deterministic given the incumbent, so replicates would only
# measure the incumbent's spread, and the question is not "what is the share" but "is it on the
# same side of 0.65 as the finished run's".
set -u
cd /home/user/oraclemaster/research/exact_packer/session2/recon || exit 1
echo brkgate > harness/CURRENT
L=results/audit/brkgate.log
mkdir -p results/audit; touch $L
ci(){ ( cd "$(git rev-parse --show-toplevel)" \
        && git add research/exact_packer/session2/recon/results/audit/brkgate.log \
                  research/exact_packer/session2/recon/harness/CURRENT \
        && git commit -q -m "in-flight: brkgate $1" \
        && git push -q origin claude/repair-plan-model-1ig6it ) >/dev/null 2>&1; }

run(){ # tag prob limit env
    local tag="$1"
    grep -vE '^# ' $L 2>/dev/null | grep -q "\[$tag\]" && return
    echo "# [$tag]" >> $L
    env $4 OGC_WSTAT=1 timeout $(( $3 * 4 )) /usr/bin/python3.12 harness/run1.py myalgorithm $2 $3 \
        "[$tag]" --data data/stage2 >> $L 2>&1 || echo "P$2 [$tag] CRASH rc=$?" >> $L
    ci "$tag"
}

# The two brk earns on first: they are the ones the gate can break.
for p in 1 3 16 24 20; do
  run "share.p$p" $p 240 "OGC_BRK=1 BRK_DEBUG=1"
done
echo "BRKGATEDONE" >> $L
echo idle > harness/CURRENT

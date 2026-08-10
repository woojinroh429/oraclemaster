#!/bin/bash
# JUDGE THE SHIPPED WORKER COUNT THE WAY THIS REPOSITORY JUDGES CHANGES.
#
# report/techreport_ko.md, section on 자리별 가격 산정, states the convention for the finals set:
# all 40 instances, paired, 180 s, judged by SIGN COUNTS OVER THE SET rather than per instance --
# because one instance answers the same question with about 3% of spread, and unchanged code moved
# 8.4% between two runs an hour apart on this machine.  No single pair resolves an effect this size.
#
# THIS SESSION DID THE OPPOSITE.  Thirteen arms were judged on stage-2 prob_1 and prob_16 with
# replicates, per instance.  Twelve produced signs that flipped on the next draw; the thirteenth --
# nw = cpu-1 for timelimit <= 240 -- produced 37 pairs that did not flip and was shipped on them.
# 37 pairs on two instances is still two instances.  This queue is the actual test.
#
#     data/stage2      the FINALS training set: all 40 have Z1 > 0, n from 150 to 300
#                      (data/train is the preliminary set -- 21 of its 40 have Z1 = 0)
#     180 s            the budget the convention uses, and inside the gate, so w3 is what runs
#     40 pairs         w4 then w3 on each instance, back to back, same machine state
#     sign count       wins, losses, ties over the set; the median move, not the mean, because
#                      the objective spans 6,804 to 75,792,403 and a mean is just the largest few
#
# WHAT DECIDES IT, written before the numbers land.  The gate ships three workers below 240 s, so:
#
#     w3 wins clearly on the set    keep the gate, and the 37 pairs were pointing at something real
#     roughly even                  drop it -- an inert change is complexity with no return
#     w3 loses on the set           revert to WORKERS=4 unconditionally and rebuild
#
# Instances run in order 1..40, so an interrupted queue still yields whole pairs and a partial sign
# count that means something.  ~4 hours for the full set.
set -u
cd /home/user/oraclemaster/research/exact_packer/session2/recon || exit 1
echo nw40 > harness/CURRENT
L=results/audit/nw40.log
mkdir -p results/audit; touch $L
ci(){ ( cd "$(git rev-parse --show-toplevel)" \
        && git add research/exact_packer/session2/recon/results/audit/nw40.log \
                  research/exact_packer/session2/recon/harness/CURRENT \
                  research/exact_packer/session2/recon/harness/nw40.sh \
        && git commit -q -m "in-flight: nw40 $1" \
        && git push -q origin claude/repair-plan-model-1ig6it ) >/dev/null 2>&1; }

run(){ # tag prob env
    local tag="$1"
    grep -vE '^# ' $L 2>/dev/null | grep -q "\[$tag\]" && return
    echo "# [$tag]" >> $L
    env $3 OGC_WSTAT=1 timeout 460 /usr/bin/python3.12 harness/run1.py myalgorithm $2 180 \
        "[$tag]" --data data/stage2 >> $L 2>&1 || echo "P$2 [$tag] CRASH rc=$?" >> $L
}

for p in $(seq 1 40); do
  run "s2.p$p.w4" $p "WORKERS=4"
  run "s2.p$p.w3" $p "WORKERS=3"
  ci "p$p"
done
echo "NW40DONE" >> $L
echo idle > harness/CURRENT

#!/bin/bash
# THE AMPLIFIER ITSELF.  OGC_THRUHZ=3.0 is a constant nobody measured.
#
# THRUBEAM ships now, and all it does is multiply the future-tardiness term by THRUHZ inside the
# beam's level rank.  Ten paired cells said the flag never loses and sometimes wins large; none of
# them asked whether 3.0 is the right multiplier.  1.0 is the flag switched off, so the sweep spans
# the flag's own decision.
#
# EVERY ARM RE-RUN ON THE CURRENT BUILD.  The h.* cells already in thru.log straddle the commit that
# made THRUBEAM the default -- the block that sets it changed the worker's timing, and on this
# project that alone has moved an objective 1.03%.  Cells from both sides of it cannot be compared,
# so the reference arm is measured here rather than taken from before.
set -u
cd /home/user/oraclemaster/research/exact_packer/session2/recon || exit 1
echo hz > harness/CURRENT
( cd "$(git rev-parse --show-toplevel)" \
  && git add research/exact_packer/session2/recon/harness/CURRENT \
  && git commit -q -m "queue: CURRENT=hz" \
  && git push -q origin claude/repair-plan-model-1ig6it ) >/dev/null 2>&1
L=results/audit/hz.log
mkdir -p results/audit; touch $L
ci(){ ( cd "$(git rev-parse --show-toplevel)" \
        && git add research/exact_packer/session2/recon/results/audit/hz.log \
                  research/exact_packer/session2/recon/harness/CURRENT \
        && git commit -q -m "in-flight: hz $1" \
        && git push -q origin claude/repair-plan-model-1ig6it ) >/dev/null 2>&1; }

run(){ # tag prob limit env
    local tag="$1"
    grep -vE '^# ' $L 2>/dev/null | grep -q "\[$tag\]" && return
    echo "# [$tag]" >> $L
    env $4 OGC_WSTAT=1 timeout $(( $3 * 4 )) /usr/bin/python3.12 harness/run1.py myalgorithm $2 $3 \
        "[$tag]" --data data/stage2 >> $L 2>&1 || echo "P$2 [$tag] CRASH rc=$?" >> $L
    ci "$tag"
}

# prob_16 and prob_24 first: they are where THRUBEAM paid most, so they are where the multiplier
# has the most room to be wrong.  prob_1 third as the instance that must not regress.
for p in 16 24 1 20 6; do
  for h in 1.0 2.0 3.0 5.0; do
    run "p$p.h$h" $p 240 "OGC_THRUHZ=$h"
  done
done
echo "HZDONE" >> $L
echo idle > harness/CURRENT

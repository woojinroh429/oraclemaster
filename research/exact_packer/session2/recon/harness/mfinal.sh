#!/bin/bash
# THE ACTUAL SHIPPING A/B: TODAY'S DEFAULT AGAINST THE SHAPE RULE.
#
# mship arm B compared MSET=1 with MSET=8 and found -17.23% above peak_util 2.0 and +9.61% below,
# nine draws each way with no sign flip.  But the SHIPPED default is neither: it is MSET="1,2"
# indexed by wid%2, so one worker in three already runs M=2 and part of the branching value is
# already collected.  Measuring against MSET=1 overstates what the change is worth.
#
# CONTROL: the shipped build exactly -- nothing set, MSET defaults to "1,2".
# RULE:    OGC_MSET=8 on instances with peak_util >= 2.0; below it, nothing set at all, so those
#          runs are byte-identical to control and are here only to confirm that.
#
#   peak_util   P36 4.66   P13 4.09   P2 3.29   P23 2.79   P11 2.14  |  P16 1.23  P3 1.18  P1 1.02
#
# The five above the cut carry the claim; the three below are the no-harm check and must come back
# identical or within the ordinary run-to-run spread.
#
# WHAT WOULD MAKE IT FAIL, named first.  If the one M=2 worker in the default already collects most
# of the gain, the -17% collapses toward the -5.1% that M=2 measured on P13 at WORKERS=1, and the
# change stops being worth a rebuild this close to the deadline.
set -u
cd /home/user/oraclemaster/research/exact_packer/session2/recon || exit 1
while [ "$(cat harness/CURRENT 2>/dev/null)" != "idle" ]; do sleep 15; done
echo mfinal > harness/CURRENT
L=results/audit/mfinal.log
mkdir -p results/audit; touch $L
ci(){ ( cd "$(git rev-parse --show-toplevel)" \
        && git add research/exact_packer/session2/recon/results/audit/mfinal.log \
                  research/exact_packer/session2/recon/harness/CURRENT \
                  research/exact_packer/session2/recon/harness/mfinal.sh \
        && git commit -q -m "in-flight: mfinal $1" \
        && git push -q origin claude/repair-plan-model-1ig6it ) >/dev/null 2>&1; }
run(){ local tag="$1" p="$2" envs="$3"
    grep -vE '^# ' $L 2>/dev/null | grep -q "\[$tag\]" && return
    echo "# [$tag]" >> $L
    env $envs timeout 200 /usr/bin/python3.12 harness/run1.py myalgorithm $p 60 \
        "[$tag]" --data data/stage2 >> $L 2>&1 || echo "P$p [$tag] CRASH rc=$?" >> $L
    ci "$tag"; }
for rep in 1 2 3; do
  for p in 2 36 13 23 11; do
    run "c.p$p.r$rep" $p "OGC_DUMMY=0"      # shipped default
    run "t.p$p.r$rep" $p "OGC_MSET=8"       # the rule, above the cut
  done
  for p in 16 3 1; do
    run "c.p$p.r$rep" $p "OGC_DUMMY=0"      # below the cut: rule changes nothing
  done
done
echo "MFINALDONE" >> $L
echo idle > harness/CURRENT

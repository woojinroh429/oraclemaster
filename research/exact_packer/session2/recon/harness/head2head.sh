#!/bin/bash
# THE SUBMITTED ARTIFACT AGAINST THE NEW ONE, UNZIPPED, NOT THE WORKING TREE.
#
# wdef's arm A is byte-for-byte the configuration in OGC2026_dirgate.zip -- verified by unzipping
# it: RESFRAC "0.50", no OGC_CPUCAP, OGC_ROUNDS defaulting to 1.  So the -17.36% already applies to
# that file.  What wdef did NOT use is the shipped .so files from either zip; it ran the working
# tree against locally built extensions.
#
# This runs each ZIP'S OWN extracted contents -- its myalgorithm.py and its five compiled modules --
# so nothing about the comparison depends on the build tree being what I think it is.
#
# P1 and P3 only, the two instances named as the target, three draws each.  No WORKERS in the
# environment, so both sides pick their own worker count exactly as the grader would.
set -u
cd /home/user/oraclemaster/research/exact_packer/session2/recon || exit 1
while [ "$(cat harness/CURRENT 2>/dev/null)" != "idle" ]; do sleep 15; done
echo head2head > harness/CURRENT
L=results/audit/head2head.log
S=/tmp/claude-0/-home-user-oraclemaster/55043662-747d-5eda-b837-388adc057292/scratchpad
mkdir -p results/audit; touch $L
ci(){ ( cd "$(git rev-parse --show-toplevel)" \
        && git add research/exact_packer/session2/recon/results/audit/head2head.log \
                  research/exact_packer/session2/recon/harness/CURRENT \
                  research/exact_packer/session2/recon/harness/head2head.sh \
        && git commit -q -m "in-flight: head2head $1" \
        && git push -q origin claude/repair-plan-model-1ig6it ) >/dev/null 2>&1; }
run(){ local tag="$1" dir="$2" p="$3"
    grep -vE '^# ' $L 2>/dev/null | grep -q "\[$tag\]" && return
    echo "# [$tag]" >> $L
    ( cd "$dir" && OGC_WSTAT=1 timeout 220 /usr/bin/python3.12 harness/run1.py myalgorithm $p 60 \
        "[$tag]" --data data/stage2 ) >> $L 2>&1 || echo "P$p [$tag] CRASH rc=$?" >> $L
    ci "$tag"; }
for rep in 1 2 3; do
  for p in 1 3; do
    run "old.p$p.r$rep" $S/dg      $p
    run "new.p$p.r$rep" $S/ziptest $p
  done
done
echo "H2HDONE" >> $L
echo idle > harness/CURRENT

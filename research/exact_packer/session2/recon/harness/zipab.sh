#!/bin/bash
# THE TWO ZIPS, HEAD TO HEAD, AS THE GRADER RUNS THEM.
#
# WHY THIS EXISTS.  Everything measured today was a knob inside one working tree.  The user holds
# two actual artifacts and the question that matters is which of THOSE scores better -- not which
# environment variable wins in isolation.  This runs each zip from its own extracted directory,
# with its own .so files, no environment set, exactly as the grader would.
#
#     zA  OGC2026_gate_endpad.zip   scored 69,827,705, 6 of 8 against the competitor
#     zB  OGC2026_ffport.zip        the one I sent and then told you not to submit
#
# WHAT zB ACTUALLY CONTAINS, because it is not just FFSET.  Diffing the two:
#
#     myalgorithm.py   OGC_STEPS  (default "1,2" -- identical to the old hard-coded tuple)
#                      OGC_FFSET  (default "0.85,0.6" -- the change measured in ffport)
#     ogc_fast.so      DIFFERS -- it carries the PERMARG width-controller patch, which I had
#                      already measured and rejected (12 paired cells, mean +0.80%, prob_1 +3.92%)
#
# It got in because permarg.sh restores the .so it swaps into the working tree, but
# build_submission.sh compiles from ogc_fast.cpp and the SOURCE was left patched with the default
# ON.  So zB is FFSET's gain mixed with a measured loss, and no knob-level result predicts what the
# combination does.  That is the honest reason to measure the artifact rather than reason about it.
#
# WHAT WOULD MAKE THIS MISLEAD, named first.  One paired draw per instance, and the per-instance
# noise measured today is large -- prob_1 22.9%, prob_16 17.9% on identical code, against prob_3
# 1.2% and prob_7 0.0%.  So a single instance moving 5% here is not evidence.  What 14 paired
# instances CAN support is the sign of the aggregate and the count of wins, which is what
# per-instance rank scoring actually pays for.
#
# Instances chosen to span what is known: prob_1 (where FFSET wins big), prob_2/27/33 (where it
# lost 6.8-8.9%), prob_3/16/20 (the ffport set), and prob_5/7/10/13/24/26/30 for breadth.
set -u
cd /home/user/oraclemaster/research/exact_packer/session2/recon || exit 1
. harness/lock.sh
lock_acquire zipab
S=/tmp/claude-0/-home-user-oraclemaster/55043662-747d-5eda-b837-388adc057292/scratchpad
D="$PWD/data/stage2"
L=results/audit/zipab.log
mkdir -p results/audit; touch $L
ci(){ ( cd "$(git rev-parse --show-toplevel)" \
        && git add research/exact_packer/session2/recon/results/audit/zipab.log \
                  research/exact_packer/session2/recon/harness/CURRENT \
                  research/exact_packer/session2/recon/harness/zipab.sh \
        && git commit -q -m "in-flight: zipab $1" \
        && git push -q origin claude/repair-plan-model-1ig6it ) >/dev/null 2>&1; }
run(){ local z="$1" p="$2" rep="$3" _s _e
    local tag="$z.p$p.r$rep"
    grep -vE '^# ' $L 2>/dev/null | grep -q "\[$tag\]" && return
    echo "# [$tag]" >> $L
    _s=$(date +%s.%N)
    ( cd "$S/$z" && timeout 200 /usr/bin/python3.12 run1.py myalgorithm "$p" 60 "[$tag]" --data "$D" ) >> $L 2>&1 \
        || echo "P$p [$tag] CRASH rc=$?" >> $L
    _e=$(date +%s.%N)
    echo "# WALL [$tag] $(awk -v a="$_s" -v b="$_e" 'BEGIN{printf "%.2f", b-a}')" >> $L
    ci "$tag"; }
for rep in 1 2; do
  for p in 1 2 27 33 3 16 20 5 7 10 13 24 26 30; do
    run zA $p $rep
    run zB $p $rep
  done
done
echo "ZIPABDONE" >> $L
lock_release zipab

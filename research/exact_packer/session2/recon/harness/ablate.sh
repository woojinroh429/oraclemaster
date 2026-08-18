#!/bin/bash
# Is `bay` worth its 19.4%?  Is `brk` worth its 7.1%?  Asked as an ablation across the WHOLE
# practice set, not as a verdict per instance.
#
# WHY THE WHOLE SET.  prob_36 answers the same question twice with a 3.2% spread and answers it
# 8.4% differently from one hour to the next, while the effects being chased are under 1%.  No
# number of replicates on one instance beats that.  Forty PAIRED instances do: per-instance
# noise is roughly symmetric, so a systematic effect shows up in the SIGN COUNT even when every
# single pair is inside its own noise.  28 of 40 in one direction is p < 0.01; 20 of 40 is
# nothing.  This is the test that should have judged the late window.
#
# Shipped configuration -- four workers, defaults -- because that is what is being asked about.
# Arms interleaved per instance so a slow patch of machine hits all three alike.
cd "$(dirname "$0")/.."
L=results/audit/ablate.log; : > $L
for p in $(seq 1 40); do
  for arm in full nobay nobrk; do
    case $arm in
      full)  OPS="" ;;
      nobay) OPS="beam,grow,bal,pref,brk" ;;
      nobrk) OPS="beam,grow,bal,pref,bay" ;;
    esac
    OGC_OPS="$OPS" /usr/bin/python3.12 harness/run1.py myalgorithm $p 180 "$arm" \
        --data data/stage2 >> $L 2>&1
  done
done
echo ABLATEDONE >> $L

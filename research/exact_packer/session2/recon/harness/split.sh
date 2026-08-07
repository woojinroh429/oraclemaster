#!/bin/bash
# BEAMCAP, ASKED DETERMINISTICALLY.
#
# OGC_BEAMCAP caps the SECONDS one beam draw may ask for, so a 240 s worker takes ~14 narrow draws
# instead of ~10 wide ones.  Measured in wall-clock it was unreadable: rep1 said prob_16 +2.73% and
# rep2 said -1.55%, prob_20 said -5.02% then +1.32%, and the baseline itself spans 19.6% on
# prob_16.  Four cells never separated "searches better" from "did more work".
#
# In work units the same question has no noise in it:
#
#     given a TOTAL work budget W, is min over one draw of W better or worse than
#     min over n draws of W/n?
#
# That is exactly what the cap trades.  A worker's beam share in a 240 s run is roughly 30,000
# state expansions (140 s of beam at ~225 expansions/s measured on prob_16), taken today as ~10
# draws; the cap makes it ~14.  So the splits below bracket both.
#
# Draw i runs axis (i mod 6), which is what _worker does -- axes[gen % len(axes)] -- so the split
# is compared against the real rotation and not against n copies of one configuration.
#
# THE SECOND HALF OF THE MEASUREMENT IS THE WALL TIME, and it is printed for every draw.  Equal
# work is not equal time: each draw re-enters the engine and rebuilds occupancy, so n draws of W/n
# cost more seconds than one draw of W.  If a split wins on work and loses on seconds it does not
# ship.  Recording both is the point -- it is the distinction that was missing all day.
set -u
cd "$(dirname "$0")/.." || exit 1
echo split > harness/CURRENT
( cd "$(git rev-parse --show-toplevel)" \
  && git add research/exact_packer/session2/recon/harness/CURRENT \
  && git commit -q -m "queue: CURRENT=split" \
  && git push -q origin claude/repair-plan-model-1ig6it ) >/dev/null 2>&1
L=results/audit/split.log
mkdir -p results/audit; touch $L

W=24000                      # total work per arm, per instance

for p in 16 4 24 20; do
  for n in 1 4 8 12 16; do
    per=$(( W / n ))
    for ((i=0;i<n;i++)); do
      ax=$(( i % 6 ))
      tag="p$p.n$n.d$i"
      grep -vE '^# ' $L 2>/dev/null | grep -q "\[$tag\]" && continue
      echo "# [$tag]" >> $L
      timeout 1200 /usr/bin/python3.12 harness/beam1.py $p --work $per --axis $ax \
          --tag "[$tag]" >> $L 2>&1 || echo "P$p [$tag] CRASH rc=$?" >> $L
    done
    ( cd "$(git rev-parse --show-toplevel)" \
      && git add research/exact_packer/session2/recon/results/audit/split.log \
                research/exact_packer/session2/recon/harness/CURRENT \
      && git commit -q -m "in-flight: split p$p n$n" ) >/dev/null 2>&1
  done
  echo "PROBDONE $p" >> $L
done
echo "SPLITDONE" >> $L
echo idle > harness/CURRENT

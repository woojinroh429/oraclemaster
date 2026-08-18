#!/bin/bash
# THE WORKER PORTFOLIO IS A FIXED 2:2 AND THE RIGHT ANSWER IS 4:0 OR 0:4, WORTH +-18%.
#
# _worker sets OGC_BEAMAIM from OGC_AIMSET, default "0.90,0.10", indexed by wid % 2.  aim is the
# fraction of its slice a beam may spend, and it feeds the width directly: left = budget*AIM -
# elapsed, Bcur = left/(per*rem).  So workers 0 and 2 run deep and workers 1 and 3 run shallow.
#
# Measured, for the first time, from BEAMSTAT's new work= field on real 240 s runs:
#
#     aim 0.90   used~0.88  salv=0  level=1.00   work 3,258 .. 9,666
#     aim 0.10   used=0.10  salv=1  level=0.13-0.38   work 41 .. 115
#
# The shallow half completes 13-38% of its levels and is finished by greedy rollout.  Those are not
# beam solutions.
#
# Then, across 877 logged runs with four workers (round 0 only), taking min(wid 0, wid 2) as the
# deep answer and min(wid 1, wid 3) as the shallow one:
#
#     P16  shallow 133/153  -17.96%     P1   deep 107/121  +18.06%
#     P20  shallow 132/140  -17.84%     P4   deep  23/27   + 8.82%
#     P36  shallow  12/12   -13.93%     P34  deep   7/11   + 8.32%
#     P26  shallow  48/61   -10.01%     P3   deep  34/52   + 1.28%
#     P30  shallow  45/56   - 9.10%     P12  deep  30/53   + 0.95%
#     P24  shallow  20/26   - 5.02%     P6   even  59/65   - 0.51%
#
# It splits by instance and it splits along the orientation line: every instance where DEEP wins
# is a 12-orientation instance (P1 99.3%, P4 99.6%, P3 96.0%), and those are the LOOSE ones --
# peak concurrent area over bay area, median 76.9% against 119.3% for the 8-orientation set.  Where
# there is room, the beam's lookahead pays; where placement is forced, a greedy rollout is as good
# and many cheap draws beat few deep ones.
#
# AND THE MECHANISM MEANT TO ADAPT THIS DOES NOT MOVE.  The ratchet is
#     salvaged -> aim = max(0.10, aim*0.60) ;  width_capped -> aim = min(0.90, aim+0.10)
# A shallow worker always salvages, so it floors at 0.10, and its width never reaches Bmax, so it
# can never climb.  A deep worker reports capped=1 and stays at 0.90.  Neither population moves:
# the "adaptive" aim is a constant 2:2 split in practice.
#
#     base   0.90,0.10    as shipped
#     deep   0.90         all four workers deep
#     shal   0.10         all four workers shallow
#
# INSTANCES SPAN BOTH POLES DELIBERATELY -- P16 and P20 where shallow wins by ~18%, P1 and P4 where
# deep wins by 9-18%, P6 where it is a wash.  Measuring only one pole would produce a confident
# conclusion that is wrong on half the hidden set.
#
# It also separates a confound in the 877-run table: wid picks BOTH the aim and the starting axis
# (axes[(wid+i) % 6]), so "deep vs shallow" there is entangled with "axes {0,2} vs {1,3}".
# OGC_AIMSET changes the aim and leaves the axis rotation alone.
#
# Read with:  python3.12 harness/beamside.py results/audit/aimsplit.log base
set -u
cd "$(dirname "$0")/.." || exit 1
echo aimsplit > harness/CURRENT
( cd "$(git rev-parse --show-toplevel)" \
  && git add research/exact_packer/session2/recon/harness/CURRENT \
  && git commit -q -m "queue: CURRENT=aimsplit" \
  && git push -q origin claude/repair-plan-model-1ig6it ) >/dev/null 2>&1
L=results/audit/aimsplit.log
mkdir -p results/audit; touch $L

run(){ # rep arm prob aimset
    local tag="r$1.$2.$3"
    grep -vE '^# ' $L 2>/dev/null | grep -q "\[$tag\]" && return
    echo "# [$tag]" >> $L
    OGC_AIMSET="$4" OGC_WSTAT=1 OGC_BEAMSTAT=1 timeout 1200 \
        /usr/bin/python3.12 harness/run1.py myalgorithm $3 240 "[$tag]" --data data/stage2 \
        >> $L 2>&1 || echo "P$3 [$tag] CRASH rc=$?" >> $L
    ( cd "$(git rev-parse --show-toplevel)" \
      && git add research/exact_packer/session2/recon/results/audit/aimsplit.log \
                research/exact_packer/session2/recon/harness/CURRENT \
      && git commit -q -m "in-flight: aimsplit $tag" ) >/dev/null 2>&1
}

for rep in 1 2; do
  for p in 16 1 20 4 6; do
    run $rep base $p "0.90,0.10"
    run $rep deep $p "0.90"
    run $rep shal $p "0.10"
  done
  echo "REPDONE $rep" >> $L
done
echo "AIMSPLITDONE" >> $L
echo idle > harness/CURRENT

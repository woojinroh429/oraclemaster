#!/bin/bash
# THE BEST WORKER COUNT DEPENDS ON INSTANCE SIZE, AND WE USE A CONSTANT.
#
# cliff.log, all at 30 s on the submission zip:
#
#     P13 (peak_util 4.09)   nw=1  87,984,880   nw=3  87,874,924   nw=4  67,982,224   nw=7  FLOOR
#     P25 (peak_util 6.26)   nw=1  90,954,876   nw=3     FLOOR     nw=4     FLOOR     nw=7  FLOOR
#
# On the largest instance ONLY a single worker returns a real answer; three, four and seven all come
# back with _safe_sequential, 4,255,755,887 against 90,954,876 -- a factor of 47.  On P13 the
# optimum is four.  The shipped rule is cpu_count-1 regardless of instance.
#
# THE MECHANISM IS A THRESHOLD, NOT A TREND.  A beam draw either completes or returns nothing, and
# the compute it needs scales with the instance.  Splitting the allowance N ways can put every
# worker below that threshold at once, so the whole portfolio returns empty together and the safety
# net becomes the answer.  Bigger instance, lower N at which that happens.
#
# WHAT IT IS WORTH.  Everything else measured today moves the band by single digits.  This is 47x on
# one instance, and the finals set is eight instances scored together.
#
# CONFOUND, NAMED: nw=1 does not go through _pool_round -- `out = [_worker(...)]` runs it in process
# -- so part of its margin may be the absence of spawn and pickling rather than compute per worker.
# That does not change which setting wins, but it makes nw=1's margin an upper bound on the
# "more compute per worker" explanation.
#
# GRID: eight instances spanning the range, four worker counts, two draws, 30 s.  The small
# instances are here to check that any size rule does not cost them.
#
#     small   P1  (1.02)   P3  (1.18)
#     mid     P16 (1.23)   P2  (3.29)
#     large   P13 (4.09)   P23 (2.79)   P36 (4.66)   P25 (6.26)
set -u
cd /home/user/oraclemaster/research/exact_packer/session2/recon || exit 1
while [ "$(cat harness/CURRENT 2>/dev/null)" != "idle" ]; do sleep 15; done
echo nwsize > harness/CURRENT
L=results/audit/nwsize.log
S=/tmp/claude-0/-home-user-oraclemaster/55043662-747d-5eda-b837-388adc057292/scratchpad
mkdir -p results/audit; touch $L
ci(){ ( cd "$(git rev-parse --show-toplevel)" \
        && git add research/exact_packer/session2/recon/results/audit/nwsize.log \
                  research/exact_packer/session2/recon/harness/CURRENT \
                  research/exact_packer/session2/recon/harness/nwsize.sh \
        && git commit -q -m "in-flight: nwsize $1" \
        && git push -q origin claude/repair-plan-model-1ig6it ) >/dev/null 2>&1; }
run(){ local tag="$1" p="$2" w="$3"
    grep -vE '^# ' $L 2>/dev/null | grep -q "\[$tag\]" && return
    echo "# [$tag]" >> $L
    ( cd "$S/zt" && env WORKERS=$w timeout 200 /usr/bin/python3.12 harness/run1.py myalgorithm $p 30 \
        "[$tag]" --data data/stage2 ) >> $L 2>&1 || echo "P$p [$tag] CRASH rc=$?" >> $L
    ci "$tag"; }
for rep in 1 2; do
  for p in 25 13 23 36 16 2 1 3; do
    for w in 1 2 3 4; do
      run "n.p$p.w$w.r$rep" $p $w
    done
  done
done
echo "NWSIZEDONE" >> $L
echo idle > harness/CURRENT

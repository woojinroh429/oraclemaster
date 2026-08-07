#!/bin/bash
# THE SCORE IS A MINIMUM, SO BUY SPREAD -- NOT A BETTER AVERAGE.
#
# This queue exists because the previous one failed in an informative direction.  OGC_BEAMCAP
# capped what a single beam draw may ask for, which raised the draw count on prob_16 from 30 to 43
# and did this:
#
#     P16  base    min 3,479,878   median worker 3,860,013   spread 24.15%
#     P16  cap12   min 3,574,878   median worker 3,822,046   spread 17.95%
#     P16  cap20   min 3,528,888   median worker 3,823,143   spread 17.32%
#     P4   base    min 2,554,029   cap12 2,554,029 (tie)     cap20 2,737,344 (+7.18%)
#
# The median worker IMPROVED and the minimum got WORSE, and the spread fell in every capped cell.
# The reported answer is min over workers, so it is set by the left tail of the draw distribution,
# not by its centre.  Tightening the distribution is the wrong move by construction.
#
# The record already contained the counterexample and it was read backwards.  prob_16's best ever
# 240 s answer, 2,795,643, came from the OGC_ADAPTB=0 arm -- the arm with the LARGEST spread of
# anything tried, 27.9% -- and that arm was rejected in the pin queue for "failing to reduce
# variance".  Under a min-of-N rule, spread at equal centre is the thing you pay for.
#
#     base   as shipped
#     pinb   OGC_ADAPTB=0                pins ogc_fast's per-level width; the 2,795,643 arm,
#                                        re-judged on the minimum instead of on its spread
#     jit    OGC_AXJIT=0.25              per-draw jitter of the continuous axis terms
#     both   OGC_ADAPTB=0 OGC_AXJIT=0.25
#
# Why jitter is not just another knob.  _fresh takes no random input: problem, seconds, and one of
# six axis dicts, into a deterministic beam.  The set of constructions a run can reach is SIX, and
# a 240 s run takes thirty draws out of it.  Jitter is seeded on (wid, gen), so it is reproducible
# and it turns those thirty repeats into thirty distinct samples without changing the count, the
# width policy, or the budget.
#
# 0.25 is a scale, not a tuning: a term is multiplied by between 1/1.25 and 1.25.  If spread is
# what pays, this should show at any sane setting; if it only works at one value, it is noise.
#
# prob_4 guards against fitting prob_16 -- it improves with budget where prob_16 does not, and
# 12.6% of its answer comes from operators none of these arms touch.  prob_24 repeats to the digit,
# so anything that moves there is the arm.
#
# Read with:  python3.12 harness/beamside.py results/audit/spread.log base
set -u
cd "$(dirname "$0")/.." || exit 1
echo spread > harness/CURRENT
( cd "$(git rev-parse --show-toplevel)" \
  && git add research/exact_packer/session2/recon/harness/CURRENT \
  && git commit -q -m "queue: CURRENT=spread" \
  && git push -q origin claude/repair-plan-model-1ig6it ) >/dev/null 2>&1
L=results/audit/spread.log
mkdir -p results/audit; touch $L

run(){ # rep arm prob env
    local tag="r$1.$2.$3"
    grep -vE '^# ' $L 2>/dev/null | grep -q "\[$tag\]" && return
    echo "# [$tag]" >> $L
    env $4 OGC_WSTAT=1 timeout 1200 /usr/bin/python3.12 harness/run1.py myalgorithm \
        $3 240 "[$tag]" --data data/stage2 >> $L 2>&1 \
        || echo "P$3 [$tag] HANG-OR-CRASH rc=$?" >> $L
    ( cd "$(git rev-parse --show-toplevel)" \
      && git add research/exact_packer/session2/recon/results/audit/spread.log \
                research/exact_packer/session2/recon/harness/CURRENT \
      && git commit -q -m "in-flight: spread $tag" ) >/dev/null 2>&1
}

for rep in 1 2; do
    for p in 16 4 24 20; do
        run $rep base $p ""
        run $rep pinb $p "OGC_ADAPTB=0"
        run $rep jit  $p "OGC_AXJIT=0.25"
        run $rep both $p "OGC_ADAPTB=0 OGC_AXJIT=0.25"
    done
    echo "REPDONE $rep" >> $L
done
echo "SPREADDONE" >> $L
echo beamhard > harness/CURRENT
nohup bash harness/beamhard.sh >> results/beamhard.log 2>&1 < /dev/null &

#!/bin/bash
# THE ONLY CONFIGURATION THAT KEEPS ALL THREE.
#
# The bound is worth 545,561 on P6 (30,111,690 -> 29,566,129, reproduced twice, about five times
# that instance's spread) and about 2.2% on P5, while costing P3 7.7% (80,795 -> 86,975).  Choosing
# between them is a losing framing: what is actually wanted is the bound ON with P3's loss removed.
#
# P3's loss has a known shape.  80,795 appears only in runs where brk constructs 83,095, and that
# comes from one particular incumbent (base 107,195) which the bound-on trajectory never visits.
# brk draws 8-17 samples from a distribution whose yield ranges 6,590-31,315, all from pool[0].
# Widening where it draws is the intervention; whether it recovers 80,795 WITH the bound on is the
# question this measures.
#
# Rate 0.0 with the bound on is the control that isolates the sampling from the bound: it should
# reproduce 86,975 / 87,175.  If it does not, the comparison is measuring something else and the
# rest of the sweep means nothing.
set -u
cd "$(dirname "$0")/.." || exit 1
mkdir -p results
exec 8>"/tmp/ogc_$(basename "$0").lock"
flock -n 8 || { echo "another $(basename "$0") is already running"; exit 0; }
exec 9>/tmp/ogc_experiment.lock
flock 9 || exit 1

for rate in 0.0 0.34 0.5; do
  for r in 1 2 3; do
    tag=$(echo "$rate" | tr -d '.')
    f="results/bpon_${tag}_r${r}.log"
    [ -s "$f" ] && continue
    OGC_PRUNE=1 OGC_BRKPOOL=$rate BRK_DEBUG=1 timeout 1500 \
        python3.12 harness/run1.py myalgorithm 3 240 "brkpool+bound $rate r$r" > "$f" 2>&1
    echo "    $(grep -h '^P3 ' "$f" | tail -1)"
    echo "      brk: $(grep -o 'obj [0-9]* vs base [0-9]*' "$f" | tr '\n' '|')"
    ( cd ../../.. && git add -f "research/exact_packer/session2/recon/$f" >/dev/null 2>&1 \
      && git commit -q -m "brkpool+bound $rate r$r" >/dev/null 2>&1 \
      && git push -q origin claude/repair-plan-model-1ig6it >/dev/null 2>&1 )
  done
done
echo "brkpool_on done $(date -u +%H:%M:%S)"

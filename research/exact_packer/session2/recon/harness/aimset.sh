#!/bin/bash
# Four workers stacked on two beam aims, or spread across four?
#
# THE LEVER ROUNDS COULD NOT BE.  Rounds failed because buying more draws means shortening each
# one, and at 60 s that trade loses (mean +2.43% at R=2, and P1 alone gave up 40%).  This changes
# what the four draws ARE without touching how long any of them gets: same wall clock, same core
# count, same everything except how alike the workers are.
#
# WHY THE CURRENT SPLIT IS WORTH DOUBTING.  Even workers run beam aim 0.90 and odd ones 0.10, and
# that 2:2 exists because 0.10 measured -24.3% to -11.9% on 250-300 block instances while costing
# +25.09% on prob_1 -- both settings had to be in the portfolio, so both went in.  Every one of
# those numbers was taken at 180 s.  The competition budget is 60 s, where the beam gets through
# far less of the instance, and the split has never been re-checked there.  If at 60 s one aim
# never supplies the minimum, two of four cores are producing draws the answer discards.
#
# The alternative the source already names: spread the aims instead of stacking them.  OGC_AIMSET
# is read as a list and indexed by wid, so "0.90,0.45,0.20,0.10" gives four distinct workers where
# today there are two pairs.  No code changes, nothing hard-coded about any instance, and the
# minimum still discards whichever loses.
#
#   arm  pair    OGC_AIMSET=0.90,0.10             (shipped default, 2+2)
#   arm  spread  OGC_AIMSET=0.90,0.45,0.20,0.10   (4 distinct)
#   arm  low     OGC_AIMSET=0.10                  (all four low -- the control that says whether
#                                                  the portfolio is worth anything at all here)
#
# The `low` arm matters: if it matches `pair`, the high-aim workers were contributing nothing and
# the portfolio is theatre on this budget.  If it is much worse, they are carrying instances and
# the split is right even where it looks idle.
#
# Runs AFTER axis, which says whether there is anything to fix.  Rep-major, worst-case ranked.
set -u
cd "$(dirname "$0")/.." || exit 1
echo aimset > harness/CURRENT
L=results/audit/aimset.log
mkdir -p results/audit; touch $L

run(){ # rep arm aims prob
    local tag="r$1.$2.$4"
    # SKIP ON A RESULT, NOT ON THE MARKER.  The marker is written BEFORE the run, so a queue
    # killed mid-cell leaves an orphan "# [tag]" line with no result -- and this test then
    # matched it on resume and skipped the cell forever.  Nine such orphans existed across
    # today's logs, including one this session was actively waiting on (w3grid r1.dn.26).
    # In a paired design a lost arm silently invalidates the whole instance.  Excluding the
    # marker lines makes the test key on evidence the run finished.
    grep -vE '^# ' $L 2>/dev/null | grep -q "\[$tag\]" && return
    echo "# [$tag]" >> $L
    OGC_AIMSET="$3" OGC_WSTAT=1 timeout 300 /usr/bin/python3.12 harness/run1.py myalgorithm $4 60 \
        "[$tag]" --data data/stage2 >> $L 2>&1
    ( cd "$(git rev-parse --show-toplevel)" \
      && git add research/exact_packer/session2/recon/results/audit/aimset.log \
      && git commit -q -m "in-flight: aimset $tag" ) >/dev/null 2>&1
}

for rep in 1 2 3 4 5; do
    for p in 1 12 16 26 6 3 20 30; do
        run $rep pair   "0.90,0.10"           $p
        run $rep spread "0.90,0.45,0.20,0.10" $p
        run $rep low    "0.10"                $p
    done
    echo "REPDONE $rep" >> $L
done
echo "AIMSETDONE" >> $L
echo idle > harness/CURRENT

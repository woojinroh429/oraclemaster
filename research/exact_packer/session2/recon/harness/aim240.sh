#!/bin/bash
# DOES THE AIM SPLIT PAY BY OBJECTIVE CLASS, AT THE REAL BUDGET?
#
# results/audit/bytype.md re-read the aimset log by what each instance's objective is made of and
# found the only sign-consistent result of the session: against a control with all four workers at
# beam aim 0.10, the shipped 0.90/0.10 split was worse on 4 of 4 tardiness-dominated instances
# (median +2.95%) and better on 3 of 3 preference-dominated ones (median -2.80%).  Pooled that is
# +0.18%, which is what was reported at the time as no effect.
#
# Two reasons it is worth the machine time before anything is built: the knob already exists
# (OGC_AIMSET), and the class is not an instance property that has to be guessed -- it is
# prob_info["weights"] times any solution's Z1/Z2/Z3, and _safe_sequential yields a solution at no
# cost.  If the rule holds, choosing the aim set per instance is a few lines and no new search.
#
# What could make it not hold, and is the reason the Z3-dominated instances are IN this queue
# rather than assumed: if `low` also wins on the preference-dominated class, there is no class
# rule -- 0.10 is simply better and the shipped split should just be replaced.  That is a
# different and simpler conclusion, and this design can return it.
#
# The prior evidence is n=4 and n=3 at a 60 s limit.  This is 240 s, eight tardiness-dominated
# instances spanning 61-98% Z1 and six preference-dominated spanning 76-94% Z3, two replicates,
# classes interleaved so an early stop still has both.
set -u
cd "$(dirname "$0")/.." || exit 1
echo aim240 > harness/CURRENT
L=results/audit/aim240.log
mkdir -p results/audit; touch $L

run(){ # rep arm prob aimset
    local tag="r$1.$2.$3"
    # SKIP ON A RESULT, NOT ON THE MARKER.  The marker is written BEFORE the run, so a queue
    # killed mid-cell leaves an orphan "# [tag]" line with no result -- and this test then
    # matched it on resume and skipped the cell forever.  Nine such orphans existed across
    # today's logs, including one this session was actively waiting on (w3grid r1.dn.26).
    # In a paired design a lost arm silently invalidates the whole instance.  Excluding the
    # marker lines makes the test key on evidence the run finished.
    grep -vE '^# ' $L 2>/dev/null | grep -q "\[$tag\]" && return
    echo "# [$tag]" >> $L
    OGC_AIMSET="$4" OGC_WSTAT=1 timeout 960 /usr/bin/python3.12 harness/run1.py myalgorithm $3 240 \
        "[$tag]" --data data/stage2 >> $L 2>&1 \
        || echo "P$3 [$tag] HANG-OR-CRASH rc=$?" >> $L
    ( cd "$(git rev-parse --show-toplevel)" \
      && git add research/exact_packer/session2/recon/results/audit/aim240.log \
      && git commit -q -m "in-flight: aim240 $tag" ) >/dev/null 2>&1
}

# interleaved: Z1-dominated then Z3-dominated, alternating, so a partial queue covers both classes
ORDER="2 34 25 12 36 3 20 21 6 22 30 1 16 26"
for rep in 1 2; do
    for p in $ORDER; do
        run $rep base $p "0.90,0.10"
        run $rep low  $p "0.10"
    done
    echo "REPDONE $rep" >> $L
done
echo "AIM240DONE" >> $L
echo idle > harness/CURRENT

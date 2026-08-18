#!/bin/bash
# prob_7, WHICH MAY BE THE PRACTICE PROXY FOR HIDDEN P1, AND WHICH THIS BUILD NEVER MEASURED.
#
# THE REASON THIS EXISTS.  A competitor reports that reducing prob_7 moved their HIDDEN P1 a long
# way.  Everything this study has done for hidden P1 was aimed at practice prob_1 on the assumption
# that the names correspond; if the real correspondence is prob_7, then the -9.03% the fill gate
# bought on prob_1 may be buying nothing where it counts, and prob_7 is the instance to judge on.
#
# It is second-hand and it is one data point, so it is not treated as established -- but prob_7 is
# inside DIRGATE's firing set {1,3,7,16,27,33} and it is the one member of that set the fill gate
# was never measured on.  ffwall covered prob_1, prob_3, prob_16, prob_2, prob_13.  prob_7, prob_27
# and prob_33 are untested with FILLFLOOR at 10, and they are shipping with it.
#
# THAT GAP IS THE POINT REGARDLESS OF WHOSE INSTANCE MAPS TO WHAT.  A global default went into a
# build on evidence from five instances, and three gate members were never asked.  prob_7 carries
# the most Z1-weighted objective of the set (13333 / 7 / 150), so if the recovered tail helps or
# hurts tardiness specifically, this is where it shows.
#
# ARMS: A is FILLFLOOR 40, the old closed gate at 60 s -- what the 72,188,856 build did.  C is
# FILLFLOOR 10, what OGC2026_gate_endpad.zip ships.  Both carry the shipped ENDPAD 5, so this
# isolates the gate and does not re-litigate the margin.
#
# NO WORKERS IN THE ENVIRONMENT.  Whatever nw the shipped code picks is what is judged.
#
# WHAT WOULD MAKE IT FAIL, named first.  If C loses on prob_7, prob_27 or prob_33 by more than the
# -9.03% it wins on prob_1, the gate is a net loss across DIRGATE's own set and the FILLFLOOR
# change comes back out of the build -- the cap removal and ENDPAD stand on their own and do not
# depend on it.  The second failure mode is the wall: prob_7 and prob_33 were never wall-checked
# either, so any cell at or past 60 s of WALL is reported before any objective is.
#
# JUDGED, fixed before the run: paired ratio within replicate, four replicates, three instances.
set -u
cd /home/user/oraclemaster/research/exact_packer/session2/recon || exit 1
. harness/lock.sh
lock_acquire p7gate
L=results/audit/p7gate.log
mkdir -p results/audit; touch $L
ci(){ ( cd "$(git rev-parse --show-toplevel)" \
        && git add research/exact_packer/session2/recon/results/audit/p7gate.log \
                  research/exact_packer/session2/recon/harness/CURRENT \
                  research/exact_packer/session2/recon/harness/p7gate.sh \
        && git commit -q -m "in-flight: p7gate $1" \
        && git push -q origin claude/repair-plan-model-1ig6it ) >/dev/null 2>&1; }
run(){ local tag="$1" p="$2" ff="$3" _s _e
    grep -vE '^# ' $L 2>/dev/null | grep -q "\[$tag\]" && return
    echo "# [$tag]" >> $L
    _s=$(date +%s.%N)
    env OGC_FILLFLOOR=$ff OGC_WSTAT=1 timeout 200 /usr/bin/python3.12 \
        harness/run1.py myalgorithm $p 60 "[$tag]" --data data/stage2 >> $L 2>&1 \
        || echo "P$p [$tag] CRASH rc=$?" >> $L
    _e=$(date +%s.%N)
    echo "# WALL [$tag] $(awk -v a="$_s" -v b="$_e" 'BEGIN{printf "%.2f", b-a}')" >> $L
    ci "$tag"; }
# prob_7 first and at every replicate, because it is the one the report points at.
for rep in 1 2 3 4; do
  for p in 7 27 33; do
    run "A.p$p.r$rep" $p 40
    run "C.p$p.r$rep" $p 10
  done
done
echo "P7GATEDONE" >> $L
lock_release p7gate

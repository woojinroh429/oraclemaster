#!/bin/bash
# THE FILL GATE AT THE DEFAULT WORKER COUNT, WHICH IS NOT THE ONE idle60 MEASURED.
#
# idle60 judged arm C (FILLFLOOR 10 at 60 s) across 36 cells and found it safe: on prob_16 it was
# INERT, returning 3,199,896 to the digit in both replicates at 46.09 and 46.87 s.  Every one of
# those cells passed WORKERS=7.
#
# THE SHIPPED PATH DOES NOT.  With the cap removed, nw = min(8, cpu_count()) - 1, which on this
# four-core box is THREE.  A smoke run of the shipped defaults -- no environment at all -- returned:
#
#     prob_1    536,363   WALL 56.43      the best prob_1 draw of the session
#     prob_3  4,748,401   WALL 42.09
#     prob_16 3,230,017   WALL 60.26      OVER, and idle60 said this instance was inert
#     prob_13 68,921,195  WALL 60.07      OVER
#
# The gate opens on DIFFERENT INSTANCES at different worker counts, because what is left after the
# polish depends on how the round consumed its budget, and that depends on the pool.  So "inert on
# prob_16" is a fact about nw=7 and says nothing about nw=3.  This is the same error wdef.sh was
# written to correct -- "EVERY MEASUREMENT TODAY WAS MADE ON A WORKER COUNT THE GRADER WILL NOT
# USE" -- and it has recurred with the worker counts swapped.
#
# NO WORKERS IN THE ENVIRONMENT.  Whatever nw the shipped code picks is what is judged.
#
# ARMS: A is FILLFLOOR 40, which at 60 s is the old closed gate and the dirgate build's behaviour.
# C is FILLFLOOR 10, the change under test.  Paired within replicate on the five instances whose
# margin is known to be thin or whose gate is known to open: prob_16 and prob_13 overran in the
# smoke, prob_2 sat at 59.06-59.91 at nw=7, prob_1 is what the change is for, prob_3 is the other
# DIRGATE instance in the practice set.
#
# WHAT WOULD MAKE IT FAIL, named first, and it is the likely outcome.  If C overruns at nw=3 on
# prob_16 or prob_13 while A does not, the change is disqualified as it stands and the fix is to
# make the gate leave more headroom rather than to abandon it -- the fill round already receives
# `left` as a hard bound and reserves 8 s, so an overrun means one of those two is not being
# honoured and that is a bug worth finding regardless of whether this change ships.
#
# THE OTHER OUTCOME THAT MATTERS: if A ALSO overruns on prob_16 and prob_13, the overrun is
# pre-existing at nw=3 and belongs to the shipped build, not to this change.  That is a more
# serious finding than the gate question, because the shipped build is what scored 72,188,856.
#
# JUDGED, fixed before the run: any arm with a cell over 60.0 s of WALL is disqualified.  Quality
# is read only from arms that survive that test, paired ratio within replicate, median over three.
set -u
cd /home/user/oraclemaster/research/exact_packer/session2/recon || exit 1
. harness/lock.sh
lock_acquire ffwall
L=results/audit/ffwall.log
mkdir -p results/audit; touch $L
if [ "$(lock_box_busy)" -gt 0 ]; then
    echo "# ABORT: solvers already running" >> $L; lock_release ffwall; exit 1
fi
ci(){ ( cd "$(git rev-parse --show-toplevel)" \
        && git add research/exact_packer/session2/recon/results/audit/ffwall.log \
                  research/exact_packer/session2/recon/harness/CURRENT \
                  research/exact_packer/session2/recon/harness/ffwall.sh \
        && git commit -q -m "in-flight: ffwall $1" \
        && git push -q origin claude/repair-plan-model-1ig6it ) >/dev/null 2>&1; }
run(){ local tag="$1" p="$2" ff="$3" _s _e
    grep -vE '^# ' $L 2>/dev/null | grep -q "\[$tag\]" && return
    echo "# [$tag]" >> $L
    _s=$(date +%s.%N)
    env OGC_WSTAT=1 OGC_FILLFLOOR=$ff timeout 200 /usr/bin/python3.12 \
        harness/run1.py myalgorithm $p 60 "[$tag]" --data data/stage2 >> $L 2>&1 \
        || echo "P$p [$tag] CRASH rc=$?" >> $L
    _e=$(date +%s.%N)
    echo "# WALL [$tag] $(awk -v a="$_s" -v b="$_e" 'BEGIN{printf "%.2f", b-a}')" >> $L
    ci "$tag"; }
for rep in 1 2 3; do
  for p in 16 13 2 1 3; do
    run "A.p$p.r$rep" $p 40
    run "C.p$p.r$rep" $p 10
  done
done
echo "FFWALLDONE" >> $L
lock_release ffwall

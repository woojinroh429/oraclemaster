#!/bin/bash
# FILL THE 400% ALLOWANCE, AND STOP DERIVING THE WORKER COUNT FROM A NUMBER WE CANNOT SEE.
#
# MEASURED ON THIS BOX, during a live solve: each worker runs at 99.4-99.6% of a core and the
# PARENT runs at 2.9%.  Three workers is 300% of a 400% allowance -- a quarter of the budget is
# not being used.
#
# THE BIGGER PROBLEM IS NOT THE WASTE, IT IS THE VARIANCE.  nw comes from os.cpu_count(), and the
# organisers' notice says every core stays visible under throttling, so the same build behaves
# two different ways depending on a number we have never observed:
#
#     grader cpu_count()=4   ->  nw=3  ->  300% asked, 100% idle
#     grader cpu_count()=8   ->  nw=7  ->  700% asked, throttled to 400%, ~57% per worker
#
# EVERY LOCAL MEASUREMENT THIS PROJECT HAS TAKEN WAS AT ~100% PER WORKER.  If the grader reports
# eight cores then the shipped build runs in a configuration nothing was measured in -- and it is
# the configuration where prob_13 floored 2 of 2 when forced with WORKERS=7.
#
# PINNING nw TO THE ALLOWANCE REMOVES THE UNKNOWN.  At ~99% per worker plus a ~3% parent, four
# workers is 403% -- the allowance, near exactly -- and it is the same four whether the grader
# reports four cores or sixteen.  That is the whole argument: not that 4 beats 3 on quality, but
# that 4 is the same everywhere and 3-or-7 is a coin flip on hardware we cannot inspect.
#
# WHY THIS IS NOT capfix's CAP COMING BACK.  That capped cpu_count() to 4 in order to REDUCE the
# worker count to 3, on the reasoning that three workers each get a full core and search deeper.
# It was reasoned rather than measured, it was the only unmeasured change in that build, and the
# scoreboard charged 2.11% for it on the six instances only it could touch.  This does the
# opposite -- it RAISES the count where cpu_count() is small -- and it is being measured before it
# ships, on the axis that matters.
#
# WHAT WOULD MAKE IT FAIL, named first, and there are two.
#
# ONE: results/audit already contains 23 pairs finding w3 BEATS w4, which is where `_full - 1`
# came from.  That measurement was taken on a build with neither the fill gate nor ENDPAD, and it
# rested on the parent not being free -- "three workers gives each a full core and change".  The
# parent is 2.9%.  The premise is gone but the measurement is not, and if w3 still wins here it
# wins and the allowance stays partly idle.
#
# TWO, AND IT OUTRANKS QUALITY: more workers means less CPU each, and a worker that does not
# finish inside the deadline contributes nothing.  When none finish the run returns
# _safe_sequential -- on prob_13 that is 4,027,473,504 against 68,921,195, FIFTY-EIGHT TIMES
# WORSE.  prob_13 carries four replicates here for that reason alone.  If WORKERS=4 raises the
# floor rate above WORKERS=3, the extra 100% of CPU is being bought with the disaster and the
# answer is no, whatever the means say.
#
# ARMS: WORKERS 3 (shipped on a four-core box), 4 (the allowance), 5 (deliberately over, so the
# shape of the cost is visible rather than inferred from two points).
#
# JUDGED, fixed before the run: floor count first, then paired quality ratio against WORKERS=3
# within replicate, then the wall.  Any arm that floors more than WORKERS=3 is rejected on that
# alone.
set -u
cd /home/user/oraclemaster/research/exact_packer/session2/recon || exit 1
. harness/lock.sh
lock_acquire cpufill
L=results/audit/cpufill.log
mkdir -p results/audit; touch $L
ci(){ ( cd "$(git rev-parse --show-toplevel)" \
        && git add research/exact_packer/session2/recon/results/audit/cpufill.log \
                  research/exact_packer/session2/recon/harness/CURRENT \
                  research/exact_packer/session2/recon/harness/cpufill.sh \
        && git commit -q -m "in-flight: cpufill $1" \
        && git push -q origin claude/repair-plan-model-1ig6it ) >/dev/null 2>&1; }
run(){ local tag="$1" p="$2" w="$3" _s _e
    grep -vE '^# ' $L 2>/dev/null | grep -q "\[$tag\]" && return
    echo "# [$tag]" >> $L
    _s=$(date +%s.%N)
    env WORKERS=$w OGC_WSTAT=1 timeout 200 /usr/bin/python3.12 \
        harness/run1.py myalgorithm $p 60 "[$tag]" --data data/stage2 >> $L 2>&1 \
        || echo "P$p [$tag] CRASH rc=$?" >> $L
    _e=$(date +%s.%N)
    echo "# WALL [$tag] $(awk -v a="$_s" -v b="$_e" 'BEGIN{printf "%.2f", b-a}')" >> $L
    ci "$tag"; }
# prob_13 first at every replicate: the floor is the deciding axis and it needs the samples.
for rep in 1 2 3 4; do
  for w in 3 4 5; do
    run "w$w.p13.r$rep" 13 $w
  done
done
for rep in 1 2 3; do
  for p in 1 7 16; do
    for w in 3 4 5; do
      run "w$w.p$p.r$rep" $p $w
    done
  done
done
echo "CPUFILLDONE" >> $L
lock_release cpufill

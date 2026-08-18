#!/bin/bash
# WHERE THE UNUSED CORES ARE, AND HOW MUCH THEY ARE WORTH.
#
# WHAT THE omp RUN ESTABLISHED.  The shipped configuration means 269% CPU with nw=3, i.e. 90% of
# the 300% that three workers can use.  I first read the remaining 130 points as headroom against
# the 400% allowance; that was wrong -- with three workers the ceiling is 300%, and peak already
# reaches 345-364% because the parent works too, so a fourth worker would breach the limit rather
# than fill a gap.  The real question is where the missing 10% inside 300% goes.
#
# A 0.25 s CPU trace of one P1 run answers it exactly:
#
#     0- 5s  300%     20-25s  275%      40-45s  314%
#     5-10s  314%     25-30s  191%      45-50s  123%
#    10-15s  315%     30-35s  313%
#    15-20s  314%     35-40s  314%
#
# Two windows, 24.4-27.8 s and 45.6-49.2 s, sit at ~104% with the process count dropping from 5 to
# 2.  That is the SERIAL SECTION BETWEEN WORKER ROUNDS -- the parent running the polish while two
# of three cores do nothing.  About 7.1 s of a 49 s run, 14.5% of the wall clock, at one third of
# the available parallelism.
#
# WHAT THIS IS WORTH, computed rather than asserted, because the number decides whether to touch
# the code at all.  7.1 s x 2 idle cores = ~14 core-seconds.  A worker round on P1 is three workers
# for roughly 20 s, so 14 core-seconds is about 0.7 of one worker draw against the ~6 the run
# already takes.  From the measured draw price list (prob_1: k=6 -> k=12 is -11.0%), one extra
# draw in six is worth roughly 1%.  That is small, and it is the honest size to hold in mind
# before writing any code -- this is not a 6% lever.
#
# WHY MEASURE IT ON MORE INSTANCES FIRST.  The gap's size is set by how long the polish runs, and
# the polish is known to be frequently INERT: results/audit records four different rosters coming
# back with the beam's solution untouched, and myalgorithm.py's own note says _z3_improve "returns
# immediately when it has nothing to do".  An instance where the polish does nothing has no gap to
# recover, and an instance where it runs long has a large one.  P1 alone cannot tell which case is
# typical, and the whole value of the lever is the population average.
#
# WHAT WOULD MAKE THIS MISLEAD, named first.  The trace measures a PROCESS COUNT and a CPU rate,
# not what the parent is doing.  A window at 104% with 2 processes is consistent with the polish
# working hard single-threaded, and equally consistent with the parent spinning while a straggler
# worker finishes -- the second would be recoverable by a different mechanism than the first, and
# the trace cannot separate them.  The per-round WALL vs the reported solve time is carried
# alongside for that reason.
#
# JUDGED, fixed before the run: report, per instance, total seconds below 200% CPU and the implied
# idle core-seconds, as a FRACTION of the run.  No adoption decision is attached -- this run only
# sizes the opportunity.  If the population median is under 10 core-seconds the lever is not worth
# code risk this close to the deadline and that will be stated plainly.
set -u
cd /home/user/oraclemaster/research/exact_packer/session2/recon || exit 1
. harness/lock.sh
lock_acquire idlegap
S=/tmp/claude-0/-home-user-oraclemaster/55043662-747d-5eda-b837-388adc057292/scratchpad
L=results/audit/idlegap.log
mkdir -p results/audit results/audit/traces; touch $L
ci(){ ( cd "$(git rev-parse --show-toplevel)" \
        && git add research/exact_packer/session2/recon/results/audit/idlegap.log \
                  research/exact_packer/session2/recon/results/audit/traces \
                  research/exact_packer/session2/recon/harness/CURRENT \
                  research/exact_packer/session2/recon/harness/idlegap.sh \
        && git commit -q -m "in-flight: idlegap $1" \
        && git push -q origin claude/repair-plan-model-1ig6it ) >/dev/null 2>&1; }
trace(){ local p="$1" rep="$2"
    local tag="p$p.r$rep"
    local T="results/audit/traces/$tag.txt"
    grep -q "^# \[$tag\]" $L 2>/dev/null && return
    echo "# [$tag]" >> $L
    CLK=$(getconf CLK_TCK); : > "$T"
    env OMP_NUM_THREADS=1 timeout 200 bash -c \
        "cd '$S/omp_off' && exec python3.12 run1.py myalgorithm $p 60 '[$tag]' --data '$PWD/data/stage2'" >> $L 2>&1 &
    local CPID=$! PG n=0
    PG=$(ps -o pgid= -p $CPID | tr -d ' ')
    declare -A prev
    while kill -0 $CPID 2>/dev/null; do
        local tot=0 np=0 pp cur ut st
        for pp in $(pgrep -g $PG 2>/dev/null); do
            read -r _ _ _ _ _ _ _ _ _ _ _ _ _ ut st _ < /proc/$pp/stat 2>/dev/null || continue
            cur=$(( ut + st )); np=$(( np + 1 ))
            [ -n "${prev[$pp]:-}" ] && tot=$(( tot + cur - prev[$pp] ))
            prev[$pp]=$cur
        done
        [ $n -gt 0 ] && awk -v t="$tot" -v c="$CLK" -v k="$np" \
            'BEGIN{printf "%.0f %d\n", t*100.0/(c*0.25), k}' >> "$T"
        n=$(( n + 1 )); sleep 0.25
    done
    wait $CPID
    awk -v tag="$tag" '{n++; if($1<200){lo++; idle+=(300-$1)/100.0*0.25}}
        END{printf "# GAP [%s] wall=%.1fs  below200=%.1fs (%.0f%%)  idle_core_s=%.1f\n",
                   tag, n*0.25, lo*0.25, lo*100.0/n, idle}' "$T" >> $L
    ci "$tag"; }
for rep in 1 2; do
  for p in 1 3 5 16 20 7 13 26; do trace $p $rep; done
done
echo "IDLEGAPDONE" >> $L
lock_release idlegap

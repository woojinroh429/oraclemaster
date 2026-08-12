#!/bin/bash
# MAKE THE BEAM FASTER RATHER THAN SMARTER, AND PROVE THE ANSWER DID NOT MOVE.
#
# WHY THIS IS THE RIGHT LEVER NOW.  flatctl separated time from configuration on prob_1: three
# times the clock is worth -30.7% with DIRGATE held on, and 455,298 at 180 s sits below the ENTIRE
# attractor set every 60 s approach this session has reached (473,456 / 489,878 / 515,621 /
# 605,585 / 683,809 / 712,652).  prob_1 is not stuck, it is starved.  A beam that does the same
# work in less time converts directly into that curve without changing a single decision.
#
# AND UNLIKE EVERY TUNING ARM THIS SESSION, ACCELERATION IS FALSIFIABLE THE STRICT WAY.  With
# OGC_WORKCAP the beam stops after a fixed number of expansions instead of on the clock, so the
# search is deterministic: same states, same order, same answer.  A faster build must return the
# SAME OBJECTIVE and a lower used-fraction.  If the objective moves, the change is not an
# acceleration and it does not matter how fast it was.
#
# TWO CANDIDATES, both already in the engine and both dark.
#
# OGC_DEDUP=0 -- this one is not a gamble, it is removing work the file says is pointless.  From
# ogc_fast.cpp:2203: "MEASURED INERT: identical to the last digit on prob_30/39/22/26/35.  Our beam
# uses a FIXED dispatch order, so every state at level k has placed the same block SET and differs
# only in placements -- two states can only collide if they made identical choices, which candidate
# generation already prevents.  Left in (it is free) but expect nothing."  It is NOT free: it
# allocates an unordered_set reserved at nch*2 and hashes every candidate, once per level, across
# 150-300 levels at beam width 48-96.  The claim under test is that removing it is bit-identical
# and measurably cheaper.
#
# OGC_FCACHE=1 -- memoises the (occ,F) grid per (bay, cur, ex, maxLb, overlapping content) so
# sibling beam states sharing a bay's contents skip O(placed x footprint) layer stamping and pay
# only an O(placed) hash.  Beam search is exactly the workload that shape helps: siblings at a
# level differ in one placement and share everything else.  Its own comment bounds the risk -- a
# wrong hit can only mark an infeasible cell clear, the commit then fails check_feasibility and
# best-of drops it, so a stale entry costs a candidate and never buys a wrong answer.
#
# WHAT WOULD MAKE EACH FAIL, named first.
#   DEDUP=0   should be free and identical.  If the objective MOVES, then the dedup is not inert
#             on these instances and the file's claim was measured on five others -- that is a
#             finding about correctness, not speed, and the arm dies.
#   FCACHE=1  the risk is not wrong answers, it is that the cache never hits, or hits so rarely
#             that hashing every overlapping placement per call costs more than the stamping it
#             skips.  Then it is slower with an identical objective, which the same table shows.
#             The second risk is memory: the map is thread_local and unbounded, so a long run on a
#             300-block instance could grow it without limit -- the wall and any crash are read
#             before the timing.
#
# DESIGN.  Two halves, and they answer different questions.
#   FIXED-WORK half (OGC_WORKCAP=4000): the beam performs an identical amount of search, so the
#     objective must not move and `used` measures pure throughput.  This is the correctness proof
#     and the speedup measurement in one cell.
#   FREE-RUNNING half (no WORKCAP, the shipped path): whether the throughput actually converts
#     into a better answer at 60 s, which is the only thing that scores.
#
# JUDGED, fixed before the run: in the fixed-work half, an arm is disqualified if any objective
# differs from baseline -- speed is irrelevant if the search changed.  Surviving arms are ranked on
# used-fraction.  In the free-running half, paired ratio against baseline, three replicates.
set -u
cd /home/user/oraclemaster/research/exact_packer/session2/recon || exit 1
. harness/lock.sh
lock_acquire accel
L=results/audit/accel.log
mkdir -p results/audit; touch $L
ci(){ ( cd "$(git rev-parse --show-toplevel)" \
        && git add research/exact_packer/session2/recon/results/audit/accel.log \
                  research/exact_packer/session2/recon/harness/CURRENT \
                  research/exact_packer/session2/recon/harness/accel.sh \
        && git commit -q -m "in-flight: accel $1" \
        && git push -q origin claude/repair-plan-model-1ig6it ) >/dev/null 2>&1; }
run(){ local tag="$1" p="$2" env0="$3" _s _e
    grep -vE '^# ' $L 2>/dev/null | grep -q "\[$tag\]" && return
    echo "# [$tag]" >> $L
    _s=$(date +%s.%N)
    env $env0 OGC_BEAMSTAT=1 OGC_WSTAT=1 WORKERS=1 timeout 200 /usr/bin/python3.12 \
        harness/run1.py myalgorithm $p 60 "[$tag]" --data data/stage2 >> $L 2>&1 \
        || echo "P$p [$tag] CRASH rc=$?" >> $L
    _e=$(date +%s.%N)
    echo "# WALL [$tag] $(awk -v a="$_s" -v b="$_e" 'BEGIN{printf "%.2f", b-a}')" >> $L
    ci "$tag"; }
# ---- fixed-work half: WORKERS=1 and a work cap make this deterministic, so one cell each is
# ---- enough and any objective difference is a real difference rather than a draw.
for p in 1 3 16; do
  run "F.base.p$p"   $p "OGC_WORKCAP=4000"
  run "F.dedup.p$p"  $p "OGC_WORKCAP=4000 OGC_DEDUP=0"
  run "F.fcache.p$p" $p "OGC_WORKCAP=4000 OGC_FCACHE=1"
  run "F.both.p$p"   $p "OGC_WORKCAP=4000 OGC_DEDUP=0 OGC_FCACHE=1"
done
echo "ACCELFIXEDDONE" >> $L
# ---- free-running half: the shipped path, whether throughput becomes score.
run2(){ local tag="$1" p="$2" env0="$3" _s _e
    grep -vE '^# ' $L 2>/dev/null | grep -q "\[$tag\]" && return
    echo "# [$tag]" >> $L
    _s=$(date +%s.%N)
    env $env0 OGC_WSTAT=1 timeout 200 /usr/bin/python3.12 \
        harness/run1.py myalgorithm $p 60 "[$tag]" --data data/stage2 >> $L 2>&1 \
        || echo "P$p [$tag] CRASH rc=$?" >> $L
    _e=$(date +%s.%N)
    echo "# WALL [$tag] $(awk -v a="$_s" -v b="$_e" 'BEGIN{printf "%.2f", b-a}')" >> $L
    ci "$tag"; }
for rep in 1 2 3; do
  for p in 1 3 16; do
    run2 "R.base.p$p.r$rep"   $p ""
    run2 "R.dedup.p$p.r$rep"  $p "OGC_DEDUP=0"
    run2 "R.fcache.p$p.r$rep" $p "OGC_FCACHE=1"
    run2 "R.both.p$p.r$rep"   $p "OGC_DEDUP=0 OGC_FCACHE=1"
  done
done
echo "ACCELDONE" >> $L
lock_release accel

#!/bin/bash
# HOW MUCH END MARGIN THE RUN ACTUALLY NEEDS, AND WHAT IT COSTS TO BUY IT.
#
# Every deadline in algorithm() was `timelimit - elapsed - 1.0`, and the run still returns past the
# limit.  By algorithm()'s OWN clock at 60 s, not the wall (results/audit/mins.log, 27 cells):
#
#     MGATE on (MSET=8)    7 of 9 cells at >= 60 s
#     MGATE off            2 of 9
#
# The second goes between the last deadline test and the return: pool.terminate() and join() on
# nw forked processes, the final _total() evaluations, the polish's last look.  An overrun is a
# disqualification rather than a bad score, so this is the one number in the file that should be
# generous instead of optimal.
#
# ARMS: OGC_ENDPAD 1 (the old literal, for comparison), 3 (the new default), 5 (comfortable).
#
# WHAT WOULD MAKE IT FAIL, named first, and it is a real risk rather than a formality.  On the
# saturated instances the workers barely land inside the deadline as it is -- prob_13's pool needs
# essentially the whole remaining clock -- so moving the deadline in by 2 or 4 seconds can turn a
# draw that arrived into a draw that was killed, and a round that collects NOTHING falls through
# to _safe_sequential at fifty-eight times worse.  So the floor count is the first thing read, not
# the means: if ENDPAD 3 or 5 floors an instance that ENDPAD 1 did not, the margin is being bought
# with the exact catastrophe it was meant to prevent and the answer is to fix the tail cost
# instead.
#
# THE OTHER FAILURE MODE is that 2 seconds of a 60 s budget is 3.3% of the search and these
# instances are sensitive to it -- P36 moved 13.6% between MGATE on and off.  If ENDPAD 5 costs
# more quality than the overrun risk is worth, 3 is the compromise and the table will say so.
#
# INSTANCES: prob_13, prob_2, prob_36 are where the overrun was measured.  prob_1, prob_3, prob_16
# are the DIRGATE instances the submission is played for -- they must not pay for a fix aimed at
# somebody else, and prob_1 in particular has just gained 9% from the fill gate.
#
# JUDGED, fixed before the run: floor count first, then the count of cells at >= 60 s by
# algorithm()'s own clock, then paired quality ratio against ENDPAD 1 within replicate.
set -u
cd /home/user/oraclemaster/research/exact_packer/session2/recon || exit 1
. harness/lock.sh
lock_acquire endpad
L=results/audit/endpad.log
mkdir -p results/audit; touch $L
ci(){ ( cd "$(git rev-parse --show-toplevel)" \
        && git add research/exact_packer/session2/recon/results/audit/endpad.log \
                  research/exact_packer/session2/recon/harness/CURRENT \
                  research/exact_packer/session2/recon/harness/endpad.sh \
        && git commit -q -m "in-flight: endpad $1" \
        && git push -q origin claude/repair-plan-model-1ig6it ) >/dev/null 2>&1; }
run(){ local tag="$1" p="$2" ep="$3" _s _e
    grep -vE '^# ' $L 2>/dev/null | grep -q "\[$tag\]" && return
    echo "# [$tag]" >> $L
    _s=$(date +%s.%N)
    env OGC_ENDPAD=$ep OGC_WSTAT=1 timeout 200 /usr/bin/python3.12 \
        harness/run1.py myalgorithm $p 60 "[$tag]" --data data/stage2 >> $L 2>&1 \
        || echo "P$p [$tag] CRASH rc=$?" >> $L
    _e=$(date +%s.%N)
    echo "# WALL [$tag] $(awk -v a="$_s" -v b="$_e" 'BEGIN{printf "%.2f", b-a}')" >> $L
    ci "$tag"; }
for rep in 1 2 3; do
  for p in 13 2 36 1 3 16; do
    for ep in 1 3 5; do
      run "e$ep.p$p.r$rep" $p $ep
    done
  done
done
echo "ENDPADDONE" >> $L
lock_release endpad

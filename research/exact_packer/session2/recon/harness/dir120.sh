#!/bin/bash
# THE AXIS DIRECTOR, MEASURED IN THE REGIME THE SCORE IS ACTUALLY DECIDED IN.
#
# THE BUDGET.  `def algorithm(prob_info, timelimit=60)`, and PROJECT.md records that the grader's
# machine is about twice as fast as this container -- prob_20 read grader 60 s = 114,950 against
# local 60 s = 177,111 and local 120 s = 105,274, i.e. grader 60 s lands between local 110 s and
# 120 s.  So LOCAL 120 s is the faithful proxy and every cell run earlier tonight, all at 240 s,
# was measuring twice the real budget.
#
# WHY THAT MATTERS MOST FOR THIS PARTICULAR ARM.  The director's own comment:
#
#     "at 240 s that is ~30 draws over 6 axes, five each; at the 60 s the hidden set gives its
#      early instances it is closer to one each, so the axis that would have won gets a single
#      draw and the run is decided by which one that was."
#
# It predicts its own effect grows as draws get scarce.  At 240 s it read -7.64% and -12.83% on
# prob_16 -- the two largest effects measured all night -- and 240 s is the regime where it should
# matter LEAST.
#
# REPLICATES, BECAUSE prob_16 IS THE NOISIEST INSTANCE HERE.  Its control has read 2,674,298 /
# 2,902,331 / 2,962,652 / 2,971,117 / 3,271,810 in this build today: a 22.3% span against a claimed
# 10% effect.  Two pairs cannot read that and four cannot either.  Halving the budget halves the
# cell cost, which is the only reason six pairs is affordable, and six is still thin.
#
# THE VETOES.  prob_1 is where axis pinning lost outright, so the director must not damage a
# rotation that was already right.  prob_20 is the tardiness family, furthest from prob_16, where
# the odd configuration wins 95% of the time.  prob_40 is n=300, where surveying six axes costs the
# most and concentrating on one costs the most if the survey was wrong.
set -u
cd /home/user/oraclemaster/research/exact_packer/session2/recon || exit 1
echo dir120 > harness/CURRENT
L=results/audit/dir120.log
mkdir -p results/audit; touch $L
ci(){ ( cd "$(git rev-parse --show-toplevel)" \
        && git add research/exact_packer/session2/recon/results/audit/dir120.log \
                  research/exact_packer/session2/recon/harness/CURRENT \
        && git commit -q -m "in-flight: dir120 $1" \
        && git push -q origin claude/repair-plan-model-1ig6it ) >/dev/null 2>&1; }

run(){ # tag prob limit env
    local tag="$1"
    grep -vE '^# ' $L 2>/dev/null | grep -q "\[$tag\]" && return
    echo "# [$tag]" >> $L
    env $4 OGC_WSTAT=1 timeout $(( $3 * 4 + 60 )) /usr/bin/python3.12 harness/run1.py myalgorithm $2 $3 \
        "[$tag]" --data data/stage2 >> $L 2>&1 || echo "P$2 [$tag] CRASH rc=$?" >> $L
    ci "$tag"
}

for rep in 1 2 3 4 5 6; do
  run "r$rep.p16.off" 16 120 ""
  run "r$rep.p16.dir" 16 120 "OGC_AXDIR=1"
done
echo "== DIR120 prob_16 done ==" >> $L

for rep in 1 2 3 4; do
  run "r$rep.p1.off" 1 120 ""
  run "r$rep.p1.dir" 1 120 "OGC_AXDIR=1"
done
echo "== DIR120 prob_1 done ==" >> $L

for rep in 1 2 3; do
  for p in 20 40; do
    run "r$rep.p$p.off" $p 120 ""
    run "r$rep.p$p.dir" $p 120 "OGC_AXDIR=1"
  done
done
echo "DIR120DONE" >> $L
echo idle > harness/CURRENT

#!/bin/bash
# brk ON ONE WORKER OF EACH CONFIGURATION, AGAINST brk EVERYWHERE AND brk NOWHERE.
#
# prob_1 r3 is the whole reason this arm exists.  brk paid on seven of eight worker-rounds there
# and the run finished 18% worse than its control, because the beam's try count over round 0 fell
# 39 -> 23.  The answer is the MINIMUM over four workers and what reaches prob_1's good basin is
# the beam restarting, so brk was spending the restarts that find a different hill in order to
# climb the one it was standing on.
#
# OGC_BRKPAR=half puts brk on (wid//2)%2 == 0, i.e. one worker of each configuration, leaving the
# other pure.  The pure workers keep the control's restart count, so the min should not be able to
# fall below a control draw the way r3 did, while brk's upside stays on the other two.
#
# THREE ARMS, PAIRED, BECAUSE TWO CANNOT SEPARATE THE HYPOTHESES.
#
#     off    brk nowhere      the control
#     all    brk everywhere   what zip D ships
#     half   brk on two       this arm
#
# WHAT WOULD REFUSE IT.  If half is no better than all on prob_1, the restart-starvation story is
# wrong and something else produced r3.  If half is no better than off anywhere -- including
# prob_3, the one instance with a surviving paired gain -- then brk has nothing to contribute
# through any wiring and the honest ship is B.  And if half beats both on prob_16/24/20 rather
# than merely matching off, that would mean brk helps there after 118 worker-rounds of finding
# nothing, which would say the measurement is wrong rather than the operator is good.
#
# prob_1 gets FOUR replicates.  Its controls span 422,629 to 492,458 -- 16% -- and three was not
# enough to keep me from reporting a draw as an effect twice tonight.  prob_3 and prob_16 get two.
set -u
cd /home/user/oraclemaster/research/exact_packer/session2/recon || exit 1
echo brkhalf > harness/CURRENT
L=results/audit/brkhalf.log
mkdir -p results/audit; touch $L
ci(){ ( cd "$(git rev-parse --show-toplevel)" \
        && git add research/exact_packer/session2/recon/results/audit/brkhalf.log \
                  research/exact_packer/session2/recon/harness/CURRENT \
        && git commit -q -m "in-flight: brkhalf $1" \
        && git push -q origin claude/repair-plan-model-1ig6it ) >/dev/null 2>&1; }

run(){ # tag prob limit env
    local tag="$1"
    grep -vE '^# ' $L 2>/dev/null | grep -q "\[$tag\]" && return
    echo "# [$tag]" >> $L
    env $4 OGC_WSTAT=1 timeout $(( $3 * 4 )) /usr/bin/python3.12 harness/run1.py myalgorithm $2 $3 \
        "[$tag]" --data data/stage2 >> $L 2>&1 || echo "P$2 [$tag] CRASH rc=$?" >> $L
    ci "$tag"
}

for rep in 1 2 3 4; do
  run "r$rep.p1.off"  1 240 "OGC_BRK=0"
  run "r$rep.p1.all"  1 240 "OGC_BRK=1 OGC_BRKPAR=all"
  run "r$rep.p1.half" 1 240 "OGC_BRK=1 OGC_BRKPAR=half"
done
echo "== BRKHALF prob_1 done ==" >> $L

for rep in 1 2; do
  for p in 3 16; do
    run "r$rep.p$p.off"  $p 240 "OGC_BRK=0"
    run "r$rep.p$p.all"  $p 240 "OGC_BRK=1 OGC_BRKPAR=all"
    run "r$rep.p$p.half" $p 240 "OGC_BRK=1 OGC_BRKPAR=half"
  done
done
echo "BRKHALFDONE" >> $L
echo idle > harness/CURRENT

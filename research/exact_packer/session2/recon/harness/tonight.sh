#!/bin/bash
# THE OVERNIGHT CHAIN.  One resume target, three experiments, in the order their answers are needed.
#
# WHY A CHAIN AND NOT THREE QUEUED SCRIPTS.  keepalive.sh relaunches exactly one script after a
# container restart, named by harness/RESUME.  Three scripts waiting on the experiment lock do not
# survive a restart -- the waiters are killed with everything else and only the named one comes
# back.  That is how tonight's runs kept dying at four cells: the survivor was relaunched, the
# queue behind it was not.  A single chained script is the thing keepalive can actually resume,
# and every stage skips work whose cells already exist, so resuming repeats nothing.
#
# ORDER, and the reason for it:
#   1. gridstep   finishes the FINEFRAC replicates on prob_1/3/16.  Nearly complete already, and it
#                 is what the scan's rule will be anchored to.
#   2. scan40     FINEFRAC 0.85 against 0.60 on all forty instances, paired.  This is the one that
#                 decides whether prob_1's -21.6% can be shipped behind a rule, and it needs the
#                 most wall time, so it goes before the speculative work.
#   3. permarg    the marginal-cost width controller.  Speculative -- it installs a patched engine
#                 and restores it on exit -- so it runs last, where a failure costs nothing that
#                 was already decided.
#
# THE LOOP IS DELIBERATE.  Each stage returns when its own cells are done; the outer loop then
# re-enters and the next stage begins.  When all three are complete the loop still spins at a
# minute per pass, which costs nothing and keeps RESUME pointing somewhere real, so a restart at
# 4am resumes the chain instead of falling back to a finished queue.
set -u
cd /home/user/oraclemaster/research/exact_packer/session2/recon || exit 1
exec 8>"/tmp/ogc_tonight.lock"
flock -n 8 || { echo "tonight.sh already running"; exit 0; }
echo tonight > harness/RESUME
log(){ echo "=== $* $(date -u +%H:%M:%S)" >> results/audit/tonight.log; }
mkdir -p results/audit
for pass in 1 2 3 4 5 6 7 8 9 10 11 12; do
    log "pass $pass begins"
    if ! grep -q GRIDSTEPDONE results/audit/gridstep.log 2>/dev/null; then
        log "gridstep"; bash harness/gridstep.sh >> results/audit/tonight.log 2>&1
    fi
    if ! grep -q SCAN40DONE results/audit/scan40.log 2>/dev/null; then
        log "scan40"; bash harness/scan40.sh >> results/audit/tonight.log 2>&1
    fi
    if ! grep -q PERMARGDONE results/audit/permarg.log 2>/dev/null; then
        log "permarg"; bash harness/permarg.sh >> results/audit/tonight.log 2>&1
    fi
    if grep -q GRIDSTEPDONE results/audit/gridstep.log 2>/dev/null \
       && grep -q SCAN40DONE results/audit/scan40.log 2>/dev/null \
       && grep -q PERMARGDONE results/audit/permarg.log 2>/dev/null; then
        log "all three complete"
        ( cd ../../.. && git add -A research/exact_packer/session2/recon/results/audit/ >/dev/null 2>&1 \
          && git commit -q -m "tonight: all three stages complete" >/dev/null 2>&1 \
          && git push -q origin claude/repair-plan-model-1ig6it >/dev/null 2>&1 )
        break
    fi
    sleep 60
done
log "chain exiting"

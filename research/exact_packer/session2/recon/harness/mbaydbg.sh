#!/bin/bash
# WHY did the two-bay arm return 0 application(s)?  Two answers, opposite meanings.
#
# The arm can return nothing because the operator ran and found no improving move -- the
# neighbourhood is bigger and empty, and the idea is dead.  Or because the tier chooser declined
# every call: the superset raises candidates from R to R+cap, the build is roughly 4x, and
# _pred(_nc) + _MINASK > _room fires before a single column is generated.  Then nothing was
# measured about the neighbourhood at all, only about the budget.
#
# mbay3 cannot tell these apart, by construction -- it runs with BRK_DEBUG off so the log stays
# readable.  This turns it on for one instance and reads the exits:
#
#   "brk: declined, smallest tier predicts Ns of Ms"   -> budget.  The idea is untested.
#   "brk tier: ..." followed by "-> DISCARD"           -> ran, found nothing.  The idea is weak.
#   "brk[...] admitted/moved/displaced ... -> KEEP"    -> ran and improved.
#
# P1 is the target because it is where the difference showed: the one-bay arm took -0.51% from
# the same incumbent and the two-bay arm took nothing.  If P1 says "declined", the eight-instance
# table is measuring the tier ladder rather than the neighbourhood, and the comparison has to be
# rerun at a budget that lets the larger build through.
#
# Runs AFTER the queue, never beside it: two solvers at once change the wall-clock path, and that
# has moved an objective by 7.7% on an unchanged build.
set -u
cd "$(dirname "$0")/.." || exit 1
P=${1:-1}
L=results/audit/mbaydbg_p$P.log
mkdir -p results/audit
BRK_DEBUG=1 timeout 900 /usr/bin/python3.12 harness/mbay.py $P 30 60 3 > $L 2>&1
echo "--- exits seen ---" >> $L
grep -c "brk: declined" $L | sed 's/^/declined: /' >> $L
grep -c "brk tier:" $L | sed 's/^/tier chosen: /' >> $L
grep -c "KEEP" $L | sed 's/^/KEEP: /' >> $L
grep -c "DISCARD" $L | sed 's/^/DISCARD: /' >> $L
echo "MBAYDBGDONE" >> $L
( cd "$(git rev-parse --show-toplevel)" \
  && git add research/exact_packer/session2/recon/results/audit/mbaydbg_p$P.log \
  && git commit -q -m "mbaydbg: tier trace for the two-bay arm on P$P" ) >/dev/null 2>&1

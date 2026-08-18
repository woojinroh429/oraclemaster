#!/bin/bash
# EVERY MEASUREMENT TODAY WAS MADE ON A WORKER COUNT THE GRADER WILL NOT USE.
#
# The shipped path picks nw = cpu_count - 1 for timelimit <= 240, so on the four-core grader it runs
# THREE workers.  rfship, rf4, gaterf, w3rf and rounds05 all pass WORKERS=4 -- 18 occurrences across
# the five scripts.  A gate smoke run of the edited module printed `WSTAT round=0 n=3`, which is how
# this surfaced.
#
# THE GAP MATTERS MOST FOR ROUNDS, because that arm's whole argument is draw count: the answer is a
# minimum over nw draws per round, so R=2 is 8 draws at WORKERS=4 and 6 draws at the shipped 3.  A
# tail statistic measured with a third of its draws removed is not the same statistic.
#
# IT ALSO MATTERS FOR THE RESERVE, though less directly.  The module's own worker-count note records
# that three workers each get a full core "and the search each one gets to do is deeper for it" --
# so at nw=3 each draw is already deeper, which is exactly the resource RESFRAC 0.05 was buying.
# The two changes may be paying for the same thing twice.
#
# ARMS, all at the shipped worker count -- no WORKERS in the environment:
#     A  RESFRAC 0.50, ROUNDS 1   the gate as it shipped in OGC2026_dirgate.zip
#     B  RESFRAC 0.05, ROUNDS 1   the reserve change alone
#     C  RESFRAC 0.05, ROUNDS 2   the reserve change plus more draws
#
# WHAT WOULD MAKE IT FAIL, named first.  If at nw=3 the deeper per-worker search already reaches
# what the extra reserve was buying, B collapses toward A and the -6.65% ratio-mean measured at
# WORKERS=4 does not transfer.  And if six draws is below whatever threshold makes the extra round
# worth its depth cost, C loses to B even though it beat R=1 at eight draws.  Either outcome is a
# real answer and the build follows it rather than the WORKERS=4 table.
#
# JUDGED, fixed before the run: three draws per cell, paired within replicate, ratio-mean and
# geometric mean across the six firing instances as the user asked.  B ships over A, and C ships
# over B, only on its own evidence at this worker count.
set -u
cd /home/user/oraclemaster/research/exact_packer/session2/recon || exit 1
while [ "$(cat harness/CURRENT 2>/dev/null)" != "idle" ]; do sleep 15; done
echo wdef > harness/CURRENT
L=results/audit/wdef.log
mkdir -p results/audit; touch $L
ci(){ ( cd "$(git rev-parse --show-toplevel)" \
        && git add research/exact_packer/session2/recon/results/audit/wdef.log \
                  research/exact_packer/session2/recon/harness/CURRENT \
                  research/exact_packer/session2/recon/harness/wdef.sh \
        && git commit -q -m "in-flight: wdef $1" \
        && git push -q origin claude/repair-plan-model-1ig6it ) >/dev/null 2>&1; }
run(){ local tag="$1"
    grep -vE '^# ' $L 2>/dev/null | grep -q "\[$tag\]" && return
    echo "# [$tag]" >> $L
    env $3 timeout 220 /usr/bin/python3.12 harness/run1.py myalgorithm $2 60 \
        "[$tag]" --data data/stage2 >> $L 2>&1 || echo "P$2 [$tag] CRASH rc=$?" >> $L
    ci "$tag"; }

# P1 and P3 first -- the two instances the submission is being played for.
for rep in 1 2 3; do
  for p in 1 3 27 16 7 33; do
    run "A.p$p.r$rep" $p "OGC_WSTAT=1 OGC_RESFRAC=0.50 OGC_ROUNDS=1"
    run "B.p$p.r$rep" $p "OGC_WSTAT=1 OGC_RESFRAC=0.05 OGC_ROUNDS=1"
    run "C.p$p.r$rep" $p "OGC_WSTAT=1 OGC_RESFRAC=0.05 OGC_ROUNDS=2"
  done
done
echo "WDEFDONE" >> $L
echo idle > harness/CURRENT

#!/bin/bash
# THE OTHER HALF OF THE 2.03x, AND THE BIGGER SPACE OF THE TWO.
#
# The direction that DIRSET=2 hands to config A is a PAIR -- order=lst and w3mul=0.5 -- and a
# worker carrying neither drew a median of 993,027 against 482,866 and 489,878 for the two that
# carry both.  That 2.03x is the largest single effect measured in this session.  w3sweep.sh is
# pricing the w3mul half; this prices the order half.
#
# order is not a scalar.  _draw_order builds a completely different priority per value:
#
#     lst         due - processing time            latest start time
#     edd         due                              earliest due date
#     defer_big   big-and-late-released last, then due
#     big_first   blocks over twice mean area first, then due
#     cohort      grouped
#     rank / aspect / sac*                         other rules entirely
#
# So this is six different dispatch policies rather than six points on a curve, and _AXES itself
# only ever uses four of them (defer_big, lst, edd, big_first).  cohort and rank have never been
# run as the whole pool's order on this instance.
#
#
# rank's FAMILY, NOT rank ALONE -- the file says why.  _draw_order's own comment records that
# rank scores rank(due) + rank(-area), that its geometry term correlates with its scheduling term
# at rho = +0.23 and with every other order's area term by construction, and that it therefore
# "produces a sequence close to what the list already makes".  Running rank by itself would mostly
# re-measure lst and edd.
#
# The same comment names what IS different: aspect (long side / short side) and boxfill (polygon
# area / bounding-box area) measured rho = -0.053 and -0.061 against area over all forty stage-2
# instances, so they separate blocks that size and deadline never do -- and they keep rank's
# scheduling half rather than dropping it, which matters because the objective is 89% weighted
# tardiness.  sac3 is the third variant: rank with the three largest area*processing-time blocks
# forced to the front.
#
# So the arm list is lst / edd / defer_big / big_first / rank / sac3 / aspect / boxfill.  cohort is
# dropped to keep the queue under an hour; it is a grouping rule rather than a priority and can be
# added if any of these move.
#
# SAME UNIFORM RIG as w3sweep, for the same reason: DIRSET=0 with single-element AIMSET and MSET
# makes all four workers identical, so contention is constant and order is the only free variable,
# and every run writes four draws instead of one usable number.
#
# w3mul IS PINNED AT 1.0 HERE, NOT 0.5.  1.0 makes the beam's internal ratio 6667/600 -- exactly
# the instance's own objective -- so the order comparison is not tilted by a weight that is itself
# under test.  Whatever w3sweep settles gets combined with the winner afterwards, not before.
#
# READ THE DRAWS.  The run objective is a minimum over four workers and has flipped this session's
# readings eleven times; the WSTAT lines give four samples per run and the three cells that were
# consistent under that view stayed consistent.  Twelve draws per arm here.
set -u
cd /home/user/oraclemaster/research/exact_packer/session2/recon || exit 1
echo ordsweep > harness/CURRENT
L=results/audit/ordsweep.log
mkdir -p results/audit; touch $L
U="WORKERS=4 OGC_DIRSET=0 OGC_AIMSET=0.90 OGC_MSET=1 OGC_W3MUL=1.0"
ci(){ ( cd "$(git rev-parse --show-toplevel)" \
        && git add research/exact_packer/session2/recon/results/audit/ordsweep.log \
                  research/exact_packer/session2/recon/harness/CURRENT \
                  research/exact_packer/session2/recon/harness/ordsweep.sh \
        && git commit -q -m "in-flight: ordsweep $1" \
        && git push -q origin claude/repair-plan-model-1ig6it ) >/dev/null 2>&1; }

run(){ # tag env
    local tag="$1"
    grep -vE '^# ' $L 2>/dev/null | grep -q "\[$tag\]" && return
    echo "# [$tag]" >> $L
    env $2 OGC_WSTAT=1 timeout 400 /usr/bin/python3.12 harness/run1.py myalgorithm 1 120 \
        "[$tag]" --data data/stage2 >> $L 2>&1 || echo "P1 [$tag] CRASH rc=$?" >> $L
    ci "$tag"
}

for rep in 1 2 3; do
  for O in lst edd defer_big big_first rank sac3 aspect boxfill; do
    run "ord.$O.r$rep" "$U OGC_ORDER=$O"
  done
done
echo "ORDSWEEPDONE" >> $L
echo idle > harness/CURRENT

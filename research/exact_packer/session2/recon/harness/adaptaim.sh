#!/bin/bash
# OGC_ADAPTAIM: a lever that is already built, already reasoned through, and has never been run.
#
# _adapt_aim() lets each worker move its own beam aim from the beam's OWN report -- salvaged means
# it overran and the aim comes down hard, finished-at-full-width means the aim was not binding and
# it creeps up.  Nothing is gated on any property of the instance.  The source says why that
# matters, and the measurement behind it kills the explanation I reached for earlier today:
#
#     "The low aim wins on a 150-block instance whose blocks carry three or more layers and loses
#      on the flat 150-block ones, because layers make the descent test expensive and it is total
#      work, not block count, that decides whether the beam can finish.  No property we can read
#      off the instance separates those cases."
#
# I had just written that P1 is the exception because 150 blocks means the beam finishes.  Block
# count does not decide it and this was measured before I said it.
#
# The default is OFF, with the comment "until it is measured against the fixed 0.90/0.10
# portfolio".  That measurement is this file.  aimset moves where the four workers START; this
# moves where they END UP, and the two are different questions -- with ADAPTAIM on, a worker that
# starts at the wrong aim can walk to the right one, so a fixed split matters less.
#
#   arm  fixed    shipped default, _ADAPTAIM off
#   arm  adapt    OGC_ADAPTAIM=1, same 0.90/0.10 starting points
#
# Same instances and budget as aimset so the three logs compare directly.  Rep-major.
set -u
cd "$(dirname "$0")/.." || exit 1
echo adaptaim > harness/CURRENT
L=results/audit/adaptaim.log
mkdir -p results/audit; touch $L

run(){ # rep arm prob
    local tag="r$1.$2.$3"
    # SKIP ON A RESULT, NOT ON THE MARKER.  The marker is written BEFORE the run, so a queue
    # killed mid-cell leaves an orphan "# [tag]" line with no result -- and this test then
    # matched it on resume and skipped the cell forever.  Nine such orphans existed across
    # today's logs, including one this session was actively waiting on (w3grid r1.dn.26).
    # In a paired design a lost arm silently invalidates the whole instance.  Excluding the
    # marker lines makes the test key on evidence the run finished.
    grep -vE '^# ' $L 2>/dev/null | grep -q "\[$tag\]" && return
    echo "# [$tag]" >> $L
    env $( [ "$2" = adapt ] && echo OGC_ADAPTAIM=1 ) OGC_WSTAT=1 \
        timeout 300 /usr/bin/python3.12 harness/run1.py myalgorithm $3 60 "[$tag]" \
        --data data/stage2 >> $L 2>&1
    ( cd "$(git rev-parse --show-toplevel)" \
      && git add research/exact_packer/session2/recon/results/audit/adaptaim.log \
      && git commit -q -m "in-flight: adaptaim $tag" ) >/dev/null 2>&1
}

for rep in 1 2 3 4 5; do
    for p in 1 12 16 26 6 3 20 30; do
        run $rep fixed $p
        run $rep adapt $p
    done
    echo "REPDONE $rep" >> $L
done
echo "ADAPTDONE" >> $L
echo idle > harness/CURRENT

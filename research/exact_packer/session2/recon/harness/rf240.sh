#!/bin/bash
# THE POLISH RESERVE, RE-ASKED ON THE BUILD THAT NOW SHIPS.
#
# ax1z1 put the whole of prob_1's improvement on the reserve and none of it on w3mul:
#
#     a1.plain     438,791   Z1=8   Z3=622
#     a1.rf35      422,629   Z1=7   Z3=608     <- project best on this instance
#     a1.rf50      422,629   identical
#     a1.w05rf35   422,629   identical
#     a1.w05rf50   422,629   identical
#     a1.nodir     566,541   dir2 off -- so dir2 is load bearing here, +34% without it
#
# Four different w3mul/resfrac combinations return the same number, so what moved prob_1 from
# 438,791 to 422,629 is the polish getting more budget, full stop.  And rf35 = rf50 says the pass
# converges inside 35% and does not use more, so the knob has a floor rather than a slope.
#
# WHY THIS IS WORTH RE-READING.  The reserve was measured at 240 s once tonight, on prob_16 and
# prob_36, and the small default won:
#
#     P16  240s   base 3,281,165   rf35 3,760,629   rf50 3,552,573
#     P36  240s   base 76,875,827  rf35 78,263,904  rf50 77,594,861
#
# That ladder predates three things that have since changed the build: the m=1/m=2 worker
# portfolio, dir2, and the discarded-draw fix that was throwing away one of every four draws.  The
# last one alone changes what a reserve costs -- taking budget from the workers is cheaper when the
# workers are keeping all their results.  A measurement taken before a 25% change in effective draw
# count is not a measurement of the current build.
#
# Six instances, base against rf35, on the shipped configuration.  If prob_1 keeps its 3.6% and the
# large instances stay inside the 2-4% tolerance, the reserve ships; if prob_16 and prob_36
# reproduce their earlier losses, it does not, and prob_1's 422,629 stays a fact about a pinned
# axis rather than something reachable.
set -u
cd /home/user/oraclemaster/research/exact_packer/session2/recon || exit 1
echo rf240 > harness/CURRENT
( cd "$(git rev-parse --show-toplevel)" \
  && git add research/exact_packer/session2/recon/harness/CURRENT \
  && git commit -q -m "queue: CURRENT=rf240" \
  && git push -q origin claude/repair-plan-model-1ig6it ) >/dev/null 2>&1
L=results/audit/rf240.log
mkdir -p results/audit; touch $L
ci(){ ( cd "$(git rev-parse --show-toplevel)" \
        && git add research/exact_packer/session2/recon/results/audit/rf240.log \
                  research/exact_packer/session2/recon/harness/CURRENT \
        && git commit -q -m "in-flight: rf240 $1" \
        && git push -q origin claude/repair-plan-model-1ig6it ) >/dev/null 2>&1; }

run(){ # tag prob limit env
    local tag="$1"
    grep -vE '^# ' $L 2>/dev/null | grep -q "\[$tag\]" && return
    echo "# [$tag]" >> $L
    env $4 OGC_WSTAT=1 timeout $(( $3 * 4 )) /usr/bin/python3.12 harness/run1.py myalgorithm $2 $3 \
        "[$tag]" --data data/stage2 >> $L 2>&1 || echo "P$2 [$tag] CRASH rc=$?" >> $L
    ci "$tag"
}

# prob_1 first and with a replicate, because it is the instance the claim is about and the one
# whose single cells lie.  prob_16 and prob_36 next: they are where the earlier ladder said no.
run "p1.base.r1"  1 240 ""
run "p1.rf35.r1"  1 240 "OGC_RESFRAC=0.35"
run "p1.base.r2"  1 240 ""
run "p1.rf35.r2"  1 240 "OGC_RESFRAC=0.35"
for p in 16 36 20 6 24; do
  run "p$p.base"  $p 240 ""
  run "p$p.rf35"  $p 240 "OGC_RESFRAC=0.35"
done
echo "RF240DONE" >> $L

# then the throughput knobs, then the OGC_SHARE replicate study.
exec bash harness/speed.sh

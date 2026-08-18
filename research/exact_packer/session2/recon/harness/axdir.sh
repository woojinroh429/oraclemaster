#!/bin/bash
# THE AXIS DIRECTOR HAS BEEN WRITTEN, REASONED THROUGH, AND LEFT OFF.
#
# `_ax_pick` is an epsilon-greedy director over the six axes -- untried first, then OGC_AXEPS=0.25
# exploration, then the best mean relative deficit -- with a capped reward chosen precisely because
# quality(axis, work) is not monotone.  It is gated on OGC_AXDIR=1 and defaults to OFF, so the
# shipped behaviour is `axes[gen[0] % 6]`, a plain counter.
#
# ITS OWN COMMENT DESCRIBES THE FAILURE THE USER IS REPORTING:
#
#     "at the 60 s the hidden set gives its early instances it is closer to one each, so the axis
#      that would have won gets a single draw and the run is decided by which one that was."
#
# WHAT MAKES THIS THE RIGHT THING TO TEST NOW, RATHER THAN OGC_AXIS=2.
#
#     prob_16 production, 249 runs   min 2,454,368   median 3,472,568   p90 3,829,684
#     prob_16 with OGC_AXIS=2, one cell                2,521,495
#
# Pinning axis 2 lands 27% under the median, in the top 3% of everything ever recorded on this
# instance.  But pinning is an instance-specific choice: on prob_1 no pinned axis beat the
# rotation, and the 7th submission's global override bought P1 and P3 and lost 14-19% on P2, P5
# and P8.  The director makes the SAME choice at runtime, per instance, per worker, from measured
# deficits -- so it can concentrate on axis 2 where axis 2 wins and stay spread where nothing does.
# There is no threshold and no instance label anywhere in it.
#
# THE INSTANCE SET IS CHOSEN TO BREAK IT, NOT TO FLATTER IT.
#     prob_16   where a pinned axis wins by 27%: the director must find that
#     prob_1    where pinning LOST: the director must not damage the rotation
#     prob_20   tardiness family, odd config wins 95%, furthest from prob_16
#     prob_40   n=300, where concentrating draws costs the most survey time
#
# AND THE 60 s BUDGET IS RUN AS WELL AS 240 s, because the comment says the effect should be
# LARGER when draws are scarce, and the hidden set's early instances get 60 s.  If the director
# only helps at 240 s it is not answering the failure it was written for.
set -u
cd /home/user/oraclemaster/research/exact_packer/session2/recon || exit 1
echo axdir > harness/CURRENT
L=results/audit/axdir.log
mkdir -p results/audit; touch $L
ci(){ ( cd "$(git rev-parse --show-toplevel)" \
        && git add research/exact_packer/session2/recon/results/audit/axdir.log \
                  research/exact_packer/session2/recon/harness/CURRENT \
        && git commit -q -m "in-flight: axdir $1" \
        && git push -q origin claude/repair-plan-model-1ig6it ) >/dev/null 2>&1; }

run(){ # tag prob limit env
    local tag="$1"
    grep -vE '^# ' $L 2>/dev/null | grep -q "\[$tag\]" && return
    echo "# [$tag]" >> $L
    env $4 OGC_WSTAT=1 timeout $(( $3 * 4 + 60 )) /usr/bin/python3.12 harness/run1.py myalgorithm $2 $3 \
        "[$tag]" --data data/stage2 >> $L 2>&1 || echo "P$2 [$tag] CRASH rc=$?" >> $L
    ci "$tag"
}

# prob_16 first at both budgets: this is the family the hidden P1 belongs to.
for rep in 1 2; do
  run "r$rep.p16.off"  16 240 ""
  run "r$rep.p16.dir"  16 240 "OGC_AXDIR=1"
done
for rep in 1 2; do
  run "r$rep.p16s.off" 16 60 ""
  run "r$rep.p16s.dir" 16 60 "OGC_AXDIR=1"
done
echo "== AXDIR prob_16 done ==" >> $L

# Then the three that can refute it.
for rep in 1 2; do
  for p in 1 20 40; do
    run "r$rep.p$p.off" $p 240 ""
    run "r$rep.p$p.dir" $p 240 "OGC_AXDIR=1"
  done
done
echo "AXDIRDONE" >> $L
echo idle > harness/CURRENT

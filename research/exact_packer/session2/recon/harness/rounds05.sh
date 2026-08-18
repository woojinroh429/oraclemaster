#!/bin/bash
# THE KNOB THAT WAS RETIRED BY A MEASUREMENT ITS OWN CODE SAYS WAS IMPOSSIBLE.
#
# The answer algorithm() returns is a MINIMUM over the workers, and WSTAT shows the workers inside
# one round landing far apart:
#
#     P16 round0   4,462,755   2,796,522   5,028,855   4,193,718     spread 79.8%
#     P1  round0     578,411     822,149     721,754     900,853     spread 55.8%
#
# The winner is 37% below the median worker.  A minimum over draws is a TAIL statistic, so the
# lever on it is the NUMBER of draws, not the quality of the average -- and OGC_ROUNDS is exactly
# that lever: it splits wbudget into _R rounds and each round redraws all four workers with fresh
# seeds and axis rotations.
#
# IT IS NOT SHIPPED.  `_R = max(1, int(os.environ.get("OGC_ROUNDS", "1")))` and nothing in the
# module sets it, though one comment at line 3367 asserts it is already shipped.  It is not.
#
# AND THE MEASUREMENT THAT RETIRED IT COULD NOT HAVE FIRED.  From the module's own note at the
# round loop: at a 60 s limit wbudget was about 47, _rb about 23 and reserve about 12, "so the
# second round was unaffordable by the same arithmetic -- R=2 was never two rounds there either."
#
# RESFRAC 0.05 CHANGES THAT ARITHMETIC, and that is the reason to re-open it now rather than at
# any earlier point today.  Reserve falls to 3 s, wbudget rises to about 56, and _rb at R=2 is
# about 28 -- the second round becomes affordable for the first time.  The thirty seconds 0.05
# recovered may be worth more as a second set of draws than as a longer first one.
#
# WHERE R=2 DID FIRE IT WAS WORTH 20%.  rounds.log, P16 at 60 s: R1 3,513,968, R2 2,796,522,
# R3 2,809,807 -- and 2,796,522 recurs across cells, so it is a basin R1 does not reach rather
# than a lucky draw.  rfship's best P16 at 0.05 is 3,051,577, which R2 beats by 8.3%.
#
# ARMS.  R=2 and R=3 at RESFRAC 0.05, against R=1 at 0.05 as control -- so this is measured on top
# of the change being shipped, not against the old regime.  WSTAT=1 throughout: the per-round
# spreads say whether later rounds are redrawing or re-deriving, which is the mechanism and is
# worth more than the totals if the arm fails.
#
# WHAT WOULD MAKE IT FAIL, named first.  Splitting 56 s into two 28 s rounds halves the depth each
# draw reaches, and rfship just showed depth is what 0.05 buys -- P7 and P16 gained 16.6% and 19.1%
# from the longer round.  If depth is the whole story, R=2 gives back exactly what 0.05 won.  The
# WSTAT spreads distinguish the two: if round 1 lands on round 0's numbers the rounds are not
# independent draws and the arm is dead regardless of totals.
#
# JUDGED, fixed before the run: three draws per cell, paired within replicate, median across the
# six firing instances.  An arm ships only if its median absolute sum beats R=1 at 0.05 AND it does
# not lose more than 5% on P1, which is the instance the hidden set is being played for.
set -u
cd /home/user/oraclemaster/research/exact_packer/session2/recon || exit 1
while [ "$(cat harness/CURRENT 2>/dev/null)" != "idle" ]; do sleep 15; done
echo rounds05 > harness/CURRENT
L=results/audit/rounds05.log
mkdir -p results/audit; touch $L
ci(){ ( cd "$(git rev-parse --show-toplevel)" \
        && git add research/exact_packer/session2/recon/results/audit/rounds05.log \
                  research/exact_packer/session2/recon/harness/CURRENT \
                  research/exact_packer/session2/recon/harness/rounds05.sh \
        && git commit -q -m "in-flight: rounds05 $1" \
        && git push -q origin claude/repair-plan-model-1ig6it ) >/dev/null 2>&1; }
run(){ local tag="$1"
    grep -vE '^# ' $L 2>/dev/null | grep -q "\[$tag\]" && return
    echo "# [$tag]" >> $L
    env $3 timeout 220 /usr/bin/python3.12 harness/run1.py myalgorithm $2 60 \
        "[$tag]" --data data/stage2 >> $L 2>&1 || echo "P$2 [$tag] CRASH rc=$?" >> $L
    ci "$tag"; }

# P16 first -- it is where R=2 was measured at 20% and where the claim can be checked directly.
# Then P1, the instance the hidden set is being played for.  Then the rest of the firing band.
for rep in 1 2 3; do
  for p in 16 1 7 33 3 27; do
    run "R1.p$p.r$rep" $p "WORKERS=4 OGC_WSTAT=1 OGC_RESFRAC=0.05 OGC_ROUNDS=1"
    run "R2.p$p.r$rep" $p "WORKERS=4 OGC_WSTAT=1 OGC_RESFRAC=0.05 OGC_ROUNDS=2"
    run "R3.p$p.r$rep" $p "WORKERS=4 OGC_WSTAT=1 OGC_RESFRAC=0.05 OGC_ROUNDS=3"
  done
done
echo "ROUNDS05DONE" >> $L
echo idle > harness/CURRENT

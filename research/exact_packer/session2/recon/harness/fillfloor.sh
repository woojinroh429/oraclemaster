#!/bin/bash
# A THIRD OF THE BUDGET IS DISCARDED AT 120 s, AND THE THRESHOLD THAT DOES IT WAS CALIBRATED
# SOMEWHERE ELSE.
#
# Mined from every run this project has logged (1,923 rows), median budget utilisation is 98.3%.
# The exceptions are not spread out, they are specific:
#
#     P1  120s  66.7%      P8  120s  63.3%      P2  60s  60.0%
#     P16 120s  74.2%      P33 60s  61.7%       P7/P21/P22 60s  64.2%
#     P27 60s   67.5%      P34 60s  73.3%       P1  60s  81.7%
#     ------------------------------------------------------------
#     nearly every other instance/budget pair   98-100%
#
# The arithmetic is exact.  reserve = RESFRAC * timelimit, so at 120 s with RESFRAC 0.35 the
# workers get 120 - 42 - 1 = 77 s -- and the logs say "ran 79s".  What happens to the other 41 s
# is the fill-round gate:
#
#     if left < _need + 8.0 or min(_rb, left - 8.0) < _ff:  break        # _ff = OGC_FILLFLOOR = 40
#
# At 120 s, left is about 40 and _rb is 77, so min(77, 32) = 32 < 40 and the loop breaks.  The
# 40 s goes to the polish instead, and _z3_improve returns immediately when it has nothing to do --
# so those seconds are discarded.  At 240 s left is about 83, min(155, 75) = 75 clears the floor,
# the fill round runs, and utilisation is 96.7%.  The floor is the whole difference.
#
# WHY THE FLOOR IS NOT WRONG WHERE IT WAS SET, AND MAY BE WRONG HERE.  Its comment records the
# calibration: 35 s failed, 47 s succeeded, 40 splits them -- measured on prob_16 at 240 s, where
# the polish DOES spend its reserve (77 of 84 s).  There the trade is "short fill round" against
# "more polish", and a 27-31 s round losing to the polish is a real result.  At 120 s the polish
# comes back at once, so the trade is "short fill round" against NOTHING AT ALL.  That comparison
# has never been run.
#
# WHAT WOULD MAKE IT FAIL, named first.  A fill round is a fresh draw from the same distribution,
# and the answer is a minimum, so a short round can only help if it lands better than everything
# before it -- with 32 s against a 77 s round-0, that is unlikely per round.  It also costs the
# polish its reserve on instances where the polish is NOT idle, which is why the arms below are
# paired per instance rather than pooled: the ones where the polish works should show the loss.
set -u
cd /home/user/oraclemaster/research/exact_packer/session2/recon || exit 1
while [ "$(cat harness/CURRENT 2>/dev/null)" != "idle" ]; do sleep 20; done
echo fillfloor > harness/CURRENT
L=results/audit/fillfloor.log
mkdir -p results/audit; touch $L
ci(){ ( cd "$(git rev-parse --show-toplevel)" \
        && git add research/exact_packer/session2/recon/results/audit/fillfloor.log \
                  research/exact_packer/session2/recon/harness/CURRENT \
                  research/exact_packer/session2/recon/harness/fillfloor.sh \
        && git commit -q -m "in-flight: fillfloor $1" \
        && git push -q origin claude/repair-plan-model-1ig6it ) >/dev/null 2>&1; }

run(){ # tag prob budget env
    local tag="$1"
    grep -vE '^# ' $L 2>/dev/null | grep -q "\[$tag\]" && return
    echo "# [$tag]" >> $L
    env $4 OGC_DIRGATE=0 timeout $(( $3 * 3 + 60 )) /usr/bin/python3.12 harness/run1.py myalgorithm $2 $3 \
        "[$tag]" --data data/stage2 >> $L 2>&1 || echo "P$2 [$tag] CRASH rc=$?" >> $L
    ci "$tag"
}

# DIRGATE is disabled throughout so this measures the floor and nothing else.
# 120 s, the budget where the waste is largest, on the three instances that show it.
for rep in 1 2; do
  for p in 1 16 8; do
    run "ff.p$p.120.f40.r$rep" $p 120 "WORKERS=4"
    run "ff.p$p.120.f12.r$rep" $p 120 "WORKERS=4 OGC_FILLFLOOR=12"
  done
done
# 60 s, where the leftover is smaller but the polish is idle too.
for p in 22 27 33; do
  run "ff.p$p.60.f40" $p 60 "WORKERS=4"
  run "ff.p$p.60.f12" $p 60 "WORKERS=4 OGC_FILLFLOOR=12"
done
echo "FILLFLOORDONE" >> $L
echo idle > harness/CURRENT

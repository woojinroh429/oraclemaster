#!/bin/bash
# MEASURE THE FILL ROUND FROM INSIDE THE RUN, BECAUSE THE OBJECTIVE CANNOT ANSWER THIS.
#
# fillfloor.sh asked whether recovering the discarded budget improves the objective, paired one
# draw per instance.  That design was wrong and it produced a wrong reading: P16 came back +11.2%
# and was called a loss, when P16's own 120 s control spans 39.1% over 32 logged runs
# (2,828,835 to 3,933,854, median 3,488,736) and both cells sit either side of that median.  One
# pair on these instances cannot resolve anything, which this session has now demonstrated
# repeatedly.
#
# THE QUESTION DOES NOT NEED STATISTICS.  A fill round runs AFTER round 0 and its results enter
# through
#
#     if o < best[0]:  best = (o, s)
#
# a plain minimum.  Extra draws cannot make the answer worse.  The only cost is the reserve it
# takes from the polish, and the gate only opens when the polish was going to idle anyway --
# measured, at 120 s: P1 ran 79 s of 120 with ~2 s of polish, P16 ran 84 s with ~7 s.
#
# So the thing to count is how often the fill round actually SUPPLIES the minimum.  The code
# already prints it under OGC_WSTAT:
#
#     FILL round=N budget=X moved=1 best=Y
#
# moved=1 means that round improved on everything before it.  That is an internal comparison
# inside a single run, so it carries no run-to-run noise at all: either the recovered seconds
# produced a better solution in that run, or they did not.
#
# WHAT THE ANSWER LOOKS LIKE.  moved=1 on a decent fraction of runs means the recovered time is
# worth having and OGC_FILLFLOOR should drop for budgets where the polish idles.  moved=0
# everywhere means the fill round is real but useless -- a 32 s round after a 77 s round-0 simply
# does not beat it -- and the honest conclusion is that the discarded third of the budget cannot
# be spent this way, which is worth knowing and closes the direction.
#
# NOTE ON THE COST SIDE.  This does not measure instances where the polish is NOT idle; there the
# floor should stay where it is.  Utilisation is the discriminator and it is already mined per
# instance/budget, so that gate can be written from data if the count comes back positive.
set -u
cd /home/user/oraclemaster/research/exact_packer/session2/recon || exit 1
while [ "$(cat harness/CURRENT 2>/dev/null)" != "idle" ]; do sleep 20; done
echo fillmoved > harness/CURRENT
L=results/audit/fillmoved.log
mkdir -p results/audit; touch $L
ci(){ ( cd "$(git rev-parse --show-toplevel)" \
        && git add research/exact_packer/session2/recon/results/audit/fillmoved.log \
                  research/exact_packer/session2/recon/harness/CURRENT \
                  research/exact_packer/session2/recon/harness/fillmoved.sh \
        && git commit -q -m "in-flight: fillmoved $1" \
        && git push -q origin claude/repair-plan-model-1ig6it ) >/dev/null 2>&1; }

run(){ # tag prob budget
    local tag="$1"
    grep -vE '^# ' $L 2>/dev/null | grep -q "\[$tag\]" && return
    echo "# [$tag]" >> $L
    WORKERS=4 OGC_DIRGATE=0 OGC_FILLFLOOR=12 OGC_WSTAT=1 \
        timeout $(( $3 * 3 + 60 )) /usr/bin/python3.12 harness/run1.py myalgorithm $2 $3 \
        "[$tag]" --data data/stage2 >> $L 2>&1 || echo "P$2 [$tag] CRASH rc=$?" >> $L
    ci "$tag"
}

# The instances and budgets the utilisation mine flagged as discarding the most.
for rep in 1 2; do
  for p in 1 16 8 2; do
    run "fm.p$p.120.r$rep" $p 120
  done
  for p in 22 27 33 34 7 21; do
    run "fm.p$p.60.r$rep" $p 60
  done
done
echo "FILLMOVEDDONE" >> $L
echo idle > harness/CURRENT

#!/bin/bash
# IS THERE A REVERSAL AT 240 s AT ALL?  THE CROSSOVER HUNT WAS PREMATURE.
#
# nwbud.sh read one pair per instance at 240 s and both favoured w4 (+3.6%, +5.2%), which was
# written up as "the 120 s win does not survive to 240 s".  The very next control draw broke it:
#
#     240 s prob_1 w4   422,629   564,221      span 33.5%
#     240 s prob_1 w3   437,697                beats the second control draw by 22%
#
# The 240 s control is the NOISIEST of the three budgets measured -- 20.0% at 60 s, 13.0% at
# 120 s, 33.5% at 240 s -- and a +3.6% reading inside a 33.5% band is not a reversal, it is one
# lucky control draw.  The assumption that longer budgets are quieter was wrong: more rounds
# means more places for the search to diverge.
#
# SO THE ORDER WAS WRONG.  nwx.sh was queued to bisect a crossover between 120 s and 240 s, but a
# crossover only needs locating if it exists, and one pair per instance does not establish it.
# Five pairs at 240 s answer the question that gates everything downstream; 180 s answers nothing
# until they do.  nwx.sh stays on disk and runs only if the reversal turns out to be real.
#
# prob_1 FIRST, and here is why.  At 240 s a pair costs 8 minutes, so five pairs on both instances
# is 80 minutes.  prob_1 carries the larger measured effect at 120 s (-15.5% vs -5.0%) and the
# wider control band at 240 s, so it is both the more informative and the more demanding cell.
# If the reversal is not there it is nowhere.
set -u
cd /home/user/oraclemaster/research/exact_packer/session2/recon || exit 1
echo nw240 > harness/CURRENT
L=results/audit/nwbud.log
mkdir -p results/audit; touch $L
ci(){ ( cd "$(git rev-parse --show-toplevel)" \
        && git add research/exact_packer/session2/recon/results/audit/nwbud.log \
                  research/exact_packer/session2/recon/harness/CURRENT \
                  research/exact_packer/session2/recon/harness/nw240.sh \
        && git commit -q -m "in-flight: nw240 $1" \
        && git push -q origin claude/repair-plan-model-1ig6it ) >/dev/null 2>&1; }

run(){ # tag prob limit env
    local tag="$1"
    grep -vE '^# ' $L 2>/dev/null | grep -q "\[$tag\]" && return
    echo "# [$tag]" >> $L
    env $4 OGC_WSTAT=1 timeout $(( $3 * 4 + 60 )) /usr/bin/python3.12 harness/run1.py myalgorithm $2 $3 \
        "[$tag]" --data data/stage2 >> $L 2>&1 || echo "P$2 [$tag] CRASH rc=$?" >> $L
    ci "$tag"
}

# take prob_1 to five pairs at 240 s
for rep in 2 3 4 5; do
  run "b240.r$rep.p1.w4" 1 240 "WORKERS=4"
  run "b240.r$rep.p1.w3" 1 240 "WORKERS=3"
done
echo "== NW240 prob_1 done ==" >> $L
# then prob_16 to three
for rep in 2 3; do
  run "b240.r$rep.p16.w4" 16 240 "WORKERS=4"
  run "b240.r$rep.p16.w3" 16 240 "WORKERS=3"
done
echo "NW240DONE" >> $L
echo idle > harness/CURRENT

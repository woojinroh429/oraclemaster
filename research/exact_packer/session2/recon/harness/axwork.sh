#!/bin/bash
# QUALITY AS A FUNCTION OF (AXIS, WORK).  One table that answers the allocation question offline.
#
# WHY THE PREVIOUS QUEUE WAS WRONG.  split.sh compared "one draw of W" against "n draws of W/n"
# with draw i on axis i mod 6 -- so n=1 ran ONLY axis 0 and n=4 ran axes 0-3.  It read -61.87% for
# splitting on prob_16, and that number is an artefact: axis 2 returned 2,477,998 while axes 0, 1
# and 3 returned 6,408,684 / 6,214,513 / 4,876,883 at the same 6,000 work.  The split was not
# competing against a fair baseline, it was competing against the wrong axis.
#
# AND THE ARTEFACT IS MORE INTERESTING THAN THE THING IT BROKE.
#
#     prob_16, work=6000, one beam draw, ~20 s:  axis 2 -> 2,477,998  feasible
#
# The best result this project has ever recorded on prob_16 is 2,795,643, from a 60 s run with the
# polish and OGC_ROUNDS=2; today's 240 s runs return 3.28M-3.66M.  A single draw on the right axis
# beats all of it by 11.4%.
#
# It also explains today's BEAMCAP result.  Axis 2 at 3,000 work returns 3,159,373 and at 6,000
# returns 2,477,998 -- 21.6% for doubling the draw.  Production gives a draw ~14 s, which at the
# measured 220 expansions/s is ~3,000 work, which is exactly where prob_16 sits.  BEAMCAP makes
# draws SMALLER, so on prob_16 it moves the wrong way, and it measured +2.73% there.
#
# A SECOND THING THE WORK MODE MAKES OBVIOUS.  With no clock in the search, one axis at one work
# budget has one answer.  So the production loop's repeated _fresh calls -- axes[gen % 6] -- have
# at most SIX distinct results per work level; every draw past the sixth re-derives an answer
# already held, and only differs in production because the clock perturbs it.  Splitting past six
# buys nothing by construction.
#
# WHAT THIS QUEUE BUILDS.  quality(axis, work) for every axis and four work levels.  From that
# table any allocation policy can be scored WITHOUT running anything further: uniform rotation over
# six axes at W/6 each, everything on the best axis, two axes at W/2, and so on -- all are sums and
# minima over cells that are already measured.  That is the point of a deterministic table; the
# noisy method needed a fresh queue per policy and could not resolve the answer anyway.
#
# Read with:  python3.12 harness/axworkread.py results/audit/axwork.log
set -u
cd "$(dirname "$0")/.." || exit 1
echo axwork > harness/CURRENT
( cd "$(git rev-parse --show-toplevel)" \
  && git add research/exact_packer/session2/recon/harness/CURRENT \
  && git commit -q -m "queue: CURRENT=axwork" \
  && git push -q origin claude/repair-plan-model-1ig6it ) >/dev/null 2>&1
L=results/audit/axwork.log
mkdir -p results/audit; touch $L

# work-major: the cheap levels complete first, so a table exists early even if the run is cut off
for w in 1500 3000 6000 12000; do
  for p in 16 4 24; do
    for ax in 0 1 2 3 4 5; do
      tag="p$p.w$w.a$ax"
      grep -vE '^# ' $L 2>/dev/null | grep -q "\[$tag\]" && continue
      echo "# [$tag]" >> $L
      timeout 1800 /usr/bin/python3.12 harness/beam1.py $p --work $w --axis $ax \
          --tag "[$tag]" >> $L 2>&1 || echo "P$p [$tag] CRASH rc=$?" >> $L
    done
    ( cd "$(git rev-parse --show-toplevel)" \
      && git add research/exact_packer/session2/recon/results/audit/axwork.log \
                research/exact_packer/session2/recon/harness/CURRENT \
      && git commit -q -m "in-flight: axwork p$p w$w" ) >/dev/null 2>&1
  done
  echo "WORKDONE $w" >> $L
done
echo "AXWORKDONE" >> $L
echo idle > harness/CURRENT

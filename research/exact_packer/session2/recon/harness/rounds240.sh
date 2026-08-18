#!/bin/bash
# OGC_ROUNDS AT THE REAL BUDGET.  The knob was retired on a 60 s measurement that could not have
# worked, and it is the largest effect anything in this project has shown.
#
# prob_16 at 60 s, every replicate, min over workers:
#
#     R1   3,513,968  3,513,968  3,513,968  3,513,968      <- today's default
#     R2   2,796,522  2,796,522  2,796,522  2,796,522      -20.42%
#     R3   2,795,643  2,795,643  2,795,643                 -20.44%
#
# Identical to the last digit in every cell.  This is not a lucky draw: it is what the arm returns.
# For scale, the current default at 240 s returned 3,479,878 / 3,602,025 / 3,630,739 / 3,656,247 on
# the same instance today -- four runs spanning 5.1% and every one of them ~23% above what R2 gets
# in a quarter of the time.
#
# Across the eight instances the 60 s sweep covered, worst cell per arm:
#
#     P16 -20.44%   P26 -4.03%   P6 -3.54%   P12 +0.16%   P3 +3.60%   P30 +5.07%   P1 +9.83%
#     P20 +20182.09%   <- 1,858,406,007
#
# WHY P20 BLEW UP, from the code rather than from a guess.  `best` is initialised outside the round
# loop and a round replaces the answer only by beating it, so a bad round cannot damage the result.
# The single path that returns a number like that is `best[1] is None` -- every worker in every
# round returned nothing -- falling through to the _safe_sequential floor.  At 60 s, wbudget ~ 47
# and R=3 gives each round ~15.7 s; a beam on an instance the size of prob_20 does not finish in
# that, returns None, and the run has no answer to keep.
#
# At 240 s the same arithmetic gives wbudget ~ 236 and ~78 s per round -- five times the slice that
# starved.  So the retirement measurement was taken in the one regime where the knob cannot work,
# which is also what the round-loop comment already suspected about R=2 at 60 s.
#
# NO CODE CHANGE FIRST.  A starvation guard (clamp R to what the budget can feed) is obvious and
# will probably be needed, but adding it now would make the result unreadable -- an improvement
# could be the rounds or could be the guard.  Measure the knob as it stands, then fix what the
# measurement shows.
#
# prob_20 is the cell that decides whether this is usable at all: 1,858,406,007 again means R is
# dangerous and needs the guard before anything else; a normal number means the 60 s retirement was
# an artefact of the budget.
#
# Same eight instances as the 60 s sweep so the two tables compare directly.  Instance-major, so an
# early stop leaves complete R1/R2/R3 triples rather than one arm across everything.
set -u
cd "$(dirname "$0")/.." || exit 1
echo rounds240 > harness/CURRENT
( cd "$(git rev-parse --show-toplevel)" \
  && git add research/exact_packer/session2/recon/harness/CURRENT \
  && git commit -q -m "queue: CURRENT=rounds240" \
  && git push -q origin claude/repair-plan-model-1ig6it ) >/dev/null 2>&1
L=results/audit/rounds240.log
mkdir -p results/audit; touch $L

run(){ # rep R prob
    local tag="r$1.R$2.$3"
    grep -vE '^# ' $L 2>/dev/null | grep -q "\[$tag\]" && return
    echo "# [$tag]" >> $L
    OGC_ROUNDS=$2 OGC_WSTAT=1 timeout 1200 /usr/bin/python3.12 harness/run1.py myalgorithm $3 240 \
        "[$tag]" --data data/stage2 >> $L 2>&1 \
        || echo "P$3 [$tag] HANG-OR-CRASH rc=$?" >> $L
    ( cd "$(git rev-parse --show-toplevel)" \
      && git add research/exact_packer/session2/recon/results/audit/rounds240.log \
                research/exact_packer/session2/recon/harness/CURRENT \
      && git commit -q -m "in-flight: rounds240 $tag" ) >/dev/null 2>&1
}

# prob_20 first: it is the one that can kill the idea, and there is no point measuring the other
# seven if R returns the fallback floor at this budget too.  prob_16 second: the -20% claim.
for rep in 1 2; do
    for p in 20 16 1 26 6 3 12 30; do
        for R in 1 2 3; do run $rep $R $p; done
    done
    echo "REPDONE $rep" >> $L
done
echo "ROUNDS240DONE" >> $L
echo idle > harness/CURRENT

#!/bin/bash
# AMPLE TIME CHANGES WHAT IS BINDING.  This is the campaign for that assumption.
#
# Everything measured in this session assumed 60-120 s, because the hidden set was reported to give
# its early instances little time.  Under ample time the constraint moves, and the file already
# records where it moves to:
#
#     "240 s and 360 s return the SAME answer on stage-2 prob_1, giving pref twice its slice
#      changed nothing, and removing operators that earn nothing does not help either.  Time past
#      convergence is spent, not used."
#
# and, from three runs of unchanged code on prob_20: 12,746,324 / 10,628,401 / 10,531,622 -- two of
# three reach the same solution and one misses it by 20%.  So with time to spare the beam is not
# what is short; the number of independent draws is.  The score is a MINIMUM over draws, and the
# distribution of a minimum tightens with the count, not with the length of each one.
#
# THE FOUR QUESTIONS, IN THE ORDER THEIR ANSWERS ARE WORTH:
#
#   A  census   which operators earn anything at a long budget, so the useless ones can go
#   B  rounds   R rounds of nw workers at wbudget/R -- the direct lever on draw count
#   C  reserve  how much of a long budget the polish should hold, now that the beam has slack
#   D  policy   the axis director and the scheduled tardiness pass, at the budget that matters
#
# Four instances spanning the classes: prob_1 (150 blocks, beam finishes, loose), prob_20 (250,
# slice-bound at short budgets), prob_16 (300, the class nothing in this session had run until the
# cliff phase), prob_6 (85% of its objective in w1*Z1).  Per-instance scoring means an arm has to
# hold on all four, not win a median.
set -u
cd /home/user/oraclemaster/research/exact_packer/session2/recon || exit 1
echo long > harness/CURRENT
( cd "$(git rev-parse --show-toplevel)" \
  && git add research/exact_packer/session2/recon/harness/CURRENT \
  && git commit -q -m "queue: CURRENT=long" \
  && git push -q origin claude/repair-plan-model-1ig6it ) >/dev/null 2>&1
L=results/audit/long.log
mkdir -p results/audit; touch $L
ci(){ ( cd "$(git rev-parse --show-toplevel)" \
        && git add research/exact_packer/session2/recon/results/audit/long.log \
                  research/exact_packer/session2/recon/harness/CURRENT \
        && git commit -q -m "in-flight: long $1" \
        && git push -q origin claude/repair-plan-model-1ig6it ) >/dev/null 2>&1; }

run(){ # tag prob limit env
    local tag="$1"
    grep -vE '^# ' $L 2>/dev/null | grep -q "\[$tag\]" && return
    echo "# [$tag]" >> $L
    env $4 timeout $(( $3 * 4 )) /usr/bin/python3.12 harness/run1.py myalgorithm $2 $3 \
        "[$tag]" --data data/stage2 >> $L 2>&1 || echo "P$2 [$tag] CRASH rc=$?" >> $L
    ci "$tag"
}

INST="1 20 16 6"

# A -- OPERATOR CENSUS.  OGC_OPSTAT prints tried / seconds / %budget / gain / gain-per-second for
# every operator in the roster.  Four operators are registered and four more are defined and
# deliberately unregistered because they were measured to earn nothing; the registered four have
# never been read at 240 s on this instance set.  An operator taking budget and returning zero is
# draws not taken, and under a minimum over draws that is the most expensive thing in the file.
for p in $INST; do
  run "cen.p$p" $p 240 "OGC_OPSTAT=1 OGC_WSTAT=1"
done
echo "== CENSUS done ==" >> $L

# PHASE ORDER CHANGED MID-CAMPAIGN, AND THE ROSTER LADDER IS WHY.  prob_1 and prob_20 came back
# with every arm inside the instance's own replicate spread and base nominally best on both:
#
#     P1    base 470,530  nobay 470,530  fill 470,530  beamgrow 612,635  beamonly 530,650
#     P20   base 8,908,086  nobay +3.90%  beamgrow +2.00%  beamonly +2.66%  fill +0.61%
#
# Nothing is removable and nothing is recoverable there.  The two phases below carry the only
# numbers in this campaign that are larger than the noise -- the aim sweep is 17.8% on P36 and
# the round count is the direct lever on a minimum over draws -- so they run first and the rest
# of the roster ladder waits behind them.

# A2 -- THE AIM SPLIT, PROMOTED TO SECOND BECAUSE THE CLIFF LADDER SAYS IT IS THE BIGGEST NUMBER
# HERE.  P36 returned 76,060,831 at 120 s and 76,875,827 at 240 s: doubling the budget bought
# nothing and cost a little.  A longer budget buys WIDTH -- the adaptive controller spends whatever
# the aim allows -- and the file's own aim sweep says width is what is hurting that class:
#
#     aim        0.90         0.45         0.20         0.10
#     P36   89,254,771   84,214,242   75,600,230   73,339,019      -17.8%
#     P13   75,460,745   72,861,873   68,648,923   66,618,791
#
# against +25.09% for the same 0.10 on prob_1, where the beam finishes and a lower aim only takes
# width away.  The shipped portfolio splits the difference 2:2 and never revisits it.
#
# Three arms plus the control: all-low, all-high, and the adaptive rule that has been implemented
# and switched off since it was written.  prob_1 is in the set as the instance the low aim must not
# be allowed to wreck -- per-instance scoring means an arm has to hold everywhere, and all-low is
# exactly the arm that would look wonderful on a mean.
for p in 16 36 1; do
  run "am.p$p.base"  $p 240 ""
  run "am.p$p.lo"    $p 240 "OGC_AIMSET=0.10"
  run "am.p$p.hi"    $p 240 "OGC_AIMSET=0.90"
  run "am.p$p.adapt" $p 240 "OGC_ADAPTAIM=1"
done
echo "== AIM 240 done ==" >> $L

# B -- ROUNDS.  The knob was retired on a measurement that could not have worked: the round loop
# then required a full round plus the polish reserve before starting another, and at the 60 s it
# was read at, wbudget ~ 47, _rb ~ 23 and reserve ~ 12 -- R=2 ran ONE round.  That arithmetic is
# fixed.  At 240 s R=4 gives four rounds of four workers, sixteen draws against four, each on a
# quarter of the slice; whether the shorter slice costs more than the extra draws buy is exactly
# the question ample time makes interesting, because a beam with slack loses little by being
# shortened.
for p in $INST; do
  for r in 1 2 4; do
    run "rd.p$p.R$r" $p 240 "OGC_ROUNDS=$r"
  done
done
echo "== ROUNDS 240 done ==" >> $L

# POLICY MOVED AHEAD OF THE REST.  Four phases have now refuted the premise this campaign was
# built on -- that a long budget is misallocated.  The census found bay taking a fifth of every
# worker for nothing and removing it changed nothing; the roster ladder put every arm inside the
# replicate spread; the fill gate recovered 32 idle seconds and returned the identical answer;
# rounds degrade prob_1 monotonically, +45.13% at R=4.  At 240 s prob_1 has converged and moving
# budget between operators does not buy a better answer.
#
# What does still vary is which BASIN construction reaches: prob_1 returned 524,295 from a plain
# 60 s baseline cell against 470,530 as its best 240 s result, and prob_20 on unchanged code spans
# 12,746,324 / 10,628,401 / 10,531,622.  That is diversity, not allocation, and the two arms below
# are the ones aimed at it -- the axis director, which spends draws on the construction that is
# actually working on THIS instance, and ruin_tardy scheduled beside the beam rather than given a
# constant share of the tail.

# D -- POLICY.  The axis director and the scheduled tardiness pass, at 240 s.  More draws is also
# more evidence for the director to rank axes on, so its case is strongest exactly here; and the
# tardiness pass registered as an operator competes for budget on measured yield instead of a
# constant share, which is what broke it at a fixed half of the tail.
#
# OGC_ADAPTAIM IS IN THIS PHASE BECAUSE THE CLIFF LADDER PUT IT THERE.  aim is the fraction of its
# slice a beam may spend and it becomes width directly.  The sweep in the file is the largest single
# effect recorded anywhere in it:
#
#     aim        0.90         0.45         0.20         0.10
#     P36   89,254,771   84,214,242   75,600,230   73,339,019      -17.8%
#     P25   83,469,231   77,800,747   69,865,266   68,973,666
#     P13   75,460,745   72,861,873   68,648,923   66,618,791
#     P20   10,553,084    9,826,336    9,543,763    9,255,809
#
# and on prob_1, where the beam finishes, the same 0.10 is +25.09% because the low aim only takes
# width away from a beam that had nothing to salvage.  So the portfolio ships a fixed 2:2 split of
# 0.90 and 0.10 and every worker is stuck with whichever it drew.
#
# The cliff ladder is what makes this urgent under an ample-time assumption.  P36 does not improve
# with more budget at all -- base is 76,060,831 at 120 s and 76,875,827 at 240 s -- which is the
# same non-monotonicity: a longer budget buys WIDTH, and on a saturated 300-block instance width is
# what is hurting.  More time cannot help an instance whose beam is already too wide for it; a lower
# aim can, and 73.3M against 89.3M is four times any other effect in this campaign.
#
# _adapt_aim already implements it -- multiplicative decrease when the beam salvaged, additive
# increase when it finished at full width, clamped to the swept range -- and it has been off by
# default and unmeasured since it was written.  It is the same shape as the axis director: replace a
# fixed portfolio position with what this instance's own behaviour reports.
D5="OGC_AXDIR=1 OGC_AXSCAN=0.5"
#
# The separate ADAPTAIM arm is gone: it is the default now, so base already carries it and a
# dedicated cell would be a duplicate.  Four arms, and the two that matter are read separately
# before being read together, because this session has twice shipped a combination whose parts were
# never priced.
#
# z1op IS THE RUIN-AND-RECREATE ONE.  Engine::ruin_tardy tears out late blocks and rebuilds, scoring
# the full objective internally and keeping its own incumbent, so it cannot return something worse
# than it was handed.  It measured 5 of 5 at 60 s and 1 of 4 at 120 s -- but on a base that has
# since been reverted, and given a CONSTANT half of the polish tail, which is exactly what broke it:
# at 60 s the half it took from z3_reassign was idle and at 120 s it was still collecting
# preference.  Registered in the roster it takes what it earns instead, competing with the beam on
# measured yield, which is the arm that has never been read.
for p in $INST; do
  run "po.p$p.base" $p 240 ""
  run "po.p$p.dir5" $p 240 "$D5"
  run "po.p$p.z1op" $p 240 "OGC_Z1OP=1"
  run "po.p$p.both" $p 240 "$D5 OGC_Z1OP=1"
done
echo "== POLICY 240 done ==" >> $L

# A1 -- THE ROSTER, BECAUSE THE CENSUS CAME BACK UNAMBIGUOUS.  Summed over the four workers of each
# 240 s cell:
#
#     cell     op    tried    sec   %budget            gain
#     p1       bay      4    109.8   13.8%          69,945
#     p20      bay      5    161.0   20.3%               0
#     p16      bay      4    158.2   19.9%           9,647
#     p6       bay      4    144.4   18.0%           8,326
#
# against the beam's 3.9e9 to 3.4e10 on the same cells.  bay is registered as a SEARCH operator, so
# its opening probe is a fifth of the budget rather than the budget/(2n) a repair pass gets; it
# spends that fifth, returns nothing, and gain/spent never picks it again -- but the fifth is gone.
# Every worker, every instance, ~19% of the compute for a rounding error.  Under a minimum over
# draws that is draws not taken.
#
# The other two are smaller and not obviously wrong.  grow books 0.9-2.3M for 10-18%, pref 45k-317k
# for 10-15%; both are real, both are three to four orders of magnitude below the beam per second.
# The beam's own figure is inflated -- its total is dominated by the first draw replacing the
# fallback -- so the ladder is measured rather than argued: drop bay, then bay+bal+pref, then
# everything but the beam, and see where it stops paying.
for p in $INST; do
  run "op.p$p.base"     $p 240 ""
  run "op.p$p.nobay"    $p 240 "OGC_OPS=beam,grow,bal,pref"
  run "op.p$p.beamgrow" $p 240 "OGC_OPS=beam,grow"
  run "op.p$p.beamonly" $p 240 "OGC_OPS=beam"
  # THE IDLE TAIL, WHICH THE ROSTER CELLS THEMSELVES EXPOSED.  op.p1.base ran 200 s of its 240:
  # reserve 40, workers 199, polish back in about a second, 39 s left -- and the fill loop's gate
  # is max(8, 0.25*_rb) + 8 = 57.8 s, so it never opens.  16% of a long budget, idle, every run.
  # A fill round cannot make the answer worse (best spans the rounds and is replaced only when
  # beaten), so the gate is a preference about round length being paid for in search.
  run "op.p$p.fill"     $p 240 "OGC_FILLMIN=1"
done
echo "== ROSTER 240 done ==" >> $L

# C -- RESERVE.  The polish converges early by construction -- z3_reassign stops after 4*n_bays+8
# consecutive rounds that find nothing to ruin -- and measured on prob_1 at 240 s it came back in
# about 17 s of the ~120 it was handed.  Whatever it does not spend used to be thrown away; the
# FILL loop now hands it back to the workers, which makes a SMALL reserve safe in a way it was not
# before.  0.05 and 0.10 are below anything shipped.
for p in $INST; do
  for rf in 0.05 0.10; do
    run "rs.p$p.rf$rf" $p 240 "OGC_RESFRAC=$rf"
  done
done
echo "== RESERVE 240 done ==" >> $L

echo "LONGDONE" >> $L
echo idle > harness/CURRENT

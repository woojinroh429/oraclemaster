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

# D -- POLICY.  The axis director and the scheduled tardiness pass, at 240 s.  More draws is also
# more evidence for the director to rank axes on, so its case is strongest exactly here; and the
# tardiness pass registered as an operator competes for budget on measured yield instead of a
# constant share, which is what broke it at a fixed half of the tail.
D5="OGC_AXDIR=1 OGC_AXSCAN=0.5"
for p in $INST; do
  run "po.p$p.base" $p 240 ""
  run "po.p$p.dir5" $p 240 "$D5"
  run "po.p$p.z1op" $p 240 "OGC_Z1OP=1"
  run "po.p$p.both" $p 240 "$D5 OGC_Z1OP=1"
done
echo "== POLICY 240 done ==" >> $L

echo "LONGDONE" >> $L
echo idle > harness/CURRENT

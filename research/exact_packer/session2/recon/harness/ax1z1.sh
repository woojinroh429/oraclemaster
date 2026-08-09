#!/bin/bash
# _AXES[1] REACHES Z1 = 1 ON prob_1.  THAT CHANGES WHAT THE INSTANCE'S FLOOR LOOKS LIKE.
#
# prob_1 weights are w1=6667, w2=3, w3=600, and the axis study's first pass reads:
#
#     arm         obj        Z1     Z2      Z3
#     base     516,577      13    4102     696
#     ax0      518,731      19    3686     635
#     ax1      472,330       1    2221     765      <- essentially no tardiness at all
#     ax2      516,577      13    4102     696
#
# Every result this project has recorded on prob_1 carries Z1 between 7 and 42.  _AXES[1] --
# defer_big, Bmul 1.0, K 4, pos_lam 0.12, fut_beta 1.0, w3mul 3.0, cohort 0.3 -- pinned on all four
# workers reaches Z1 = 1, so the tardiness on this instance is very nearly removable and nothing
# shipped has been removing it.
#
# ARITHMETIC, because it says how much is on the table.  The best objective seen here is 437,484 at
# Z1=15, Z2=3990, Z3=541.  Hold that Z3 and take ax1's Z1:
#
#     6667*15 + 3*3990 + 600*541 = 437,469     what we get
#     6667* 1 + 3*3990 + 600*541 = 343,807     the same layout with ax1's tardiness
#     6667* 1 + 3*2221 + 600*600 = 373,330     ax1's own Z1 and Z2 with a merely good Z3
#
# The third line is roughly where a competitor is reported to sit.  So the gap is not in Z1 and not
# in Z2 -- it is that ax1 pays Z3=765 for its Z1=1, which at w3=600 costs 134,400 against Z3=541.
#
# WHAT THIS QUEUE ASKS.  ax1 gets Z1 to 1 with w3mul=3.0, the HARDEST preference chasing in the
# roster, and still lands on a poor Z3.  So its Z3 is not lost to the beam being uninterested in
# preference; it is lost to the layout the Z1=1 packing forces.  The pass that fixes Z3 after the
# fact is z3_reassign, and it works best exactly where a Z1=1 solution leaves room.  Three levers:
#
#     w3mul   0.5 / 1.0 / 3.0    stop the beam fighting for preference, leave it to the polish
#     resfrac 0.35 / 0.50        give the polish enough budget to collect it
#     dirset  the shipped split, to check ax1 is not simply what dir2 already finds
#
# All pinned to _AXES[1] so the reading is about that construction, and prob_1 only, because that is
# the instance the priority is about.
set -u
cd /home/user/oraclemaster/research/exact_packer/session2/recon || exit 1
echo ax1z1 > harness/CURRENT
( cd "$(git rev-parse --show-toplevel)" \
  && git add research/exact_packer/session2/recon/harness/CURRENT \
  && git commit -q -m "queue: CURRENT=ax1z1" \
  && git push -q origin claude/repair-plan-model-1ig6it ) >/dev/null 2>&1
L=results/audit/ax1z1.log
mkdir -p results/audit; touch $L
ci(){ ( cd "$(git rev-parse --show-toplevel)" \
        && git add research/exact_packer/session2/recon/results/audit/ax1z1.log \
                  research/exact_packer/session2/recon/harness/CURRENT \
        && git commit -q -m "in-flight: ax1z1 $1" \
        && git push -q origin claude/repair-plan-model-1ig6it ) >/dev/null 2>&1; }

run(){ # tag prob limit env
    local tag="$1"
    grep -vE '^# ' $L 2>/dev/null | grep -q "\[$tag\]" && return
    echo "# [$tag]" >> $L
    env $4 OGC_WSTAT=1 timeout $(( $3 * 4 )) /usr/bin/python3.12 harness/run1.py myalgorithm $2 $3 \
        "[$tag]" --data data/stage2 >> $L 2>&1 || echo "P$2 [$tag] CRASH rc=$?" >> $L
    ci "$tag"
}

A1="OGC_AXIS=1"
run "a1.plain"    1 240 "$A1"
run "a1.w05"      1 240 "$A1 OGC_W3MUL=0.5"
run "a1.w10"      1 240 "$A1 OGC_W3MUL=1.0"
run "a1.rf35"     1 240 "$A1 OGC_RESFRAC=0.35"
run "a1.rf50"     1 240 "$A1 OGC_RESFRAC=0.50"
run "a1.w05rf35"  1 240 "$A1 OGC_W3MUL=0.5 OGC_RESFRAC=0.35"
run "a1.w05rf50"  1 240 "$A1 OGC_W3MUL=0.5 OGC_RESFRAC=0.50"
run "a1.nodir"    1 240 "$A1 OGC_DIRSET=0"
echo "== AX1Z1 pass 1 done ==" >> $L

# the two best of the above, repeated, plus the shipped build for reference on the same machine hour
run "ref.ship"    1 240 ""
run "a1.plain.r2" 1 240 "$A1"
run "a1.w05.r2"   1 240 "$A1 OGC_W3MUL=0.5"
echo "AX1Z1DONE" >> $L
echo idle > harness/CURRENT

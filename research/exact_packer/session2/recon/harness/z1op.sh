#!/bin/bash
# THE TARDINESS OPERATOR IS DEFINED, EXPOSED, REGISTERED -- AND FILTERED OUT OF THE ROSTER.
#
#     ("z1", lambda t: _z1_improve(prob_info, pool[0][1], t), True, False, 0.5)]
#     if os.environ.get("OGC_Z1OP") != "1":
#         ops = [o for o in ops if o[0] != "z1"]
#
# so ruin_tardy never runs.  The reason on file is a measurement of a DIFFERENT wiring: as a
# fixed half-and-half share of the polish tail it won 5 of 5 at 60 s and lost 3 of 4 at 120 s,
# because the half it took from z3_reassign was idle at 60 s and working at 120 s (P1 ends
# Z3=608 with it off and Z3=910 with it on).  The file's own note then argues the fix -- give it
# to gain/spent instead of a constant, exactly as `pref` is handled -- and that version has never
# been measured at 240 s.
#
# WHY IT SHOULD MATTER HERE.  z3_reassign's move loop opens with
#
#     if(cur_pen<=0) continue;                          // skip blocks already in their best bay
#     for(int tb=0;tb<n_bays;tb++){ if(prefv(b,tb)<=prefv(b,cur_bay)) continue;
#
# so a block that is LATE but already in its favourite bay is never touched, and a move trading a
# little preference for a lot of tardiness is never generated -- even though the acceptance test
# w1*dtardy + w3*dpen < 0 would take it.  On prob_1, Z1 sits at 7-19 against w1 = 6667, which is
# 11-29% of the objective, and nothing in the roster aims there.
#
# WHY THE SHELVING NOTE DOES NOT APPLY TO prob_1.  It was shelved on the real P6: "102 of 102
# completed rounds were rejected because throughput is fixed and Z1 is conserved under
# rearrangement".  That is a property of a SATURATED yard -- P6 runs at 85% w1*Z1.  prob_1's three
# bays sit at 0.28 / 0.63 / 0.80 utilisation.  Shelved on the wrong instance type.
set -u
cd /home/user/oraclemaster/research/exact_packer/session2/recon || exit 1
echo z1op > harness/CURRENT
L=results/audit/z1op.log
mkdir -p results/audit; touch $L
ci(){ ( cd "$(git rev-parse --show-toplevel)" \
        && git add research/exact_packer/session2/recon/results/audit/z1op.log \
                  research/exact_packer/session2/recon/harness/CURRENT \
        && git commit -q -m "in-flight: z1op $1" \
        && git push -q origin claude/repair-plan-model-1ig6it ) >/dev/null 2>&1; }
run(){ local tag="$1"
    grep -vE '^# ' $L 2>/dev/null | grep -q "\[$tag\]" && return
    echo "# [$tag]" >> $L
    env $4 OGC_WSTAT=1 timeout $(( $3 * 4 )) /usr/bin/python3.12 harness/run1.py myalgorithm $2 $3 \
        "[$tag]" --data data/stage2 >> $L 2>&1 || echo "P$2 [$tag] CRASH rc=$?" >> $L
    ci "$tag"
}
for rep in 1 2 3; do
  run "r$rep.p1.off" 1 240 ""
  run "r$rep.p1.z1"  1 240 "OGC_Z1OP=1"
done
echo "== Z1OP prob_1 done ==" >> $L
for rep in 1 2; do
  for p in 16 3 20; do
    run "r$rep.p$p.off" $p 240 ""
    run "r$rep.p$p.z1"  $p 240 "OGC_Z1OP=1"
  done
done
echo "Z1OPDONE" >> $L
echo idle > harness/CURRENT

#!/bin/bash
# THE SECOND ROUND WITHOUT PAYING FOR IT OUT OF THE FIRST.
#
# What the tailcut queue settled.  A second worker round cuts prob_1's right tail -- four
# replicates, mean -1.04%, worst case -6.38%, run-to-run range 19.4% -> 8.0% -- and prob_16 pays
# +10.69% for it over two replicates, because prob_16's best worker needs the depth: it reaches
# 2,671,848 with a 199 s round and only 2,879,376 with 155 s, and the 67 s second round does not
# recover it.  prob_3 is free (-0.03%) and prob_20 is +2.23%.
#
# That arm bought the round by RAISING THE RESERVE, which shortens round 0 as a side effect --
# 155+76 is 199 minus 44, not 199 plus something.  This arm does not.
#
#     OGC_POLCAP=5     the tail polish is handed the whole reserve and does not want it: prob_3
#                      returns 4,274,798 with a 39 s polish and 4,277,106 with a 5 s one, and
#                      ax1z1 got 422,629 to the digit from an 84 s and a 120 s reserve.  Capping
#                      it releases the reserve's unused seconds.
#     OGC_PARFILL=1    caps the fill gate at 20 s so those seconds can actually open a round --
#                      the shipped gate demands 0.25*_rb = 49.75 s and about 35 would be free.
#
# Round 0 keeps its full 199 s on every instance.  prob_1's second round comes out of the 40 s it
# currently discards (it returns at 200 s of 240); prob_16 returns at 239 s, so its polish is the
# only thing that can lose, and the cap is the one thing being measured against it.
#
# WHAT WOULD REFUTE IT.  If prob_16 loses anyway, its tail polish genuinely earns its 40 s and the
# cap is wrong -- which would be worth knowing on its own, since nothing has ever priced that pass.
# If prob_1 does not gain, a ~27 s round is too short to cut the tail and only the 76 s one does,
# which means the tail cut is unavailable without paying round 0 for it, and variant B is the only
# way to have it.
set -u
cd /home/user/oraclemaster/research/exact_packer/session2/recon || exit 1
echo freeround > harness/CURRENT
( cd "$(git rev-parse --show-toplevel)" \
  && git add research/exact_packer/session2/recon/harness/CURRENT \
  && git commit -q -m "queue: CURRENT=freeround" \
  && git push -q origin claude/repair-plan-model-1ig6it ) >/dev/null 2>&1
L=results/audit/freeround.log
mkdir -p results/audit; touch $L
ci(){ ( cd "$(git rev-parse --show-toplevel)" \
        && git add research/exact_packer/session2/recon/results/audit/freeround.log \
                  research/exact_packer/session2/recon/harness/CURRENT \
        && git commit -q -m "in-flight: freeround $1" \
        && git push -q origin claude/repair-plan-model-1ig6it ) >/dev/null 2>&1; }

run(){ # tag prob limit env
    local tag="$1"
    grep -vE '^# ' $L 2>/dev/null | grep -q "\[$tag\]" && return
    echo "# [$tag]" >> $L
    env $4 OGC_WSTAT=1 timeout $(( $3 * 4 )) /usr/bin/python3.12 harness/run1.py myalgorithm $2 $3 \
        "[$tag]" --data data/stage2 >> $L 2>&1 || echo "P$2 [$tag] CRASH rc=$?" >> $L
    ci "$tag"
}

C="OGC_POLCAP=5 OGC_PARFILL=1"

# prob_16 FIRST.  It is the instance variant B died on, and the only way this arm can lose.
for rep in 1 2; do
  run "r$rep.p16.base" 16 240 ""
  run "r$rep.p16.free" 16 240 "$C"
done
echo "== FREEROUND veto done ==" >> $L

for rep in 1 2 3 4; do
  run "r$rep.p1.base" 1 240 ""
  run "r$rep.p1.free" 1 240 "$C"
done
echo "== FREEROUND prob_1 done ==" >> $L

for rep in 1 2; do
  for p in 3 20 24; do
    run "r$rep.p$p.base" $p 240 ""
    run "r$rep.p$p.free" $p 240 "$C"
  done
done
echo "FREEROUNDDONE" >> $L
echo idle > harness/CURRENT

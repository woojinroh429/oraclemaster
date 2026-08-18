#!/bin/bash
# STOP CREDITING THE FLOOR ESCAPE, SO SELECTION FOLLOWS MARGINAL PAYOFF.
#
# Selection is `max(gain[i]/spent[i])` and the pool starts at the _safe_sequential floor.  Whichever
# operator first replaces it books the whole drop: OPSTAT on prob_1 gives beam 978,969,222 against
# pref's 155,451, with a final objective near 500,000.  After that the rate ordering cannot change.
#
# probe.log is the proof that this decides runs.  Capping the opening slice at 2 s changes only WHO
# wins that race and the band swings 30-60%: prob_1 -7.0%, prob_7 +59.3%, prob_16 +37.5%,
# prob_33 +34.4%, with grow on 90.7% of the budget and beam on 0.0 s.
#
# OGC_GAINFAIR=1 skips the credit for the floor-escaping improvement only.  Smoke on prob_1 at 0.05,
# single worker: the answer is unchanged at 571,668, but the profile moves -- pref goes from 3 tries
# on 11.1% of the budget to 7 tries on 28.0%, and beam from 29.4% to 11.4%.  The reallocation is
# real; whether it is worth anything is what the band decides.
#
# WHAT WOULD MAKE IT FAIL, named first.  prob_1's answer did not move despite the reallocation, so
# the marginal rates may simply not be a better signal than the artefact was -- pref at 7,123/s and
# grow at 268/s are both tiny, and picking between small numbers is not obviously better than
# picking arbitrarily.  And beam losing two thirds of its share is a real risk: beam is the operator
# that produced every answer this study has recorded.
#
# ARMS: J = 0.05 + GAINFAIR.  K = 0.05 + GAINFAIR + PROBE=2, because the two are meant to work
# together -- cheap probes only misfire because the race decides everything, and if the race no
# longer decides everything the probe cap should stop being dangerous.
#
# JUDGED: three draws, paired against final.log's B cells (same engine, same worker count), by
# ratio-mean and geometric mean over the six firing instances.
set -u
cd /home/user/oraclemaster/research/exact_packer/session2/recon || exit 1
while [ "$(cat harness/CURRENT 2>/dev/null)" != "idle" ]; do sleep 15; done
echo gainfair > harness/CURRENT
L=results/audit/gainfair.log
mkdir -p results/audit; touch $L
ci(){ ( cd "$(git rev-parse --show-toplevel)" \
        && git add research/exact_packer/session2/recon/results/audit/gainfair.log \
                  research/exact_packer/session2/recon/harness/CURRENT \
                  research/exact_packer/session2/recon/harness/gainfair.sh \
        && git commit -q -m "in-flight: gainfair $1" \
        && git push -q origin claude/repair-plan-model-1ig6it ) >/dev/null 2>&1; }
run(){ local tag="$1"
    grep -vE '^# ' $L 2>/dev/null | grep -q "\[$tag\]" && return
    echo "# [$tag]" >> $L
    env $3 timeout 220 /usr/bin/python3.12 harness/run1.py myalgorithm $2 60 \
        "[$tag]" --data data/stage2 >> $L 2>&1 || echo "P$2 [$tag] CRASH rc=$?" >> $L
    ci "$tag"; }
for rep in 1 2 3; do
  for p in 1 7 16 33 3 27; do
    run "J.p$p.r$rep" $p "OGC_RESFRAC=0.05 OGC_GAINFAIR=1"
    run "K.p$p.r$rep" $p "OGC_RESFRAC=0.05 OGC_GAINFAIR=1 OGC_PROBE=2"
  done
done
echo "GAINFAIRDONE" >> $L
echo idle > harness/CURRENT

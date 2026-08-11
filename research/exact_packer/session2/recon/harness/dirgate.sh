#!/bin/bash
# DOES THE GATE HELP P1, AND DOES IT HARM ANYTHING ELSE.
#
# OGC_DIRGATE applies the 2.6M-P1 build's whole configuration -- order=lst, w3mul=0.5,
# resfrac=0.50, on every worker -- to instances whose peak simultaneous block area is at most
# 1.30x the total bay area, and nothing else.  Ten of the forty finals instances qualify:
#
#     P22 0.68   P12 0.94   P21 0.94   P1 1.02   P34 1.02
#     P27 1.11   P3 1.18    P7 1.23    P16 1.23  P33 1.24
#
# Of those, three have paired numbers in the file: P1 -13.65%, P16 -24.30% at 240 s, and P3 -2.55%
# on the hidden set.  The other seven are being taken on the mechanism's word, and that is exactly
# what this measures.
#
# ABOVE THE THRESHOLD NOTHING RUNS.  The gate is the only new code on that path and it is a single
# comparison, so a non-firing instance is byte-identical to the build this replaces.  P4 (1.35, the
# nearest non-firing instance and a measured LOSER of this configuration) is run both ways to
# demonstrate that rather than assert it -- if those two rows differ at all, the claim is false.
#
# SHORT BUDGET ON PURPOSE.  The user reports the hidden set gives P1 a short limit, and every
# number in the file for this configuration was taken at 240 s.  Whether a knob measured at 240 s
# survives at 60 s is a separate question that this project has had reverse on it before, so 60 s
# is the primary budget and prob_1 also gets 120 s.
#
# WHAT WOULD MAKE IT FAIL, named first.  A loss on any of the seven untested firing instances is a
# reason to tighten the threshold, not to keep the gate and hope -- the whole promise here is "P1
# and nothing else gets hurt", and one instance going the wrong way breaks it.  One draw per
# instance cannot resolve 1-3%, so anything inside that band is read as no evidence either way; the
# arm is only in trouble if a firing instance moves several per cent the wrong way.
set -u
cd /home/user/oraclemaster/research/exact_packer/session2/recon || exit 1
while [ "$(cat harness/CURRENT 2>/dev/null)" != "idle" ]; do sleep 20; done
echo dirgate > harness/CURRENT
L=results/audit/dirgate.log
mkdir -p results/audit; touch $L
ci(){ ( cd "$(git rev-parse --show-toplevel)" \
        && git add research/exact_packer/session2/recon/results/audit/dirgate.log \
                  research/exact_packer/session2/recon/harness/CURRENT \
                  research/exact_packer/session2/recon/harness/dirgate.sh \
        && git commit -q -m "in-flight: dirgate $1" \
        && git push -q origin claude/repair-plan-model-1ig6it ) >/dev/null 2>&1; }

run(){ # tag prob budget env
    local tag="$1"
    grep -vE '^# ' $L 2>/dev/null | grep -q "\[$tag\]" && return
    echo "# [$tag]" >> $L
    env $4 timeout $(( $3 * 3 + 60 )) /usr/bin/python3.12 harness/run1.py myalgorithm $2 $3 \
        "[$tag]" --data data/stage2 >> $L 2>&1 || echo "P$2 [$tag] CRASH rc=$?" >> $L
    ci "$tag"
}

# 1. the target, both budgets, three replicates
for rep in 1 2 3; do
  run "g.p1.60.off.r$rep"  1 60  "WORKERS=4 OGC_DIRGATE=0"
  run "g.p1.60.on.r$rep"   1 60  "WORKERS=4"
  run "g.p1.120.off.r$rep" 1 120 "WORKERS=4 OGC_DIRGATE=0"
  run "g.p1.120.on.r$rep"  1 120 "WORKERS=4"
done
# 2. the other nine firing instances -- the harm check
for p in 3 7 12 16 21 22 27 33 34; do
  run "g.p$p.60.off" $p 60 "WORKERS=4 OGC_DIRGATE=0"
  run "g.p$p.60.on"  $p 60 "WORKERS=4"
done
# 3. a non-firing instance, and a measured loser of this configuration: must be identical
for p in 4 20; do
  run "g.p$p.60.off" $p 60 "WORKERS=4 OGC_DIRGATE=0"
  run "g.p$p.60.on"  $p 60 "WORKERS=4"
done
echo "DIRGATEDONE" >> $L
echo idle > harness/CURRENT

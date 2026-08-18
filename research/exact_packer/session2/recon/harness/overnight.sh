#!/bin/bash
# THE OVERNIGHT QUEUE.  Runs unattended, in the order that keeps every later answer meaningful.
#
# Every stage writes one result file per run and PUSHES it.  The container has restarted twice
# today, each time rewinding local git and deleting untracked files, so a local commit is not
# durable.  Every stage also skips a run whose result file already exists, so a restart resumes
# instead of repeating.
#
# WHERE THINGS STAND
#
#   P3, three paired reps      nent 6: 80,795 / 80,795 / 84,990   mean 82,193
#                              nent 3: 88,695 / 86,085 / 90,970   mean 88,583   -7.2%
#   P3, step 3 nent 3          81,085 but 279 s -- as good, 39 s too slow
#   P4, nent 6 FORCED          killed at 28 minutes; forced knobs bypass the predictor
#   packer speed               masks verified/measured by stage 0 before anything trusts them
#
# ORDER, AND WHY
#
#   1  PREDICTOR GATE.  nent=6 now sits in _TIERS as the top tier.  The whole question is
#      whether the cost model grants it on P3 and refuses it on P4 -- if it does not, every
#      later stage is measuring a build that would be disqualified.  P4 FIRST because that is
#      the one that fails.
#   2  (3,40,6).  step and nent are different dimensions -- where a block may sit against when
#      it may enter -- and each was worth ~8.7% alone.  If they are independent this is the
#      best P3 available; if the masks did not speed the build enough it will overrun, and that
#      is the answer too.
#   3  P3 REPS at the predictor's own choice, to get a mean rather than a single run against
#      the 3.0% noise band.
#   4  SIX-PROBLEM SWEEP.  P5 and P6 have never been measured on this build at all.  Nothing
#      ships until they are, and P1/P2/P3/P4 are re-run alongside so the set is one comparison
#      rather than six dates.
#
# Budgets are the real ones from HIDDEN_SET.md: P1 60, P2 120, P3 240, P4 480, P5 600, P6 900.
set -u
cd "$(dirname "$0")/.." || exit 1
mkdir -p results
exec 8>"/tmp/ogc_$(basename "$0").lock"
flock -n 8 || { echo "another $(basename "$0") is already running"; exit 0; }
exec 9>/tmp/ogc_experiment.lock
flock 9 || exit 1

say () { echo "=== $* $(date -u +%H:%M:%S)"; }

push () {  # file msg
    ( cd ../../.. && git add -f "research/exact_packer/session2/recon/$1" >/dev/null 2>&1 \
      && git commit -q -m "overnight: $2" >/dev/null 2>&1 \
      && git push -q origin claude/repair-plan-model-1ig6it >/dev/null 2>&1 )
}

run () {  # module prob secs tag outfile [env...]
    local mod=$1 prob=$2 secs=$3 tag=$4 out=$5; shift 5
    [ -s "results/$out" ] && return
    say "$out ($tag)"
    env "$@" timeout $((secs * 5 + 300)) \
        python3.12 harness/run1.py "$mod" "$prob" "$secs" "$tag" > "results/$out" 2>&1
    tail -1 "results/$out"
    push "results/$out" "$tag"
}

OGC_DK=0 OGC_FASTOBJ=1 OGC_BRK=1 \
    python3.12 harness/mkbase.py 0.3 myalg_brk.py 0 "" 0 1.0 "" 0 "" >/dev/null || exit 1
python3.12 -c "
import inspect, myalg_brk as A, bayrepack as R
r = inspect.getsource(R)
assert '(4, 40, 6)' in r, 'the nent=6 tier is not in the table'
assert '_PAIRRATE = [6.4e-08]' in r or '_PAIRRATE = [6.4e-8]' in r, 'rate seed missing'
assert 'import bayrepack as _brk' in inspect.getsource(A)
print('arm and tier table verified')" || exit 1

# ---- 1. does the predictor grant nent=6 on P3 and refuse it on P4?
say "STAGE 1  predictor gate"
run myalg_brk 4 480 "pred P4 r1" "on_pred_p4_r1.log" BRK_DEBUG=1
run myalg_brk 3 240 "pred P3 r1" "on_pred_p3_r1.log" BRK_DEBUG=1

# ---- 2. both dimensions at once, forced, to see if they compose
say "STAGE 2  (3,40,6)"
run myalg_brk 3 240 "s3 n40 e6" "on_s3e6_r1.log" BRK_STEP=3 BRK_NOUT=40 BRK_NENT=6
run myalg_brk 3 240 "s3 n40 e6 r2" "on_s3e6_r2.log" BRK_STEP=3 BRK_NOUT=40 BRK_NENT=6

# ---- 3. reps at the predictor's own choice, for a mean against the 3.0% band
say "STAGE 3  P3 reps"
for rep in 2 3 4; do
    run myalg_brk 3 240 "pred P3 r$rep" "on_pred_p3_r${rep}.log"
done

# ---- 4. the whole set, on the build that would actually ship
say "STAGE 4  six-problem sweep"
run myalg_brk 1  60 "sweep P1" "on_sweep_p1.log"
run myalg_brk 2 120 "sweep P2" "on_sweep_p2.log"
run myalg_brk 5 600 "sweep P5" "on_sweep_p5.log"
run myalg_brk 6 900 "sweep P6" "on_sweep_p6.log"

say "overnight done"

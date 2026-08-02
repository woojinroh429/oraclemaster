#!/bin/bash
# GET P3's 80,795 BACK WITHOUT PUTTING P6 OVER 900 s.
#
# 80,795 is not a fluke.  It is reproduced twice -- bt_4_40_6 and n6_p3_r2, both 239 s of a
# 240 s budget -- by FORCING step 4 / nout 40 / nent 6.  The tier is affordable on P3; the
# chooser simply stopped being allowed to pick it:
#
#     room 97s -> tier 0 (4,40,6)  pred build 62.1s   ncol~31,142    87,990 / 86,635
#     room 40s -> tier 3 (6,10,1)  pred build  8.3s   ncol~11,402    94,630 / 91,250
#
# Capping the ask on the SLICE capped the tier chooser with it.  P3 gives hard=114 s and a 40 s
# slice, and 62.1 > 40, so the lever measured to be worth 8,000 on P3 can no longer be chosen.
#
# WHY THE SLICE LOOKED NECESSARY, AND WHY IT WAS NOT.  The slice was adopted because P6 ran
# 1014 s against 900 s.  But the trace shows the cap was never the leak -- the build PREDICTION
# was:
#
#     pred 107.1s -> build 115.5s        rate 6.9e-08
#     pred 119.3s -> build 202.4s        rate 1.086e-07
#     pred 128.7s -> build 200.3s        rate 9.958e-08
#     pred 132.5s -> build 214.4s        rate 1.036e-07
#
# The seeded _PAIRRATE of 6.4e-08 is 1.6x optimistic on P6, and it never corrects because brk is
# called about once per worker and each worker is its own process.  The column count is fine
# (40,908 estimated against 40,756 real) -- it is the SECONDS that are wrong.
#
# THE FIX REMOVES THE PREDICTION FROM THE DEADLINE.  cranepack now takes total_s and bounds
# build + search against its OWN measured build time:
#
#     search_budget = max(0, total_s - build_ms/1000)
#
# so nothing has to be predicted for the deadline to hold.  The cap goes back to the run's
# remaining time (hard * 0.85), which restores tier 0 on P3, and a mispredicted tier now costs
# search time -- quality -- instead of costing the budget.
#
# WHAT WOULD REFUTE THIS.  If P6 comes back over 900 s, the prediction was not the whole story
# and the slice cap has to return, in which case P3 needs a different answer entirely.  P6
# therefore runs FIRST, before any P3 number can be celebrated.
set -u
cd "$(dirname "$0")/.." || exit 1
mkdir -p results
exec 8>"/tmp/ogc_$(basename "$0").lock"
flock -n 8 || { echo "another $(basename "$0") is already running"; exit 0; }
exec 9>/tmp/ogc_experiment.lock
flock 9 || exit 1

echo "== rebuild cranepack (total_s) $(date -u +%H:%M:%S)"
g++ -O3 -shared -std=c++17 -fPIC -w $(python3.12 -m pybind11 --includes) \
    cranepack.cpp -o cranepack.cpython-312-x86_64-linux-gnu.so || exit 1

python3.12 -c "
import inspect, cranepack as CP, bayrepack as R
# the deadline must be honoured without a prediction, and every old caller must be untouched
import numpy as np
assert 'total_s' in CP.pack.__doc__, CP.pack.__doc__
r = inspect.getsource(R)
assert '_cap = (float(hard) if hard is not None else SL) * 0.85' in r, 'cap is still the slice'
assert '_room = (float(hard) if hard is not None else SL) * 0.85' in r, 'tier chooser still capped'
assert 'total_s=(_cap if _tier >= 0' in r, 'total_s not passed'
print('total_s wired; cap and tier chooser are both the run deadline')" || exit 1

# THE BITSET IS OFF FOR ALL OF THIS.  The same .so also carries the free-column bitset, whose
# placement identity has NOT been proved yet -- the first attempt at proving it was mis-designed
# (it unbound the deadline on a 31k-column tier and had not finished a single arm in 22 minutes).
# Measuring the cap change on an unproven search would confound the two, and this queue is the
# one carrying the 80,795 claim.  CRANEPACK_NOBITS=1 selects the original linear scan, so what
# runs here is the shipped search with exactly one change: total_s.
run () {  # module prob secs tag outfile [env...]
    [ -s "results/$5" ] && return
    echo "=== $5 ($4) $(date -u +%H:%M:%S)"
    env CRANEPACK_NOBITS=1 "${@:6}" BRK_DEBUG=1 timeout $(( $3 * 5 + 300 )) \
        python3.12 harness/run1.py "$1" "$2" "$3" "$4" > "results/$5" 2>&1
    tail -1 "results/$5"
    ( cd ../../.. && git add -f "research/exact_packer/session2/recon/results/$5" >/dev/null 2>&1 \
      && git commit -q -m "result: $4" >/dev/null 2>&1 \
      && git push -q origin claude/repair-plan-model-1ig6it >/dev/null 2>&1 )
}

# P6 is the risk and runs first: if the deadline does not hold, no P3 number matters.
run myalg_brk 6 900 "gb80 P6"     "gb_p6.log"
run myalg_brk 3 240 "gb80 P3 r1"  "gb_p3_r1.log"
run myalg_brk 3 240 "gb80 P3 r2"  "gb_p3_r2.log"
# the ceiling this is chasing, measured again under the new code: tier 0 forced everywhere
run myalg_brk 3 240 "gb80 P3 forced" "gb_p3_forced.log" BRK_STEP=4 BRK_NOUT=40 BRK_NENT=6
run myalg_brk 4 480 "gb80 P4"     "gb_p4.log"
echo "getback80 done $(date -u +%H:%M:%S)"

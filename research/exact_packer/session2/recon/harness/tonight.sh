#!/bin/bash
# Overnight chain.  The speed work is CLOSED -- three attempts, none of them paid -- so this
# just runs the queue against the packer every number today was measured on.
#
#   parallel build   0.9x.  No core was idle: myalg_brk pins OMP_NUM_THREADS=1 because four
#                    worker processes already saturate the 400% cap.
#   entry-time sweep 0.9x.  It removes 330M CHEAP pair-visits; the outer loop's own filters
#                    had already cut 400M to 34.7M, and the cost is the polygon calls that
#                    all pass the time test by definition.
#   layer bitmasks   unmeasured, because my own A/B could not see them -- CRANEPACK_SLOW
#                    switches the loop, and the masks sit inside crane_conflict, so BOTH arms
#                    carried them.  The one indirect number (53.6 s against an earlier 58.3 s,
#                    ~1.09x) is two different runs and inside noise.
#
# cranepack.cpp is back at 5e3d776 and the .so is rebuilt from it, so source and binary agree
# and the queue's results are comparable to everything measured today.
set -u
cd "$(dirname "$0")/.." || exit 1
exec bash harness/overnight.sh

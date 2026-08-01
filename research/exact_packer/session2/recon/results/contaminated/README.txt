q23 results quarantined: TWO queue23.sh processes ran at once (PIDs 1905 and 7082) -- one
launched by hand, one by the keepalive supervisor added to stop queues from dying silently.

The supervisor checks `pgrep -f harness/queue23.sh` before launching, and that raced with the
manual launch.  The per-run guard `[ -s results/$3 ] && return` cannot help once both processes
are past it: each re-ran reps the other had already written.

Caught because the monitor reported q23_warm_r4 = 86,635 (Z2 2507, Z3 494) minutes after I had
read 86,665 (Z2 3023, Z3 477) out of the same file.  The file had been rewritten.

WHAT THIS RETRACTS.  "The control returns 86,665 three times, spread zero, so the current code
is deterministic" is NOT established.  The three cold logs are separate files and each holds one
value, but there is no way to tell whether a value came from an independent run or from one
process overwriting the other's.  The claim that the 9,490 spread was an artefact of mixing
queues with different code also rested on this and is unproven.

The keepalive supervisor is the cause and is removed.  A rerun must be single-instance, and the
queue scripts already hold flock on /tmp/ogc_experiment.lock -- which serialises them against
EACH OTHER but not against a second copy of themselves, because both copies would simply take
the lock in turn and interleave their writes to the same result files.

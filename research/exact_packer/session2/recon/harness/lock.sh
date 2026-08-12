# OWNER-CHECKED LOCK.  Source this; call lock_acquire <tag> and lock_release <tag>.
#
# THE BUG THIS EXISTS TO PREVENT, which cost a full rf7 run and an idle60 run on the night of the
# 12th.  The old protocol was two lines in every script:
#
#     while [ "$(cat harness/CURRENT)" != "idle" ]; do sleep 15; done
#     echo <tag> > harness/CURRENT          ... work ...        echo idle > harness/CURRENT
#
# `echo idle` names no owner, so ANY script's exit frees the lock for EVERYONE.  m120 was believed
# cut but was still running; when its last cell finished at 01:58:49 it wrote `idle` over a lock
# rf7 was holding, and idle60's waiter -- doing exactly what it was told -- started 11 seconds
# later.  Three runs then shared the box.  rf7's six P1 replicates were void and nobody could tell
# from the log, because a contended cell looks exactly like a clean one.
#
# TWO CHANGES.  The file now records "<tag> <pid>", so release can refuse to free another script's
# lock; and acquire treats a lock whose PID is dead as free, so a killed run cannot wedge the queue
# the way the old protocol would have if it had been owner-checked without a liveness test.
#
# The re-read after claiming is not ceremony: two waiters can both see "idle" in the same 15 s
# window and both write.  Whoever's write lands second owns it, so the loser must notice and go
# back to waiting rather than proceed believing it holds the lock.
_LOCKF=harness/CURRENT

_lock_owner_alive(){ # $1 = contents of lock file; true if a live PID owns it
    local _p; _p=$(printf '%s\n' "$1" | awk '{print $2}')
    [ -n "$_p" ] && kill -0 "$_p" 2>/dev/null; }

lock_acquire(){ # $1 = tag
    local _tag="$1" _c
    while :; do
        _c=$(cat "$_LOCKF" 2>/dev/null)
        if [ "$_c" = "idle" ] || [ -z "$_c" ] || ! _lock_owner_alive "$_c"; then
            printf '%s %s\n' "$_tag" "$$" > "$_LOCKF"
            sleep 2
            [ "$(cat "$_LOCKF" 2>/dev/null)" = "$_tag $$" ] && return 0
        fi
        sleep 15
    done; }

lock_release(){ # $1 = tag -- refuses to free a lock this process does not hold
    local _c; _c=$(cat "$_LOCKF" 2>/dev/null)
    if [ "$_c" = "$1 $$" ]; then
        echo idle > "$_LOCKF"
    else
        echo "# LOCK NOT RELEASED by $1/$$: held by '$_c'" >&2
    fi; }

# Any process still running a solver, regardless of which script launched it.  A script that is
# about to take the lock can use this to refuse to start on a box that is not actually quiet --
# the liveness test above only knows about the recorded owner, not about orphans.
lock_box_busy(){ ps -eo args 2>/dev/null | grep -c "[r]un1\.py"; }

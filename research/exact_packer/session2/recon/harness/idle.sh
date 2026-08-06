#!/bin/bash
# NO-OP QUEUE.  harness/CURRENT names the queue keepalive brings back after a restart or a
# compaction, and its fallback when the named file is missing is overnight.sh -- so writing
# "idle" into CURRENT without this file present does not stop the machine, it silently starts
# the overnight queue instead.  That is how r240 came back at 16:34 after being killed.
#
# Existing and doing nothing is the whole job: it gives CURRENT a way to say "nothing should be
# running" that keepalive can actually honour.
exit 0

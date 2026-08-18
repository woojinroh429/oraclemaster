"""Prove the claim the fix rests on: a worker killed by a signal hangs pool.map(), and does not
hang _pool_round().

The bug was found from a kernel line and a missing log entry, which is evidence that something
went wrong, not evidence of WHAT.  The mechanism -- Pool reaps a dead worker and never resubmits
its task, so map() waits on a result that cannot arrive -- is worth demonstrating rather than
asserting, because the whole fix is shaped around it and a wrong mechanism means a wrong fix.

Both arms use the same crashing worker: four workers, one of which raises SIGSEGV on itself.  The
survivors only sleep, so this costs no measurable CPU and can run beside other work.

    arm A   pool.map      -- expected to still be waiting when the cap expires
    arm B   _pool_round   -- expected to return the three survivors, promptly

Run: python3.12 harness/poolhang.py
"""
import multiprocessing
import os
import signal
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import myalgorithm as M          # noqa: E402

CAP = 15.0


def crashy(args):
    """args is _worker's tuple; index 2 is wid.  Worker 1 of 4 dies the way ogc_fast died."""
    if args[2] % 4 == 1:
        os.kill(os.getpid(), signal.SIGSEGV)
    time.sleep(1.0)
    return {"operations": {}, "wid": args[2]}


M._worker = crashy


def arm_map():
    t = time.time()
    q = multiprocessing.Queue()

    def run():
        try:
            with multiprocessing.Pool(processes=4) as pool:
                r = pool.map(crashy, [(None, 5.0, i, None, 0.25, None) for i in range(4)])
            q.put(len(r))
        except Exception as e:
            q.put("raised %s" % type(e).__name__)

    # NOT daemonic.  A daemonic process may not have children, so creating the Pool inside one
    # raises AssertionError at once and the arm "finishes" in 0.0s -- which reads exactly like
    # "map did not hang" and would have retired the bug as a misdiagnosis.
    p = multiprocessing.Process(target=run)
    p.start()
    p.join(CAP)
    el = time.time() - t
    if p.is_alive():
        p.terminate()
        return "STILL WAITING after %.1fs (capped)" % el, el, False
    return "returned %s after %.1fs" % (q.get() if not q.empty() else "?", el), el, True


def arm_round():
    t = time.time()
    out = M._pool_round(None, 5.0, 0, 4, None, None, CAP)
    el = time.time() - t
    # COUNT SURVIVORS, NOT SLOTS.  _pool_round returns a fixed-length list in wid order with None
    # where a worker died, so len(out) is nw whatever happened -- it went on reporting "4 of 4"
    # through a worker that had segfaulted, which is the arm passing while measuring nothing.
    live = sum(1 for s in out if s is not None)
    return ("returned %d live of %d slots after %.1fs" % (live, len(out), el)), el, live == 3


if __name__ == "__main__":
    multiprocessing.set_start_method("fork", force=True)
    a, ael, adone = arm_map()
    print("pool.map      %s" % a, flush=True)
    b, bel, bdone = arm_round()
    print("_pool_round   %s" % b, flush=True)
    # bdone now carries "and exactly the three survivors came back", so a run that returned
    # promptly with the wrong contents fails instead of passing on its timing alone.
    ok = (not adone) and bdone and bel < CAP - 1.0
    print("\n%s: map %s, _pool_round %s"
          % ("PASS" if ok else "FAIL",
             "hangs" if not adone else "did NOT hang -- mechanism is not what was assumed",
             "returns 3 survivors in %.1fs" % bel if bdone else
             "did not return the 3 survivors promptly"))
    sys.exit(0 if ok else 1)

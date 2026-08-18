"""
Faithful micro-benchmark of the ALNS *repair* step, comparing the two ways to
reinsert removed blocks into a partial state:

  (A) Python _try_place_block  on a _CppState  (current v58 behaviour; C++ is used
      only for the per-candidate feasibility check, the candidate loop is Python)
  (B) C++   E.find_best_placement on an ogc_fast.Engine (the whole candidate search
      moves into C++ -- the "CPPREPAIR" idea)

For each trial we pick K random blocks, remove them from an identical reduced
state, reinsert the SAME K blocks in the SAME order both ways, and record:
  - reinsertion wall-time (=> iters/sec proxy; ratio is throttling-robust because
    A and B run back-to-back in the same trial)
  - the resulting FULL-solution objective (quality)
  - how many blocks B failed to seat (find_best_placement returned ok=0)

If B is much faster AND equal-or-better objective => CPPREPAIR is worth wiring in.
If B is faster but worse objective (the line-2338 caveat) => keep it OFF.
"""
import os, sys, json, time, random
os.environ.setdefault("ENGINE_DIR", ".")
sys.path.insert(0, ".")
import myalgorithm as M
from utils import check_feasibility

def build_assign(inst, tl=8.0):
    blocks = inst["blocks"]; n = len(blocks)
    rel = [blocks[b]["release_time"] for b in range(n)]
    due = [blocks[b]["due_date"] for b in range(n)]
    area = []
    for b in range(n):
        bb = M._orient_bbox(blocks[b], 0)
        area.append((bb[2]-bb[0])*(bb[3]-bb[1]))
    order = sorted(range(n), key=lambda b: (rel[b], -area[b], due[b]))
    return M._cppnfp_construct(inst, order, time.time()+tl)

def full_obj(inst, assign, bay_unit):
    return M._objective(list(assign.values()), inst, bay_unit)[0]

def reinsert_order(inst, removed):
    B = inst["blocks"]
    return sorted(removed, key=lambda b: (B[b]["due_date"], B[b]["release_time"],
                                          -B[b]["workload"]))

def build_engine(inst, assign, skip):
    E = M._ogc_fast_engine(inst); E.clear_all()
    for b, a in assign.items():
        if b in skip:
            continue
        E.add(int(a["bay_id"]), b, int(a["orient_idx"]), float(a["x"]),
              float(a["y"]), int(a["entry_time"]), int(a["exit_time"]))
    return E

def cand_times(inst, assign, skip, bid):
    rt = inst["blocks"][bid]["release_time"]
    base = {int(rt)}
    for b, a in assign.items():
        if b in skip:
            continue
        if a["exit_time"] >= rt:
            base.add(int(a["exit_time"]))
    return sorted(base)

_infeasB = 0
_CHECK_FEAS = os.environ.get("CHECKFEAS", "1") == "1"

def main():
    global _infeasB
    path = sys.argv[1] if len(sys.argv) > 1 else "../data/train/prob_20.json"
    ntrials = int(sys.argv[2]) if len(sys.argv) > 2 else 60
    seed = int(sys.argv[3]) if len(sys.argv) > 3 else 12345
    inst = json.load(open(path))
    nm = os.path.basename(path).replace(".json", "")
    bay_unit = M._bay_unit_weights(inst["bays"])
    n_bays = len(inst["bays"])

    assign = build_assign(inst)
    placed = sorted(assign.keys())
    base_obj = full_obj(inst, assign, bay_unit)
    print(f"{nm}: {len(inst['blocks'])} blocks, {len(placed)} seated, base_obj={base_obj:.0f}", flush=True)

    rng = random.Random(seed)
    tA = tB = 0.0
    sumA = sumB = 0.0            # summed resulting objective
    worseB = betterB = eqB = 0  # per-trial objective comparison
    failB = 0                   # blocks B couldn't seat
    failA = 0
    ntr = 0
    for _ in range(ntrials):
        K = rng.randint(2, 14)
        if K > len(placed):
            continue
        removed = rng.sample(placed, K)
        skip = set(removed)
        ins = reinsert_order(inst, removed)
        reduced = {b: dict(a) for b, a in assign.items() if b not in skip}

        # ---- A: Python _try_place_block on a _CppState ----
        stA = M._CppState(inst)
        for b, a in reduced.items():
            bd = inst["blocks"][b]
            blk = M.Block(block_id=b, block_data=bd, x=a["x"], y=a["y"], orient_idx=a["orient_idx"])
            stA.add(dict(a), blk)
        dl = time.time() + 30
        t0 = time.time()
        okA = True
        for b in ins:
            r = M._try_place_block(stA, b, list(range(n_bays)), dl)
            if r is None:
                okA = False
        tA += time.time() - t0
        objA = full_obj(inst, stA.assign, bay_unit) if okA and len(stA.assign) == len(placed) else None
        if objA is None:
            failA += 1

        # ---- B: C++ find_best_placement on ogc_fast.Engine ----
        E = build_engine(inst, assign, skip)
        newB = {}
        t0 = time.time()
        okB = True
        for b in ins:
            ct = cand_times(inst, {**reduced, **newB}, set(), b)
            res = E.find_best_placement(b, list(range(n_bays)), ct)
            if res[0]:
                _, bay, oi, x, y, en, ex = res
                E.add(int(bay), b, int(oi), float(x), float(y), int(en), int(ex))
                newB[b] = {"block_id": b, "bay_id": int(bay), "x": int(x), "y": int(y),
                           "orient_idx": int(oi), "entry_time": int(en), "exit_time": int(ex)}
            else:
                okB = False
                failB += 1
        tB += time.time() - t0
        objB = None
        if okB and len(newB) == K:
            merged = {**reduced, **newB}
            objB = full_obj(inst, merged, bay_unit)
            # CRITICAL: verify B's reinserted solution is actually crane-feasible.
            if _CHECK_FEAS:
                sol = M._build_operations(list(merged.values()))
                ck = check_feasibility(inst, sol)
                if not ck["feasible"]:
                    global _infeasB
                    _infeasB += 1
                    objB = None

        ntr += 1
        if objA is not None:
            sumA += objA
        if objB is not None:
            sumB += objB
        if objA is not None and objB is not None:
            if objB < objA - 1e-6:
                betterB += 1
            elif objB > objA + 1e-6:
                worseB += 1
            else:
                eqB += 1

    print(f"  trials={ntr}  A_time={tA:.2f}s  B_time={tB:.2f}s  speedup={tA/max(tB,1e-9):.1f}x", flush=True)
    print(f"  reinsert-fail:  A={failA}  B_blocks={failB}   B_INFEASIBLE_trials={_infeasB}", flush=True)
    print(f"  objective (summed over trials): A={sumA:.0f}  B={sumB:.0f}  "
          f"B-A={sumB-sumA:+.0f} ({100*(sumB-sumA)/max(sumA,1):+.2f}%)", flush=True)
    print(f"  per-trial quality:  B better={betterB}  equal={eqB}  worse={worseB}", flush=True)
    print("ALLDONE", flush=True)

if __name__ == "__main__":
    main()

"""
Profile the ALNS hotspots + iteration-outcome distribution to find the bottleneck:
why do more ALNS iterations yield little improvement? cProfile the single-worker
solve, and instrument _alns to count outcomes (repair-fail / SA-reject / accepted-worse
/ improved / new-best) and iters/sec.
"""
import os, sys, json, time, cProfile, pstats, io
os.environ.setdefault("ENGINE_DIR", ".")
sys.path.insert(0, ".")
import myalgorithm as M

# ---- instrument _alns: wrap it to count outcomes via a global counter ----
_orig_build = M._build_operations
_stats = {"iters":0}

def profile_solve(path, tl=30):
    inst=json.load(open(path))
    pr=cProfile.Profile()
    pr.enable()
    t0=time.time()
    sol=M._solve_once(inst, tl, seed=12345, shared={}, lock=None, worker_id=0,
                      use_cpp=True, il_mode=False, absorb=False)
    dt=time.time()-t0
    pr.disable()
    s=io.StringIO()
    ps=pstats.Stats(pr, stream=s).sort_stats("cumulative")
    ps.print_stats(25)
    return s.getvalue(), dt, sol

def main():
    path=sys.argv[1] if len(sys.argv)>1 else "../data/train/prob_28.json"
    tl=float(sys.argv[2]) if len(sys.argv)>2 else 30
    out,dt,sol=profile_solve(path,tl)
    print(f"=== {os.path.basename(path)} solve {dt:.1f}s ===")
    # print only lines mentioning our functions / hotspots
    for line in out.splitlines():
        low=line.lower()
        if any(k in line for k in ("_alns","clone","_try_place_block","placement_feasible",
               "check_feasibility","_build_operations","aug_obj","cur_obj","_objective",
               "pick_removal","_op_","add(","remove(","ncalls","cumulative","_CppState","_State")):
            print(line)
    print("ALLDONE")

if __name__=="__main__": main()

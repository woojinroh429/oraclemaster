"""
Test: run _exact_reassign (CP-SAT capacity-feedback global scheduler, currently
gated to low-density z1s<0.5) on P4-class Z1-dominated instances (prob_28/30),
compare its realized objective/Z1 to the baseline construction. Both 'seed' and
'feedback' modes. Budget = 40s (like the construction tail).
"""
import os, sys, json, time
os.environ.setdefault("ENGINE_DIR", ".")
sys.path.insert(0, ".")
import myalgorithm as M
from utils import check_feasibility

def main():
    for path in (sys.argv[1:] or ["../data/train/prob_28.json","../data/train/prob_30.json"]):
        inst=json.load(open(path)); nm=os.path.basename(path).replace(".json","")
        bay_unit=M._bay_unit_weights(inst["bays"])
        # baseline construction
        base=M.algorithm(inst,60); bck=check_feasibility(inst,base)
        line=f"{nm}: baseline obj={bck['objective']:.0f} Z1={bck['obj1']:.0f} Z3={bck['obj3']:.0f}"
        for mode in ("seed","feedback"):
            t0=time.time(); dl=time.time()+40
            try:
                res=M._exact_reassign(inst, bay_unit, dl, mip_cap=6.0, mode=mode)
            except Exception as e:
                line+=f" | {mode}=ERR({e})"; continue
            dt=time.time()-t0
            best = res[0] if isinstance(res, tuple) else res
            if best is None:
                line+=f" | {mode}=None({dt:.0f}s)"; continue
            ck=check_feasibility(inst, M._build_operations([best[b] for b in sorted(best)]))
            if not ck["feasible"]:
                line+=f" | {mode}=INFEAS({dt:.0f}s)"; continue
            d=100*(ck["objective"]-bck["objective"])/bck["objective"]
            line+=f" | {mode} obj={ck['objective']:.0f}({d:+.1f}%) Z1={ck['obj1']:.0f} ({dt:.0f}s)"
        print(line, flush=True)
    print("ALLDONE")

if __name__=="__main__": main()

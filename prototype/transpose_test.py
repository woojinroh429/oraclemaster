"""
Overfitting detector: transpose the WHOLE instance 90 degrees (bay width<->height,
every block-layer vertex (x,y)->(y,x)). This is the SAME problem rotated, so the
optimal objective is identical (Z1/Z2/Z3 don't depend on spatial rotation). If our
algorithm scores much worse on the transposed instance, it is overfit to the
training bay orientation (wide-short strips). A robust/general algorithm is
rotation-invariant.
"""
import os, sys, json, copy, time
os.environ.setdefault("ENGINE_DIR", ".")
sys.path.insert(0, ".")
import myalgorithm as M
from utils import check_feasibility

def transpose(inst):
    t=copy.deepcopy(inst)
    for b in t["bays"]:
        b["width"], b["height"] = b["height"], b["width"]
    for blk in t["blocks"]:
        for orient in blk["shape"]:
            orient["layers"]=[[[y,x] for (x,y) in layer] for layer in orient["layers"]]
    return t

def run(inst):
    t0=time.time(); sol=M.algorithm(inst,60); dt=time.time()-t0
    ck=check_feasibility(inst,sol)
    return ck, dt

def main():
    for path in (sys.argv[1:] or ["../data/train/prob_28.json"]):
        nm=os.path.basename(path).replace(".json","")
        inst=json.load(open(path))
        o,od=run(inst)
        ti=transpose(inst)
        to,td=run(ti)
        if not (o["feasible"] and to["feasible"]):
            print(f"{nm}: orig feas={o['feasible']} trans feas={to['feasible']} !! FEASIBILITY BROKEN",flush=True); continue
        d=100*(to["objective"]-o["objective"])/max(1,o["objective"])
        print(f"{nm}: orig obj={o['objective']:.0f} (Z1={o['obj1']:.0f} Z3={o['obj3']:.0f}) | "
              f"TRANSPOSED obj={to['objective']:.0f} (Z1={to['obj1']:.0f} Z3={to['obj3']:.0f}) | "
              f"delta={d:+.1f}% {'<-- OVERFIT to orientation' if abs(d)>5 else '(rotation-robust)'}",flush=True)
    print("ALLDONE")

if __name__=="__main__": main()

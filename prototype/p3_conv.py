"""
P3-proxy Z3-convergence test. P3 is low-density (Z1=0), Z3(bay-preference)-dominated.
Run Z3-dominated proxies at 60s vs 180s; if Z3 drops with more time, P3 is
search-limited (fixable in 60s), not at a packing floor.
"""
import os, sys, json, time
os.environ.setdefault("ENGINE_DIR", ".")
sys.path.insert(0, ".")
import myalgorithm as M
from utils import check_feasibility

def dc(path, tl):
    inst=json.load(open(path)); w=inst.get("weights",{})
    w1,w2,w3=w.get("w1",1.),w.get("w2",1.),w.get("w3",1.)
    t0=time.time(); sol=M.algorithm(inst,tl); dt=time.time()-t0
    ck=check_feasibility(inst,sol)
    return ck["objective"],ck["obj1"],ck["obj2"],ck["obj3"],w1,w2,w3,dt

def main():
    # Z3-dominated proxies (low-density / preference-heavy) + prob_20 (known P3-class)
    probs = sys.argv[1:] or ["../data/train/prob_20.json","../data/train/prob_22.json",
                             "../data/train/prob_24.json","../data/train/prob_29.json"]
    for path in probs:
        nm=os.path.basename(path).replace(".json","")
        o6,z16,z26,z36,w1,w2,w3,d6=dc(path,60)
        o18,z118,z218,z318,_,_,_,d18=dc(path,180)
        tot6=max(1,o6)
        print(f"{nm} w=({w1:.0f},{w2:.0f},{w3:.0f}) | 60s obj={o6:.0f} "
              f"Z1={z16:.0f} Z2={z26:.0f} Z3={z36:.0f}(w={w3*z36:.0f},{100*w3*z36/tot6:.0f}%) | "
              f"180s obj={o18:.0f} Z3={z318:.0f} | dObj={100*(o18-o6)/tot6:+.1f}% "
              f"dZ3={100*(z318-z36)/max(1,z36):+.1f}%",flush=True)
    print("ALLDONE")

if __name__=="__main__": main()

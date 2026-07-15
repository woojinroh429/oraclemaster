"""
Convergence-asymmetry test. Run P4-scale (n=150) and P5-scale (n=200) proxies at
60s vs 180s. If P4's Z1/obj drops a lot at 180s, P4 is search-limited (fixable in
60s with a better basin). If flat, P4 is at a true floor.
"""
import os, sys, json, time
os.environ.setdefault("ENGINE_DIR", ".")
sys.path.insert(0, ".")
import myalgorithm as M
from utils import check_feasibility

def run(path, tl):
    inst=json.load(open(path)); t0=time.time(); sol=M.algorithm(inst,tl); dt=time.time()-t0
    ck=check_feasibility(inst,sol); return ck["objective"],ck["obj1"],ck["obj3"],dt

def main():
    for path in (sys.argv[1:] or ["../data/train/prob_28.json","../data/train/prob_30.json",
                                   "../data/train/prob_31.json"]):
        nm=os.path.basename(path).replace(".json","")
        o6,z16,z36,d6=run(path,60)
        o18,z118,z318,d18=run(path,180)
        dz1=100*(z118-z16)/max(1,z16); do=100*(o18-o6)/max(1,o6)
        print(f"{nm}: 60s obj={o6:.0f} Z1={z16:.0f} | 180s obj={o18:.0f} Z1={z118:.0f} | "
              f"dObj={do:+.1f}% dZ1={dz1:+.1f}%",flush=True)
    print("ALLDONE")

if __name__=="__main__": main()

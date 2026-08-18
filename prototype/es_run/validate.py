# best_theta 를 여러 인스턴스에서 검증: native rank vs ES-policy 의 Z1/Z2/Z3/obj.
# 목적: 학습이 prob_25에만 과적합인지, 다른 인스턴스로 일반화되는지 판정.
import os, sys, json, glob, numpy as np
ENGINE_DIR=os.environ["ENGINE_DIR"]; sys.path.insert(0,ENGINE_DIR)
import myalgorithm as M
from myalgorithm import _smallright_construct, _build_operations
from utils import check_feasibility
from es_np import prep, forward, rank_base, nparam, shapes, ALPHA
DL=float(os.environ.get("DEADLINE","15")); STEP=int(os.environ.get("STEP","1"))
HID=int(os.environ.get("HIDDEN","32"))

def run(P, pri):
    ext=[float(x) for x in pri]
    recs=_smallright_construct(P["inst"],DL,0.60,STEP,"bigleft","rank",ext_entry=ext,tiebreak="due")
    if not recs or len(recs)!=P["n"]: return None
    ck=check_feasibility(P["inst"], _build_operations(list(recs.values())))
    if not ck.get("feasible"): return None
    return ck
def run_native(P):
    recs=_smallright_construct(P["inst"],DL,0.60,STEP,"bigleft","rank",tiebreak="due")
    if not recs or len(recs)!=P["n"]: return None
    ck=check_feasibility(P["inst"], _build_operations(list(recs.values())))
    return ck if ck.get("feasible") else None

def main():
    theta=np.load(os.environ["THETA"])
    paths=os.environ["VAL"].split(",")
    d=prep(paths[0])["BF"].shape[1]; D=nparam(d,HID)
    assert theta.size==D, f"theta {theta.size} != {D}"
    print(f"{'inst':10s} {'ratio':6s} | {'nat_Z1':>7s} {'es_Z1':>7s} {'dZ1%':>7s} | {'nat_obj':>9s} {'es_obj':>9s} {'dobj%':>7s} | verdict")
    for p in paths:
        P=prep(p)
        try: r=M._demand_ratio(P["inst"],*M._footprint_areas(P["inst"])[:2])
        except Exception: r=float('nan')
        nat=run_native(P)
        es =run(P, rank_base(P)+ALPHA*forward(theta,P["BF"],d,HID))
        if nat is None or es is None:
            print(f"{P['name']:10s} {r:6.3f} | FAIL nat={nat is not None} es={es is not None}"); continue
        z1n,z1e=nat["obj1"],es["obj1"]; on,oe=nat["objective"],es["objective"]
        dz1=100*(z1n-z1e)/max(1,z1n); dob=100*(on-oe)/max(1,on)
        verd="ES win" if oe<on else ("tie" if oe==on else "rank win")
        print(f"{P['name']:10s} {r:6.3f} | {z1n:7.0f} {z1e:7.0f} {dz1:+7.2f} | {on:9.0f} {oe:9.0f} {dob:+7.2f} | {verd}")
if __name__=="__main__": main()

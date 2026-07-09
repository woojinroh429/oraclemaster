# 반복 LNS: {지각 시간창 ruin -> regret recreate -> 개선시 채택} 를 T초 반복.
# rr.py one-shot 이득이 반복 개선루프에 embed 됐을 때 baseline을 실제로 이기는지(robust) 검증.
import os, sys, json, time, random, argparse
sys.path.insert(0, os.environ.get("ENGINE_DIR","../sv34"))
import myalgorithm as M
from myalgorithm import _build_operations, _footprint_areas, _demand_ratio
from utils import check_feasibility
from rr import baseline, recreate_regret, objize

def rand_window(inst, recs, rng, tgt):
    """지각블록 하나를 무작위 중심으로 잡고 |W|<=tgt 창 구성."""
    B=inst["blocks"]; n=len(B)
    tardy=[b for b in range(n) if recs[b]["exit_time"]>B[b]["due_date"]]
    if not tardy: return None
    c=rng.choice(tardy)
    ct=(recs[c]["entry_time"]+recs[c]["exit_time"])//2
    # ct 중심으로 시간반경 확장하며 |W| 제한
    rad=1; W=set()
    while True:
        t1,t2=ct-rad,ct+rad
        Wn=set(b for b in range(n) if recs[b]["entry_time"]<t2 and recs[b]["exit_time"]>t1)
        if len(Wn)>tgt or (t1<-5 and t2>max(recs[b]["exit_time"] for b in range(n))+5):
            break
        W=Wn; rad+=2
    return W if len(W)>=3 else Wn

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("inst")
    ap.add_argument("--cdl",type=float,default=12.0); ap.add_argument("--step",type=int,default=1)
    ap.add_argument("--secs",type=float,default=40.0); ap.add_argument("--tgt",type=int,default=22)
    ap.add_argument("--seed",type=int,default=7); a=ap.parse_args()
    inst=json.load(open(a.inst)); name=os.path.basename(a.inst).replace(".json",""); n=len(inst["blocks"])
    ar,bc,_=_footprint_areas(inst); ratio=_demand_ratio(inst,ar,bc)
    recs,ckb=baseline(inst,a.cdl,a.step)
    if recs is None: print(f"{name}: baseline FAIL"); return
    best=recs; best_obj=ckb['objective']; base_obj=ckb['objective']; base_z1=ckb['obj1']
    print(f"{name} n={n} ratio={ratio:.3f} baseline Z1={base_z1:.0f} obj={base_obj:.0f}")
    rng=random.Random(a.seed); dl=time.time()+a.secs; it=0; acc=0
    while time.time()<dl:
        it+=1
        W=rand_window(inst,best,rng,a.tgt)
        if not W: break
        new=recreate_regret(inst,best,W,ar,k=2)
        if new is None: continue
        ck=objize(inst,new)
        if ck['feasible'] and ck['objective']<best_obj-1e-9:
            best=new; best_obj=ck['objective']; acc+=1
    ckf=objize(inst,best)
    dv=100*(base_obj-best_obj)/base_obj
    print(f"  iterLNS: iters={it} accepts={acc} -> Z1={ckf['obj1']:.0f} obj={best_obj:.0f}  vs baseline {dv:+.2f}%")

if __name__=="__main__": main()

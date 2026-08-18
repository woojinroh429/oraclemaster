# CONTROL: realise v77's OWN schedule with the same naive exact-engine realiser.
# If Z1 blows up vs v77's actual -> the realiser packs worse than v77 (realiser is the culprit).
import json, os, sys
SP="/tmp/claude-0/-home-user-oraclemaster/55043662-747d-5eda-b837-388adc057292/scratchpad"
sys.path.insert(0, os.path.join(SP,"v77")); os.environ["ENGINE_DIR"]=os.path.join(SP,"v77")
import myalgorithm as M
from utils import check_feasibility
from collections import defaultdict
inst=json.load(open(os.path.join(SP,"data/train/prob_38.json"))); B=inst["blocks"]; bays=inst["bays"]; n=len(B); m=len(bays)
pt=[b["processing_time"] for b in B]; rel=[b["release_time"] for b in B]; due=[b["due_date"] for b in B]
sol=M.algorithm(inst,30); ck=check_feasibility(inst,sol)
place={}
for tk,lst in sol["operations"].items():
    for op in lst:
        if op.get("type")=="ENTRY":
            b=op["block_id"]; place[b]=dict(bay=op["bay_id"],x=op["x"],y=op["y"],oi=op["orient_idx"],en=int(tk),ex=int(tk)+pt[b])
print(f"v77 actual Z1={ck['obj1']:.0f}",flush=True)
bybay=defaultdict(list)
for b in place: bybay[place[b]["bay"]].append(b)
def realise(bay,bl,ent):
    E=M._ogc_fast_engine(inst); E.clear_all()
    order=sorted(bl,key=lambda b:(ent[b],due[b])); res={}
    for b in order:
        t=max(ent[b],rel[b]); g=0; ok=False
        while not ok and g<800:
            g+=1; r=E.find_best_placement(b,[bay],[t])
            if r and r[0]:
                _,bj,o,x,y,en,ex=r; E.add(int(bj),b,int(o),float(x),float(y),int(en),int(ex)); res[b]=(en,ex); ok=True
            else: t+=1
        if not ok: res[b]=(place[b]["en"],place[b]["ex"])
    return res
tot=0
for j in range(m):
    bl=bybay[j]
    if not bl: continue
    ent={b:place[b]["en"] for b in bl}   # v77's OWN entry times
    r=realise(j,bl,ent)
    rz=sum(max(0,r[b][1]-due[b]) for b in bl)
    vz=sum(max(0,place[b]["ex"]-due[b]) for b in bl); tot+=rz
    print(f"  bay{j}: v77_actual_Z1={vz}  realiser_on_v77sched={rz}  {'SAME' if rz==vz else ('WORSE +'+str(rz-vz) if rz>vz else 'better')}",flush=True)
print(f"  TOTAL realiser-on-v77-schedule Z1={tot} vs v77 actual {ck['obj1']:.0f}",flush=True)

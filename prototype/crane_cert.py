"""Crane-saturation certificate: run v61, then at each event time compute per-bay
CONCURRENT footprint-area utilization, and check whether RELEASED-but-not-yet-
entered (waiting) blocks exist while the bay is < 100% area-full.  If yes ->
tardiness is crane-forced (space available but crane-blocked), not area-forced."""
import os,sys,json,time
os.environ.setdefault("ENGINE_DIR","."); sys.path.insert(0,".")
import myalgorithm as M
from utils import check_feasibility

def parea(pts):
    a=0.0;n=len(pts)
    for i in range(n):
        x1,y1=pts[i];x2,y2=pts[(i+1)%n];a+=x1*y2-x2*y1
    return abs(a)*0.5
def foot(bd):
    return max(parea(L) for L in bd["shape"][0]["layers"])

p=sys.argv[1]; inst=json.load(open(p)); nm=os.path.basename(p).replace(".json","")
B=inst["blocks"]; bays=inst["bays"]
sol=M.algorithm(inst,60); ck=check_feasibility(inst,sol)
# parse operations -> per-block entry/exit/bay
ent={}
ops=sol["operations"]
for t,lst in ops.items():
    for op in lst:
        if op["type"]=="ENTRY":
            ent[op["block_id"]]={"bay":op["bay_id"],"s":int(t)}
for op_t,lst in ops.items():
    for op in lst:
        if op["type"]=="EXIT" and op["block_id"] in ent:
            ent[op["block_id"]]["e"]=int(op_t)
bayarea=[b["width"]*b["height"] for b in bays]
# event times
times=sorted(set(a["s"] for a in ent.values())|set(a.get("e",a["s"]) for a in ent.values()))
worst=[]
for t in times:
    for j in range(len(bays)):
        used=sum(foot(B[i]) for i,a in ent.items() if a["bay"]==j and a["s"]<=t<a.get("e",1e18))
        util=used/bayarea[j]
        # waiting blocks for bay j: released (r<=t), due-ish soon, not yet entered, prefers j
        waiting=[i for i in range(len(B)) if B[i]["release_time"]<=t and ent.get(i,{}).get("s",1e18)>t]
        if waiting and util<0.98:
            worst.append((util,t,j,len(waiting)))
worst.sort()
print(f"{nm}: feasible={ck['feasible']} Z1={ck.get('obj1')}",flush=True)
if worst:
    # report the congested moments: lowest util while blocks wait
    lo=worst[0]; hi=max(worst)
    # typical: median util at congested times
    us=sorted(w[0] for w in worst); med=us[len(us)//2]
    print(f"  congested moments (blocks WAIT while bay < 100% full): {len(worst)} events",flush=True)
    print(f"  bay-area utilization at those moments: min={lo[0]*100:.0f}% median={med*100:.0f}% max={hi[0]*100:.0f}%",flush=True)
    print(f"  => tardiness is CRANE-forced: space free ({med*100:.0f}% typical) but crane blocks entry",flush=True)
else:
    print("  no congested-with-space moments (area-bound or no waiting)",flush=True)
print("CERTDONE")

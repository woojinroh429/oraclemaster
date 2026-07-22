"""Clean rollout (pilot) look-ahead test vs greedy, on ONE congested bay, using the
fast recon engine (RASTER).  For each block (EDD order) we enumerate several feasible
positions at its earliest entry and, for each, greedily roll out the next K blocks and
score their tardiness -> commit the position that least harms the future (directly tests
whether crane-shadow-aware look-ahead beats the myopic bottom-left greedy).
Usage: python3.12 rollout_test.py prob_27 [K=6] [NALT=6]
"""
import json,os,sys,time
from collections import defaultdict
SP="/tmp/claude-0/-home-user-oraclemaster/55043662-747d-5eda-b837-388adc057292/scratchpad"
ENG=os.path.join(SP,"v77rec"); sys.path.insert(0,ENG); os.environ["ENGINE_DIR"]=ENG; os.environ["NICE"]="0"
import myalgorithm as M
from utils import check_feasibility
NAME=sys.argv[1] if len(sys.argv)>1 else "prob_27"
K=int(sys.argv[2]) if len(sys.argv)>2 else 6
NALT=int(sys.argv[3]) if len(sys.argv)>3 else 6
d=json.load(open(os.path.join(SP,"data/train",NAME+".json"))); B=d["blocks"]; bays=d["bays"]
rt=[b["release_time"] for b in B]; pt=[b["processing_time"] for b in B]; due=[b["due_date"] for b in B]
# heuristic bay assignment (to pick the congested bay + its block set)
sol=M.algorithm(d,15); ck=check_feasibility(d,sol)
pl={}
for tk,lst in sol["operations"].items():
    for op in lst:
        if op.get("type")=="ENTRY": pl[op["block_id"]]=dict(bay=op["bay_id"],ex=int(tk)+pt[op["block_id"]])
bybay=defaultdict(list)
for b in pl: bybay[pl[b]["bay"]].append(b)
J=max(bybay,key=lambda j:sum(max(0,pl[b]["ex"]-due[b]) for b in bybay[j]))
blocks=bybay[J]; heur=sum(max(0,pl[b]["ex"]-due[b]) for b in blocks)
W=bays[J]["width"]; H=bays[J]["height"]
print(f"{NAME} bay{J}: {len(blocks)}blk heur_bayZ1={heur}  (K={K} NALT={NALT})",flush=True)

E=M._ogc_fast_engine(d)
def feas_positions(b, en, cap):
    """a few distinct feasible (oi,x,y) for block b at entry en (greedy-best first + grid spread)."""
    out=[]
    r=E.find_best_placement(b,[J],[en])
    if r[0] and int(r[5])==en: out.append((int(r[2]),int(r[3]),int(r[4])))
    # grid spread candidates
    bd=B[b]
    import itertools
    for oi in range(len(bd["shape"])):
        bb=M._orient_bbox(bd,oi); w=bb[2]-bb[0]; h=bb[3]-bb[1]
        step=max(3, int(min(W,H)/4))
        for gx in range(0,int(W-w)+1,step):
            for gy in range(0,int(H-h)+1,step):
                x=gx-int(bb[0]); y=gy-int(bb[1])
                if E.placement_feasible(J,b,oi,float(x),float(y),en,en+pt[b]):
                    if (oi,x,y) not in out: out.append((oi,x,y))
                    if len(out)>=cap: return out
        if len(out)>=cap: return out
    return out[:cap]

def earliest_entry(b, start):
    for en in range(max(rt[b],start), start+200):
        r=E.find_best_placement(b,[J],[en])
        if r[0]: return en, r
    return None, None

def greedy_finish(order_rest, exits):
    """greedily place remaining blocks (find_best_placement earliest), return added list + tardiness."""
    added=[]; tard=0
    for b in order_rest:
        base=sorted({rt[b]} | {e for e in exits})
        base=[e for e in base if e>=rt[b]] or [rt[b]]
        r=E.find_best_placement(b,[J],base)
        if not r[0]:
            # push later
            en=max(rt[b], max(exits) if exits else rt[b])
            while True:
                r=E.find_best_placement(b,[J],[en])
                if r[0]: break
                en+=1
        _,bay,oi,x,y,en,ex=r
        E.add(int(bay),b,int(oi),float(x),float(y),int(en),int(ex)); added.append(b)
        exits=exits+[int(ex)]; tard+=max(0,int(ex)-due[b])
    return added, tard

def run(use_rollout):
    E.clear_all()
    order=sorted(blocks,key=lambda b:(due[b],rt[b]))
    exits=[]; tard=0; t0=time.time()
    for i,b in enumerate(order):
        base=sorted({rt[b]} | {e for e in exits}); base=[e for e in base if e>=rt[b]] or [rt[b]]
        en,r0=earliest_entry(b, base[0])
        if r0 is None: continue
        if not use_rollout:
            _,bay,oi,x,y,en,ex=r0
            E.add(int(bay),b,int(oi),float(x),float(y),int(en),int(ex)); exits.append(int(ex)); tard+=max(0,int(ex)-due[b]); continue
        # ROLLOUT: try NALT positions, roll out next K blocks, pick min future tardiness
        cands=feas_positions(b,en,NALT)
        best=None; bestpos=None
        future=order[i+1:i+1+K]
        for (oi,x,y) in cands:
            ex=en+pt[b]
            E.add(J,b,int(oi),float(x),float(y),int(en),int(ex))
            added,ftard=greedy_finish(future, exits+[ex])
            for ab in added: E.remove(ab)
            E.remove(b)
            score=max(0,ex-due[b])+ftard
            if best is None or score<best: best=score; bestpos=(oi,x,y,ex)
        oi,x,y,ex=bestpos
        E.add(J,b,int(oi),float(x),float(y),int(en),int(ex)); exits.append(int(ex)); tard+=max(0,ex-due[b])
    return tard, time.time()-t0

gt,gd=run(False); print(f"  GREEDY   bayZ1={gt}  [{gd:.0f}s]",flush=True)
rt_,rd=run(True); print(f"  ROLLOUT  bayZ1={rt_}  [{rd:.0f}s]   vs greedy {gt}  vs heur {heur}  {'WIN' if rt_<gt else ('=' if rt_==gt else 'worse')}",flush=True)
print("ALLDONE",flush=True)

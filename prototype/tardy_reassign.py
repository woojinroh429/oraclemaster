"""
Standalone validator: tardiness-driven earlier-entry reassignment on a solved
assignment. For each tardy block that WAITED (entry>release), try to re-enter it
earlier (entry closer to release) in ANY bay (least-congested first), C++-verify,
accept iff the FULL objective strictly improves. Measure Z1/obj before vs after.
"""
import os, sys, json, time, copy
os.environ.setdefault("ENGINE_DIR", ".")
sys.path.insert(0, ".")
import numpy as np
import myalgorithm as M
from utils import check_feasibility

def reconstruct(inst, sol):
    ops=sol["operations"]; place={}
    for ts,lst in ops.items():
        t=int(ts)
        for o in lst:
            b=o["block_id"]
            if o["type"]=="ENTRY":
                place.setdefault(b,{}).update(bay_id=o["bay_id"],x=o["x"],y=o["y"],
                                              orient_idx=o["orient_idx"],entry_time=t,block_id=b)
            else: place.setdefault(b,{})["exit_time"]=t
    # blocks that never exit within horizon: exit = entry+processing
    for b,p in place.items():
        if "exit_time" not in p:
            p["exit_time"]=p["entry_time"]+inst["blocks"][b]["processing_time"]
    return place

def bbox(B,b,oi):
    L=B[b]["shape"][oi]["layers"]; xs=[q[0] for l in L for q in l]; ys=[q[1] for l in L for q in l]
    return min(xs),min(ys),max(xs),max(ys)

def build_engine(inst, assign, exclude):
    E=M._ogc_fast_engine(inst); E.clear_all()
    for b,a in assign.items():
        if b in exclude: continue
        try: E.add(int(a["bay_id"]),b,int(a["orient_idx"]),float(a["x"]),float(a["y"]),
                   int(a["entry_time"]),int(a["exit_time"]))
        except Exception: pass
    return E

def find_earliest(inst, E, b, bay, en, ex):
    """first-feasible bottom-left position for block b in bay at [en,ex)."""
    B=inst["blocks"]; W=inst["bays"][bay]["width"]; H=inst["bays"][bay]["height"]
    best=None
    for oi in range(len(B[b]["shape"])):
        x0,y0,x1,y1=bbox(B,b,oi)
        if (x1-x0)>W or (y1-y0)>H: continue
        for iy in range(int(np.ceil(-y0)),int(np.floor(H-y1))+1):
            for ix in range(int(np.ceil(-x0)),int(np.floor(W-x1))+1):
                if E.placement_feasible(bay,b,oi,float(ix),float(iy),en,ex):
                    return (oi,ix,iy)
    return None

def main():
    for path in (sys.argv[1:] or ["../data/train/prob_28.json","../data/train/prob_30.json"]):
        inst=json.load(open(path)); B=inst["blocks"]; nbay=len(inst["bays"])
        t0=time.time(); sol=M.algorithm(inst,60); solve_t=time.time()-t0
        assign=reconstruct(inst,sol)
        ck0=check_feasibility(inst,_ops(assign))
        nm=os.path.basename(path).replace(".json","")
        deadline=time.time()+20  # 20s reassignment budget
        cur=ck0["objective"]; moves=0
        for _pass in range(8):
            if time.time()>deadline: break
            # tardy blocks that waited, worst first
            tardy=[]
            for b,a in assign.items():
                tard=max(0,a["exit_time"]-B[b]["due_date"])
                wait=a["entry_time"]-B[b]["release_time"]
                if tard>0 and wait>0: tardy.append((b,tard,wait))
            tardy.sort(key=lambda x:-x[1])
            changed=False
            for b,tard,wait in tardy:
                if time.time()>deadline: break
                rel=B[b]["release_time"]; pt=B[b]["processing_time"]; cur_en=assign[b]["entry_time"]
                # occupancy per bay at candidate earlier times
                E=build_engine(inst,assign,{b})
                done=False
                # try each earlier entry time from release up to just below current
                for en in range(rel, cur_en):
                    ex=en+pt
                    # bays ordered by least present at en
                    def npres(j):
                        return sum(1 for bb,aa in assign.items() if bb!=b and aa["bay_id"]==j
                                   and aa["entry_time"]<ex and aa["exit_time"]>en)
                    for bay in sorted(range(nbay),key=npres):
                        pos=find_earliest(inst,E,b,bay,en,ex)
                        if pos:
                            oi,ix,iy=pos
                            trial=copy.deepcopy(assign)
                            trial[b]={"block_id":b,"bay_id":bay,"x":ix,"y":iy,"orient_idx":oi,
                                      "entry_time":en,"exit_time":ex}
                            ck=check_feasibility(inst,_ops(trial))
                            if ck["feasible"] and ck["objective"]<cur-1e-9:
                                assign=trial; cur=ck["objective"]; moves+=1; changed=True; done=True; break
                    if done: break
                # keep going through tardy list
            if not changed: break
        ck1=check_feasibility(inst,_ops(assign))
        print(f"{nm}: obj {ck0['objective']:.0f} -> {ck1['objective']:.0f} "
              f"({100*(ck1['objective']-ck0['objective'])/ck0['objective']:+.2f}%) | "
              f"Z1 {ck0['obj1']:.0f}->{ck1['obj1']:.0f} Z3 {ck0['obj3']:.0f}->{ck1['obj3']:.0f} | "
              f"moves={moves}")
    print("ALLDONE")

def _ops(assign):
    return M._build_operations(list(assign.values()))

if __name__=="__main__": main()

"""
LOOKAHEAD placement POC (friend's hint: "a rule that looks into the future").
Offline problem => we know all future releases. Compare, in the SAME minimal greedy
crane constructor, two position rules:
  GREEDY   : bottom-left (myopic; ignores future blocks)
  LOOKAHEAD: among the top-M bottom-left candidates, pick the one that keeps the most
             of the next K future blocks still feasibly placeable (reserve room for
             imminent arrivals). If it reduces Z1 (tardiness) vs GREEDY, lookahead is
             the lever P4 needs.
Metric: total Z1 (tardiness) of the realized schedule (lower = better).
"""
import os, sys, json, time
os.environ.setdefault("ENGINE_DIR", ".")
sys.path.insert(0, ".")
import numpy as np
import myalgorithm as M

def bbox(B,b,oi):
    L=B[b]["shape"][oi]["layers"]; xs=[q[0] for l in L for q in l]; ys=[q[1] for l in L for q in l]
    return min(xs),min(ys),max(xs),max(ys)

def feasible_positions(inst, E, b, bay, en, ex, step=1, cap=None):
    B=inst["blocks"]; W=inst["bays"][bay]["width"]; H=inst["bays"][bay]["height"]; out=[]
    for oi in range(len(B[b]["shape"])):
        x0,y0,x1,y1=bbox(B,b,oi)
        if (x1-x0)>W or (y1-y0)>H: continue
        for iy in range(int(np.ceil(-y0)),int(np.floor(H-y1))+1,step):
            for ix in range(int(np.ceil(-x0)),int(np.floor(W-x1))+1,step):
                if E.placement_feasible(bay,b,oi,float(ix),float(iy),en,ex):
                    out.append((oi,ix,iy,ix+x0,iy+y0))
                    if cap and len(out)>=cap: return out
    return out

def any_feasible(inst, E, b, bays, en, ex, step=3):
    for bay in range(len(bays)):
        if feasible_positions(inst,E,b,bay,en,ex,step=step,cap=1): return True
    return False

def construct(inst, rule, M_top=6, K_future=3):
    B=inst["blocks"]; bays=inst["bays"]; n=len(B)
    order=sorted(range(n), key=lambda b:(B[b]["release_time"], -_area(B,b)))
    E=M.M._ogc_fast_engine(inst) if hasattr(M,"M") else M._ogc_fast_engine(inst)
    E.clear_all()
    assign={}
    # future map: for lookahead, the blocks after current in release order
    for pos_i,b in enumerate(order):
        rel=B[b]["release_time"]; pt=B[b]["processing_time"]; due=B[b]["due_date"]
        placed=None
        # earliest entry time with a feasible position (search forward, bounded)
        for en in range(rel, rel+80):
            ex=en+pt
            # scan all bays
            allc=[]
            for bay in range(len(bays)):
                for (oi,ix,iy,wx,wy) in feasible_positions(inst,E,b,bay,en,ex,step=1):
                    allc.append((bay,oi,ix,iy,wx,wy))
            if not allc: continue
            if rule=="GREEDY":
                bay,oi,ix,iy,_,_=min(allc,key=lambda c:(c[1] if False else 0, c[5], c[4]))  # (wy,wx) bottom-left
                # proper bottom-left: min (h, wy, wx) — approx by (wy,wx)
                bay,oi,ix,iy,wx,wy=min(allc,key=lambda c:(c[5],c[4]))
                placed=(bay,oi,ix,iy,en,ex); break
            else:
                topM=sorted(allc,key=lambda c:(c[5],c[4]))[:M_top]
                # future blocks = next K in release order
                fut=[order[j] for j in range(pos_i+1, min(pos_i+1+K_future,len(order)))]
                best=None; bestscore=None
                for (bay,oi,ix,iy,wx,wy) in topM:
                    try: E.add(bay,b,oi,float(ix),float(iy),en,ex)
                    except Exception: continue
                    ok=0
                    for f in fut:
                        fr=B[f]["release_time"]; fex=fr+B[f]["processing_time"]
                        if any_feasible(inst,E,f,bays,fr,fex,step=3): ok+=1
                    try: E.remove(bay,b)
                    except Exception: pass
                    key=(-ok, wy, wx)   # keep most future blocks feasible, then bottom-left
                    if bestscore is None or key<bestscore: bestscore=key; best=(bay,oi,ix,iy,en,ex)
                placed=best; break
        if placed is None:
            # fallback: latest attempt at due-pt
            en=max(rel,due-pt); ex=en+pt
            for bay in range(len(bays)):
                fp=feasible_positions(inst,E,b,bay,en,ex,step=2,cap=1)
                if fp: oi,ix,iy,_,_=fp[0]; placed=(bay,oi,ix,iy,en,ex); break
        if placed is None: continue
        bay,oi,ix,iy,en,ex=placed
        try: E.add(bay,b,oi,float(ix),float(iy),en,ex)
        except Exception: continue
        assign[b]={"block_id":b,"bay_id":bay,"x":ix,"y":iy,"orient_idx":oi,"entry_time":en,"exit_time":ex}
    return assign

def _area(B,b):
    best=None
    for oi in range(len(B[b]["shape"])):
        x0,y0,x1,y1=bbox(B,b,oi); a=(x1-x0)*(y1-y0)
        if best is None or a<best: best=a
    return best

def _pref_bay(B,b):
    p=B[b]["bay_preferences"]; return max(range(len(p)),key=lambda j:p[j])

def z1_of(inst,assign):
    B=inst["blocks"]; return sum(max(0,assign[b]["exit_time"]-B[b]["due_date"]) for b in assign)

def main():
    from utils import check_feasibility
    for path in (sys.argv[1:] or ["../data/train/prob_28.json","../data/train/prob_30.json"]):
        inst=json.load(open(path)); nm=os.path.basename(path).replace(".json","")
        for rule in ("GREEDY","LOOKAHEAD"):
            t0=time.time(); a=construct(inst,rule); dt=time.time()-t0
            ck=check_feasibility(inst, M._build_operations([a[b] for b in sorted(a)])) if len(a)==len(inst["blocks"]) else None
            z1=z1_of(inst,a); feas = ck["feasible"] if ck else "partial(%d/%d)"%(len(a),len(inst["blocks"]))
            obj = ck["objective"] if ck and ck["feasible"] else None
            print(f"{nm} {rule:9s}: placed={len(a)}/{len(inst['blocks'])} Z1(sched)={z1} "
                  f"feas={feas} obj={obj} ({dt:.0f}s)",flush=True)
    print("ALLDONE")

if __name__=="__main__": main()

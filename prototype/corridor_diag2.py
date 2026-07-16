"""
Precise corridor-first premise test. For a tardy WAITING block, at the times it is
waiting, in the bay it ends up in: measure FREE floor area (footprint gaps) vs
CRANE-ACCESSIBLE area for that block. If free >> accessible, overhangs block free
floor -> corridor-first (avoid overhangs) has a real target. If free ~ accessible ~0,
the floor is genuinely footprint-full -> no corridor target.
"""
import os, sys, json
os.environ.setdefault("ENGINE_DIR", ".")
sys.path.insert(0, ".")
import numpy as np
import myalgorithm as M

def reconstruct(inst, sol):
    ops=sol["operations"]; place={}
    for ts,lst in ops.items():
        t=int(ts)
        for o in lst:
            b=o["block_id"]
            if o["type"]=="ENTRY":
                place.setdefault(b,{}).update(bay=o["bay_id"],x=o["x"],y=o["y"],oi=o["orient_idx"],en=t)
            else: place.setdefault(b,{})["ex"]=t
    for b,p in place.items():
        if "ex" not in p: p["ex"]=p["en"]+inst["blocks"][b]["processing_time"]
    return place

def bbox(B,b,oi):
    L=B[b]["shape"][oi]["layers"]; xs=[q[0] for l in L for q in l]; ys=[q[1] for l in L for q in l]
    return min(xs),min(ys),max(xs),max(ys)

def raster_union(layers, ox, oy, W, H):
    full=np.zeros((H,W),bool)
    for verts in layers:
        v=np.asarray(verts,float)+np.array([ox,oy])
        if len(v)<3: continue
        x0=max(0,int(np.floor(v[:,0].min())));x1=min(W,int(np.ceil(v[:,0].max())))
        y0=max(0,int(np.floor(v[:,1].min())));y1=min(H,int(np.ceil(v[:,1].max())))
        if x1<=x0 or y1<=y0: continue
        xs=np.arange(x0,x1)+0.5;ys=np.arange(y0,y1)+0.5;gx,gy=np.meshgrid(xs,ys)
        ins=np.zeros(gx.shape,bool);n=len(v);j=n-1
        for i in range(n):
            xi,yi=v[i];xj,yj=v[j]
            ins^=((yi>gy)!=(yj>gy))&(gx<(xj-xi)*(gy-yi)/(yj-yi+1e-12)+xi);j=i
        full[y0:y1,x0:x1]|=ins
    return full

def main():
    for path in (sys.argv[1:] or ["../data/train/prob_28.json","../data/train/prob_30.json"]):
        inst=json.load(open(path)); B=inst["blocks"]; bays=inst["bays"]
        sol=M.algorithm(inst,60); place=reconstruct(inst,sol)
        nm=os.path.basename(path).replace(".json","")
        # pick worst tardy waited block
        cand=[(b,p) for b,p in place.items() if max(0,p["ex"]-B[b]["due_date"])>0 and p["en"]>B[b]["release_time"]]
        if not cand: print(f"{nm}: no tardy-waited"); continue
        hb,ha=max(cand,key=lambda r:r[1]["ex"]-B[r[0]]["due_date"])
        bayj=ha["bay"]; W=bays[bayj]["width"]; H=bays[bayj]["height"]
        rel=B[hb]["release_time"]; enter=ha["en"]
        # measure at each wait time
        rows=[]
        for t in range(rel, enter):
            pres=[b for b,p in place.items() if b!=hb and p["bay"]==bayj and p["en"]<=t<p["ex"]]
            # free floor (footprint gaps)
            occ=np.zeros((H,W),bool)
            for b in pres:
                a=place[b]; occ|=raster_union(B[b]["shape"][a["oi"]]["layers"], a["x"],a["y"],W,H)
            free=int((~occ).sum()); tot=W*H
            # crane-accessible for hb (block 82's shape)
            E=M._ogc_fast_engine(inst); E.clear_all()
            for b in pres:
                a=place[b]
                try: E.add(bayj,b,int(a["oi"]),float(a["x"]),float(a["y"]),int(a["en"]),int(a["ex"]))
                except Exception: pass
            x0,y0,x1,y1=bbox(B,hb,ha["oi"]); acc=0; nn=0
            ex=t+B[hb]["processing_time"]
            for ix in range(int(np.ceil(-x0)),int(np.floor(W-x1))+1):
                for iy in range(int(np.ceil(-y0)),int(np.floor(H-y1))+1):
                    nn+=1
                    if E.placement_feasible(bayj,hb,int(ha["oi"]),float(ix),float(iy),t,ex): acc+=1
            rows.append((t,free,tot,acc,nn))
        avgfree=np.mean([100*f/tt for _,f,tt,_,_ in rows])
        totacc=sum(a for *_,a,_ in rows)
        print(f"{nm}: block {hb} tard={ha['ex']-B[hb]['due_date']} bay={bayj} {W}x{H} waits t[{rel},{enter}) | "
              f"avg FREE floor={avgfree:.0f}% | crane-accessible positions for it across all wait-times={totacc} | "
              f"=> {'OVERHANG-blocked (corridor target!)' if avgfree>15 and totacc==0 else 'footprint-full (no corridor target)' if avgfree<10 else 'mixed'}",flush=True)
    print("ALLDONE")

if __name__=="__main__": main()

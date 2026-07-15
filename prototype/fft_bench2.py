"""
Decisive measurement (real bay size): cost of the full C++ position scan for ONE
block placement vs the FFT correlation cost at the same bay size. Reconstructs a
real congested bay state from a solved instance's operation schedule.
"""
import os, sys, json, time
os.environ.setdefault("ENGINE_DIR", ".")
sys.path.insert(0, ".")
import numpy as np
import myalgorithm as M

def rasterize(verts, W, H, ox, oy):
    verts = np.asarray(verts, float) + np.array([ox, oy])
    if len(verts) < 3: return np.zeros((H, W), bool)
    x0=max(0,int(np.floor(verts[:,0].min())));x1=min(W,int(np.ceil(verts[:,0].max())))
    y0=max(0,int(np.floor(verts[:,1].min())));y1=min(H,int(np.ceil(verts[:,1].max())))
    if x1<=x0 or y1<=y0: return np.zeros((H,W),bool)
    xs=np.arange(x0,x1)+0.5; ys=np.arange(y0,y1)+0.5; gx,gy=np.meshgrid(xs,ys)
    inside=np.zeros(gx.shape,bool); n=len(verts); j=n-1
    for i in range(n):
        xi,yi=verts[i]; xj,yj=verts[j]
        inside ^= ((yi>gy)!=(yj>gy))&(gx<(xj-xi)*(gy-yi)/(yj-yi+1e-12)+xi); j=i
    full=np.zeros((H,W),bool); full[y0:y1,x0:x1]=inside; return full

def reconstruct(sol):
    ops = sol["operations"]
    place={}  # bid -> dict
    for t_str, lst in ops.items():
        t=int(t_str)
        for o in lst:
            b=o["block_id"]
            if o["type"]=="ENTRY":
                place.setdefault(b,{}).update(bay=o["bay_id"],x=o["x"],y=o["y"],oi=o["orient_idx"],en=t)
            else:
                place.setdefault(b,{})["ex"]=t
    return place

def main():
    path=sys.argv[1] if len(sys.argv)>1 else "../data/train/prob_30.json"
    tl=float(sys.argv[2]) if len(sys.argv)>2 else 60
    inst=json.load(open(path)); B=inst["blocks"]; bays=inst["bays"]
    sol=M.algorithm(inst,tl); place=reconstruct(sol)
    # busiest bay/time
    by_bay={}
    for b,p in place.items():
        if "en" in p and "ex" in p and "bay" in p: by_bay.setdefault(p["bay"],[]).append(b)
    bayj=max(by_bay,key=lambda j:len(by_bay[j]))
    W=bays[bayj]["width"]; H=bays[bayj]["height"]
    members=by_bay[bayj]
    def present(t): return [b for b in members if place[b]["en"]<=t<place[b]["ex"]]
    hb=max(members,key=lambda b:len(present(place[b]["en"])))
    en,ex=place[hb]["en"],place[hb]["ex"]
    co=[b for b in members if b!=hb and place[b]["en"]<ex and place[b]["ex"]>en]
    print(f"{os.path.basename(path)} bay={bayj} {W}x{H}={W*H}cells | held {hb} [{en},{ex}) co-present={len(co)}")

    E=M._ogc_fast_engine(inst); E.clear_all()
    for b,p in place.items():
        if b==hb: continue
        try: E.add(int(p["bay"]),b,int(p["oi"]),float(p["x"]),float(p["y"]),int(p["en"]),int(p["ex"]))
        except Exception: pass
    def bb(b,oi):
        L=B[b]["shape"][oi]["layers"]; xs=[q[0] for l in L for q in l]; ys=[q[1] for l in L for q in l]
        return min(xs),min(ys),max(xs),max(ys)
    norients=len(B[hb]["shape"])
    # (A) full C++ scan
    reps=5; t0=time.time(); ccalls=0; feas=0
    for _ in range(reps):
        ccalls=0; feas=0
        for oi in range(norients):
            x0,y0,x1,y1=bb(hb,oi)
            if (x1-x0)>W or (y1-y0)>H: continue
            for ix in range(int(np.ceil(-x0)),int(np.floor(W-x1))+1):
                for iy in range(int(np.ceil(-y0)),int(np.floor(H-y1))+1):
                    ccalls+=1
                    if E.placement_feasible(bayj,hb,oi,float(ix),float(iy),en,ex): feas+=1
    tA=(time.time()-t0)/reps
    # (B) FFT correlation cost at same size (obstacle FFT built once, reused per orient)
    maxL=max(len(B[b]["shape"][place[b]["oi"]]["layers"]) for b in co) if co else 1
    t0=time.time()
    for _ in range(reps):
        raw=[np.zeros((H,W),bool) for _ in range(maxL)]
        for b in co:
            p=place[b]; layers=B[b]["shape"][p["oi"]]["layers"]
            for jl,l in enumerate(layers):
                if jl<maxL: raw[jl]|=rasterize(l,W,H,p["x"],p["y"])
        Ok=[None]*maxL; acc=np.zeros((H,W),bool)
        for k in range(maxL-1,-1,-1): acc=acc|raw[k]; Ok[k]=acc.copy()
        bh_pad=H+2; fw=W+H
        FOk=[np.fft.rfft2(o.astype(np.float64),s=(H+H,W+W)) for o in Ok]
        surv=0
        for oi in range(norients):
            x0,y0,x1,y1=bb(hb,oi)
            if (x1-x0)>W or (y1-y0)>H: continue
            layers=B[hb]["shape"][oi]["layers"]
            infeas=None
            for k,l in enumerate(layers):
                if k>=maxL: break
                m=rasterize(l,W,H,-x0,-y0)
                FN=np.fft.rfft2(m[::-1,::-1].astype(np.float64),s=(H+H,W+W))
                c=np.fft.irfft2(FOk[k]*FN,s=(H+H,W+W))
                infeas = c if infeas is None else infeas+c
            surv += int((infeas<0.5).sum())
    tB=(time.time()-t0)/reps
    print(f"(A) full C++ scan : {ccalls} calls, {feas} feasible, {tA*1000:.3f}ms/placement ({tA*1e6/max(ccalls,1):.3f}us/call)")
    print(f"(B) FFT full map  : maxL={maxL}, {tB*1000:.3f}ms/placement (obstacle-FFT reused across {norients} orients)")
    print(f"    ratio A/B = {tA/max(tB,1e-9):.2f}x  (FFT map replaces the {ccalls} C++ feas calls)")
    print("ALLDONE")

if __name__=="__main__": main()

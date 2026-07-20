"""Pairwise crane+overlap CONFLICT generator for the set-packing packer.

Two placed blocks A,B (each: world-coord layer polygons, entry, exit) CONFLICT iff
they are co-present in time AND some layer geometry violates the grader's j>=k rule:
  - resting  (j==k): layer k of A vs layer k of B overlap
  - descent  : the LATER-entering block's layer k vs the other's layer j>k
  - ascent   : the EARLIER-exiting block's layer k vs the other's layer j>k
Verified against utils.check_feasibility on random 2-block placements.
"""
import json, os, sys, math
SP="/tmp/claude-0/-home-user-oraclemaster/55043662-747d-5eda-b837-388adc057292/scratchpad"
sys.path.insert(0, os.path.join(SP,"v71")); os.chdir(os.path.join(SP,"v71"))
import myalgorithm as M
from shapely.geometry import Polygon
from shapely import STRtree  # noqa
# grader counts a collision when intersection AREA > 0 (edge-touching = LineString,
# area 0 -> allowed).  Match it exactly; a packer must NOT miss any real overlap
# (false-negative = infeasible output).  A tiny epsilon guards pure float noise on
# genuine touching but is far below any real overlap on integer-positioned polygons.
EPS=1e-9

def world_layers(d, bid, x, y, o):
    """list of shapely Polygons, one per layer, at placement (x,y,orient o).
    Uses layers_at_pos() (WORLD coords, translation applied) -- NOT resolved_layers()
    which returns origin-frame vertices and would ignore (x,y)."""
    bd=d["blocks"][bid]
    blk=M.Block(block_id=bid, block_data=bd, x=int(x), y=int(y), orient_idx=int(o))
    out=[]
    for L in blk.layers_at_pos():
        pts=[(float(p[0]),float(p[1])) for p in L]
        out.append(Polygon(pts) if len(pts)>=3 else None)
    return out

def _ov(pa, pb):
    if pa is None or pb is None: return False
    if not pa.is_valid: pa=pa.buffer(0)
    if not pb.is_valid: pb=pb.buffer(0)
    # AABB quick reject
    ax0,ay0,ax1,ay1=pa.bounds; bx0,by0,bx1,by1=pb.bounds
    if ax1<=bx0 or bx1<=ax0 or ay1<=by0 or by1<=ay0: return False
    return pa.intersection(pb).area > 0.0   # grader: area>0 (touching=LineString area 0 allowed)

def conflict(La, ea, xa, Lb, eb, xb):
    """La/Lb: layer polygons; (ea,xa)/(eb,xb): entry/exit of A/B."""
    if not (ea < xb and eb < xa):  # not co-present (half-open)
        return False
    Ka, Kb = len(La), len(Lb)
    # resting j==k
    for k in range(min(Ka, Kb)):
        if _ov(La[k], Lb[k]): return True
    # descent: later-entering block sweeps down through the other's upper layers
    if ea >= eb:  # A enters at/after B -> A descends through B
        for k in range(Ka):
            for j in range(k+1, Kb):
                if _ov(La[k], Lb[j]): return True
    if eb >= ea:  # B descends through A
        for k in range(Kb):
            for j in range(k+1, Ka):
                if _ov(Lb[k], La[j]): return True
    # ascent: earlier-exiting block sweeps up through the other's upper layers
    if xa <= xb:  # A exits at/before B -> A ascends through B
        for k in range(Ka):
            for j in range(k+1, Kb):
                if _ov(La[k], Lb[j]): return True
    if xb <= xa:  # B ascends through A
        for k in range(Kb):
            for j in range(k+1, Ka):
                if _ov(Lb[k], La[j]): return True
    return False

# ---------- verification against grader PRIMITIVES (ground truth) ----------
def grader_conflict(bay, A, B, ea, xa, eb, xb):
    from utils import check_collisions, check_entry, check_exit
    if not (ea < xb and eb < xa): return False   # not co-present
    if check_collisions(bay, [A, B]): return True                       # resting j==k
    if ea >= eb and check_entry(bay, [B], A): return True               # A descends thru B
    if eb >= ea and check_entry(bay, [A], B): return True               # B descends thru A
    if xa <= xb and check_exit(bay, [B], A): return True                # A ascends thru B
    if xb <= xa and check_exit(bay, [A], B): return True                # B ascends thru A
    return False

def _inbounds_pos(bb, W, H, rng):
    xlo,xhi=int(math.ceil(-bb[0])), int(math.floor(W-bb[2]))
    ylo,yhi=int(math.ceil(-bb[1])), int(math.floor(H-bb[3]))
    if xlo>xhi or ylo>yhi: return None
    return rng.randint(xlo,xhi), rng.randint(ylo,yhi)

def verify(name, trials=600):
    import random
    from utils import Bay
    d=json.load(open(_find(name))); B=d["blocks"]; bays=d["bays"]; n=len(B); m=len(bays)
    rng=random.Random(0); mism=0; cop=0; concnt=0
    for _ in range(trials):
        i=rng.randrange(n); k=rng.randrange(n)
        if i==k: continue
        j=rng.randrange(m); W=bays[j]["width"]; H=bays[j]["height"]
        oi=rng.randrange(len(B[i]["shape"])); ok=rng.randrange(len(B[k]["shape"]))
        bi=M._orient_bbox(B[i],oi); bk=M._orient_bbox(B[k],ok)
        pi=_inbounds_pos(bi,W,H,rng); pk=_inbounds_pos(bk,W,H,rng)
        if pi is None or pk is None: continue
        xi,yi=pi; xk,yk=pk
        # force frequent co-presence: overlapping intervals near a common base
        base=rng.randint(0,5)
        ei=B[i]["release_time"]+base; xi_t=ei+B[i]["processing_time"]
        ek=B[k]["release_time"]+rng.randint(-3,3)
        # align so they co-present often: pull ek toward ei
        ek=max(0, ei + rng.randint(-B[i]["processing_time"], B[i]["processing_time"]))
        xk_t=ek+B[k]["processing_time"]
        co = (ei < xk_t and ek < xi_t)
        if co: cop+=1
        La=world_layers(d,i,xi,yi,oi); Lb=world_layers(d,k,xk,yk,ok)
        myc=conflict(La,ei,xi_t,Lb,ek,xk_t)
        bayj=Bay(width=W,height=H,id=j)
        A=M.Block(block_id=i,block_data=B[i],x=xi,y=yi,orient_idx=oi)
        Bk=M.Block(block_id=k,block_data=B[k],x=xk,y=yk,orient_idx=ok)
        gc=grader_conflict(bayj,A,Bk,ei,xi_t,ek,xk_t)
        if myc: concnt+=1
        if myc!=gc:
            mism+=1
            if mism<=8:
                print(f"  MISMATCH mine={myc} grader={gc} blk=({i},{k}) t=({ei},{xi_t}),({ek},{xk_t})", flush=True)
    print(f"{name}: {trials} trials, {cop} co-present, {concnt} conflicts, MISMATCHES={mism}", flush=True)

def _find(n):
    for sub in ("data/training_instances/train","data/train"):
        p=os.path.join(SP,sub,n+".json")
        if os.path.exists(p): return p

if __name__=="__main__":
    for nm in ["prob_20","prob_17"]:
        verify(nm, trials=500)

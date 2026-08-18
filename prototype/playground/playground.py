# 수동 배치 실험 하네스 (공식 geometry 사용). 전략 = (블록순서, 위치스코어).
# density-score / pair-packing / area / bigleft 등을 꽂아 공식 채점기로 비교.
import sys, os, json, math, time, itertools
from utils import (Bay, Block, check_entry, check_exit, check_collisions,
                   check_feasibility, _resolve_layers, _bounding_box)
from baseline_greedy import _block_bbox, _candidate_positions, _find_earliest_slot
from shapely.geometry import Polygon
from shapely.ops import unary_union

def _build_operations(assignments):
    buckets={}
    for a in assignments:
        buckets.setdefault(a["exit_time"],[]).append((0,"EXIT",a))
        buckets.setdefault(a["entry_time"],[]).append((1,"ENTRY",a))
    ops={}
    for t in sorted(buckets):
        row=[]
        for _,kind,a in sorted(buckets[t],key=lambda z:z[0]):
            if kind=="ENTRY":
                row.append({"type":"ENTRY","block_id":a["block_id"],"bay_id":a["bay_id"],
                            "x":a["x"],"y":a["y"],"orient_idx":a["orient_idx"]})
            else:
                row.append({"type":"EXIT","block_id":a["block_id"],"bay_id":a["bay_id"]})
        ops[str(t)]=row
    return {"operations":ops}

# ---- 블록 기하 특성 (orientation별) ----
def orient_geom(bd, oi):
    layers=_resolve_layers(bd["shape"][oi]["layers"])
    polys=[Polygon([(float(p[0]),float(p[1])) for p in L]) for L in layers]
    polys=[p for p in polys if p.is_valid and p.area>0]
    foot=unary_union(polys)                     # footprint (union of layers)
    area=foot.area
    x0,y0,x1,y1=_block_bbox(bd,oi)
    bbox_area=max(1e-9,(x1-x0)*(y1-y0))
    hull=foot.convex_hull.area if area>0 else 1e-9
    return dict(area=area, bbox=bbox_area, hull=max(1e-9,hull),
                w=x1-x0, h=y1-y0, rect_density=area/bbox_area, hull_density=area/max(1e-9,hull))

def block_feats(prob):
    B=prob["blocks"]; n=len(B); feats=[]
    for i in range(n):
        gs=[orient_geom(B[i],oi) for oi in range(len(B[i]["shape"]))]
        # 대표: 최대 footprint area orientation
        rep=max(gs,key=lambda g:g["area"])
        feats.append(dict(idx=i, area=rep["area"], geoms=gs,
                          rect_density=max(g["rect_density"] for g in gs),
                          hull_density=max(g["hull_density"] for g in gs),
                          due=B[i]["due_date"], rel=B[i]["release_time"], pt=B[i]["processing_time"]))
    return feats

# ---- 그리디 배치기: 주어진 순서로, 위치는 pos_score 최소 ----
def place(prob, order, pos_score, deadline=1e9):
    B=prob["blocks"]; bays=prob["bays"]; m=len(bays)
    Bay_objs=[Bay(width=bays[j]["width"],height=bays[j]["height"]) for j in range(m)]
    placed_in_bay={j:[] for j in range(m)}       # list[Block]
    sched_in_bay={j:[] for j in range(m)}        # list[(entry,exit)]
    assign={}; t0=time.time()
    for i in order:
        if time.time()-t0>deadline: return None
        bd=B[i]; R=bd["release_time"]; P=bd["processing_time"]; D=bd["due_date"]
        best=None
        for j in range(m):
            bw=bays[j]["width"]; bh=bays[j]["height"]
            for oi in range(len(bd["shape"])):
                x0,y0,x1,y1=_block_bbox(bd,oi)
                if (x1-x0)>bw+1e-6 or (y1-y0)>bh+1e-6: continue
                cands=_candidate_positions(bw,bh,placed_in_bay[j],(x0,y0,x1,y1))
                for (px,py) in cands:
                    blk=Block(block_id=i,block_data=bd,x=float(px),y=float(py),orient_idx=oi)
                    en,ex=_find_earliest_slot(blk,Bay_objs[j],placed_in_bay[j],sched_in_bay[j],R,P)
                    if en is None: continue
                    wx=px+x0; wy=py+y0
                    sc=pos_score(i,j,oi,wx,wy,x1-x0,y1-y0,en,ex,D,bw,bh)
                    if best is None or sc<best[0]:
                        best=(sc,j,oi,px,py,en,ex,blk)
        if best is None: return None
        _,j,oi,px,py,en,ex,blk=best
        placed_in_bay[j].append(blk); sched_in_bay[j].append((en,ex))
        assign[i]={"block_id":i,"bay_id":j,"x":int(px),"y":int(py),"orient_idx":oi,
                   "entry_time":int(en),"exit_time":int(ex)}
    return assign

def evaluate(prob, assign):
    if assign is None or len(assign)!=len(prob["blocks"]): return None
    sol=_build_operations([assign[i] for i in range(len(prob["blocks"]))])
    return check_feasibility(prob, sol)

# ---- 위치 스코어들 ----
def sc_bigleft(i,j,oi,wx,wy,w,h,en,ex,D,bw,bh): return (h, wx, wy, j)       # flattest, left, bottom
def sc_bottomleft(i,j,oi,wx,wy,w,h,en,ex,D,bw,bh): return (wy, wx, j)       # bottom, left
def sc_bigright(i,j,oi,wx,wy,w,h,en,ex,D,bw,bh): return (h, bw-(wx+w), wy, j)

if __name__=="__main__":
    path=sys.argv[1]
    prob=json.load(open(path)); n=len(prob["blocks"])
    F=block_feats(prob)
    orders={
        "area_desc": sorted(range(n), key=lambda i:-F[i]["area"]),
        "rect_dens": sorted(range(n), key=lambda i:(-F[i]["rect_density"], -F[i]["area"])),
        "hull_dens": sorted(range(n), key=lambda i:(-F[i]["hull_density"], -F[i]["area"])),
        "edd":       sorted(range(n), key=lambda i:prob["blocks"][i]["due_date"]),
    }
    print(f"=== {prob['name']} (n={n}) 수동배치 전략 비교 ===")
    for onm,order in orders.items():
        for snm,sc in [("bigleft",sc_bigleft),("bottomleft",sc_bottomleft)]:
            a=place(prob,order,sc)
            ck=evaluate(prob,a)
            if ck and ck["feasible"]:
                print(f"  order={onm:<10} pos={snm:<11} obj={ck['objective']:<9.0f} Z1={ck['obj1']:.0f} Z2={ck['obj2']:.0f} Z3={ck['obj3']:.0f}")
            else:
                print(f"  order={onm:<10} pos={snm:<11} 실패/infeasible")

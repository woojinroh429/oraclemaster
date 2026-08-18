# 수동 배치 하네스 v2: 복합 스코어(tardiness+Z2+선호, packing tie-break) + 전략 실험.
# 전략 = (블록순서, packing tie-break). density-score / pair-packing / bigleft 등 비교.
import sys, os, json, math, time
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

def orient_geom(bd, oi):
    layers=_resolve_layers(bd["shape"][oi]["layers"])
    polys=[Polygon([(float(p[0]),float(p[1])) for p in L]) for L in layers]
    polys=[p for p in polys if p.is_valid and p.area>0]
    foot=unary_union(polys); area=foot.area
    x0,y0,x1,y1=_block_bbox(bd,oi); bbox_area=max(1e-9,(x1-x0)*(y1-y0))
    hull=max(1e-9, foot.convex_hull.area if area>0 else 1e-9)
    return dict(area=area, bbox=bbox_area, hull=hull, w=x1-x0, h=y1-y0,
                rect_density=area/bbox_area, hull_density=area/hull)

def block_feats(prob):
    B=prob["blocks"]; n=len(B); F=[]
    for i in range(n):
        gs=[orient_geom(B[i],oi) for oi in range(len(B[i]["shape"]))]
        rep=max(gs,key=lambda g:g["area"])
        F.append(dict(idx=i, area=rep["area"],
                      rect_density=max(g["rect_density"] for g in gs),
                      hull_density=max(g["hull_density"] for g in gs),
                      due=B[i]["due_date"], rel=B[i]["release_time"], pt=B[i]["processing_time"],
                      wl=B[i]["workload"]))
    return F

def bay_units(prob):
    bays=prob["bays"]; areas=[b["width"]*b["height"] for b in bays]
    avg=sum(areas)/len(areas)
    return [avg/a for a in areas]

# 복합 스코어 greedy. tie_break(...)이 packing 전략(작을수록 우선).
def place(prob, order, tie_break, deadline=1e9, pack_w=1e-4):
    B=prob["blocks"]; bays=prob["bays"]; m=len(bays)
    w=prob["weights"]; w1,w2,w3=w["w1"],w["w2"],w["w3"]
    u=bay_units(prob)
    Bay_objs=[Bay(width=bays[j]["width"],height=bays[j]["height"]) for j in range(m)]
    placed={j:[] for j in range(m)}; sched={j:[] for j in range(m)}
    loads=[0.0]*m; assign={}; t0=time.time()
    for i in order:
        if time.time()-t0>deadline: return None
        bd=B[i]; R=bd["release_time"]; P=bd["processing_time"]; D=bd["due_date"]
        prefs=bd["bay_preferences"]; smax=max(prefs); wl=bd["workload"]
        best=None
        for j in range(m):
            bw=bays[j]["width"]; bh=bays[j]["height"]
            newload=loads[j]+wl
            imb=max((abs(u[j]*newload-u[k]*loads[k]) for k in range(m) if k!=j), default=0.0)
            pref_pen=smax-prefs[j]
            for oi in range(len(bd["shape"])):
                x0,y0,x1,y1=_block_bbox(bd,oi)
                if (x1-x0)>bw+1e-6 or (y1-y0)>bh+1e-6: continue
                pbb=[b.bounding_rect() for b in placed[j]]
                for (px,py) in _candidate_positions(bw,bh,placed[j],(x0,y0,x1,y1)):
                    blk=Block(block_id=i,block_data=bd,x=float(px),y=float(py),orient_idx=oi)
                    en,ex=_find_earliest_slot(blk,Bay_objs[j],placed[j],sched[j],R,P)
                    if en is None: continue
                    tard=max(0,ex-D)
                    wx=px+x0; wy=py+y0
                    tb=tie_break(i,j,oi,wx,wy,x1-x0,y1-y0,en,ex,D,bw,bh,pbb)
                    sc=w1*tard + w2*imb + w3*pref_pen + pack_w*tb
                    if best is None or sc<best[0]:
                        best=(sc,j,oi,px,py,en,ex,blk)
        if best is None: return None
        _,j,oi,px,py,en,ex,blk=best
        placed[j].append(blk); sched[j].append((en,ex)); loads[j]+=wl
        assign[i]={"block_id":i,"bay_id":j,"x":int(px),"y":int(py),"orient_idx":oi,
                   "entry_time":int(en),"exit_time":int(ex)}
    return assign

def evaluate(prob, assign):
    if assign is None or len(assign)!=len(prob["blocks"]): return None
    return check_feasibility(prob,_build_operations([assign[i] for i in range(len(prob["blocks"]))]))

# packing tie-breaks (스칼라, 작을수록 우선). pbb=present 블록 bbox 리스트.
def tb_bigleft(i,j,oi,wx,wy,w,h,en,ex,D,bw,bh,pbb): return wx*1000+wy
def tb_bottom(i,j,oi,wx,wy,w,h,en,ex,D,bw,bh,pbb):  return wy*1000+wx
def tb_bigright(i,j,oi,wx,wy,w,h,en,ex,D,bw,bh,pbb): return (bw-(wx+w))*1000+wy
def tb_topy(i,j,oi,wx,wy,w,h,en,ex,D,bw,bh,pbb):    return (wy+h)*1000+wx
def tb_interlock(i,j,oi,wx,wy,w,h,en,ex,D,bw,bh,pbb):
    # PAIR-PACKING/맞물림: 후보 bbox가 기존 블록 bbox와 겹치는 면적↑ = 오목부에 끼워짐(같은
    # 레이어 충돌은 이미 배제됨). 겹침 클수록 촘촘 -> 음수. tie-break로 좌하단.
    ov=0.0
    for (x0,y0,x1,y1) in pbb:
        dx=min(wx+w,x1)-max(wx,x0); dy=min(wy+h,y1)-max(wy,y0)
        if dx>0 and dy>0: ov+=dx*dy
    return -ov*1000 + wx + wy*0.001

if __name__=="__main__":
    path=sys.argv[1]; DL=float(sys.argv[2]) if len(sys.argv)>2 else 300.0
    prob=json.load(open(path)); n=len(prob["blocks"]); F=block_feats(prob)
    orders={
        "edd":       sorted(range(n), key=lambda i:(F[i]["due"],-F[i]["area"])),
        "area_desc": sorted(range(n), key=lambda i:-F[i]["area"]),
        "rank":      None,  # due-rank+area-rank
        "rect_dens": sorted(range(n), key=lambda i:(-F[i]["rect_density"],-F[i]["area"])),
        "hull_dens": sorted(range(n), key=lambda i:(-F[i]["hull_density"],-F[i]["area"])),
    }
    du=sorted(range(n),key=lambda i:F[i]["due"]); ar=sorted(range(n),key=lambda i:-F[i]["area"])
    rd={b:p for p,b in enumerate(du)}; ra={b:p for p,b in enumerate(ar)}
    orders["rank"]=sorted(range(n),key=lambda i:(rd[i]+ra[i],F[i]["due"]))
    tbs={"bigleft":tb_bigleft,"bigright":tb_bigright,"interlock":tb_interlock}
    print(f"=== {prob['name']} (n={n}) 복합스코어 배치 | DL={DL:.0f}s ===",flush=True)
    best_overall=None
    for onm,order in orders.items():
        for tnm,tb in tbs.items():
            t=time.time(); a=place(prob,order,tb,deadline=DL/ (len(orders)*len(tbs)) *3)
            ck=evaluate(prob,a); dt=time.time()-t
            if ck and ck["feasible"]:
                o=ck["objective"]
                print(f"  {onm:<10} {tnm:<9} obj={o:<10.0f} Z1={ck['obj1']:.0f} Z2={ck['obj2']:.0f} Z3={ck['obj3']:.0f} ({dt:.0f}s)",flush=True)
                if best_overall is None or o<best_overall[0]: best_overall=(o,onm,tnm)
            else:
                print(f"  {onm:<10} {tnm:<9} 실패 ({dt:.0f}s)",flush=True)
    if best_overall: print(f"  >>> 최선: {best_overall[1]}+{best_overall[2]} obj={best_overall[0]:.0f}",flush=True)

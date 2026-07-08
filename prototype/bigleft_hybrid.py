# bigleft 배치정책 재현 + dispatch 순서(rank vs CPSAT) 하이브리드 → realized Z1.
#  bigleft: 큰블록 score=(높이,x,y,bay) 좌측·낮게 클러스터 / 작은블록 score=(-free_span,y,x) gap-fill.
#  feasibility는 비트엔진(크레인 보수적 shadow, 검증 0위반 확인됨).
import sys, json, time
sys.path.insert(0,'/home/user/oraclemaster/prototype')
from ortools.sat.python import cp_model
from solve_setpack import build_placements, exact_check, aabb_offsets

def shoelace(pts):
    a=0.0
    for i in range(len(pts)):
        x1,y1=pts[i]; x2,y2=pts[(i+1)%len(pts)]; a+=x1*y2-x2*y1
    return abs(a)/2.0

def cpsat_order(prob,eff,tl):
    B=prob['blocks']; bays=prob['bays']; n=len(B); m=len(bays)
    dem=[max(1,int(round(shoelace(b['shape'][0]['layers'][0])))) for b in B]
    cap=[max(1,int(round(bays[k]['width']*bays[k]['height']*eff))) for k in range(m)]
    H=max(b['due_date'] for b in B)+max(b['processing_time'] for b in B)+50
    md=cp_model.CpModel(); ent=[md.NewIntVar(B[i]['release_time'],H,'') for i in range(n)]
    pres={}; ivb={k:[] for k in range(m)}; dmb={k:[] for k in range(m)}; tard=[]
    for i in range(n):
        p=B[i]['processing_time']; pl=[]
        for k in range(m):
            pv=md.NewBoolVar(''); pres[i,k]=pv; pl.append(pv)
            ivb[k].append(md.NewOptionalIntervalVar(ent[i],p,ent[i]+p,pv,'')); dmb[k].append(dem[i])
        md.AddExactlyOne(pl)
        t=md.NewIntVar(0,H,''); md.Add(t>=ent[i]+p-B[i]['due_date']); tard.append(t)
    for k in range(m): md.AddCumulative(ivb[k],dmb[k],cap[k])
    md.Minimize(sum(tard))
    so=cp_model.CpSolver(); so.parameters.max_time_in_seconds=tl; so.parameters.num_search_workers=8
    so.Solve(md)
    return [so.Value(ent[i]) for i in range(n)]

def place_bigleft(prob, per_block, Kmax, order, small_thresh=0.60):
    B=prob['blocks']; n=len(B); m=len(prob['bays']); bw=[bb['width'] for bb in prob['bays']]; bh=[bb['height'] for bb in prob['bays']]
    grid={}; placed_by_bay={j:[] for j in range(m)}; chosen=[]; H=max(b['due_date'] for b in B)+500
    # 면적 순위(큰 area=rank0). ra[i]>=thresh → 작은 블록
    ar=[shoelace(B[i]['shape'][0]['layers'][0]) for i in range(n)]
    o=sorted(range(n),key=lambda i:-ar[i]); ra=[0.0]*n
    for p,i in enumerate(o): ra[i]=p/max(1,n-1)
    # placement bbox 캐시
    for i in range(n):
        for p in per_block[i]:
            if 'bbox' not in p:
                ax0,ax1,ay0,ay1=aabb_offsets(B[i],p['o'])
                p['bbox']=(p['x']+ax0,p['x']+ax1,p['y']+ay0,p['y']+ay1); p['h']=ay1-ay0
    def free_span(bay,en,cx0,cx1,cy0):
        band=bh[bay]*0.6; occ=[]
        for (x0,x1,y0,y1,EN,EX) in placed_by_bay[bay]:
            if EN<=en<EX and y0<band: occ.append((x0,x1))
        if cy0<band: occ.append((cx0,cx1))
        occ.sort(); c=0.0; fm=0.0
        for a,b in occ:
            if a>c: fm=max(fm,a-c)
            if b>c: c=b
        return max(fm, bw[bay]-c)
    def fits(p,en,EX):
        for day in range(en,EX):
            for L in range(1,Kmax+1):
                if p['shadow'][L] & grid.get((p['bay'],L,day),0): return False
        return True
    for i in order:
        R=B[i]['release_time']; P=B[i]['processing_time']; D=B[i]['due_date']; sml=ra[i]>=small_thresh
        found=None
        for en in range(R,H-P):
            EX=en+P; best=None
            for p in per_block[i]:
                if not fits(p,en,EX): continue
                x0,x1,y0,y1=p['bbox']
                if sml: sc=(-free_span(p['bay'],en,x0,x1,y0), p['y'], p['x'], p['bay'])
                else:   sc=(p['h'], p['x'], p['y'], p['bay'])
                if best is None or sc<best[0]: best=(sc,p)
            if best: found=(best[1],en,EX); break
        if not found: return None
        p,en,EX=found
        for day in range(en,EX):
            for L in range(1,Kmax+1):
                k=(p['bay'],L,day); grid[k]=grid.get(k,0)|p['shadow'][L]
        x0,x1,y0,y1=p['bbox']; placed_by_bay[p['bay']].append((x0,x1,y0,y1,en,EX))
        chosen.append(dict(i=i,bay=p['bay'],o=p['o'],x=p['x'],y=p['y'],EN=en,EX=EX,tard=max(0,EX-D),
                           prefloss=max(B[i]['bay_preferences'])-B[i]['bay_preferences'][p['bay']],workload=B[i]['workload']))
    return chosen

path=sys.argv[1]; TL=int(sys.argv[2]) if len(sys.argv)>2 else 120; SX=int(sys.argv[3]) if len(sys.argv)>3 else 2
prob=json.load(open(path)); B=prob['blocks']; n=len(B)
nm=prob['name']
t=time.time(); per_block,Kmax=build_placements(prob,list(range(n)),SX,SX)
# 순서들
du=sorted(range(n),key=lambda i:B[i]['due_date']); ar=sorted(range(n),key=lambda i:-shoelace(B[i]['shape'][0]['layers'][0]))
rd={b:p/max(1,n-1) for p,b in enumerate(du)}; raa={b:p/max(1,n-1) for p,b in enumerate(ar)}
rank=sorted(range(n),key=lambda i:(rd[i]+raa[i],B[i]['due_date']))
tc=time.time(); cen=cpsat_order(prob,0.63,TL); cps=sorted(range(n),key=lambda i:(cen[i],B[i]['due_date']))
print(f"=== {nm} | build+cpsat {time.time()-t:.0f}s (cpsat {time.time()-tc:.0f}s) | bigleft 배치 ===",flush=True)
for name,order in [("rank(현재)",rank),("CPSAT",cps)]:
    ts=time.time(); ch=place_bigleft(prob,per_block,Kmax,order)
    if ch is None or len(ch)!=n: print(f"  {name:<12} 실현실패({0 if ch is None else len(ch)}/{n})",flush=True); continue
    errs,obj=exact_check(prob,ch); Z1=sum(c['tard'] for c in ch)
    print(f"  {name:<12} realized Z1={Z1:<6} 위반={len(errs)} ({time.time()-ts:.0f}s)",flush=True)

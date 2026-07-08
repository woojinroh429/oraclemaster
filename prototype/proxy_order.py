# 개념검증: 같은 배치기(비트엔진 bottom-left, 크레인 보수적)에 3가지 dispatch 순서를 먹여
#  realized Z1 비교. 순서만 다름 → "CP-SAT 순서가 배치와 하이브리드해도 EDD/rank보다 낮은가?"
import sys, json, time
sys.path.insert(0,'/home/user/oraclemaster/prototype')
from ortools.sat.python import cp_model
from solve_setpack import build_placements, exact_check

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
    en=[so.Value(ent[i]) for i in range(n)]
    baypref=[[k for k in range(m) if so.Value(pres[i,k])==1][0] for i in range(n)]
    return en, baypref

def place(prob, per_block, Kmax, order, baybias=None):
    B=prob['blocks']; m=len(prob['bays']); grid={}; H=max(b['due_date'] for b in B)+500; chosen=[]
    for i in order:
        R=B[i]['release_time']; P=B[i]['processing_time']; D=B[i]['due_date']
        pj = baybias[i] if baybias else B[i]['bay_preferences'].index(max(B[i]['bay_preferences']))
        plist=sorted(per_block[i], key=lambda q:(q['bay']!=pj, q['y'], q['x']))  # 선호베이+bottom-left
        found=None
        for en in range(R,H-P):
            EX=en+P
            for p in plist:
                ok=True
                for day in range(en,EX):
                    for L in range(1,Kmax+1):
                        if p['shadow'][L] & grid.get((p['bay'],L,day),0): ok=False;break
                    if not ok:break
                if ok: found=(p,en,EX);break
            if found:break
        if not found: return None
        p,en,EX=found
        for day in range(en,EX):
            for L in range(1,Kmax+1):
                k=(p['bay'],L,day); grid[k]=grid.get(k,0)|p['shadow'][L]
        chosen.append(dict(i=i,bay=p['bay'],o=p['o'],x=p['x'],y=p['y'],EN=en,EX=EX,
                           tard=max(0,EX-D),prefloss=max(B[i]['bay_preferences'])-B[i]['bay_preferences'][p['bay']],
                           workload=B[i]['workload']))
    return chosen

path=sys.argv[1]; TL=int(sys.argv[2]) if len(sys.argv)>2 else 60
prob=json.load(open(path)); B=prob['blocks']; n=len(B)
print(f"=== {prob['name']} 순서별 realized Z1 (같은 bottom-left 배치기) ===",flush=True)
t=time.time(); per_block,Kmax=build_placements(prob,list(range(n)),3,3); print(f"build {time.time()-t:.0f}s",flush=True)
# 순서들
edd=sorted(range(n),key=lambda i:(B[i]['due_date'],B[i]['release_time']))
du=sorted(range(n),key=lambda i:B[i]['due_date'])
import math
def area(i):
    xs=[v[0] for v in B[i]['shape'][0]['layers'][0]]; ys=[v[1] for v in B[i]['shape'][0]['layers'][0]]
    return (max(xs)-min(xs))*(max(ys)-min(ys))
ar=sorted(range(n),key=lambda i:-area(i))
rd={b:p/max(1,n-1) for p,b in enumerate(du)}; ra={b:p/max(1,n-1) for p,b in enumerate(ar)}
rank=sorted(range(n),key=lambda i:(rd[i]+ra[i],B[i]['due_date']))
t=time.time(); cen,cbay=cpsat_order(prob,0.63,TL); print(f"cpsat {time.time()-t:.0f}s",flush=True)
cps=sorted(range(n),key=lambda i:(cen[i],B[i]['due_date']))
for name,order,bias in [("EDD",edd,None),("rank",rank,None),("CPSAT",cps,None),("CPSAT+bay",cps,cbay)]:
    ch=place(prob,per_block,Kmax,order,bias)
    if ch is None or len(ch)!=n: print(f"  {name:<10} 실현실패"); continue
    errs,obj=exact_check(prob,ch); Z1=sum(c['tard'] for c in ch)
    print(f"  {name:<10} realized Z1={Z1:<6} 검증위반={len(errs)}",flush=True)

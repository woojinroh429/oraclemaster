# 스케줄링 방법 비교 (realizer 배제, area 완화 eff 고정).
#  CP-SAT 최적 스케줄  vs  탐욕 event-driven(EDD / rank) 스케줄
#  → 같은 조건에서 "스케줄 자체"의 지연(Z1)만 비교.
import sys, json, glob, time
from ortools.sat.python import cp_model

def shoelace(pts):
    a=0.0
    for i in range(len(pts)):
        x1,y1=pts[i]; x2,y2=pts[(i+1)%len(pts)]; a+=x1*y2-x2*y1
    return abs(a)/2.0

def load_inst(path):
    j=json.load(open(path)); B=j['blocks']; bays=j['bays']
    dem=[max(1,int(round(shoelace(b['shape'][0]['layers'][0])))) for b in B]
    return j,B,bays,dem

def cpsat_sched(j,B,bays,dem,eff,tl):
    n=len(B); m=len(bays); cap=[max(1,int(round(bays[k]['width']*bays[k]['height']*eff))) for k in range(m)]
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
    st=so.Solve(md)
    return sum(so.Value(t) for t in tard), so.StatusName(st)

def greedy_sched(j,B,bays,dem,eff,mode='edd'):
    n=len(B); m=len(bays); cap=[bays[k]['width']*bays[k]['height']*eff for k in range(m)]
    H=max(b['due_date'] for b in B)+sum(b['processing_time'] for b in B)+50
    load=[[0.0]*(H+2) for _ in range(m)]
    # 우선순위
    if mode=='edd': order=sorted(range(n),key=lambda i:(B[i]['due_date'],B[i]['release_time']))
    else:  # rank: due_rank + area_rank
        du=sorted(range(n),key=lambda i:B[i]['due_date']); ar=sorted(range(n),key=lambda i:-dem[i])
        rd={b:p/max(1,n-1) for p,b in enumerate(du)}; ra={b:p/max(1,n-1) for p,b in enumerate(ar)}
        order=sorted(range(n),key=lambda i:(rd[i]+ra[i],B[i]['due_date']))
    Z1=0
    for i in order:
        R=B[i]['release_time']; P=B[i]['processing_time']; D=B[i]['due_date']
        pj=B[i]['bay_preferences'].index(max(B[i]['bay_preferences']))
        placed=False
        for en in range(R,H-P):
            # 선호 베이 우선, 안되면 다른 베이
            for k in [pj]+[x for x in range(m) if x!=pj]:
                if all(load[k][t]+dem[i]<=cap[k]+1e-9 for t in range(en,en+P)):
                    for t in range(en,en+P): load[k][t]+=dem[i]
                    Z1+=max(0,en+P-D); placed=True; break
            if placed: break
        if not placed: Z1+=H  # 극단(발생 안하도록 H 큼)
    return Z1

files=[f'data/trainset2/train/prob_{k}.json' for k in [27,28,36,37,38,39,40]]
EFF=0.63; TL=int(sys.argv[1]) if len(sys.argv)>1 else 60
print(f"{'inst':<9}{'CPSAT':>8}{'st':>6}{'greedyEDD':>10}{'greedyRank':>11}  (area완화 eff={EFF})")
for f in files:
    try:
        j,B,bays,dem=load_inst(f)
        zc,st=cpsat_sched(j,B,bays,dem,EFF,TL)
        ze=greedy_sched(j,B,bays,dem,EFF,'edd')
        zr=greedy_sched(j,B,bays,dem,EFF,'rank')
        nm=f.split('/')[-1].replace('.json','')
        print(f"{nm:<9}{zc:>8}{st[:4]:>6}{ze:>10}{zr:>11}",flush=True)
    except Exception as e:
        print(f"{f}: ERR {str(e)[:50]}",flush=True)

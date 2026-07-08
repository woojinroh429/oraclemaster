# Layer-1 스케줄 백본: 베이배정 + 시작시각을 CP-SAT로. 2D를 레이어1 면적 누적으로 완화.
# (2D 무겹침 ⟹ 각 시점 면적합 ≤ 베이면적 이므로 유효 완화 → 이 Z1은 실제 Z1의 하한/목표)
import sys, json, time
from ortools.sat.python import cp_model

def shoelace(pts):
    a=0.0
    for i in range(len(pts)):
        x1,y1=pts[i]; x2,y2=pts[(i+1)%len(pts)]
        a+=x1*y2-x2*y1
    return abs(a)/2.0

def solve(path, tl=600, cap_mode='area'):
    j=json.load(open(path)); B=j['blocks']; bays=j['bays']; w=j['weights']
    n=len(B); m=len(bays)
    # 레이어1 면적(회전 불변) 또는 1D 폭
    dem=[]
    for b in B:
        L1=b['shape'][0]['layers'][0]
        if cap_mode=='area': dem.append(max(1,int(round(shoelace(L1)))))
        else:  # width: AABB 폭
            xs=[v[0] for v in L1]; dem.append(max(1,int(round(max(xs)-min(xs)))))
    if cap_mode=='area': capj=[bb['width']*bb['height'] for bb in bays]
    else: capj=[bb['width'] for bb in bays]
    H=max(b['due_date'] for b in B)+max(b['processing_time'] for b in B)+300
    avg=sum(bb['width']*bb['height'] for bb in bays)/m
    u_s=[round(1000*avg/(bb['width']*bb['height'])) for bb in bays]

    md=cp_model.CpModel()
    x={}; starts=[]; ends=[]; tards=[]
    ivs={jj:[] for jj in range(m)}; dms={jj:[] for jj in range(m)}
    for i,b in enumerate(B):
        s=md.NewIntVar(b['release_time'], H, f's{i}'); e=md.NewIntVar(0,H,f'e{i}')
        md.Add(e==s+b['processing_time']); starts.append(s); ends.append(e)
        t=md.NewIntVar(0,H,f't{i}'); md.Add(t>=e-b['due_date']); tards.append(t)
        xs=[]
        for jj in range(m):
            xij=md.NewBoolVar(f'x{i}_{jj}'); x[i,jj]=xij; xs.append(xij)
            iv=md.NewOptionalIntervalVar(s,b['processing_time'],e,xij,f'iv{i}_{jj}')
            ivs[jj].append(iv); dms[jj].append(dem[i])
        md.Add(sum(xs)==1)
    for jj in range(m):
        md.AddCumulative(ivs[jj], dms[jj], capj[jj])
    # Z3, Z2
    Z3=sum((max(B[i]['bay_preferences'])-B[i]['bay_preferences'][jj])*x[i,jj]
           for i in range(n) for jj in range(m))
    G=[]
    for jj in range(m):
        g=md.NewIntVar(0,10**9,f'G{jj}')
        md.Add(g==u_s[jj]*sum(B[i]['workload']*x[i,jj] for i in range(n))); G.append(g)
    Gx=md.NewIntVar(0,10**9,'Gx'); Gn=md.NewIntVar(0,10**9,'Gn')
    for g in G: md.Add(Gx>=g); md.Add(Gn<=g)
    Z2=md.NewIntVar(0,10**9,'Z2'); md.Add(Z2>=Gx-Gn)
    Z1=sum(tards)
    md.Minimize(1000*w['w1']*Z1 + 1000*w['w3']*Z3 + w['w2']*Z2)

    sol=cp_model.CpSolver(); sol.parameters.max_time_in_seconds=tl
    sol.parameters.num_search_workers=8; sol.parameters.log_search_progress=False
    t0=time.time(); st=sol.Solve(md); el=time.time()-t0
    z1=sum(sol.Value(t) for t in tards)
    z3=sum((max(B[i]['bay_preferences'])-B[i]['bay_preferences'][jj])*sol.Value(x[i,jj])
           for i in range(n) for jj in range(m))
    z2=sol.Value(Z2)/1000.0
    obj=w['w1']*z1+w['w2']*z2+w['w3']*z3
    lb=sol.BestObjectiveBound()/1000.0
    print(f"[{cap_mode}] status={sol.StatusName(st)} t={el:.0f}s | 목표 Z1={z1} Z2={z2:.1f} Z3={z3} "
          f"| obj={obj:.0f} | objLB={lb:.0f}", flush=True)
    return z1

path='data/trainset2/train/prob_38.json'
TL=int(sys.argv[1]) if len(sys.argv)>1 else 600
MODE=sys.argv[2] if len(sys.argv)>2 else 'area'
print(f"=== prob_38 Layer-1 백본 ({MODE}, TL={TL}s) | achieved Z1=154774 ===", flush=True)
solve(path, TL, MODE)

# 스케줄-우선 파이프라인 실험 (prob_38):
#  Layer-1: CP-SAT area 완화로 베이배정 + 시작순서 결정
#  Layer-2: 비트엔진으로 배정된 베이에 순서대로 최이른 실현가능 배치(크레인 보수적 shadow)
#  → 실제 feasible Z1 측정, 사용자님 achieved 2359 와 비교. 공식 check_feasibility 검증.
import sys, json, time, math
sys.path.insert(0, '/home/user/oraclemaster/prototype')
sys.path.insert(0, 'submit_v34')
from ortools.sat.python import cp_model
from solve_setpack import build_placements
import utils

def shoelace(pts):
    a=0.0
    for i in range(len(pts)):
        x1,y1=pts[i]; x2,y2=pts[(i+1)%len(pts)]; a+=x1*y2-x2*y1
    return abs(a)/2.0

def layer1_schedule(prob, tl):
    B=prob['blocks']; bays=prob['bays']; w=prob['weights']; n=len(B); m=len(bays)
    dem=[max(1,int(round(shoelace(b['shape'][0]['layers'][0])))) for b in B]
    capj=[bb['width']*bb['height'] for bb in bays]
    H=max(b['due_date'] for b in B)+max(b['processing_time'] for b in B)+300
    md=cp_model.CpModel(); x={}; ss=[]; ee=[]; tt=[]; ivs={j:[] for j in range(m)}; dms={j:[] for j in range(m)}
    for i,b in enumerate(B):
        s=md.NewIntVar(b['release_time'],H,''); e=md.NewIntVar(0,H,''); md.Add(e==s+b['processing_time'])
        t=md.NewIntVar(0,H,''); md.Add(t>=e-b['due_date']); ss.append(s); ee.append(e); tt.append(t)
        xs=[]
        for j in range(m):
            xij=md.NewBoolVar(''); x[i,j]=xij; xs.append(xij)
            ivs[j].append(md.NewOptionalIntervalVar(s,b['processing_time'],e,xij,'')); dms[j].append(dem[i])
        md.Add(sum(xs)==1)
    for j in range(m): md.AddCumulative(ivs[j],dms[j],capj[j])
    md.Minimize(sum(tt))
    so=cp_model.CpSolver(); so.parameters.max_time_in_seconds=tl; so.parameters.num_search_workers=8
    st=so.Solve(md)
    sched=[]
    for i in range(n):
        bj=[j for j in range(m) if so.Value(x[i,j])==1][0]
        sched.append((i, bj, so.Value(ss[i])))
    z1_target=sum(so.Value(t) for t in tt)
    print(f"[L1] CP-SAT {so.StatusName(st)} 목표Z1={z1_target}", flush=True)
    return sched

def realize(prob, sched, Kmax, per_block):
    B=prob['blocks']; m=len(prob['bays'])
    grid={}; H=max(b['due_date'] for b in B)+400; assign={}
    # 순서: CP-SAT 시작시각 오름차순
    for (i,bj,s0) in sorted(sched, key=lambda a:a[2]):
        b=B[i]; P=b['processing_time']; R=b['release_time']
        plist=[p for p in per_block[i] if p['bay']==bj]
        plist.sort(key=lambda q:(q['y'],q['x']))   # bottom-left
        found=None
        for en in range(max(R,s0), H-P):
            EX=en+P
            for p in plist:
                ok=True
                for day in range(en,EX):
                    for L in range(1,Kmax+1):
                        if p['shadow'][L] & grid.get((bj,L,day),0): ok=False;break
                    if not ok:break
                if ok: found=(p,en,EX);break
            if found:break
        if not found: return None
        p,en,EX=found
        for day in range(en,EX):
            for L in range(1,Kmax+1):
                k=(bj,L,day); grid[k]=grid.get(k,0)|p['shadow'][L]
        assign[i]=dict(block_id=i,bay_id=bj,x=p['x'],y=p['y'],orient_idx=p['o'],entry_time=en,exit_time=EX)
    return assign

def to_sol(assign):
    ops={}
    for a in assign.values():
        ops.setdefault(str(a['exit_time']),[]).append({'type':'EXIT','block_id':a['block_id'],'bay_id':a['bay_id']})
    for a in assign.values():
        ops.setdefault(str(a['entry_time']),[]).append({'type':'ENTRY','block_id':a['block_id'],'bay_id':a['bay_id'],'x':a['x'],'y':a['y'],'orient_idx':a['orient_idx']})
    for t in ops: ops[t].sort(key=lambda o:0 if o['type']=='EXIT' else 1)
    return {'operations':ops}

path='data/trainset2/train/prob_38.json'; prob=json.load(open(path))
TL=int(sys.argv[1]) if len(sys.argv)>1 else 180
print(f"=== prob_38 스케줄-우선 파이프라인 | 사용자 achieved Z1=2359 ===",flush=True)
t=time.time(); sched=layer1_schedule(prob,TL); print(f"L1 {time.time()-t:.0f}s",flush=True)
t=time.time(); per_block,Kmax=build_placements(prob,list(range(len(prob['blocks']))),3,3); print(f"build {time.time()-t:.0f}s",flush=True)
t=time.time(); assign=realize(prob,sched,Kmax,per_block); print(f"realize {time.time()-t:.0f}s",flush=True)
if assign is None or len(assign)!=len(prob['blocks']): print("실현 실패"); sys.exit()
sol=to_sol(assign); chk=utils.check_feasibility(prob,sol)
Z1=sum(max(0,a['exit_time']-prob['blocks'][a['block_id']]['due_date']) for a in assign.values())
print(f"[결과] feasible={chk['feasible']} 실현 Z1={Z1}  (사용자 achieved=2359, 하한=177)",flush=True)

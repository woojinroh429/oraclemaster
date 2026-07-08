# slack 재분배 아이디어 검증.
#  (A) 연료 진단: on-time 블록들의 slack(=due-exit) 총량/분포.
#  (B) 실제 연산자: 지각블록 T를 더 일찍 넣기 위해, T의 대기창에 겹치는 '여유 블록'을
#      제거→T를 릴리즈에 착석→여유블록 재착석. 총 Z1 개선시만 채택(net check). 실제 엔진.
import sys, os, json, time, copy
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import myalgorithm as MA
from myalgorithm import _smallright_construct, _build_operations, _ogc_fast_engine
from utils import check_feasibility

path=sys.argv[1]; DL=float(sys.argv[2]) if len(sys.argv)>2 else 150.0
BUD=float(sys.argv[3]) if len(sys.argv)>3 else 200.0
prob=json.load(open(path)); nm=prob.get("name",os.path.basename(path))
B=prob["blocks"]; n=len(B); m=len(prob["bays"]); bay_list=list(range(m))
due=[b["due_date"] for b in B]; rel=[b["release_time"] for b in B]; pt=[b["processing_time"] for b in B]

recs=_smallright_construct(prob,DL,0.60,1,"bigleft","rank")
if not recs or len(recs)!=n: print("실패"); sys.exit()
R={b:recs[b] for b in range(n)}
def Z1_of(Rd): return sum(max(0,Rd[b]["exit_time"]-due[b]) for b in range(n))
curZ1=Z1_of(R)
def evalfull(Rd):
    return check_feasibility(prob,_build_operations([Rd[b] for b in range(n)]))
ck0=evalfull(R)
print(f"=== {nm} (n={n}) | slack 재분배 | 시작 Z1={ck0['obj1']:.0f} feasible={ck0['feasible']} ===",flush=True)

# (A) 연료 진단
ontime=[b for b in range(n) if R[b]["exit_time"]<=due[b]]
tardy=[b for b in range(n) if R[b]["exit_time"]>due[b]]
slacks=[due[b]-R[b]["exit_time"] for b in ontime]
print(f"  on-time {len(ontime)}, tardy {len(tardy)} | slack 총합={sum(slacks)} 평균={sum(slacks)/max(1,len(slacks)):.1f} "
      f"max={max(slacks) if slacks else 0}",flush=True)
tard_total=sum(R[b]['exit_time']-due[b] for b in tardy)
print(f"  지각총합(=Z1)={tard_total}, 지각블록 평균지각={tard_total/max(1,len(tardy)):.1f}",flush=True)

# (B) 재분배 연산자
def build_engine_without(removed):
    E=_ogc_fast_engine(prob); E.clear_all()
    for bb in range(n):
        if bb in removed: continue
        r=R[bb]
        E.add(r["bay_id"],bb,r["orient_idx"],float(r["x"]),float(r["y"]),int(r["entry_time"]),int(r["exit_time"]))
    return E
def seat(E,b,tmin,window=400):
    lo=max(tmin,rel[b])
    for t in range(lo,lo+window):
        res=E.find_best_placement(b,bay_list,[t])
        if res and res[0]:
            _,bay,oi,x,y,en,ex=res
            E.add(int(bay),b,int(oi),float(x),float(y),int(en),int(ex))
            return {"block_id":b,"bay_id":int(bay),"x":int(x),"y":int(y),"orient_idx":int(oi),"entry_time":int(en),"exit_time":int(ex)}
    return None

t0=time.time(); accepted=0; tried=0
passes=0
while time.time()-t0<BUD:
    passes+=1; improved=False
    tardy_sorted=sorted([b for b in range(n) if R[b]["exit_time"]>due[b]],
                        key=lambda b:-(R[b]["exit_time"]-due[b]))
    for T in tardy_sorted:
        if time.time()-t0>BUD: break
        enT=R[T]["entry_time"]; relT=rel[T]
        if enT<=relT: continue   # 대기 없음
        # T 대기창 [relT, enT) 에 겹치는 '여유' 블록 (slack>0)
        cand=[bb for bb in range(n) if bb!=T
              and R[bb]["entry_time"]<enT and R[bb]["exit_time"]>relT
              and (due[bb]-R[bb]["exit_time"])>0]
        if not cand: continue
        # 여유 큰 순 상위 25개까지
        cand.sort(key=lambda bb:-(due[bb]-R[bb]["exit_time"])); cand=cand[:25]
        removed=set([T])|set(cand)
        tried+=1
        E=build_engine_without(removed)
        recT=seat(E,T,relT)
        if recT is None: continue
        # 여유블록 재착석: 릴리즈·due 순, 각자 릴리즈부터 earliest feasible
        order=sorted(cand,key=lambda bb:(rel[bb],due[bb]))
        tmp={T:recT}; ok=True
        for bb in order:
            rec=seat(E,bb,rel[bb])
            if rec is None: ok=False; break
            tmp[bb]=rec
        if not ok: continue
        newR=dict(R); newR.update(tmp)
        nz=Z1_of(newR)
        if nz<curZ1-1e-9:
            ck=evalfull(newR)
            if ck["feasible"] and ck["obj1"]<curZ1-1e-9:
                R=newR; curZ1=ck["obj1"]; improved=True; accepted+=1
    if not improved: break
print(f"  --- 재분배 후: Z1={curZ1:.0f} (시작 {ck0['obj1']:.0f}, Δ={ck0['obj1']-curZ1:+.0f}) "
      f"passes={passes} tried={tried} accepted={accepted} ({time.time()-t0:.0f}s) ---",flush=True)
ckf=evalfull(R)
print(f"  최종 검증: feasible={ckf['feasible']} Z1={ckf['obj1']} obj={ckf['objective']:.0f}",flush=True)

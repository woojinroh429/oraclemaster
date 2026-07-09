# 전략 연구: 파라미터화 배치정책을 진화탐색(ES)으로 학습. torch/GPU 없이 numpy+bitmask sim.
# 정책 = dispatch 순서(특징 가중합) + position 스코어(특징 가중합). ES가 가중치를 최적화하며
# 어떤 특징이 지배하는지 연구. (신경망 RL 대체: 수천~수만 롤아웃)
import sys, os, json, math, time, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from solve_setpack import build_placements, aabb_offsets

# ---------- 인스턴스 준비 ----------
def prep(path, SX=3):
    inst=json.load(open(path)); B=inst["blocks"]; n=len(B); bays=inst["bays"]
    per_block,Kmax=build_placements(inst,list(range(n)),SX,SX)
    bw=[b["width"] for b in bays]; bh=[b["height"] for b in bays]
    # 위치 특징용 bbox 캐시
    for i in range(n):
        for p in per_block[i]:
            ax0,ax1,ay0,ay1=aabb_offsets(B[i],p["o"])
            p["bx0"]=p["x"]+ax0; p["bx1"]=p["x"]+ax1; p["by0"]=p["y"]+ay0; p["by1"]=p["y"]+ay1
            p["ph"]=ay1-ay0; p["pw"]=ax1-ax0
    due=np.array([b["due_date"] for b in B]); rel=np.array([b["release_time"] for b in B])
    pt=np.array([b["processing_time"] for b in B]); wl=np.array([b["workload"] for b in B])
    ar=np.array([max(_area(B[i]) for _ in [0]) for i in range(n)])
    # 특징 랭크(0=우선). due↑급, area큼, proc김, width넓, height높, slack작음
    def rank(v,rev):
        o=np.argsort(-v if rev else v); r=np.zeros(n); r[o]=np.arange(n)/max(1,n-1); return r
    widthv=np.array([min(p["pw"] for p in per_block[i]) for i in range(n)])
    heightv=np.array([min(p["ph"] for p in per_block[i]) for i in range(n)])
    slack=due-rel-pt
    feats_disp=np.stack([rank(due,False),rank(ar,True),rank(pt,True),
                         rank(widthv,True),rank(heightv,True),rank(slack,False)],axis=1) # (n,6)
    H=int(max(due)+max(pt)+50)
    w=inst["weights"]
    return dict(inst=inst,n=n,m=len(bays),per_block=per_block,Kmax=Kmax,bw=bw,bh=bh,
                due=due,rel=rel,pt=pt,wl=wl,H=H,feats_disp=feats_disp,
                w1=w["w1"],w2=w["w2"],w3=w["w3"],
                u=_bayunits(bays), prefs=[B[i]["bay_preferences"] for i in range(n)])

def _area(b):
    L=b["shape"][0]["layers"][0]; a=0.0
    for k in range(len(L)):
        x1,y1=L[k]; x2,y2=L[(k+1)%len(L)]; a+=x1*y2-x2*y1
    return abs(a)/2
def _bayunits(bays):
    A=[b["width"]*b["height"] for b in bays]; avg=sum(A)/len(A); return [avg/a for a in A]

DISP_D=6      # dispatch 특징수
POS_D=5       # position 특징수: wx_n, wy_n, h_n, -overlap_n, -freespan_n
NW=DISP_D+POS_D

# ---------- 롤아웃 (파라미터 theta로 구성, 목적값 반환) ----------
def rollout(P, theta):
    wd=theta[:DISP_D]; wp=theta[DISP_D:]
    n=P["n"]; m=P["m"]; per=P["per_block"]; Kmax=P["Kmax"]; bw=P["bw"]; bh=P["bh"]
    due=P["due"]; rel=P["rel"]; pt=P["pt"]; wl=P["wl"]; H=P["H"]; u=P["u"]; prefs=P["prefs"]
    disp_score=P["feats_disp"]@wd    # (n,) 작을수록 우선
    grid={}; placed_bb={j:[] for j in range(m)}; loads=[0.0]*m
    assign={}
    import heapq
    order_rel=sorted(range(n),key=lambda b:rel[b]); ri=0; eh=[]; pend=set()
    cur=int(min(rel)); guard=0
    while True:
        while ri<n and rel[order_rel[ri]]<=cur: pend.add(order_rel[ri]); ri+=1
        while eh and eh[0][0]<=cur: heapq.heappop(eh)
        for j in range(m):
            placed_bb[j]=[t for t in placed_bb[j] if t[4]>cur]
        placed_now=[]
        for b in sorted(pend,key=lambda b:disp_score[b]):
            P_=int(pt[b]); D=int(due[b]); best=None
            for p in per[b]:
                en=cur; ex=cur+P_
                ok=True
                for day in range(en,ex):
                    for L in range(1,Kmax+1):
                        if p["shadow"][L] & grid.get((p["bay"],L,day),0): ok=False; break
                    if not ok: break
                if not ok: continue
                j=p["bay"]; wx=p["bx0"]; wy=p["by0"]; h=p["ph"]; w=p["pw"]
                # 위치 특징 (정규화)
                ov=0.0
                for (x0,x1,y0,y1,ex2) in placed_bb[j]:
                    dx=min(p["bx1"],x1)-max(x0,wx); dy=min(p["by1"],y1)-max(y0,wy)
                    if dx>0 and dy>0: ov+=dx*dy
                fs=bw[j]-(wx+ (p["bx1"]-p["bx0"]))  # 우측 여유(간이 free-span)
                fv=np.array([wx/max(1,bw[j]), wy/max(1,bh[j]), h/max(1,bh[j]),
                             -ov/max(1,bw[j]*bh[j]), -fs/max(1,bw[j])])
                ps=float(fv@wp)
                if best is None or ps<best[0]: best=(ps,p,en,ex)
            if best is None: continue   # 이 시각엔 자리없음 -> pend 유지, 다음 이벤트 재시도
            _,p,en,ex=best; j=p["bay"]
            for day in range(en,ex):
                for L in range(1,Kmax+1):
                    k=(j,L,day); grid[k]=grid.get(k,0)|p["occ"][L]
            placed_bb[j].append((p["bx0"],p["bx1"],p["by0"],p["by1"],ex))
            loads[j]+=wl[b]
            assign[b]=dict(bay=j,en=en,ex=ex,tard=max(0,ex-D),
                           pref=max(prefs[b])-prefs[b][j])
            heapq.heappush(eh,(ex,b)); placed_now.append(b)
        for b in placed_now: pend.discard(b)
        if not pend and ri>=n and not eh: break
        c=[]
        if ri<n: c.append(rel[order_rel[ri]])
        if eh: c.append(eh[0][0])
        if pend and not eh and ri>=n: c.append(cur+1)
        cur=int(min(c)) if c else cur+1; guard+=1
        if guard>50000: break
    if len(assign)!=n: return None
    Z1=sum(a["tard"] for a in assign.values())
    Z3=sum(a["pref"] for a in assign.values())
    bl=[0.0]*m
    for b,a in assign.items(): bl[a["bay"]]+=wl[b]
    Z2=max((abs(u[j1]*bl[j1]-u[j2]*bl[j2]) for j1 in range(m) for j2 in range(j1+1,m)),default=0.0)
    Z2=math.floor(Z2)
    return P["w1"]*Z1+P["w2"]*Z2+P["w3"]*Z3, Z1, Z2, Z3

# ---------- ES ----------
def fitness(Ps, theta):
    tot=0.0
    for P in Ps:
        r=rollout(P,theta)
        if r is None: return 1e18
        tot+=r[0]
    return tot/len(Ps)

_PS=None
def _pool_init(paths, SX):
    global _PS; _PS=[prep(p, SX) for p in paths]
def _pool_eval(theta):
    return fitness(_PS, theta)

def es(Ps, gens=60, pop=16, sigma=0.5, seed=0, pool=None):
    rng=np.random.RandomState(seed)
    theta=np.zeros(NW)
    # 좋은 초기값: rank-like (due+area 우선, 낮게·좌측)
    theta[0]=1.0; theta[1]=1.0        # due_rank, area_rank
    theta[DISP_D+0]=0.3; theta[DISP_D+1]=1.0  # wx, wy (bottom-left)
    best=(fitness(Ps,theta), theta.copy())
    hist=[best[0]]; nrolls=0
    for g in range(gens):
        cands=[theta+sigma*rng.randn(NW) for _ in range(pop)]
        fits=pool.map(_pool_eval,cands) if pool else [fitness(Ps,c) for c in cands]
        nrolls+=pop*len(Ps)
        idx=int(np.argmin(fits))
        if fits[idx]<best[0]: best=(fits[idx],cands[idx].copy())
        # (μ,λ): 상위 25% 평균으로 이동
        order=np.argsort(fits); topk=max(1,pop//4)
        theta=np.mean([cands[i] for i in order[:topk]],axis=0)
        sigma*=0.97
        hist.append(best[0])
        if g%2==0:
            print(f"  gen{g:>3} best={best[0]:.0f} sigma={sigma:.3f} rollouts={nrolls}",flush=True)
    return best, hist

if __name__=="__main__":
    import multiprocessing as mp
    GENS=int(os.environ.get("GENS","40")); POP=int(os.environ.get("POP","16")); SX=int(os.environ.get("SX","3"))
    paths=[a for a in sys.argv[1:] if a.endswith(".json")] or ["data/trainset2/train/prob_21.json"]
    print(f"=== ES 전략학습 | 인스턴스 {len(paths)}개 | 특징 disp{DISP_D}+pos{POS_D} | pop{POP} gens{GENS} SX{SX} ===",flush=True)
    t=time.time(); Ps=[prep(p,SX) for p in paths]; print(f"prep {time.time()-t:.0f}s",flush=True)
    pool=mp.Pool(processes=min(4,POP), initializer=_pool_init, initargs=(paths,SX))
    (bf,bt),hist=es(Ps, gens=GENS, pop=POP, pool=pool)
    pool.close()
    print(f"\n=== 학습완료 best_obj={bf:.0f} ===",flush=True)
    names=["due","area","proc","width","height","slack"]+["pos_wx","pos_wy","pos_h","pos_-overlap","pos_-freespan"]
    for nm,val in zip(names,bt): print(f"  w[{nm:<14}]={val:+.3f}",flush=True)

# 실엔진 위 ES (numpy 전용, torch 불필요). dispatch priority 정책 학습 -> 지각(Z1)/obj 최소화.
# fitness = 실엔진 _smallright_construct(ext_entry=neural_priority) 의 공식 objective.
import os, sys, json, glob, time
import numpy as np

ENGINE_DIR = os.environ["ENGINE_DIR"]
sys.path.insert(0, ENGINE_DIR)
import myalgorithm as M
from myalgorithm import _smallright_construct, _build_operations, _orient_bbox
from utils import check_feasibility
BIG = 1e18

CFG = dict(
    INSTANCES = os.environ.get("INSTANCES","").split(",") if os.environ.get("INSTANCES") else [],
    DEADLINE = float(os.environ.get("DEADLINE", "15")),
    STEP     = int(os.environ.get("STEP", "1")),
    POP      = int(os.environ.get("POP", "16")),
    GENS     = int(os.environ.get("GENS", "40")),
    SIGMA    = 0.15, LR = 0.03, HIDDEN = 32,
    NW       = int(os.environ.get("NW", "4")),
    OUT      = os.environ.get("OUT", "es_out"),
)
os.makedirs(CFG["OUT"], exist_ok=True)

def prep(path):
    inst=json.load(open(path)); Bl=inst["blocks"]; n=len(Bl)
    due=np.array([b["due_date"] for b in Bl],float); rel=np.array([b["release_time"] for b in Bl],float)
    pt=np.array([b["processing_time"] for b in Bl],float)
    def area(i):
        L=Bl[i]["shape"][0]["layers"][0]; a=0.0
        for k in range(len(L)):
            x1,y1=L[k]; x2,y2=L[(k+1)%len(L)]; a+=x1*y2-x2*y1
        return abs(a)/2
    ar=np.array([area(i) for i in range(n)])
    widv=np.zeros(n); hgtv=np.zeros(n)
    for i in range(n):
        ws=[];hs=[]
        for o in range(len(Bl[i]["shape"])):
            x0,y0,x1,y1=_orient_bbox(Bl[i],o); ws.append(x1-x0); hs.append(y1-y0)
        widv[i]=min(ws); hgtv[i]=min(hs)
    slack=due-rel-pt
    def rk(v,rev):
        o=np.argsort(-v if rev else v); r=np.zeros(n); r[o]=np.arange(n)/max(1,n-1); return r
    BF=np.stack([rk(due,False),rk(ar,True),rk(pt,True),rk(widv,True),rk(hgtv,True),
                 rk(slack,False), due/(due.max()+1),pt/(pt.max()+1),ar/(ar.max()+1)],axis=1).astype(np.float64)
    return dict(name=os.path.basename(path).replace('.json',''),inst=inst,n=n,BF=BF)

# --- numpy MLP: d->h->h->1, tanh ---
def shapes(d,h): return [(d,h),(h,),(h,h),(h,),(h,1),(1,)]
def nparam(d,h): return sum(int(np.prod(s)) for s in shapes(d,h))
def forward(theta, BF, d, h):
    i=0; ps=[]
    for s in shapes(d,h):
        k=int(np.prod(s)); ps.append(theta[i:i+k].reshape(s)); i+=k
    W1,b1,W2,b2,W3,b3=ps
    x=np.tanh(BF@W1+b1); x=np.tanh(x@W2+b2); return (x@W3+b3).reshape(-1)

ALPHA=0.5  # residual scale: priority = rank_base + ALPHA*neural (ES refines rank)
def rank_base(P): return P["BF"][:,0]+P["BF"][:,1]   # due_rank + area_rank (native rank)
def fitness_one(P, priority):
    ext=[float(x) for x in priority]
    try:
        recs=_smallright_construct(P["inst"], CFG["DEADLINE"], 0.60, CFG["STEP"],
                                   "bigleft", "rank", ext_entry=ext, tiebreak="due")
    except Exception:
        return BIG
    if not recs or len(recs)!=P["n"]: return BIG
    ck=check_feasibility(P["inst"], _build_operations(list(recs.values())))
    return float(ck["objective"]) if ck.get("feasible") else BIG

_PS=None; _D=None; _H=None
def _winit(paths,d,h):
    global _PS,_D,_H
    for tv in ("OMP_NUM_THREADS","OPENBLAS_NUM_THREADS","MKL_NUM_THREADS","NUMBA_NUM_THREADS"):
        os.environ[tv]="1"
    _PS=[prep(p) for p in paths]; _D=d; _H=h
def _weval(theta):
    tot=0.0
    for P in _PS:
        pri=rank_base(P)+ALPHA*forward(theta,P["BF"],_D,_H); f=fitness_one(P,pri)
        if f>=BIG: return BIG
        tot+=f
    return tot/len(_PS)

def main():
    import multiprocessing as mp
    paths=CFG["INSTANCES"]
    print("engine HAVE_CPP=%s OGC_FAST=%s"%(M.HAVE_CPP,M.HAVE_OGC_FAST),flush=True)
    print("instances:",[os.path.basename(p) for p in paths],flush=True)
    P0=prep(paths[0]); d=P0["BF"].shape[1]; h=CFG["HIDDEN"]; D=nparam(d,h)
    rng=np.random.RandomState(0)
    # baseline: rank = due_rank + area_rank (엔진 기본과 동일 order 재현)
    # native rank (production, no ext_entry) = 진짜 이겨야 할 목표
    native=np.mean([ (lambda P: (lambda ck: float(ck["objective"]) if ck.get("feasible") else BIG)(
        check_feasibility(P["inst"], _build_operations(list(
        _smallright_construct(P["inst"],CFG["DEADLINE"],0.60,CFG["STEP"],"bigleft","rank",tiebreak="due").values())))))(prep(p)) for p in paths])
    # ext_entry rank_base (ES와 동일 코드경로) = 잔차의 출발점(theta=0)
    base=np.mean([fitness_one(prep(p), rank_base(prep(p))) for p in paths])
    print(f"[native rank]={native:.0f}  [ext_entry rank base]={base:.0f}  params={D} pop={CFG['POP']} gens={CFG['GENS']} step{CFG['STEP']} DL{CFG['DEADLINE']}",flush=True)
    theta=np.zeros(D)  # gen0 = 정확히 ext_entry rank (잔차 0) -> ES가 국소 개선 탐색
    sigma=CFG["SIGMA"]; lr=CFG["LR"]; best=(BIG,None)
    pool=mp.Pool(CFG["NW"],initializer=_winit,initargs=(paths,d,h))
    t0=time.time()
    for g in range(CFG["GENS"]):
        eps=rng.randn(CFG["POP"]//2,D); eps=np.concatenate([eps,-eps])
        cand=[theta+sigma*eps[k] for k in range(CFG["POP"])]
        fits=np.array(pool.map(_weval,cand))
        if np.all(fits>=BIG):
            print(f"gen{g}: all-fail",flush=True); continue
        fm=fits.copy(); fm[fm>=BIG]=fits[fits<BIG].max()  # 실패는 최악치로
        rnk=(fm.argsort().argsort()/(len(fm)-1)-0.5)
        grad=(eps.T@(-rnk))/(CFG["POP"]*sigma)
        theta=theta+lr*grad
        if fits.min()<best[0]:
            best=(float(fits.min()),theta.copy())
            np.save(os.path.join(CFG["OUT"],"best_theta.npy"),best[1])
        g_base=100.0*(base-best[0])/base; g_nat=100.0*(native-best[0])/native
        print(f"gen{g:>3} best={best[0]:.0f} (vs ext_rank {g_base:+.2f}% | vs NATIVE rank {g_nat:+.2f}%) genmin={fits.min():.0f} sig={sigma:.3f} {time.time()-t0:.0f}s",flush=True)
        sigma=max(0.05,sigma*0.99)
    pool.close(); pool.join()
    with open(os.path.join(CFG["OUT"],"summary.txt"),"w") as f:
        f.write(f"native_rank={native:.0f}\next_entry_rank_base={base:.0f}\nbest_es={best[0]:.0f}\n"
                f"gain_vs_ext_pct={100.0*(base-best[0])/base:.3f}\ngain_vs_native_pct={100.0*(native-best[0])/native:.3f}\n")
    print(f"=== DONE native={native:.0f} ext_base={base:.0f} best={best[0]:.0f} | vs_native={100.0*(native-best[0])/native:+.2f}% ===",flush=True)

if __name__=="__main__": main()

# 한 프로세스 = 한 구성 (실 알고리즘과 동일: 인스턴스당 1프로세스, 상태오염 없음).
# 사용: python3.12 one.py <inst.json> rank | python3.12 one.py <inst.json> <theta.npy>
import os,sys,json,numpy as np
sys.path.insert(0,os.environ.get("ENGINE_DIR","../sv34"))
import myalgorithm as M
from myalgorithm import _smallright_construct,_build_operations,_orient_bbox
from utils import check_feasibility
DL=float(os.environ.get("DEADLINE","15")); STEP=int(os.environ.get("STEP","1")); HID=int(os.environ.get("HIDDEN","32"))
ALPHA=0.5
inst=json.load(open(sys.argv[1])); n=len(inst["blocks"]); which=sys.argv[2]
def BF():
    Bl=inst["blocks"]
    due=np.array([b["due_date"] for b in Bl],float); rel=np.array([b["release_time"] for b in Bl],float)
    pt=np.array([b["processing_time"] for b in Bl],float)
    def area(i):
        L=Bl[i]["shape"][0]["layers"][0]; a=0.0
        for k in range(len(L)):
            x1,y1=L[k];x2,y2=L[(k+1)%len(L)];a+=x1*y2-x2*y1
        return abs(a)/2
    ar=np.array([area(i) for i in range(n)])
    wv=np.zeros(n);hv=np.zeros(n)
    for i in range(n):
        ws=[];hs=[]
        for o in range(len(Bl[i]["shape"])):
            x0,y0,x1,y1=_orient_bbox(Bl[i],o); ws.append(x1-x0);hs.append(y1-y0)
        wv[i]=min(ws);hv[i]=min(hs)
    sl=due-rel-pt
    def rk(v,rev):
        o=np.argsort(-v if rev else v);r=np.zeros(n);r[o]=np.arange(n)/max(1,n-1);return r
    return np.stack([rk(due,False),rk(ar,True),rk(pt,True),rk(wv,True),rk(hv,True),rk(sl,False),
                     due/(due.max()+1),pt/(pt.max()+1),ar/(ar.max()+1)],axis=1)
def fwd(theta,X,d,h):
    shp=[(d,h),(h,),(h,h),(h,),(h,1),(1,)]; i=0;ps=[]
    for s in shp:
        k=int(np.prod(s));ps.append(theta[i:i+k].reshape(s));i+=k
    W1,b1,W2,b2,W3,b3=ps
    x=np.tanh(X@W1+b1);x=np.tanh(x@W2+b2);return (x@W3+b3).reshape(-1)
if which=="rank":
    recs=_smallright_construct(inst,DL,0.60,STEP,"bigleft","rank",tiebreak="due")
else:
    X=BF(); d=X.shape[1]; th=np.load(which); pri=X[:,0]+X[:,1]+ALPHA*fwd(th,X,d,HID)
    recs=_smallright_construct(inst,DL,0.60,STEP,"bigleft","rank",ext_entry=[float(x) for x in pri],tiebreak="due")
if not recs or len(recs)!=n:
    print(f"FAIL {len(recs) if recs else None}/{n}"); sys.exit()
ck=check_feasibility(inst,_build_operations(list(recs.values())))
print(f"{os.path.basename(sys.argv[1]).replace('.json',''):10s} {which if which=='rank' else 'ES':4s} Z1={ck['obj1']:.0f} obj={ck['objective']:.0f} feasible={ck['feasible']}")

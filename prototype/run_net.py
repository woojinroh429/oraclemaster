import sys, os, json, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from utils import check_feasibility
TL=float(sys.argv[1]); paths=sys.argv[2:]
def run(prob, TL):
    import importlib, myalgorithm
    importlib.reload(myalgorithm)  # fresh caches
    sol=myalgorithm.algorithm(prob,timelimit=TL)
    return check_feasibility(prob,sol)
for path in paths:
    prob=json.load(open(path)); nm=prob.get("name",os.path.basename(path))
    os.environ["NO_COREPERI"]="1"; ck0=run(prob,TL)
    os.environ["NO_COREPERI"]="0"; ck1=run(prob,TL)
    d=ck0['objective']-ck1['objective']
    tag="WIN" if d>1 else ("regress" if d<-1 else "tie")
    print(f"{nm:<9} base obj={ck0['objective']:.0f}(Z1={ck0['obj1']:.0f}) | +coreperi obj={ck1['objective']:.0f}(Z1={ck1['obj1']:.0f}) | {d:+.0f} ({d/max(1,ck0['objective'])*100:+.1f}%) {tag}",flush=True)

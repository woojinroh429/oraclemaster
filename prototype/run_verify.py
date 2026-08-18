import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from utils import check_feasibility
TL=float(sys.argv[1]); paths=sys.argv[2:]
for path in paths:
    import importlib, myalgorithm; importlib.reload(myalgorithm)
    prob=json.load(open(path)); nm=prob.get("name",os.path.basename(path))
    sol=myalgorithm.algorithm(prob,timelimit=TL); ck=check_feasibility(prob,sol)
    print(f"{nm:<9} obj={ck['objective']:.0f} Z1={ck['obj1']:.0f} Z2={ck['obj2']:.0f} Z3={ck['obj3']:.0f} feas={ck['feasible']}",flush=True)

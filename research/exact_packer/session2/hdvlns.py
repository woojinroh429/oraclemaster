"""High-density VLNS experiment: warm from the FULL pipeline solution (exact_reassign
doesn't handle util>1), then VLNS-refine (Z3 is still 88-95% of the objective on these
moderate high-density instances).  Compare to the pipeline baseline."""
import json, os, sys, time
SP="/tmp/claude-0/-home-user-oraclemaster/55043662-747d-5eda-b837-388adc057292/scratchpad"
sys.path.insert(0, os.path.join(SP,"v73")); sys.path.insert(0, os.path.join(SP,"cc"))
sys.path.insert(0, os.path.join(SP,"research"))
os.chdir(os.path.join(SP,"v73"))
import myalgorithm as M
from utils import check_feasibility
import vlns as V

def find(n):
    for sub in ("data/train","data/training_instances/train"):
        p=os.path.join(SP,sub,n+".json")
        if os.path.exists(p): return p

NAME=sys.argv[1] if len(sys.argv)>1 else "prob_24"
WARMTL=float(sys.argv[2]) if len(sys.argv)>2 else 12.0
VLNST=float(sys.argv[3]) if len(sys.argv)>3 else 18.0
inst=json.load(open(find(NAME))); B=inst["blocks"]
E=V.Engine(inst, STEP=6, TLpack=0.06)

def sol_to_assign(sol):
    a={}
    for t,ops in sol["operations"].items():
        for op in ops:
            if op["type"]=="ENTRY":
                b=op["block_id"]; en=int(t)
                a[b]=(op["bay_id"],op["orient_idx"],op["x"],op["y"],en,en+B[b]["processing_time"])
    return a

# baseline pipeline solution as warm
t0=time.time()
sol=M.algorithm(inst, WARMTL)
ck0=check_feasibility(inst, sol)
init=sol_to_assign(sol)
o0,f0=E.score(init)
print(f"{NAME}: pipeline warm obj={ck0['objective']:.0f} (Z1={ck0.get('obj1')},Z2={ck0.get('obj2')},Z3={ck0.get('obj3')}) feas={ck0['feasible']}  parsed-obj={o0:.0f} [{time.time()-t0:.1f}s]")
# VLNS refine
tb=time.time()
best,fo,ff,it,acc,imp=E.solve(time.time()+VLNST, init, seed=7, descent0=VLNST*0.45)
# real breakdown of refined
sol2=M._build_operations([{"block_id":b,"bay_id":v[0],"orient_idx":v[1],"x":v[2],"y":v[3],
                           "entry_time":v[4],"exit_time":v[5]} for b,v in best.items()])
ck2=check_feasibility(inst, sol2)
print(f"  VLNS obj={ck2['objective']:.0f} (Z1={ck2.get('obj1')},Z2={ck2.get('obj2')},Z3={ck2.get('obj3')}) feas={ck2['feasible']}  "
      f"delta={ck2['objective']-ck0['objective']:+.0f} ({(ck2['objective']-ck0['objective'])/ck0['objective']*100:+.1f}%)  it={it} acc={acc} imp={imp} [{time.time()-tb:.1f}s]")

# 학습된 정책(best_policy.pt)으로 해를 만들어 공식 포맷(operations)으로 저장 + 공식검증.
# ogc_gpu_rl.rollout(want_assign=True)는 공식 크레인체크를 쓰므로 해가 유효.
import os, json, numpy as np, glob
import ogc_gpu_rl as M
from utils import check_feasibility

def build_ops(assign):
    buckets={}
    for b,a in assign.items():
        buckets.setdefault(a["ex"],[]).append((0,"EXIT",b,a))
        buckets.setdefault(a["en"],[]).append((1,"ENTRY",b,a))
    ops={}
    for t in sorted(buckets):
        row=[]
        for _,k,b,a in sorted(buckets[t],key=lambda z:z[0]):
            row.append({"type":"ENTRY","block_id":b,"bay_id":a["bay"],"x":a["x"],"y":a["y"],"orient_idx":a["o"]}
                       if k=="ENTRY" else {"type":"EXIT","block_id":b,"bay_id":a["bay"]})
        ops[str(t)]=row
    return {"operations":ops}

def main():
    import torch
    paths=sorted(glob.glob(os.path.join(M.CFG["INSTANCE_DIR"],"*.json")))
    torch_,nn,dev,Policy=M.build_torch()
    P0=M.prep_instance(paths[0]); model=Policy(P0["BF"].shape[1],M.CFG["HIDDEN"]).to(dev)
    model.load_state_dict(torch_.load("best_policy.pt",map_location=dev)); model.eval()
    posw=model.pos.detach().cpu().numpy(); os.makedirs("solutions",exist_ok=True)
    for path in paths:
        P=M.prep_instance(path)
        with torch_.no_grad(): pri=model.priority(torch_.tensor(P["BF"]).to(dev)).cpu().numpy()
        a=M.rollout(P,pri,posw,want_assign=True)
        if a is None: print(f"{P['name']}: 배치실패"); continue
        sol=build_ops(a); json.dump(sol,open(f"solutions/{P['name']}.json","w"))
        ck=check_feasibility(P["inst"],sol)   # 공식 검증
        print(f"{P['name']}: 공식 feasible={ck['feasible']} Z1={ck['obj1']} obj={ck['objective']} -> solutions/{P['name']}.json")

if __name__=="__main__": main()

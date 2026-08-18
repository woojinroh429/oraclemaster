"""Measurement harness.  Lives in a TRACKED directory on purpose: the previous one was
under engt/, which is gitignored, so a container reset destroyed every probe while the
committed code survived.

  full   <prob> [budget]              full pipeline once
  front  <prob>                       sweep the preference frontier, construction only
  conv   <prob> [b1,b2,...]           where the pipeline stops improving
  ab     <prob> [budget] <ENV=V,...>  paired on/off at equal budget
"""
import json, os, sys, time
HERE = os.path.dirname(os.path.abspath(__file__))
REC = os.path.dirname(HERE)
sys.path.insert(0, REC); os.chdir(REC)
import myalg_legacy as M, utils


def load(prob):
    p = next(c for c in ("data/train/%s.json" % prob, "data/set1/%s.json" % prob)
             if os.path.exists(c))
    return json.load(open(p))


def sc(d, sol):
    c = utils.check_feasibility(d, sol)
    return (int(c["objective"]) if c.get("feasible") else -1), c


cmd, prob = sys.argv[1], sys.argv[2]
d = load(prob); n = len(d["blocks"])
M._CPP_ENGINE_MODE = M.HAVE_OGC_FAST
dr = M._demand_ratio_phys(d)

if cmd == "full":
    b = float(sys.argv[3]) if len(sys.argv) > 3 else 300
    t = time.time(); o, c = sc(d, M.algorithm(d, timelimit=b))
    print("FULL %s n=%d dr=%.3f bud=%.0f obj=%d Z1=%s Z2=%s Z3=%s t=%.0f"
          % (prob, n, dr, b, o, c.get("obj1"), c.get("obj2"), c.get("obj3"),
             time.time() - t), flush=True)

elif cmd == "front":
    print("%s n=%d dr=%.3f w3/w1=%.4f" % (prob, n, dr,
          d["weights"]["w3"] / d["weights"]["w1"]), flush=True)
    best = None
    for mode, bkt in (("bigleft", 0), ("coreperi", 0), ("prefmid", 0), ("preflate", 0),
                      ("prefbkt", 2), ("prefbkt", 3), ("prefbkt", 5), ("prefbkt", 8),
                      ("prefaware", 0)):
        if bkt:
            os.environ["OGC_PREFBKT"] = str(bkt)
            import importlib; importlib.reload(M); M._CPP_ENGINE_MODE = M.HAVE_OGC_FAST
        t = time.time()
        r = M._smallright_construct(d, time.time() + 240, step=1, mode=mode)
        if not r or len(r) != n:
            print("   %-9s%-3s FAIL" % (mode, bkt or ""), flush=True); continue
        o, c = sc(d, M._build_operations([r[b] for b in range(n)]))
        tag = ""
        if o > 0 and (best is None or o < best):
            best = o; tag = "  <<<"
        print("   %-9s%-3s obj=%-11d Z1=%-7s Z2=%-6s Z3=%-8s t=%.0f%s"
              % (mode, bkt or "", o, c.get("obj1"), c.get("obj2"), c.get("obj3"),
                 time.time() - t, tag), flush=True)

elif cmd == "conv":
    buds = [int(x) for x in (sys.argv[3].split(",") if len(sys.argv) > 3
                             else ["60", "120", "200", "300"])]
    out = []
    for b in buds:
        o, c = sc(d, M.algorithm(d, timelimit=b))
        g = "" if not out else "  %+.2f%%" % (100.0 * (o - out[-1][1]) / out[-1][1])
        out.append((b, o))
        print("   %-8s bud=%-4d obj=%-11d Z1=%-7s Z2=%-6s Z3=%-8s%s"
              % (prob, b, o, c.get("obj1"), c.get("obj2"), c.get("obj3"), g), flush=True)
    last = out[-1][1]; plat = next(b for b, o in out if o == last)
    print("   CONV %s n=%d dr=%.3f plateau~%ds idle_tail=%ds"
          % (prob, n, dr, plat, buds[-1] - plat), flush=True)

elif cmd == "ab":
    b = float(sys.argv[3]); envs = sys.argv[4]
    for lab in ("OFF", "ON"):
        if lab == "OFF":
            for kv in envs.split(","):
                k, v = kv.split("="); os.environ[k] = v
        else:
            for kv in envs.split(","):
                os.environ.pop(kv.split("=")[0], None)
        import importlib; importlib.reload(M); M._CPP_ENGINE_MODE = M.HAVE_OGC_FAST
        o, c = sc(d, M.algorithm(d, timelimit=b))
        print("AB %s dr=%.3f %-3s obj=%-11d Z1=%-7s Z2=%-6s Z3=%s"
              % (prob, dr, lab, o, c.get("obj1"), c.get("obj2"), c.get("obj3")), flush=True)

// cranepack: dependency-free exact-style crane packer.
//   input : a congested clique of blocks (per-orient layer polygons at origin,
//           obb, entry, exit) + bay W,H + coarse grid step.
//   build : step-grid placement columns -> pairwise crane-conflict graph
//           (fastconf j>=k rule, VALIDATED) -> maximise # distinct blocks placed.
//   solve : iterated-greedy + force/repair local search on the conflict graph
//           (no Gurobi; grader has no license).  Returns the chosen placements.
#include <pybind11/pybind11.h>
#include <pybind11/numpy.h>
#include <pybind11/stl.h>
#include <vector>
#include <cmath>
#include <algorithm>
#include <chrono>
namespace py = pybind11;
typedef std::vector<std::pair<double,double>> Poly;

// ---------- geometry (from the validated cranecheck.cpp) ----------
static inline double cross(double ox,double oy,double ax,double ay,double bx,double by){
    return (ax-ox)*(by-oy)-(ay-oy)*(bx-ox);
}
static inline int point_in_poly(double px,double py,const Poly& poly,double eps=1e-9){
    int n=poly.size(); bool inside=false;
    for(int i=0,j=n-1;i<n;j=i++){
        double xi=poly[i].first,yi=poly[i].second,xj=poly[j].first,yj=poly[j].second;
        double d=cross(xi,yi,xj,yj,px,py);
        double minx=std::min(xi,xj)-eps,maxx=std::max(xi,xj)+eps;
        double miny=std::min(yi,yj)-eps,maxy=std::max(yi,yj)+eps;
        if(std::fabs(d)<eps && px>=minx&&px<=maxx&&py>=miny&&py<=maxy) return 0;
        if(((yi>py)!=(yj>py)) && (px<(xj-xi)*(py-yi)/(yj-yi)+xi)) inside=!inside;
    }
    return inside?1:-1;
}
static inline bool seg_cross_proper(double p0x,double p0y,double p1x,double p1y,
                                    double p2x,double p2y,double p3x,double p3y){
    double d1=cross(p2x,p2y,p3x,p3y,p0x,p0y),d2=cross(p2x,p2y,p3x,p3y,p1x,p1y);
    double d3=cross(p0x,p0y,p1x,p1y,p2x,p2y),d4=cross(p0x,p0y,p1x,p1y,p3x,p3y);
    return (((d1>0&&d2<0)||(d1<0&&d2>0))&&((d3>0&&d4<0)||(d3<0&&d4>0)));
}
static bool poly_overlap(const Poly& A,const Poly& B){
    for(auto&p:A) if(point_in_poly(p.first,p.second,B)==1) return true;
    for(auto&p:B) if(point_in_poly(p.first,p.second,A)==1) return true;
    int na=A.size(),nb=B.size();
    for(int i=0;i<na;i++){
        double p0x=A[i].first,p0y=A[i].second,p1x=A[(i+1)%na].first,p1y=A[(i+1)%na].second;
        for(int j=0;j<nb;j++)
            if(seg_cross_proper(p0x,p0y,p1x,p1y,B[j].first,B[j].second,B[(j+1)%nb].first,B[(j+1)%nb].second)) return true;
    }
    return false;
}

// ---------- placement column ----------
struct Col {
    int block, orient, x, y, entry, exit;
    std::vector<Poly> layers;             // world coords
    double bx0,by0,bx1,by1;
};
static void bbox_of(Col& c){
    c.bx0=1e18;c.by0=1e18;c.bx1=-1e18;c.by1=-1e18;
    for(auto&L:c.layers) for(auto&p:L){
        c.bx0=std::min(c.bx0,p.first);c.by0=std::min(c.by0,p.second);
        c.bx1=std::max(c.bx1,p.first);c.by1=std::max(c.by1,p.second);
    }
}

// crane conflict, fastconf j>=k logic (descent OR ascent => same A_k vs B_{j>k} loop)
static bool crane_conflict(const Col& A, const Col& B){
    if(!(A.entry < B.exit && B.entry < A.exit)) return false;         // time co-presence
    if(A.bx1<=B.bx0||B.bx1<=A.bx0||A.by1<=B.by0||B.by1<=A.by0) return false; // AABB
    int Ka=A.layers.size(), Kb=B.layers.size();
    int mk=std::min(Ka,Kb);
    for(int k=0;k<mk;k++){                                            // resting j==k
        if(A.layers[k].size()<3||B.layers[k].size()<3) continue;
        if(poly_overlap(A.layers[k],B.layers[k])) return true;
    }
    bool AoverB = (A.entry>=B.entry) || (A.exit<=B.exit);             // A sweeps B upper layers
    bool BoverA = (B.entry>=A.entry) || (B.exit<=A.exit);
    if(AoverB){
        for(int k=0;k<Ka;k++){
            if(A.layers[k].size()<3) continue;
            for(int j=k+1;j<Kb;j++){
                if(B.layers[j].size()<3) continue;
                if(poly_overlap(A.layers[k],B.layers[j])) return true;
            }
        }
    }
    if(BoverA){
        for(int k=0;k<Kb;k++){
            if(B.layers[k].size()<3) continue;
            for(int j=k+1;j<Ka;j++){
                if(A.layers[j].size()<3) continue;
                if(poly_overlap(B.layers[k],A.layers[j])) return true;
            }
        }
    }
    return false;
}

// ---------- rng ----------
struct Xorshift { uint64_t s;
    Xorshift(uint64_t seed):s(seed?seed:0x9e3779b97f4a7c15ULL){}
    uint64_t next(){ s^=s<<13; s^=s>>7; s^=s<<17; return s; }
    int randint(int n){ return (int)(next()% (uint64_t)n); }
};

// ---------- main entry ----------
// blocks: list of (orient_layers, obb, entry_exit_list)
//   orient_layers   : list over orients of list of (Nx2 float64) layer arrays at origin
//   obb             : list over orients of (x0,y0,x1,y1)
//   entry_exit_list : list of (entry,exit) time-variants (>=1); columns are generated
//                     for EVERY variant so the packer can re-time a block (low-density
//                     temporal slack lever).  "one column per block" still holds.
// warm : list of (block_idx, orient, x, y) greedy placements (may be off-grid; seeded)
// returns (best_count, [(block, orient, x, y)...], n_cols, n_edges, build_ms, solve_ms)
py::tuple pack(py::list blocks, double W, double H, int step,
               double time_budget_s, uint64_t seed, py::object warm, py::object frozen){
    auto t0=std::chrono::high_resolution_clock::now();
    int nblk = (int)py::len(blocks);

    // parse per-block per-orient origin polygons + obb + entry/exit variants
    std::vector<std::vector<std::vector<Poly>>> BL(nblk); // [b][o] -> layers
    std::vector<std::vector<std::array<double,4>>> OBB(nblk);
    std::vector<std::vector<std::pair<int,int>>> ENT(nblk); // entry/exit variants
    for(int b=0;b<nblk;b++){
        py::tuple bt = py::cast<py::tuple>(blocks[b]);
        py::list orients = py::cast<py::list>(bt[0]);
        py::list obbs    = py::cast<py::list>(bt[1]);
        for(auto ee : py::cast<py::list>(bt[2])){
            py::tuple t=py::cast<py::tuple>(ee);
            ENT[b].push_back({py::cast<int>(t[0]),py::cast<int>(t[1])});
        }
        int no=(int)py::len(orients);
        BL[b].resize(no); OBB[b].resize(no);
        for(int o=0;o<no;o++){
            py::list layers=py::cast<py::list>(orients[o]);
            for(auto L : layers){
                py::array_t<double> arr=py::cast<py::array_t<double>>(L);
                auto a=arr.unchecked<2>(); Poly P;
                for(py::ssize_t i=0;i<a.shape(0);i++) P.emplace_back(a(i,0),a(i,1));
                BL[b][o].push_back(P);
            }
            py::tuple ob=py::cast<py::tuple>(obbs[o]);
            OBB[b][o]={py::cast<double>(ob[0]),py::cast<double>(ob[1]),
                       py::cast<double>(ob[2]),py::cast<double>(ob[3])};
        }
    }

    // frozen obstacle blocks (fixed placements in the bay, WORLD coords + entry/exit).
    // Any generated column that crane-conflicts with a frozen block is dropped.
    std::vector<Col> froz;
    if(!frozen.is_none()){
        for(auto item : py::cast<py::list>(frozen)){
            py::tuple t=py::cast<py::tuple>(item);
            py::list layers=py::cast<py::list>(t[0]);
            Col c; c.block=-1;c.orient=-1;c.x=0;c.y=0;
            c.entry=py::cast<int>(t[1]); c.exit=py::cast<int>(t[2]);
            for(auto L : layers){
                py::array_t<double> arr=py::cast<py::array_t<double>>(L);
                auto a=arr.unchecked<2>(); Poly P;
                for(py::ssize_t i=0;i<a.shape(0);i++) P.emplace_back(a(i,0),a(i,1));
                c.layers.push_back(std::move(P));
            }
            bbox_of(c); froz.push_back(std::move(c));
        }
    }

    // warm placements
    std::vector<std::array<int,4>> warmp; // block,orient,x,y
    if(!warm.is_none()){
        for(auto item : py::cast<py::list>(warm)){
            py::tuple t=py::cast<py::tuple>(item);
            warmp.push_back({py::cast<int>(t[0]),py::cast<int>(t[1]),
                             py::cast<int>(t[2]),py::cast<int>(t[3])});
        }
    }

    // ---- generate columns (coarse grid + warm positions) ----
    std::vector<Col> cols;
    std::vector<std::vector<int>> colsOfBlock(nblk);
    auto make_col=[&](int b,int o,int x,int y,int en,int ex){
        Col c; c.block=b;c.orient=o;c.x=x;c.y=y;c.entry=en;c.exit=ex;
        for(auto& P : BL[b][o]){
            Poly Q; Q.reserve(P.size());
            for(auto&p:P) Q.emplace_back(p.first+x,p.second+y);
            c.layers.push_back(std::move(Q));
        }
        bbox_of(c);
        for(const Col& f : froz) if(crane_conflict(c,f)) return;   // drop: hits an obstacle
        colsOfBlock[b].push_back((int)cols.size());
        cols.push_back(std::move(c));
    };
    for(int b=0;b<nblk;b++){
        for(int o=0;o<(int)BL[b].size();o++){
            double x0=OBB[b][o][0],y0=OBB[b][o][1],x1=OBB[b][o][2],y1=OBB[b][o][3];
            int xlo=(int)std::ceil(-x0), xhi=(int)std::floor(W-x1);
            int ylo=(int)std::ceil(-y0), yhi=(int)std::floor(H-y1);
            if(xlo>xhi||ylo>yhi) continue;
            std::vector<int> xs, ys;
            for(int x=xlo;x<=xhi;x+=step) xs.push_back(x);
            for(int y=ylo;y<=yhi;y+=step) ys.push_back(y);
            for(auto& wp : warmp) if(wp[0]==b&&wp[1]==o){
                if(wp[2]>=xlo&&wp[2]<=xhi) xs.push_back(wp[2]);
                if(wp[3]>=ylo&&wp[3]<=yhi) ys.push_back(wp[3]);
            }
            std::sort(xs.begin(),xs.end()); xs.erase(std::unique(xs.begin(),xs.end()),xs.end());
            std::sort(ys.begin(),ys.end()); ys.erase(std::unique(ys.begin(),ys.end()),ys.end());
            for(int x:xs) for(int y:ys) for(auto& ee : ENT[b]) make_col(b,o,x,y,ee.first,ee.second);
        }
    }
    int ncol=(int)cols.size();

    // ---- pairwise conflict graph (only across different blocks) ----
    std::vector<std::vector<int>> adj(ncol);
    long nedge=0;
    for(int a=0;a<ncol;a++){
        const Col& ca=cols[a];
        for(int b=a+1;b<ncol;b++){
            const Col& cb=cols[b];
            if(ca.block==cb.block) continue;                 // same-block handled by blockUsed
            if(ca.bx1<=cb.bx0||cb.bx1<=ca.bx0||ca.by1<=cb.by0||cb.by1<=ca.by0) continue;
            if(!(ca.entry<cb.exit&&cb.entry<ca.exit)) continue;
            if(crane_conflict(ca,cb)){ adj[a].push_back(b); adj[b].push_back(a); nedge++; }
        }
    }
    for(auto& v:adj) std::sort(v.begin(),v.end());
    auto t1=std::chrono::high_resolution_clock::now();
    double build_ms=std::chrono::duration<double,std::milli>(t1-t0).count();

    // ---- MIS heuristic: maximise distinct blocks placed ----
    // state: sel[b] = chosen column for block b or -1 ; selected columns list.
    // compatibility of col c against current selection = no adj neighbour selected.
    // Fast neighbour-in-selection test via per-column "blocked" counter.
    Xorshift rng(seed);
    std::vector<int> sel(nblk,-1);       // working
    std::vector<int> blocked(ncol,0);    // #selected columns conflicting with this col
    std::vector<char> selflag(ncol,0);

    auto add_col=[&](int c){
        int b=cols[c].block; sel[b]=c; selflag[c]=1;
        for(int nb2:adj[c]) blocked[nb2]++;
    };
    auto rem_col=[&](int c){
        int b=cols[c].block; sel[b]=-1; selflag[c]=0;
        for(int nb2:adj[c]) blocked[nb2]--;
    };
    auto clear_all=[&](){
        for(int b=0;b<nblk;b++) if(sel[b]>=0) rem_col(sel[b]);
    };
    auto count_sel=[&](){ int c2=0; for(int b=0;b<nblk;b++) if(sel[b]>=0) c2++; return c2; };

    // greedily extend current selection using a given block order; within a block
    // pick the first column with blocked==0.
    auto greedy_extend=[&](const std::vector<int>& border){
        for(int b:border){
            if(sel[b]>=0) continue;
            for(int c:colsOfBlock[b]) if(blocked[c]==0){ add_col(c); break; }
        }
    };

    std::vector<int> border(nblk); for(int b=0;b<nblk;b++) border[b]=b;

    // (2,1)-swap: remove one selected column s, add TWO freed columns from distinct
    // unplaced blocks that don't conflict with each other -> net +1 block.  Canonical
    // MIS improvement; escapes the 9-basin that force/repair alone cannot.  Returns
    // true if it improved (applied one swap).
    auto try_2_1_swap=[&]()->bool{
        for(int b=0;b<nblk;b++){
            int s=sel[b]; if(s<0) continue;
            // freed[c]: neighbours of s that become addable if s is removed
            // (blocked==1 means s is their only selected conflict) and block unplaced.
            std::vector<int> freed;
            for(int c:adj[s]) if(!selflag[c] && blocked[c]==1 && sel[cols[c].block]<0) freed.push_back(c);
            int nf=(int)freed.size();
            if(nf<2) continue;
            // find two from distinct blocks that are mutually non-conflicting
            for(int i=0;i<nf;i++){
                int c1=freed[i], b1=cols[c1].block;
                for(int k=i+1;k<nf;k++){
                    int c2=freed[k]; if(cols[c2].block==b1) continue;
                    // c1,c2 conflict?  binary search in adj[c1]
                    if(std::binary_search(adj[c1].begin(),adj[c1].end(),c2)) continue;
                    // apply: remove s, add c1,c2
                    rem_col(s); add_col(c1); add_col(c2);
                    return true;
                }
            }
        }
        return false;
    };
    auto local_opt=[&](){ while(try_2_1_swap()){} };

    // best
    std::vector<int> best_sel(nblk,-1); int best=0;
    auto save_if_better=[&](){ int c2=count_sel(); if(c2>best){ best=c2; best_sel=sel; } return c2; };

    // seed 1: warm placement (map warm to nearest generated column of same b,o,x,y)
    if(!warmp.empty()){
        clear_all();
        for(auto&wp:warmp){
            int b=wp[0]; int want=-1;
            for(int c:colsOfBlock[b]) if(cols[c].orient==wp[1]&&cols[c].x==wp[2]&&cols[c].y==wp[3]){want=c;break;}
            if(want>=0 && sel[b]<0 && blocked[want]==0) add_col(want);
        }
        greedy_extend(border);
        save_if_better();
    }

    // seed 2..: randomized greedy constructions
    // main loop: iterated force/repair local search on the incumbent.
    auto now_s=[&](){ auto t=std::chrono::high_resolution_clock::now();
                      return std::chrono::duration<double>(t-t1).count(); };
    int since_improve=0;
    // ensure we hold a working selection = current best (or a fresh greedy)
    auto load_best=[&](){ clear_all();
        for(int b=0;b<nblk;b++) if(best_sel[b]>=0){ int c=best_sel[b]; if(blocked[c]==0) add_col(c);} };

    // initial random restarts (each hardened with (2,1)-swap local opt) to get incumbent
    for(int it=0; it<200 && now_s()<time_budget_s; it++){
        clear_all();
        for(int i=nblk-1;i>0;i--){ int j=rng.randint(i+1); std::swap(border[i],border[j]); }
        greedy_extend(border);
        local_opt();
        save_if_better();
    }
    load_best();

    // iterated local search: force a random excluded block in (kick conflicts), repair.
    while(now_s()<time_budget_s){
        // snapshot current working count
        int before=count_sel();
        // pick a random excluded block that has at least one column
        int tries=0, pick=-1;
        while(tries++<2*nblk){
            int b=rng.randint(nblk);
            if(sel[b]<0 && !colsOfBlock[b].empty()){ pick=b; break; }
        }
        if(pick<0){
            // fully placed everything placeable; perturb by random restart
            clear_all();
            for(int i=nblk-1;i>0;i--){ int j=rng.randint(i+1); std::swap(border[i],border[j]); }
            greedy_extend(border);
            if(count_sel()>=before) save_if_better(); else load_best();
            continue;
        }
        // choose a random column of that block, kick out selected conflicts, add it
        int c = colsOfBlock[pick][ rng.randint((int)colsOfBlock[pick].size()) ];
        // remove selected columns adjacent to c
        for(int nb2:adj[c]) if(selflag[nb2]) rem_col(nb2);
        add_col(c);
        // repair greedily with random order, then harden with (2,1)-swap local opt
        for(int i=nblk-1;i>0;i--){ int j=rng.randint(i+1); std::swap(border[i],border[j]); }
        greedy_extend(border);
        local_opt();
        int after=count_sel();
        if(after>=before){ save_if_better(); }     // accept equal/better (plateau walk)
        else { load_best(); since_improve++; }
        if(after>before) since_improve=0;
        // occasional full restart to diversify
        if(since_improve>500){
            clear_all();
            for(int i=nblk-1;i>0;i--){ int j=rng.randint(i+1); std::swap(border[i],border[j]); }
            greedy_extend(border);
            local_opt();
            save_if_better(); load_best(); since_improve=0;
        }
    }
    auto t2=std::chrono::high_resolution_clock::now();
    double solve_ms=std::chrono::duration<double,std::milli>(t2-t1).count();

    py::list placements;
    for(int b=0;b<nblk;b++) if(best_sel[b]>=0){
        const Col& c=cols[best_sel[b]];
        placements.append(py::make_tuple(c.block,c.orient,c.x,c.y,c.entry,c.exit));
    }

    // export graph for an exact solver (Gurobi): column descriptors + edges + warm-set.
    py::array_t<int> coldesc({(py::ssize_t)ncol,(py::ssize_t)6});
    { auto r=coldesc.mutable_unchecked<2>();
      for(int c=0;c<ncol;c++){ r(c,0)=cols[c].block;r(c,1)=cols[c].orient;r(c,2)=cols[c].x;
                               r(c,3)=cols[c].y;r(c,4)=cols[c].entry;r(c,5)=cols[c].exit; } }
    py::array_t<int> edges({(py::ssize_t)nedge,(py::ssize_t)2});
    { auto r=edges.mutable_unchecked<2>(); long e=0;
      for(int a=0;a<ncol;a++) for(int nb2:adj[a]) if(nb2>a){ r(e,0)=a;r(e,1)=nb2;e++; } }
    py::list warmcols;  // column indices chosen by the heuristic (per-block)
    for(int b=0;b<nblk;b++) if(best_sel[b]>=0) warmcols.append(best_sel[b]);

    return py::make_tuple(best, placements, ncol, (long)nedge, build_ms, solve_ms,
                          coldesc, edges, warmcols);
}

PYBIND11_MODULE(cranepack,m){
    m.def("pack",&pack,
          py::arg("blocks"),py::arg("W"),py::arg("H"),py::arg("step"),
          py::arg("time_budget_s"),py::arg("seed")=12345,py::arg("warm")=py::none(),
          py::arg("frozen")=py::none());
}

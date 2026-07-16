#include <pybind11/pybind11.h>
#include <pybind11/numpy.h>
#include <pybind11/stl.h>
#include <vector>
#include <cmath>
#include <algorithm>
namespace py = pybind11;
typedef std::vector<std::pair<double,double>> Poly;

inline double cross(double ox,double oy,double ax,double ay,double bx,double by){
    return (ax-ox)*(by-oy)-(ay-oy)*(bx-ox);
}
inline int point_in_poly(double px,double py,const Poly& poly,double eps=1e-9){
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
inline bool seg_cross_proper(double p0x,double p0y,double p1x,double p1y,
                             double p2x,double p2y,double p3x,double p3y){
    double d1=cross(p2x,p2y,p3x,p3y,p0x,p0y),d2=cross(p2x,p2y,p3x,p3y,p1x,p1y);
    double d3=cross(p0x,p0y,p1x,p1y,p2x,p2y),d4=cross(p0x,p0y,p1x,p1y,p3x,p3y);
    return (((d1>0&&d2<0)||(d1<0&&d2>0))&&((d3>0&&d4<0)||(d3<0&&d4>0)));
}
bool poly_overlap(const Poly& A,const Poly& B){
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

// 블록: 층들 + bbox + 시간 + bay
struct CBlock {
    std::vector<Poly> layers;
    double bx0,by0,bx1,by1;
    int entry, exit, bay;
    int bid;
};
void compute_bbox(CBlock& b){
    b.bx0=1e18;b.by0=1e18;b.bx1=-1e18;b.by1=-1e18;
    for(auto&L:b.layers) for(auto&p:L){
        b.bx0=std::min(b.bx0,p.first);b.by0=std::min(b.by0,p.second);
        b.bx1=std::max(b.bx1,p.first);b.by1=std::max(b.by1,p.second);
    }
}

// 전역 placed 블록 저장 (여러 검사에서 재사용)
static std::vector<CBlock> g_placed;

void set_placed(py::list blocks){
    g_placed.clear();
    for(auto item : blocks){
        py::tuple t=py::cast<py::tuple>(item);
        // (layers_list, entry, exit, bay)
        py::list layers=py::cast<py::list>(t[0]);
        CBlock cb;
        for(auto L : layers){
            py::array_t<double> arr=py::cast<py::array_t<double>>(L);
            auto a=arr.unchecked<2>();
            Poly P;
            for(py::ssize_t i=0;i<a.shape(0);i++) P.emplace_back(a(i,0),a(i,1));
            cb.layers.push_back(P);
        }
        cb.entry=py::cast<int>(t[1]); cb.exit=py::cast<int>(t[2]); cb.bay=py::cast<int>(t[3]);
        compute_bbox(cb);
        g_placed.push_back(cb);
    }
}
void add_placed(py::list layers,int entry,int exit,int bay,int bid){
    CBlock cb;
    for(auto L : layers){
        py::array_t<double> arr=py::cast<py::array_t<double>>(L);
        auto a=arr.unchecked<2>(); Poly P;
        for(py::ssize_t i=0;i<a.shape(0);i++) P.emplace_back(a(i,0),a(i,1));
        cb.layers.push_back(P);
    }
    cb.entry=entry;cb.exit=exit;cb.bay=bay;cb.bid=bid;
    compute_bbox(cb);
    g_placed.push_back(cb);
}
// 특정 블록 제거 (bid로)
void remove_block(int bid){
    for(size_t i=0;i<g_placed.size();i++){
        if(g_placed[i].bid==bid){
            g_placed[i]=g_placed.back();
            g_placed.pop_back();
            return;
        }
    }
}
// 여러 블록 제거
void remove_blocks(std::vector<int> bids){
    for(int b : bids) remove_block(b);
}
// 현재 placed의 bid 목록
std::vector<int> get_placed_ids(){
    std::vector<int> r;
    for(auto& c : g_placed) r.push_back(c.bid);
    return r;
}
void clear_placed(){ g_placed.clear(); }

// 새 블록 층을 offset 적용해서 만들기
CBlock make_newblock(const std::vector<py::array_t<double>>& base_layers,double ox,double oy,int entry,int exit,int bay){
    CBlock cb;
    for(auto& arr : base_layers){
        auto a=arr.unchecked<2>(); Poly P;
        for(py::ssize_t i=0;i<a.shape(0);i++) P.emplace_back(a(i,0)+ox,a(i,1)+oy);
        cb.layers.push_back(P);
    }
    cb.entry=entry;cb.exit=exit;cb.bay=bay;
    compute_bbox(cb);
    return cb;
}

// full_check: 새블록이 g_placed와 충돌없이 놓이나 (entry+exit)
bool check_one(const CBlock& nb){
    int n_new=nb.layers.size();
    for(const auto& ex : g_placed){
        if(ex.bay!=nb.bay) continue;
        // 시간 겹침
        if(!(ex.entry<nb.exit && nb.entry<ex.exit)) continue;
        // AABB
        if(nb.bx1<=ex.bx0||ex.bx1<=nb.bx0||nb.by1<=ex.by0||ex.by1<=nb.by0) continue;
        int n_ex=ex.layers.size();
        // ENTRY: 새블록 하강. new층k vs exist층j (j>=k)
        for(int k=0;k<n_new;k++){
            if(nb.layers[k].size()<3) continue;
            for(int j=k;j<n_ex;j++){
                if(ex.layers[j].size()<3) continue;
                if(poly_overlap(nb.layers[k],ex.layers[j])) return false;
            }
        }
        // EXIT: 기존블록 상승방해. exist층k vs new층j (j>=k)
        for(int k=0;k<n_ex;k++){
            if(ex.layers[k].size()<3) continue;
            for(int j=k;j<n_new;j++){
                if(nb.layers[j].size()<3) continue;
                if(poly_overlap(ex.layers[k],nb.layers[j])) return false;
            }
        }
    }
    return true;
}

// Python 인터페이스: 새블록 base층 + 위치 -> 가능?
bool check_placement(std::vector<py::array_t<double>> base_layers,double ox,double oy,int entry,int exit,int bay){
    CBlock nb=make_newblock(base_layers,ox,oy,entry,exit,bay);
    return check_one(nb);
}


// 격자 전체 스캔: feasible한 (ix,iy) 위치들을 C++ 안에서 다 검사 (Python 왕복 없음)
// bigleft 점수: 반환은 각 위치의 (ix, iy). Python이 점수매김.
// 새블록 하나 vs 후보리스트 (미리 필터된) 크레인검사
inline bool check_against(const CBlock& nb, const std::vector<const CBlock*>& cand){
    int n_new=nb.layers.size();
    for(const CBlock* exp : cand){
        const CBlock& ex=*exp;
        if(nb.bx1<=ex.bx0||ex.bx1<=nb.bx0||nb.by1<=ex.by0||ex.by1<=nb.by0) continue;
        int n_ex=ex.layers.size();
        for(int k=0;k<n_new;k++){
            if(nb.layers[k].size()<3) continue;
            for(int j=k;j<n_ex;j++){
                if(ex.layers[j].size()<3) continue;
                if(poly_overlap(nb.layers[k],ex.layers[j])) return false;
            }
        }
        for(int k=0;k<n_ex;k++){
            if(ex.layers[k].size()<3) continue;
            for(int j=k;j<n_new;j++){
                if(nb.layers[j].size()<3) continue;
                if(poly_overlap(ex.layers[k],nb.layers[j])) return false;
            }
        }
    }
    return true;
}

py::array_t<int> scan_block(std::vector<py::array_t<double>> base_layers,
                            int lo_x,int hi_x,int lo_y,int hi_y,
                            int entry,int exit,int bay){
    std::vector<Poly> base;
    for(auto& arr : base_layers){
        auto a=arr.unchecked<2>(); Poly P;
        for(py::ssize_t i=0;i<a.shape(0);i++) P.emplace_back(a(i,0),a(i,1));
        base.push_back(P);
    }
    int n_new=base.size();
    // 후보 미리 필터: 같은 bay + 시간겹침
    std::vector<const CBlock*> cand;
    cand.reserve(g_placed.size());
    double gx0=1e18,gy0=1e18,gx1=-1e18,gy1=-1e18;
    for(const auto& ex : g_placed){
        if(ex.bay!=bay) continue;
        if(!(ex.entry<exit && entry<ex.exit)) continue;
        cand.push_back(&ex);
        gx0=std::min(gx0,ex.bx0);gy0=std::min(gy0,ex.by0);
        gx1=std::max(gx1,ex.bx1);gy1=std::max(gy1,ex.by1);
    }
    // 공간 그리드 인덱스 (후보를 버킷에)
    const double CELL=8.0;  // 버킷 크기
    int GW=1,GH=1; 
    if(!cand.empty()){
        GW=std::max(1,(int)((gx1-gx0)/CELL)+1);
        GH=std::max(1,(int)((gy1-gy0)/CELL)+1);
    }
    std::vector<std::vector<const CBlock*>> grid(GW*GH);
    auto cellof=[&](double x,double y,int&cx,int&cy){
        cx=std::min(GW-1,std::max(0,(int)((x-gx0)/CELL)));
        cy=std::min(GH-1,std::max(0,(int)((y-gy0)/CELL)));
    };
    if(!cand.empty()){
        for(const CBlock* c : cand){
            int cx0,cy0,cx1,cy1; cellof(c->bx0,c->by0,cx0,cy0); cellof(c->bx1,c->by1,cx1,cy1);
            for(int gx=cx0;gx<=cx1;gx++) for(int gy=cy0;gy<=cy1;gy++)
                grid[gx*GH+gy].push_back(c);
        }
    }
    std::vector<std::pair<int,int>> feasible;
    CBlock nb; nb.entry=entry; nb.exit=exit; nb.bay=bay; nb.layers.resize(n_new);
    std::vector<const CBlock*> local; local.reserve(16);
    for(int ix=lo_x; ix<=hi_x; ix++){
        for(int iy=lo_y; iy<=hi_y; iy++){
            for(int k=0;k<n_new;k++){
                nb.layers[k].resize(base[k].size());
                for(size_t i=0;i<base[k].size();i++)
                    nb.layers[k][i]={base[k][i].first+ix, base[k][i].second+iy};
            }
            compute_bbox(nb);
            if(cand.empty()){ feasible.push_back({ix,iy}); continue; }
            // 새블록 bbox가 걸치는 버킷의 후보만 수집 (중복 제거)
            int cx0,cy0,cx1,cy1; cellof(nb.bx0,nb.by0,cx0,cy0); cellof(nb.bx1,nb.by1,cx1,cy1);
            local.clear();
            bool ok=true;
            for(int gx=cx0;gx<=cx1&&ok;gx++) for(int gy=cy0;gy<=cy1&&ok;gy++){
                for(const CBlock* c : grid[gx*GH+gy]){
                    // AABB
                    if(nb.bx1<=c->bx0||c->bx1<=nb.bx0||nb.by1<=c->by0||c->by1<=nb.by0) continue;
                    int n_ex=c->layers.size();
                    bool hit=false;
                    for(int k=0;k<n_new&&!hit;k++){
                        if(nb.layers[k].size()<3) continue;
                        for(int jj=k;jj<n_ex;jj++){
                            if(c->layers[jj].size()<3) continue;
                            if(poly_overlap(nb.layers[k],c->layers[jj])){hit=true;break;}
                        }
                    }
                    for(int k=0;k<n_ex&&!hit;k++){
                        if(c->layers[k].size()<3) continue;
                        for(int jj=k;jj<n_new;jj++){
                            if(nb.layers[jj].size()<3) continue;
                            if(poly_overlap(c->layers[k],nb.layers[jj])){hit=true;break;}
                        }
                    }
                    if(hit){ok=false;break;}
                }
            }
            if(ok) feasible.push_back({ix,iy});
        }
    }
    py::array_t<int> result({(py::ssize_t)feasible.size(),(py::ssize_t)2});
    auto r=result.mutable_unchecked<2>();
    for(size_t i=0;i<feasible.size();i++){ r(i,0)=feasible[i].first; r(i,1)=feasible[i].second; }
    return result;
}


#include <chrono>
// 진단용: feasible/infeasible 셀의 시간을 분리 측정
py::tuple scan_timing(std::vector<py::array_t<double>> base_layers,
                      int lo_x,int hi_x,int lo_y,int hi_y,
                      int entry,int exit,int bay){
    std::vector<Poly> base;
    for(auto& arr : base_layers){
        auto a=arr.unchecked<2>(); Poly P;
        for(py::ssize_t i=0;i<a.shape(0);i++) P.emplace_back(a(i,0),a(i,1));
        base.push_back(P);
    }
    int n_new=base.size();
    std::vector<const CBlock*> cand;
    for(const auto& ex : g_placed){
        if(ex.bay!=bay) continue;
        if(!(ex.entry<exit && entry<ex.exit)) continue;
        cand.push_back(&ex);
    }
    double t_feas=0, t_infeas=0; long n_feas=0, n_infeas=0;
    CBlock nb; nb.entry=entry; nb.exit=exit; nb.bay=bay; nb.layers.resize(n_new);
    for(int ix=lo_x; ix<=hi_x; ix++){
        for(int iy=lo_y; iy<=hi_y; iy++){
            auto t0=std::chrono::high_resolution_clock::now();
            for(int k=0;k<n_new;k++){
                nb.layers[k].resize(base[k].size());
                for(size_t i=0;i<base[k].size();i++)
                    nb.layers[k][i]={base[k][i].first+ix, base[k][i].second+iy};
            }
            compute_bbox(nb);
            bool ok=check_against(nb,cand);
            auto t1=std::chrono::high_resolution_clock::now();
            double dt=std::chrono::duration<double>(t1-t0).count();
            if(ok){t_feas+=dt;n_feas++;} else {t_infeas+=dt;n_infeas++;}
        }
    }
    return py::make_tuple(n_feas,n_infeas,t_feas,t_infeas);
}


// C++ 안에서 코너후보 생성 + 크레인검사 (Python 왕복 제거)
// 후보 위치 = 벽(lo_x,lo_y) + present 블록 경계에 접하는 위치들
py::array_t<int> scan_corners(std::vector<py::array_t<double>> base_layers,
                              int lo_x,int hi_x,int lo_y,int hi_y,
                              double bx0_base,double by0_base,double bx1_base,double by1_base,
                              int entry,int exit,int bay,int PAD){
    std::vector<Poly> base;
    for(auto& arr : base_layers){
        auto a=arr.unchecked<2>(); Poly P;
        for(py::ssize_t i=0;i<a.shape(0);i++) P.emplace_back(a(i,0),a(i,1));
        base.push_back(P);
    }
    int n_new=base.size();
    // 시간겹침 후보
    std::vector<const CBlock*> cand;
    for(const auto& ex : g_placed){
        if(ex.bay!=bay) continue;
        if(!(ex.entry<exit && entry<ex.exit)) continue;
        cand.push_back(&ex);
    }
    // 후보 x,y 좌표 생성 (벽 + present 경계접촉 + ±pad 조밀 + present 정점)
    std::vector<int> xs, ys;
    auto addx=[&](int v){ if(v>=lo_x&&v<=hi_x) xs.push_back(v); };
    auto addy=[&](int v){ if(v>=lo_y&&v<=hi_y) ys.push_back(v); };
    addx(lo_x); addy(lo_y);
    for(const CBlock* c : cand){
        int cx=(int)std::ceil(c->bx1 - bx0_base);
        int cx2=(int)std::floor(c->bx0 - bx1_base);
        int cy=(int)std::ceil(c->by1 - by0_base);
        int cy2=(int)std::floor(c->by0 - by1_base);
        // ±PAD 조밀 샘플 (bbox 코너 주변만, 정점후보 없음)
        for(int p=-PAD;p<=PAD;p++){ addx(cx+p); addx(cx2+p); addy(cy+p); addy(cy2+p); }
    }
    // 중복 제거
    std::sort(xs.begin(),xs.end()); xs.erase(std::unique(xs.begin(),xs.end()),xs.end());
    std::sort(ys.begin(),ys.end()); ys.erase(std::unique(ys.begin(),ys.end()),ys.end());

    std::vector<std::pair<int,int>> feasible;
    CBlock nb; nb.entry=entry; nb.exit=exit; nb.bay=bay; nb.layers.resize(n_new);
    for(int ix : xs){
        for(int iy : ys){
            for(int k=0;k<n_new;k++){
                nb.layers[k].resize(base[k].size());
                for(size_t i=0;i<base[k].size();i++)
                    nb.layers[k][i]={base[k][i].first+ix, base[k][i].second+iy};
            }
            compute_bbox(nb);
            if(check_against(nb,cand)) feasible.push_back({ix,iy});
        }
    }
    py::array_t<int> result({(py::ssize_t)feasible.size(),(py::ssize_t)2});
    auto r=result.mutable_unchecked<2>();
    for(size_t i=0;i<feasible.size();i++){ r(i,0)=feasible[i].first; r(i,1)=feasible[i].second; }
    return result;
}

// max free horizontal gap in the bottom band, mirroring _free_span_with exactly.
// occ: sorted (start,end) intervals of present blocks dipping into the band.
static inline double free_span_with(const std::vector<std::pair<double,double>>& occ,
                                    double bw, double wx, double w, double wy, double band_top){
    double fm=0.0, c2=0.0;
    if(wy<band_top){
        double lo=wx, hi=wx+w; bool inserted=false;
        for(const auto& pr : occ){
            double a=pr.first, b_=pr.second;
            if(!inserted && lo<a){
                if(lo>c2){ double g=lo-c2; if(g>fm) fm=g; }
                if(hi>c2) c2=hi; inserted=true;
            }
            if(a>c2){ double g=a-c2; if(g>fm) fm=g; }
            if(b_>c2) c2=b_;
        }
        if(!inserted){
            if(lo>c2){ double g=lo-c2; if(g>fm) fm=g; }
            if(hi>c2) c2=hi;
        }
        if(bw>c2){ double g=bw-c2; if(g>fm) fm=g; }
        return fm;
    }
    for(const auto& pr : occ){
        double a=pr.first, b_=pr.second;
        if(a>c2){ double g=a-c2; if(g>fm) fm=g; }
        if(b_>c2) c2=b_;
    }
    if(bw>c2){ double g=bw-c2; if(g>fm) fm=g; }
    return fm;
}

// FULL bigleft placement in C++: replicates _smallright_construct's place_custom
// (mode="bigleft") scan+score for a single block over ALL bays/orientations, and
// returns the single best placement.  Kills the Python position loop AND scoring.
//   big block  (is_small=false): minimise (h, wx, wy, bay)   [early-exit per orient]
//   small block(is_small=true) : minimise (-free_span, wy, wx)  [full scan]
// iteration order bay->orient->ix->iy with strict '<' so ties resolve exactly as
// Python (first found wins).  base = per-orient list of layer polygons (Nx2, at
// origin); obb = per-orient (x0,y0,x1,y1); baydims = per-bay (w,h).
py::tuple best_bigleft(std::vector<std::vector<py::array_t<double>>> orient_layers,
                       std::vector<std::array<double,4>> obb,
                       std::vector<std::pair<double,double>> baydims,
                       int entry, int exit, bool is_small, double BAND,
                       int only_bay=-1,
                       int wlo_x=-1000000,int whi_x=1000000,
                       int wlo_y=-1000000,int whi_y=1000000){
    int n_bay=baydims.size();
    // pre-parse orient polygons into Poly vectors
    std::vector<std::vector<Poly>> O(orient_layers.size());
    for(size_t oi=0; oi<orient_layers.size(); oi++){
        for(auto& arr : orient_layers[oi]){
            auto a=arr.unchecked<2>(); Poly P;
            for(py::ssize_t i=0;i<a.shape(0);i++) P.emplace_back(a(i,0),a(i,1));
            O[oi].push_back(P);
        }
    }
    bool found=false;
    // best score keys: big=(h,wx,wy,bay) ; small=(-fs,wy,wx,0)
    double bk0=0,bk1=0,bk2=0; int bk3=0;
    int best_bay=-1,best_oi=-1,best_ix=0,best_iy=0;
    auto better=[&](double k0,double k1,double k2,int k3)->bool{
        if(!found) return true;
        if(k0!=bk0) return k0<bk0;
        if(k1!=bk1) return k1<bk1;
        if(k2!=bk2) return k2<bk2;
        return k3<bk3;
    };
    Poly tmp;
    for(int bay=0; bay<n_bay; bay++){
        if(only_bay>=0 && bay!=only_bay) continue;
        double bw=baydims[bay].first, bh=baydims[bay].second;
        std::vector<const CBlock*> cand;
        for(const auto& ex : g_placed){
            if(ex.bay!=bay) continue;
            if(!(ex.entry<exit && entry<ex.exit)) continue;
            cand.push_back(&ex);
        }
        double band_top=bh*BAND;
        std::vector<std::pair<double,double>> occ;
        if(is_small){
            for(auto* c: cand) if(c->by0<band_top) occ.push_back({c->bx0,c->bx1});
            std::sort(occ.begin(),occ.end());
        }
        for(size_t oi=0; oi<O.size(); oi++){
            double x0=obb[oi][0], y0=obb[oi][1], x1=obb[oi][2], y1=obb[oi][3];
            double w=x1-x0, h=y1-y0;
            if(w>bw+1e-9 || h>bh+1e-9) continue;
            int lo_x=(int)std::ceil(-x0), hi_x=(int)std::floor(bw-x1);
            int lo_y=(int)std::ceil(-y0), hi_y=(int)std::floor(bh-y1);
            // clip to the requested window (free-region incremental rescan)
            if(wlo_x>lo_x) lo_x=wlo_x; if(whi_x<hi_x) hi_x=whi_x;
            if(wlo_y>lo_y) lo_y=wlo_y; if(whi_y<hi_y) hi_y=whi_y;
            if(hi_x<lo_x || hi_y<lo_y) continue;
            int n_new=O[oi].size();
            CBlock nb; nb.entry=entry; nb.exit=exit; nb.bay=bay; nb.layers.resize(n_new);
            // big block: prune orients that cannot beat the incumbent on h alone
            if(!is_small && found && h>bk0) continue;
            for(int ix=lo_x; ix<=hi_x; ix++){
                double wx=ix+x0;
                if(!is_small && found && h==bk0 && wx>bk1) break; // wx only grows -> no better this orient
                for(int iy=lo_y; iy<=hi_y; iy++){
                    double wy=iy+y0;
                    // build offset layers
                    for(int k=0;k<n_new;k++){
                        nb.layers[k].resize(O[oi][k].size());
                        for(size_t i=0;i<O[oi][k].size();i++)
                            nb.layers[k][i]={O[oi][k][i].first+ix, O[oi][k][i].second+iy};
                    }
                    compute_bbox(nb);
                    if(!check_against(nb,cand)) continue;
                    if(!is_small){
                        // score (h, wx, wy, bay); first feasible in (ix,iy) order = min(wx,wy)
                        if(better(h,wx,wy,bay)){ found=true; bk0=h;bk1=wx;bk2=wy;bk3=bay;
                            best_bay=bay;best_oi=oi;best_ix=ix;best_iy=iy; }
                        break; // early-exit: this iy is the min for this ix; move to next ix
                    } else {
                        double fs=free_span_with(occ,bw,wx,w,wy,band_top);
                        if(better(-fs,wy,wx,0)){ found=true; bk0=-fs;bk1=wy;bk2=wx;bk3=0;
                            best_bay=bay;best_oi=oi;best_ix=ix;best_iy=iy; }
                    }
                }
                if(!is_small && found && h==bk0 && (ix+x0)>=bk1) {
                    // once we've recorded a wx at this orient, larger ix can't beat it
                    // (handled by the break above; keep scanning only if not yet found here)
                }
            }
        }
    }
    // also return the winning score keys (bk0,bk1,bk2) so the caller can compare
    // across bays exactly (needed for small blocks whose key is -free_span).
    return py::make_tuple(found,best_bay,best_oi,best_ix,best_iy,bk0,bk1,bk2);
}

PYBIND11_MODULE(cranecheck,m){
    m.def("set_placed",&set_placed);
    m.def("add_placed",&add_placed);
    m.def("remove_block",&remove_block);
    m.def("remove_blocks",&remove_blocks);
    m.def("get_placed_ids",&get_placed_ids);
    m.def("clear_placed",&clear_placed);
    m.def("check_placement",&check_placement);
    m.def("scan_block",&scan_block);
    m.def("scan_corners",&scan_corners);
    m.def("scan_timing",&scan_timing);
    m.def("best_bigleft",&best_bigleft,
          py::arg("orient_layers"),py::arg("obb"),py::arg("baydims"),
          py::arg("entry"),py::arg("exit"),py::arg("is_small"),py::arg("BAND"),
          py::arg("only_bay")=-1,
          py::arg("wlo_x")=-1000000,py::arg("whi_x")=1000000,
          py::arg("wlo_y")=-1000000,py::arg("whi_y")=1000000);
}

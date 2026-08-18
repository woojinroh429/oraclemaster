// st3dtcs.cpp -- C++ full-scan construction placement with 3DTCS (space-time
// contact) scoring.  Crane feasibility geometry reused verbatim from cranecheck.
// Objective terms (tardiness, preference, load) stay PRIMARY; 3DTCS contact only
// breaks ties.  Compiled as a pybind11 module `st3dtcs`.
#include <pybind11/pybind11.h>
#include <pybind11/numpy.h>
#include <pybind11/stl.h>
#include <vector>
#include <cmath>
#include <algorithm>
#include <limits>
namespace py = pybind11;
typedef std::vector<std::pair<double,double>> Poly;

// ---- geometry (verbatim from cranecheck.cpp) ----
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

struct CBlock {
    std::vector<Poly> layers;
    double bx0,by0,bx1,by1;
    int entry, exit, bay;
    double wl;
};
void compute_bbox(CBlock& b){
    b.bx0=1e18;b.by0=1e18;b.bx1=-1e18;b.by1=-1e18;
    for(auto&L:b.layers) for(auto&p:L){
        b.bx0=std::min(b.bx0,p.first);b.by0=std::min(b.by0,p.second);
        b.bx1=std::max(b.bx1,p.first);b.by1=std::max(b.by1,p.second);
    }
}

// ---- module state ----
static std::vector<CBlock> g_placed;
static std::vector<double> g_bayw, g_bayh, g_bayunit;

// per-bay uniform-grid spatial index (2D hashing): g_cell[bay][cy*ncx+cx] = list
// of placed-block indices whose bbox touches that cell.  Lets a candidate check
// only nearby blocks instead of all placed -> the dominant speedup on dense bays.
static const double CELL = 1000000.0;
static std::vector<int> g_ncx, g_ncy;
static std::vector<std::vector<std::vector<int>>> g_cell;   // [bay][cellidx][.]

static inline int _cx(int bay,double x){ int c=(int)std::floor(x/CELL); if(c<0)c=0; if(c>=g_ncx[bay])c=g_ncx[bay]-1; return c; }
static inline int _cy(int bay,double y){ int c=(int)std::floor(y/CELL); if(c<0)c=0; if(c>=g_ncy[bay])c=g_ncy[bay]-1; return c; }

void st_init(std::vector<double> bw, std::vector<double> bh, std::vector<double> bu){
    g_bayw=bw; g_bayh=bh; g_bayunit=bu; g_placed.clear();
    int nb=bw.size();
    g_ncx.assign(nb,1); g_ncy.assign(nb,1); g_cell.assign(nb,{});
    for(int b=0;b<nb;b++){
        g_ncx[b]=std::max(1,(int)std::ceil(bw[b]/CELL));
        g_ncy[b]=std::max(1,(int)std::ceil(bh[b]/CELL));
        g_cell[b].assign(g_ncx[b]*g_ncy[b], {});
    }
}
void st_clear(){
    g_placed.clear();
    for(size_t b=0;b<g_cell.size();b++)
        for(auto& v : g_cell[b]) v.clear();
}
static void _index_block(int idx){
    const CBlock& c=g_placed[idx]; int bay=c.bay;
    if(bay<0||bay>=(int)g_ncx.size()) return;
    int x0=_cx(bay,c.bx0),x1=_cx(bay,c.bx1),y0=_cy(bay,c.by0),y1=_cy(bay,c.by1);
    for(int cy=y0;cy<=y1;cy++) for(int cx=x0;cx<=x1;cx++)
        g_cell[bay][cy*g_ncx[bay]+cx].push_back(idx);
}

// build a CBlock from base (origin) layers offset by (ox,oy)
CBlock make_block(const std::vector<py::array_t<double>>& base, double ox, double oy,
                  int entry, int exit, int bay, double wl){
    CBlock cb;
    for(auto& arr : base){
        auto a=arr.unchecked<2>(); Poly P;
        for(py::ssize_t i=0;i<a.shape(0);i++) P.emplace_back(a(i,0)+ox,a(i,1)+oy);
        cb.layers.push_back(std::move(P));
    }
    cb.entry=entry;cb.exit=exit;cb.bay=bay;cb.wl=wl;
    compute_bbox(cb);
    return cb;
}

void st_add(std::vector<py::array_t<double>> base, double ox, double oy,
            int entry, int exit, int bay, double wl){
    g_placed.push_back(make_block(base, ox, oy, entry, exit, bay, wl));
    _index_block((int)g_placed.size()-1);
}

// gather unique placed indices near a candidate bbox in `bay` (with `margin`
// extra cells so edge-adjacent neighbours are included for contact).  Uses a
// stamp array to dedupe without allocations.
static std::vector<int> g_stamp;
static int g_epoch=0;
static void _gather(int bay,double nx0,double ny0,double nx1,double ny1,int margin,std::vector<int>& out){
    out.clear();
    if(bay<0||bay>=(int)g_ncx.size()) return;
    if((int)g_stamp.size()<(int)g_placed.size()) g_stamp.assign(g_placed.size(),0);
    g_epoch++;
    int x0=_cx(bay,nx0)-margin,x1=_cx(bay,nx1)+margin,y0=_cy(bay,ny0)-margin,y1=_cy(bay,ny1)+margin;
    if(x0<0)x0=0; if(y0<0)y0=0; if(x1>=g_ncx[bay])x1=g_ncx[bay]-1; if(y1>=g_ncy[bay])y1=g_ncy[bay]-1;
    for(int cy=y0;cy<=y1;cy++) for(int cx=x0;cx<=x1;cx++)
        for(int idx : g_cell[bay][cy*g_ncx[bay]+cx])
            if(g_stamp[idx]!=g_epoch){ g_stamp[idx]=g_epoch; out.push_back(idx); }
}

// Fast feasibility for a candidate given its base (origin) layers `blayers`,
// offset (ox,oy) and abs bbox.  Only blocks that pass the (cheap) time + AABB
// filter trigger the per-layer poly_overlap, and the offset polygons for the
// candidate are materialised LAZILY (once) at that point -- for the vast majority
// of scan positions nothing overlaps, so no polygon is ever built.  Same crane
// rule as cranecheck.check_one.
bool st_feasible_fast(const std::vector<Poly>& blayers, double ox, double oy,
                      double nx0,double ny0,double nx1,double ny1,
                      int entry,int exit,int bay,const std::vector<int>& near){
    int n_new=blayers.size();
    std::vector<Poly> off;              // lazily-built offset layers of candidate
    bool built=false;
    for(int idx : near){
        const CBlock& ex=g_placed[idx];
        if(ex.bay!=bay) continue;
        if(!(ex.entry<exit && entry<ex.exit)) continue;
        if(nx1<=ex.bx0||ex.bx1<=nx0||ny1<=ex.by0||ex.by1<=ny0) continue;
        if(!built){
            off.resize(n_new);
            for(int k=0;k<n_new;k++){
                off[k].reserve(blayers[k].size());
                for(auto&p:blayers[k]) off[k].emplace_back(p.first+ox,p.second+oy);
            }
            built=true;
        }
        int n_ex=ex.layers.size();
        for(int k=0;k<n_new;k++){
            if((int)off[k].size()<3) continue;
            for(int j=k;j<n_ex;j++){
                if((int)ex.layers[j].size()<3) continue;
                if(poly_overlap(off[k],ex.layers[j])) return false;
            }
        }
        for(int k=0;k<n_ex;k++){
            if((int)ex.layers[k].size()<3) continue;
            for(int j=k;j<n_new;j++){
                if((int)off[j].size()<3) continue;
                if(poly_overlap(ex.layers[k],off[j])) return false;
            }
        }
    }
    return true;
}

// 3DTCS contact of a candidate abs-bbox occupying [entry,exit) in a bay:
// spatial shared edge with time-overlapping neighbours + walls, plus temporal
// footprint overlap with blocks abutting in time.
double st_contact(double nx0,double ny0,double nx1,double ny1,int entry,int exit,int bay,const std::vector<int>& near){
    double c_sp=0.0, c_tm=0.0;
    double bw=g_bayw[bay], bh=g_bayh[bay];
    if(nx0<=1e-9) c_sp+=(ny1-ny0);
    if(nx1>=bw-1e-9) c_sp+=(ny1-ny0);
    if(ny0<=1e-9) c_sp+=(nx1-nx0);
    if(ny1>=bh-1e-9) c_sp+=(nx1-nx0);
    for(int idx : near){
        const CBlock& o=g_placed[idx];
        if(o.bay!=bay) continue;
        double ox0=o.bx0,oy0=o.by0,ox1=o.bx1,oy1=o.by1;
        if(o.entry<exit && entry<o.exit){
            double yov=std::min(ny1,oy1)-std::max(ny0,oy0);
            if(yov>1e-9 && (std::fabs(nx1-ox0)<1e-9||std::fabs(ox1-nx0)<1e-9)) c_sp+=yov;
            double xov=std::min(nx1,ox1)-std::max(nx0,ox0);
            if(xov>1e-9 && (std::fabs(ny1-oy0)<1e-9||std::fabs(oy1-ny0)<1e-9)) c_sp+=xov;
        }
        if(std::fabs(o.exit-entry)<1e-9 || std::fabs(o.entry-exit)<1e-9){
            double aov=(std::min(nx1,ox1)-std::max(nx0,ox0))*(std::min(ny1,oy1)-std::max(ny0,oy0));
            if(aov>1e-9) c_tm+=aov;
        }
    }
    double scale=1.0/std::max(1.0,std::min(bw,bh));
    return c_sp + c_tm*scale;
}

// full-scan best placement for one block.  orient_layers[oi] = base (origin)
// layers; orient_bbox[oi] = (lx0,ly0,lx1,ly1).  Returns
// (ok, bay, oi, x, y, entry, exit).  Scans entry_times (sorted) x bays (pref
// order) x orient x grid(step); key = (tard, pref_pen, load, -contact, y, x, entry).
py::tuple st_best(std::vector<std::vector<py::array_t<double>>> orient_layers,
                  std::vector<std::vector<double>> orient_bbox,
                  int release, int pt, double due, std::vector<double> prefs,
                  double w1, double w3, std::vector<double> cur_load, double wl,
                  std::vector<int> entry_times, int step){
    int n_orients=orient_layers.size();
    int n_bays=g_bayw.size();
    double mp=*std::max_element(prefs.begin(),prefs.end());
    // convert numpy base layers -> C++ Poly ONCE (not per candidate)
    std::vector<std::vector<Poly>> base_layers(n_orients);
    for(int oi=0;oi<n_orients;oi++){
        base_layers[oi].resize(orient_layers[oi].size());
        for(size_t k=0;k<orient_layers[oi].size();k++){
            auto a=orient_layers[oi][k].unchecked<2>();
            base_layers[oi][k].reserve(a.shape(0));
            for(py::ssize_t i=0;i<a.shape(0);i++) base_layers[oi][k].emplace_back(a(i,0),a(i,1));
        }
    }
    // bay order by pref desc
    std::vector<int> bay_order(n_bays);
    for(int i=0;i<n_bays;i++) bay_order[i]=i;
    std::sort(bay_order.begin(),bay_order.end(),[&](int a,int b){return prefs[a]>prefs[b];});

    bool have=false;
    double bk_tard=0,bk_pref=0,bk_load=0,bk_negc=0,bk_y=0,bk_x=0; int bk_en=0;
    int r_bay=-1,r_oi=0,r_x=0,r_y=0,r_en=0,r_ex=0;
    std::vector<int> near;

    for(int entry_t : entry_times){
        if(have && (double)(entry_t+pt)-due > bk_tard+1e-9) break;
        int exit_t=entry_t+pt;
        double tard=std::max(0.0,(double)exit_t-due);
        for(int bay : bay_order){
            double pref_pen=mp-prefs[bay];
            if(have && (tard>bk_tard+1e-9 || (std::fabs(tard-bk_tard)<1e-9 && pref_pen>bk_pref+1e-9))) break;
            double bw=g_bayw[bay], bh=g_bayh[bay];
            double load_metric=g_bayunit[bay]*(cur_load[bay]+wl);
            for(int oi=0;oi<n_orients;oi++){
                double lx0=orient_bbox[oi][0],ly0=orient_bbox[oi][1],lx1=orient_bbox[oi][2],ly1=orient_bbox[oi][3];
                if(lx1-lx0>bw+1e-9 || ly1-ly0>bh+1e-9) continue;
                int xlo=(int)std::ceil(-lx0), xhi=(int)std::floor(bw-lx1);
                int ylo=(int)std::ceil(-ly0), yhi=(int)std::floor(bh-ly1);
                for(int y=ylo;y<=yhi;y+=step){
                    for(int x=xlo;x<=xhi;x+=step){
                        // primary-key prune (tard,pref,load) before feasibility+contact
                        if(have){
                            if(tard>bk_tard+1e-9) {}
                            if(std::fabs(tard-bk_tard)<1e-9 && std::fabs(pref_pen-bk_pref)<1e-9
                               && load_metric>bk_load+1e-9) continue;
                            if(std::fabs(tard-bk_tard)<1e-9 && pref_pen>bk_pref+1e-9) continue;
                        }
                        double nx0=lx0+x, ny0=ly0+y, nx1=lx1+x, ny1=ly1+y;
                        _gather(bay,nx0,ny0,nx1,ny1,1,near);
                        if(!st_feasible_fast(base_layers[oi],(double)x,(double)y,nx0,ny0,nx1,ny1,entry_t,exit_t,bay,near)) continue;
                        double contact=st_contact(nx0,ny0,nx1,ny1,entry_t,exit_t,bay,near);
                        double negc=-contact;
                        // lexicographic (tard,pref,load,-contact,y,x,entry)
                        bool better;
                        if(!have) better=true;
                        else {
                            double a[7]={tard,pref_pen,load_metric,negc,(double)y,(double)x,(double)entry_t};
                            double b[7]={bk_tard,bk_pref,bk_load,bk_negc,bk_y,bk_x,(double)bk_en};
                            better=false;
                            for(int i=0;i<7;i++){ if(a[i]<b[i]-1e-9){better=true;break;} if(a[i]>b[i]+1e-9){break;} }
                        }
                        if(better){
                            have=true;
                            bk_tard=tard;bk_pref=pref_pen;bk_load=load_metric;bk_negc=negc;
                            bk_y=y;bk_x=x;bk_en=entry_t;
                            r_bay=bay;r_oi=oi;r_x=x;r_y=y;r_en=entry_t;r_ex=exit_t;
                        }
                    }
                }
            }
        }
        if(have && bk_tard<1e-9 && bk_pref<1e-9) break;
    }
    if(!have) return py::make_tuple(false,0,0,0,0,0,0);
    return py::make_tuple(true,r_bay,r_oi,r_x,r_y,r_en,r_ex);
}

PYBIND11_MODULE(st3dtcs,m){
    m.def("st_init",&st_init);
    m.def("st_clear",&st_clear);
    m.def("st_add",&st_add);
    m.def("st_best",&st_best);
}

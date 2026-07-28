// C++ State: 블록 로컬레이어 등록 + timeline 관리 + placement_feasible fast
#include <pybind11/pybind11.h>
#include <pybind11/numpy.h>
#include <pybind11/stl.h>
#include <cmath>
#include <vector>
#include <unordered_map>
#include <algorithm>
namespace py = pybind11;

static const double EPS = 1e-9;
static inline double orient(double ax,double ay,double bx,double by,double px,double py){
    return (bx-ax)*(py-ay)-(by-ay)*(px-ax);
}
static inline bool on_seg(double ax,double ay,double bx,double by,double px,double py){
    if(px<std::min(ax,bx)-EPS||px>std::max(ax,bx)+EPS) return false;
    if(py<std::min(ay,by)-EPS||py>std::max(ay,by)+EPS) return false;
    return true;
}
static inline bool proper_cross(double ax,double ay,double bx,double by,double cx,double cy,double dx,double dy){
    double d1=orient(cx,cy,dx,dy,ax,ay),d2=orient(cx,cy,dx,dy,bx,by);
    double d3=orient(ax,ay,bx,by,cx,cy),d4=orient(ax,ay,bx,by,dx,dy);
    // No epsilon deadzone -- the grader allows none (`inter.area > 0`).  See the TOUCH note
    // in ogc_fast.cpp for the grazing case an EPS band was hiding.
    return (((d1>0&&d2<0)||(d1<0&&d2>0))&&((d3>0&&d4<0)||(d3<0&&d4>0)));
}
// poly given as flat ptr with n points, plus offset (ox,oy)
static bool pip(double px,double py,const double* poly,int n,double ox,double oy){
    for(int i=0;i<n;i++){
        double ax=poly[2*i]+ox,ay=poly[2*i+1]+oy; int ni=(i+1)%n;
        double bx=poly[2*ni]+ox,by=poly[2*ni+1]+oy;
        double o=orient(ax,ay,bx,by,px,py);
        // boundary counts as INSIDE; the old early return also skipped the ray cast below
        if(o==0.0&&on_seg(ax,ay,bx,by,px,py)) return true;
    }
    bool inside=false;int j=n-1;
    for(int i=0;i<n;i++){
        double yi=poly[2*i+1]+oy,yj=poly[2*j+1]+oy,xi=poly[2*i]+ox,xj=poly[2*j]+ox;
        if((yi>py)!=(yj>py)){double xint=(xj-xi)*(py-yi)/(yj-yi)+xi; if(px<xint)inside=!inside;}
        j=i;
    }
    return inside;
}
// classify two layers given as flat ptrs + offsets. 0/1/2
static int classify(const double* A,int na,double aox,double aoy,
                    const double* B,int nb,double box,double boy){
    if(na<3||nb<3) return 2;
    double axmin=A[0]+aox,axmax=axmin,aymin=A[1]+aoy,aymax=aymin;
    for(int i=1;i<na;i++){double x=A[2*i]+aox,y=A[2*i+1]+aoy;
        if(x<axmin)axmin=x;if(x>axmax)axmax=x;if(y<aymin)aymin=y;if(y>aymax)aymax=y;}
    double bxmin=B[0]+box,bxmax=bxmin,bymin=B[1]+boy,bymax=bymin;
    for(int i=1;i<nb;i++){double x=B[2*i]+box,y=B[2*i+1]+boy;
        if(x<bxmin)bxmin=x;if(x>bxmax)bxmax=x;if(y<bymin)bymin=y;if(y>bymax)bymax=y;}
    if(!(axmin<bxmax&&bxmin<axmax&&aymin<bymax&&bymin<aymax)) return 2;
    for(int i=0;i<na;i++){
        double ax=A[2*i]+aox,ay=A[2*i+1]+aoy; int ni=(i+1)%na;
        double bx=A[2*ni]+aox,by=A[2*ni+1]+aoy;
        for(int k=0;k<nb;k++){
            double cx=B[2*k]+box,cy=B[2*k+1]+boy; int nk=(k+1)%nb;
            double dx=B[2*nk]+box,dy=B[2*nk+1]+boy;
            if(proper_cross(ax,ay,bx,by,cx,cy,dx,dy)) return 1;
        }
    }
    for(int i=0;i<na;i++) if(pip(A[2*i]+aox,A[2*i+1]+aoy,B,nb,box,boy)) return 1;
    for(int k=0;k<nb;k++) if(pip(B[2*k]+box,B[2*k+1]+boy,A,na,aox,aoy)) return 1;
    return 0;
}

// 블록 형상: orient별 레이어들 (로컬좌표, 원점기준)
struct LayerData { std::vector<double> pts; int npts; };
struct OrientData { std::vector<LayerData> layers; };
struct BlockShape { std::vector<OrientData> orients; };

struct TimelineEntry {
    int en, ex;        // entry, exit time
    int block_id;
    int orient;
    double ox, oy;     // offset (x,y)
    double bx0,by0,bx1,by1;  // bbox (world)
};

struct CppState {
    std::vector<BlockShape> shapes;   // per block id
    std::vector<std::vector<TimelineEntry>> timeline;  // per bay
    int n_bays;

    void init(int nbays){ n_bays=nbays; timeline.assign(nbays,{}); }

    void register_block(int bid, py::list orients_layers){
        if((int)shapes.size()<=bid) shapes.resize(bid+1);
        BlockShape bs;
        for(auto o : orients_layers){
            OrientData od;
            for(auto layer : o.cast<py::list>()){
                auto arr=layer.cast<py::array_t<double,py::array::c_style|py::array::forcecast>>();
                LayerData ld; ld.npts=(int)arr.shape(0);
                const double* p=arr.data();
                ld.pts.assign(p, p+2*ld.npts);
                od.layers.push_back(std::move(ld));
            }
            bs.orients.push_back(std::move(od));
        }
        shapes[bid]=std::move(bs);
    }

    void add(int bay,int bid,int orient,double ox,double oy,int en,int ex,
             double bx0,double by0,double bx1,double by1){
        timeline[bay].push_back({en,ex,bid,orient,ox,oy,bx0,by0,bx1,by1});
    }
    void remove(int bay,int bid){
        auto& tl=timeline[bay];
        for(size_t i=0;i<tl.size();i++) if(tl[i].block_id==bid){ tl.erase(tl.begin()+i); break; }
    }
    void clear_bay(int bay){ timeline[bay].clear(); }

    static inline bool bb_ov(double a0,double a1,double a2,double a3,double b0,double b1,double b2,double b3){
        return !(a2<=b0||b2<=a0||a3<=b1||b3<=a1);
    }

    // check_entry fast: new block (bid,orient,ox,oy) at time -> 활성블록과 충돌?
    // 반환: [status, amb_k1,amb_eid1,amb_ej1, ...]  status=1 막힘(확실), 0=계속(애매목록)
    // 활성: en<=entry_t<ex 인 timeline 블록
    py::array_t<int> check_entry_fast(int bay,int bid,int orient,double nox,double noy,
                                       double nbx0,double nby0,double nbx1,double nby1,int entry_t){
        const OrientData& nod = shapes[bid].orients[orient];
        int n_new=(int)nod.layers.size();
        std::vector<int> amb;
        for(auto& te : timeline[bay]){
            if(!(te.en<=entry_t && entry_t<te.ex)) continue;
            if(!bb_ov(nbx0,nby0,nbx1,nby1,te.bx0,te.by0,te.bx1,te.by1)) continue;
            const OrientData& eod = shapes[te.block_id].orients[te.orient];
            int n_ex=(int)eod.layers.size();
            for(int k=0;k<n_new;k++){
                const LayerData& AL=nod.layers[k];
                if(AL.npts<3) continue;
                for(int j=k;j<n_ex;j++){
                    const LayerData& BL=eod.layers[j];
                    if(BL.npts<3) continue;
                    int c=classify(AL.pts.data(),AL.npts,nox,noy, BL.pts.data(),BL.npts,te.ox,te.oy);
                    if(c==1){
                        auto r=py::array_t<int>(4); int* rp=r.mutable_data();
                        rp[0]=1; rp[1]=k; rp[2]=te.block_id; rp[3]=j; return r;
                    }
                    if(c==0){ amb.push_back(k); amb.push_back(te.block_id); amb.push_back(j); }
                }
            }
        }
        auto r=py::array_t<int>(1+(int)amb.size()); int* rp=r.mutable_data();
        rp[0]=0; for(size_t i=0;i<amb.size();i++) rp[1+i]=amb[i];
        return r;
    }

    // check_exit fast: blk(나가는 새블록) at exit_t -> 막힘?
    // 대상: en < exit_t <= ex 인 활성블록 (strict_lower OR ex==exit_t)
    py::array_t<int> check_exit_fast(int bay,int bid,int orient,double nox,double noy,
                                      double nbx0,double nby0,double nbx1,double nby1,int exit_t){
        const OrientData& nod = shapes[bid].orients[orient];
        int n_new=(int)nod.layers.size();
        std::vector<int> amb;
        for(auto& te : timeline[bay]){
            if(!(te.en < exit_t && exit_t <= te.ex)) continue;
            if(te.block_id==bid) continue;
            if(!bb_ov(nbx0,nby0,nbx1,nby1,te.bx0,te.by0,te.bx1,te.by1)) continue;
            const OrientData& eod = shapes[te.block_id].orients[te.orient];
            int n_ex=(int)eod.layers.size();
            for(int k=0;k<n_new;k++){
                const LayerData& AL=nod.layers[k];
                if(AL.npts<3) continue;
                for(int j=k;j<n_ex;j++){
                    const LayerData& BL=eod.layers[j];
                    if(BL.npts<3) continue;
                    int c=classify(AL.pts.data(),AL.npts,nox,noy, BL.pts.data(),BL.npts,te.ox,te.oy);
                    if(c==1){
                        auto r=py::array_t<int>(4); int* rp=r.mutable_data();
                        rp[0]=1; rp[1]=k; rp[2]=te.block_id; rp[3]=j; return r;
                    }
                    if(c==0){ amb.push_back(k); amb.push_back(te.block_id); amb.push_back(j); }
                }
            }
        }
        auto r=py::array_t<int>(1+(int)amb.size()); int* rp=r.mutable_data();
        rp[0]=0; for(size_t i=0;i<amb.size();i++) rp[1+i]=amb[i];
        return r;
    }

    // helper: blk(레이어 등록됨) at (nox,noy) vs other(te2) classify (fast). 막힘이면 amb 채우고 true/false
    // returns: 0 = 안막힘(애매목록 amb뒤), 1 = 확실막힘
    int classify_pair_blocks(int bid_a,int or_a,double aox,double aoy,
                             int bid_b,int or_b,double box,double boy,
                             std::vector<int>& amb, int amb_tag){
        const OrientData& A=shapes[bid_a].orients[or_a];
        const OrientData& B=shapes[bid_b].orients[or_b];
        int na=(int)A.layers.size(), nb=(int)B.layers.size();
        for(int k=0;k<na;k++){
            if(A.layers[k].npts<3) continue;
            for(int j=k;j<nb;j++){
                if(B.layers[j].npts<3) continue;
                int c=classify(A.layers[k].pts.data(),A.layers[k].npts,aox,aoy,
                               B.layers[j].pts.data(),B.layers[j].npts,box,boy);
                if(c==1) return 1;
                if(c==0){ amb.push_back(amb_tag); amb.push_back(k); amb.push_back(j); }
            }
        }
        return 0;
    }

    // _placement_feasible 3번: blk이 추가됐을때 시간겹침 other들이 막히나.
    // blk: bid,orient,nox,noy,bbox,blk_a,blk_e (아직 timeline에 없음)
    // 반환 형식: [status, then ambiguous triples...]
    //   status=1: 확실 막힘. status=0: 막힘없음(단 애매쌍은 Python이 shapely 확인 필요)
    //   애매쌍 인코딩: (encoded, a, b) 복잡 -> 단순화: 애매있으면 Python에 "재검사 필요" 신호
    // 여기선 fast 확실판정만 C++. 애매(c==0)가 하나라도 있으면 -2 반환 -> Python 폴백.
    int check_others_blocked(int bay,int bid,int orient,double nox,double noy,
                             double nbx0,double nby0,double nbx1,double nby1,
                             int blk_a,int blk_e){
        bool has_amb=false;
        for(auto& te : timeline[bay]){
            int en=te.en, ex=te.ex;
            if(!(blk_a < ex && en < blk_e)) continue;
            if(!bb_ov(nbx0,nby0,nbx1,nby1,te.bx0,te.by0,te.bx1,te.by1)) continue;
            int oid=te.block_id;
            (void)oid;
            // case1: blk_a <= en < blk_e -> other entry시 blk이 막나
            //   대상: present_at(en, strict_lower=False) + blk. other vs 그들.
            //   여기선 "other vs blk"만 확실검사 (다른 활성블록과 other관계는 원래 배치때 검증됨)
            //   즉 blk 추가로 새로 생기는 충돌 = other vs blk
            if(blk_a <= en && en < blk_e){
                std::vector<int> amb;
                int r=classify_pair_blocks(te.block_id,te.orient,te.ox,te.oy,
                                           bid,orient,nox,noy, amb, 0);
                if(r==1) return 1;
                if(!amb.empty()) has_amb=true;
            }
            if(blk_a <= ex && ex < blk_e){
                std::vector<int> amb;
                int r=classify_pair_blocks(te.block_id,te.orient,te.ox,te.oy,
                                           bid,orient,nox,noy, amb, 1);
                if(r==1) return 1;
                if(!amb.empty()) has_amb=true;
            }
            if(ex == blk_e){
                std::vector<int> amb;
                int r=classify_pair_blocks(te.block_id,te.orient,te.ox,te.oy,
                                           bid,orient,nox,noy, amb, 2);
                if(r==1) return 1;
                if(!amb.empty()) has_amb=true;
            }
        }
        return has_amb ? -2 : 0;  // -2: Python 폴백 필요
    }

    // 블록 bid+orient at offset(ox,oy)의 bbox (모든 레이어 포함)
    std::vector<double> compute_bbox(int bid,int orient,double ox,double oy){
        const OrientData& od=shapes[bid].orients[orient];
        double xmin=1e18,ymin=1e18,xmax=-1e18,ymax=-1e18;
        for(auto& L:od.layers){
            for(int i=0;i<L.npts;i++){
                double x=L.pts[2*i]+ox, y=L.pts[2*i+1]+oy;
                if(x<xmin)xmin=x; if(x>xmax)xmax=x;
                if(y<ymin)ymin=y; if(y>ymax)ymax=y;
            }
        }
        return {xmin,ymin,xmax,ymax};
    }

    // timeline 전체를 직렬화해서 반환 (clone용). [bay, en,ex,bid,orient,ox,oy,bx0,by0,bx1,by1] flat
    py::array_t<double> dump_timeline(){
        std::vector<double> out;
        for(int b=0;b<n_bays;b++)
            for(auto& t:timeline[b]){
                out.push_back(b); out.push_back(t.en); out.push_back(t.ex);
                out.push_back(t.block_id); out.push_back(t.orient);
                out.push_back(t.ox); out.push_back(t.oy);
                out.push_back(t.bx0); out.push_back(t.by0); out.push_back(t.bx1); out.push_back(t.by1);
            }
        auto r=py::array_t<double>(out.size());
        std::copy(out.begin(),out.end(),r.mutable_data());
        return r;
    }
    // timeline 통째 교체 (clone용)
    void load_timeline(py::array_t<double,py::array::c_style|py::array::forcecast> arr){
        for(int b=0;b<n_bays;b++) timeline[b].clear();
        const double* d=arr.data(); int m=(int)arr.shape(0);
        for(int i=0;i<m;i+=11){
            int b=(int)d[i];
            timeline[b].push_back({(int)d[i+1],(int)d[i+2],(int)d[i+3],(int)d[i+4],
                                   d[i+5],d[i+6],d[i+7],d[i+8],d[i+9],d[i+10]});
        }
    }
    // shapes 공유하는 새 CppState 만들기 위해 shapes 복사
    void copy_shapes_from(CppState& other){ shapes=other.shapes; }
};

PYBIND11_MODULE(ogc_state, m){
    py::class_<CppState>(m,"CppState")
        .def(py::init<>())
        .def("init",&CppState::init)
        .def("register_block",&CppState::register_block)
        .def("add",&CppState::add)
        .def("remove",&CppState::remove)
        .def("clear_bay",&CppState::clear_bay)
        .def("check_entry_fast",&CppState::check_entry_fast)
        .def("check_exit_fast",&CppState::check_exit_fast)
        .def("check_others_blocked",&CppState::check_others_blocked)
        .def("compute_bbox",&CppState::compute_bbox)
        .def("dump_timeline",&CppState::dump_timeline)
        .def("load_timeline",&CppState::load_timeline)
        .def("copy_shapes_from",&CppState::copy_shapes_from);
}

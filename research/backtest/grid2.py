import itertools, warnings; warnings.filterwarnings('ignore')
from fast import *
Ls=[(0.1,0.3,0.6),(0.15,0.4,0.8),(0.2,0.5,1.0),(0.1,0.4,1.0),(0.25,0.6,1.2),(0.15,0.3,0.6)]
Fs=[(.5,1,1),(1,1,1),(.5,.5,1),(1/3,.5,1)]
res=[]
for z0,L,F,reset,alloc,stale in itertools.product([0.3,0.4,0.6,0.8],Ls,Fs,[0.01,0.05],['all','blend'],[0,12,24]):
    p=dict(z0=z0,L=L,F=F,tilt=1,reset=reset,alloc=alloc,stale=stale)
    a=run('2006-01-02','2016-01-01','x',p); b=run('2016-01-04','2026-11-20','x',p)
    res.append(dict(z0=z0,L=str(L),F=str(tuple(round(f,2) for f in F)),reset=reset,alloc=alloc,stale=stale,A=a['irr'],B=b['irr'],cashA=a['cash'],cashB=b['cash']))
R=pd.DataFrame(res); R.to_pickle('grid2.pkl'); print(len(R))

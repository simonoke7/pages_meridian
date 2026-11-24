import itertools, warnings; warnings.filterwarnings('ignore')
from fast import *
Ls=[(0.02,0.1,0.3),(0.05,0.2,0.5),(0.1,0.3,0.6),(0.03,0.15,0.4),(0.01,0.05,0.15)]
Fs=[(1/3,.5,1),(.5,.5,1),(.25,1/3,1),(1,1,1),(.5,1,1)]
res=[]
for z0,L,F,tilt,reset,idio in itertools.product([0,0.2,0.4],Ls,Fs,[0,1,2],[0.0,0.01],[0,0.5]):
    p=dict(z0=z0,L=L,F=F,tilt=tilt,reset=reset,idio=idio,zi=-1.4)
    a=run('2006-01-02','2016-01-01','x',p); b=run('2016-01-04','2026-11-20','x',p)
    res.append(dict(z0=z0,L=str(L),F=str(tuple(round(f,2) for f in F)),tilt=tilt,reset=reset,idio=idio,A=a['irr'],B=b['irr'],cashA=a['cash'],cashB=b['cash']))
R=pd.DataFrame(res); R.to_pickle('grid.pkl'); print(len(R))

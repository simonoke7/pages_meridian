import numpy as np, pandas as pd
from sim import PX,Z,VER,AVAIL,r_cash,idx,NAMES,W,STAB
K=list(NAMES); px=PX[K].values; z=Z[K].values; av=AVAIL[K].values; rc=r_cash.values
w=np.array([W[k] for k in K]); dates=idx
fri=(dates.dayofweek==4); newm=np.r_[True, dates.month[1:]!=dates.month[:-1]]
ver=VER[K].values
STABv=STAB[K].values
def run(start,end,mode,p):
    p=dict(p); p['_lastdep']=[np.searchsorted(dates,pd.Timestamp(start))]
    i0=np.searchsorted(dates,pd.Timestamp(start)); i1=np.searchsorted(dates,pd.Timestamp(end))
    units=np.zeros(len(K)); cash=0.; contrib=0.; lvl=0; dmax=0; flows=[]; W_=[];C_=[]; nd=0
    sleeve=np.zeros(len(K)); last=np.full(len(K),-999)
    for i in range(i0,i1):
        cash*=1+rc[i]; sleeve*=1+rc[i]
        if newm[i] or i==i0:
            cash+=1000; contrib+=1000; flows.append((i,1000))
            a=av[i]
            if a.any(): sleeve[a]+=1000*w[a]/w[a].sum()
        a=av[i]
        if not a.any(): W_.append(cash); C_.append(cash); continue
        if mode=='ref':
            if cash>1:
                buy=cash*w*a/(w*a).sum(); units+=buy/np.where(a,px[i],1); cash=0; nd+=1
        elif fri[i]:
            zz=np.where(a,z[i],0); buy=np.zeros(len(K))
            if mode=='curfix':
                br=((zz<=-0.8)&a).sum()/a.sum()
                for j in np.where(a)[0]:
                    if i-last[j]<15: continue
                    if zz[j]<=p['deep'] and br>=p['br']: buy[j]=sleeve[j]; last[j]=i
                    elif zz[j]<=p['buy'] and br>=p['br']: buy[j]=p['bf']*sleeve[j]; last[j]=i
            elif mode=='current':
                for j in np.where(a)[0]:
                    if i-last[j]<15: continue
                    if ver[i,j]=='DEEP BUY': buy[j]=sleeve[j]; last[j]=i
                    elif ver[i,j]=='BUY': buy[j]=.5*sleeve[j]; last[j]=i
            else:
                depth=np.maximum(0,-zz-p['z0'])
                D=(w*depth*a).sum()/(w*a).sum()           # weighted sigma-depth beyond z0
                if D<p['reset']: lvl=0
                frac=0
                if p.get('stay') is not None and lvl>0 and D>=p['L'][0]*p['stay'] and cash>1: frac=1.0
                while lvl<len(p['L']) and D>=p['L'][lvl]:
                    frac=1-(1-frac)*(1-p['F'][lvl]); lvl+=1
                if frac>0 and p.get('confirm',0):
                    st_ok=((STABv[i]>=1)&a).sum()/a.sum()
                    if st_ok<p['confirm']: lvl-=1; frac=0
                if frac>0:
                    al=p.get('alloc','all')
                    if al=='all': sc=w*a
                    elif al=='dip': sc=w*depth**p['tilt']*a*(depth>0)
                    else:  # blend: half target weights, half tilted to dippers
                        s1=w*a/(w*a).sum(); d2=w*depth**p['tilt']*a*(depth>0)
                        sc=s1+ (d2/d2.sum() if d2.sum()>0 else s1)
                    if sc.sum()>0: buy=frac*cash*sc/sc.sum()
                # idiosyncratic rule: single deep fund dip while portfolio calm
                if p.get('idio',0)>0 and frac==0:
                    for j in np.where(a&(zz<=p['zi']))[0]:
                        if i-last[j]>p.get('icool',63): buy[j]+=p['idio']*sleeve[j]; last[j]=i
                if p.get('stale',0) and frac==0 and i-p.setdefault('_lastdep',[i0])[0]>p['stale']*21 and cash>1:
                    buy=cash*w*a/(w*a).sum()
                if buy.sum()>1: p.setdefault('_lastdep',[i0])[0]=i
                # stale-cash rule: if cash > cap share of wealth, release
            tb=buy.sum()
            if tb>cash: buy*=cash/tb
            if buy.sum()>1:
                units+=buy/np.where(a,px[i],1); cash-=buy.sum(); nd+=1
                sleeve=np.maximum(0,sleeve-buy)
            s=sleeve.sum(); 
            if s>0: sleeve*=cash/s
        inv=(units*np.nan_to_num(px[i])).sum(); W_.append(inv+cash); C_.append(cash)
    W_=np.array(W_); C_=np.array(C_)
    # IRR monthly
    fi=np.array([f[0]-i0 for f in flows]); n=len(W_)
    def npv(r): return -sum(1000/(1+r)**((f)/252) for f in fi)+W_[-1]/(1+r)**(n/252)
    lo,hi=-0.5,1.0
    for _ in range(60):
        m=(lo+hi)/2; lo,hi=(m,hi) if npv(m)>0 else (lo,m)
    Wp=W_[W_>0]; dd=(Wp/np.maximum.accumulate(Wp)-1).min()
    return dict(irr=m*100, x=W_[-1]/contrib, cash=np.nanmean(C_/np.where(W_>0,W_,np.nan))*100, dd=dd*100, n=nd)

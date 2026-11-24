import pandas as pd, numpy as np
def features(s):
    """Daily port of generateRecommendation() signals for one price series s (daily, trading days)."""
    f=pd.DataFrame(index=s.index); f['px']=s
    me=s.resample('ME').last()                       # month-end closes
    prev_me=me.shift(1).reindex(s.index,method='ffill')  # last completed month-end before current month
    cur_me=me.reindex(s.index,method='ffill')
    # month-end close of the previous month relative to date t:
    pm=s.groupby(s.index.to_period('M')).transform('first')*0  # placeholder
    mon=s.index.to_period('M')
    me_by_p=me.copy(); me_by_p.index=me_by_p.index.to_period('M')
    f['prev_me']=me_by_p.reindex(mon-1).values
    # 18M peak: max of last 19 month-ends (incl. completed ones) and last 252 daily
    roll19=me.rolling(19,min_periods=1).max(); roll19.index=roll19.index.to_period('M')
    f['pk_m']=roll19.reindex(mon-1).values
    f['pk_d']=s.rolling(252,min_periods=60).max()
    f['peak']=np.fmax(f.pk_m,f.pk_d)
    f['dd']=(s/f.peak-1)*100
    r=s.pct_change().clip(-.05,.05)
    f['vol']=r.rolling(252,min_periods=63).std(ddof=0)*np.sqrt(252)*100
    f['rvol']=r.rolling(21).std(ddof=0)*np.sqrt(252)*100
    f['roc21']=s/s.shift(21)-1; f['roc63']=s/s.shift(63)-1
    f['floor63']=s.shift(1).rolling(63).min()
    f['s1']=s>f.prev_me; f['s2']=f.roc21>f.roc63; f['s3']=s>f.floor63; f['s4']=f.rvol<f.vol
    f['stab']=f[['s1','s2','s3','s4']].sum(axis=1)
    f['ret5']=((s/s.shift(1260))**(1/5)-1)*100
    # y10 trend: last > value at midpoint of trailing 10y monthly window (use available history, >=20 months)
    n=np.arange(len(s)); 
    look=np.minimum(n,2520)//2
    f['y10pos']=np.where(n>=420, s.values > s.values[n-look], np.nan)
    f['peak3']=s.rolling(64).max(); f['dd3']=(s/f.peak3-1)*100
    f['acute']=(f.dd3/f.dd.replace(0,np.nan))
    f['ath']=s.cummax(); f['dd_ath']=(s/f.ath-1)*100
    return f
def current_verdict(f):
    v=f.vol
    build=-np.clip(.4*v,3,10); buy=-np.clip(.8*v,7,22); deep=-np.clip(1.4*v,14,35)
    dd=f.dd.round(1)
    isDeep=dd<=build.round(1)*0+deep.round(1); isMean=dd<=buy.round(1); isMild=dd<=build.round(1)
    nff=f.stab>=1
    q=f.ret5; poor=q<0; weak=q<4; strong=q>=8   # NaN -> False (no gate)
    y10=(f.y10pos==1)|f.y10pos.isna()
    deepbuy=isDeep&nff&~poor&~weak&y10
    buyv=~deepbuy&nff&~poor&~weak&(isMean|(isMild&strong))
    buildv=~deepbuy&~buyv&isMild&~isMean&nff&~poor&~weak
    out=pd.Series('HOLD',index=f.index)
    out[buildv]='BUILD'; out[buyv]='BUY'; out[deepbuy]='DEEP BUY'
    out[f.vol.isna()]=np.nan
    return out

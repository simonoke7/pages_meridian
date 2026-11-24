from data import *; from engine import *
P=proxies(); irx=cash()
idx=pd.bdate_range('2005-01-03','2026-11-20')
PX=pd.DataFrame({k:P[k] for k in NAMES}).reindex(idx).ffill()
F={k:features(P[k]) for k in NAMES}
Z=pd.DataFrame({k:(F[k].dd/F[k].vol) for k in NAMES}).reindex(idx).ffill()
VER=pd.DataFrame({k:current_verdict(F[k]) for k in NAMES}).reindex(idx).ffill()
STAB=pd.DataFrame({k:F[k].stab for k in NAMES}).reindex(idx).ffill()
AVAIL=pd.DataFrame({k:F[k].vol.notna() for k in NAMES}).reindex(idx).fillna(False).astype(bool)
r_cash=(irx.reindex(idx).ffill().fillna(0)/252)
START='2006-01-02'; SAV=1000.0
def run(policy, start=START, end='2026-11-20', **kw):
    dates=idx[(idx>=start)&(idx<=end)]
    units={k:0.0 for k in NAMES}; cash=0.0; sleeves={k:0.0 for k in NAMES}
    state={'last':{k:pd.Timestamp('1900-01-01') for k in NAMES},'armed':{k:0 for k in NAMES}}
    contrib=0; hist=[]; ndeploy=0; lastm=None
    for t in dates:
        cash*= (1+r_cash.at[t]); 
        for k in NAMES: sleeves[k]*=(1+r_cash.at[t])
        if t.month!=lastm:   # monthly savings
            lastm=t.month; cash+=SAV; contrib+=SAV
            av=[k for k in NAMES if AVAIL.at[t,k]]; w=sum(W[k] for k in av)
            for k in av: sleeves[k]+=SAV*W[k]/w
            # funds not yet available: their share stays in pooled cash via sleeves of avail funds
        if t.dayofweek==4 or policy.__name__=='ref':
            buys=policy(t,cash,sleeves,state,**kw)   # dict fund->GBP
            for k,amt in buys.items():
                amt=min(amt,cash)
                if amt<=1: continue
                units[k]+=amt/PX.at[t,k]; cash-=amt; ndeploy+=1
                sleeves[k]=max(0.0,sleeves[k]-amt)
            # keep sleeves consistent with pooled cash
            tot=sum(sleeves.values())
            if tot>0: 
                for k in sleeves: sleeves[k]*=cash/tot
        inv=sum(units[k]*PX.at[t,k] for k in NAMES if units[k])
        hist.append((t,inv+cash,cash,contrib))
    h=pd.DataFrame(hist,columns=['t','wealth','cash','contrib']).set_index('t')
    return h, ndeploy
def irr(h):
    # monthly cash flows
    m=h.resample('ME').last(); cf=-m.contrib.diff().fillna(m.contrib.iloc[0]); cf.iloc[-1]+=m.wealth.iloc[-1]
    lo,hi=-0.5,1.0
    for _ in range(100):
        mid=(lo+hi)/2; npv=sum(c/(1+mid)**(i/12) for i,c in enumerate(cf.values))
        lo,hi=(mid,hi) if npv>0 else (lo,mid)
    return mid
def summary(name,h,n):
    w=h.wealth; dd=(w/w.cummax()-1).min()
    return dict(strategy=name, final_x=round(w.iloc[-1]/h.contrib.iloc[-1],3), irr=round(irr(h)*100,2),
                avg_cash_pct=round((h.cash/h.wealth).mean()*100,1), max_dd=round(dd*100,1), deploys=n)

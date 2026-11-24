from sim import *
def ref(t,cash,sl,st):            # reference: deploy on arrival at target weights
    av=[k for k in NAMES if AVAIL.at[t,k]]; w=sum(W[k] for k in av)
    return {k:cash*W[k]/w for k in av} if cash>1 else {}
def current(t,cash,sl,st,cool=20):
    out={}
    for k in NAMES:
        if not AVAIL.at[t,k] or (t-st['last'][k]).days<cool: continue
        v=VER.at[t,k]
        if v=='DEEP BUY': out[k]=sl[k]
        elif v=='BUY': out[k]=0.5*sl[k]
        if k in out: st['last'][k]=t
    return out
def ladder(t,cash,sl,st,tiers=((-0.4,1/3),(-0.8,0.5),(-1.4,1.0)),reset=-0.1,gate_stab=0):
    """per-fund depth ladder: each tier fires once per drawdown cycle; re-arms when z recovers above reset"""
    out={}
    for k in NAMES:
        if not AVAIL.at[t,k]: continue
        z=Z.at[t,k]
        if z>reset: st['armed'][k]=0; continue
        lvl=st['armed'][k]
        while lvl<len(tiers) and z<=tiers[lvl][0]:
            if STAB.at[t,k]<gate_stab: break
            out[k]=out.get(k,0)+tiers[lvl][1]*(sl[k]-out.get(k,0)); lvl+=1
        st['armed'][k]=lvl
    return out
def breadth_pool(t,cash,sl,st,zdip=-0.8,tiers=((0.2,0.25),(0.35,0.5),(0.5,1.0)),idio=0.0,tilt=1.0,reset=0.1):
    """pooled cash; deploy fraction by breadth (share of funds with z<=zdip); allocate by weight*depth"""
    av=[k for k in NAMES if AVAIL.at[t,k]]
    z=Z.loc[t,av]; b=(z<=zdip).mean()
    if b<reset: st['armed']['_']=0
    lvl=st['armed'].get('_',0); frac=0; 
    while lvl<len(tiers) and b>=tiers[lvl][0]:
        frac=1-(1-frac)*(1-tiers[lvl][1]); lvl+=1
    st['armed']['_']=lvl
    out={}
    if frac>0:
        score={k:W[k]*(max(0,-z[k]))**tilt for k in av}; s=sum(score.values())
        if s>0: out={k:frac*cash*v/s for k,v in score.items() if v>0}
    elif idio>0:   # idiosyncratic dip: small tranche of that fund's sleeve
        for k in av:
            if z[k]<=-1.4 and (t-st['last'][k]).days>90: out[k]=idio*sl[k]; st['last'][k]=t
    return out

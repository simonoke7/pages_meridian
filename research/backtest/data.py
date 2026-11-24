import pandas as pd, numpy as np, json, glob
H='research/out/'
def rd(t): 
    s=pd.read_csv(H+t+'.csv',index_col=0,parse_dates=True).iloc[:,0]; s.index=s.index.tz_localize(None).normalize(); return s[~s.index.duplicated()]
fx=rd('GBPUSD_X')
def gbp(s): # USD price -> GBP
    df=pd.concat([s,fx],axis=1).dropna(); return df.iloc[:,0]/df.iloc[:,1]
def blend(parts):
    r=pd.concat([p.pct_change() for p,_ in parts],axis=1)
    w=np.array([w for _,w in parts]); out=[]
    rr=r.apply(lambda row: np.nansum(row.values*w)/w[~np.isnan(row.values)].sum() if (~np.isnan(row.values)).any() else np.nan,axis=1)
    return (1+rr.fillna(0)).cumprod()
def splice(early,late):
    s=pd.concat([early[early.index<late.index[0]].pct_change(), late.pct_change()]).dropna()
    return (1+s).cumprod()
def proxies():
    P={}
    P['GB00B59G4Q73']=gbp(blend([(rd('SPY'),.75),(rd('EFA'),.25)]))
    P['GB00B0CNH163']=gbp(rd('XLK'))
    ft=rd('IDX_FTAS'); ftr=(1+ft.pct_change()+0.035/252).cumprod()
    P['GB00BJS8SF95']=splice(ftr, rd('ISF.L'))
    P['IE00B4ND3602']=gbp(rd('GC_F'))
    P['IE00B6YX5D40']=gbp(rd('SDY'))
    P['IE00BYPLS672']=gbp(rd('HACK'))
    P['IE00B3X1NT05']=gbp(splice(rd('IWM'), blend([(rd('IWM'),.6),(rd('VSS'),.4)])[rd('VSS').index[1]:]))
    P['GB00B0CNH387']=gbp(rd('IXJ'))
    P['GB0006063233']=gbp(splice(rd('EEM'),rd('AAXJ')))
    P['GB00BPFJCF57']=gbp(splice(rd('VNQ'),rd('RWO')))
    P['IE00B1XNHC34']=gbp(splice(rd('PBW'),rd('ICLN')))
    out={}
    for k,s in P.items():
        s=s.dropna(); s=s[s.index>='2004-01-01']; s=s[s.index.dayofweek<5]
        out[k]=s/s.iloc[0]
    return out
def cash():
    irx=rd('IDX_IRX')/100; return irx
def actual_monthly():
    A={}
    for f in glob.glob('/home/claude/pages_meridian/docs/data/[GI]*.json'):
        d=json.load(open(f)); y=d['periods']['Y10']
        A[d['isin']]=pd.Series([p['value'] for p in y],index=pd.to_datetime([p['date'][:10] for p in y]))
    return A
NAMES={'GB00B59G4Q73':'World ex-UK','GB00B0CNH163':'Global Tech','GB00BJS8SF95':'UK Index','IE00B4ND3602':'Gold',
 'IE00B6YX5D40':'Div Aristocrats','IE00BYPLS672':'Cyber','IE00B3X1NT05':'Global Small-Cap','GB00B0CNH387':'Health & Pharma',
 'GB0006063233':'BG Pacific','GB00BPFJCF57':'Green Real Estate','IE00B1XNHC34':'Clean Energy'}
# target midpoints from PORTFOLIO_TARGETS (floor/ceiling)
FC={'GB00B59G4Q73':(15,25),'GB00B0CNH163':(10,25),'GB00BJS8SF95':(5,10),'IE00B4ND3602':(3,7),'IE00B6YX5D40':(2,7),
 'IE00BYPLS672':(5,15),'IE00B3X1NT05':(3,8),'GB00B0CNH387':(2,8),'GB0006063233':(4,12),'GB00BPFJCF57':(0,4),'IE00B1XNHC34':(2,8)}
W={k:(a+b)/2 for k,(a,b) in FC.items()}; tw=sum(W.values()); W={k:v/tw for k,v in W.items()}

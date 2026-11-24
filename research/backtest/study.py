from data import *; from engine import *
P=proxies(); rows=[]
for k in NAMES:
    s=P[k]; f=features(s); f['verdict']=current_verdict(f)
    for h,n in [(63,'f3'),(126,'f6'),(252,'f12')]: f[n]=(s.shift(-h)/s-1)*100
    f['fund']=NAMES[k]; f=f[f.index.dayofweek==4].dropna(subset=['vol','verdict'])
    f=f[f.index>='2006-01-01']
    for n in ['f3','f6','f12']: f[n+'x']=f[n]-f[n].mean()
    f['z']=f.dd/f.vol
    rows.append(f)
D=pd.concat(rows); D.to_pickle('D.pkl')

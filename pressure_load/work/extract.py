import pandas as pd, glob, sys, os
from multiprocessing import Pool
HERE=os.path.dirname(os.path.abspath(__file__))
D=os.path.join(HERE,'..','..','data')
def f(fn):
    t=pd.read_csv(fn,usecols=['gameId','playId','nflId','frameId','team','playDirection','x','y','s','a','o','dir','event'])
    ev=t[t.event.isin(['ball_snap','autoevent_ballsnap'])].groupby(['gameId','playId']).frameId.min().rename('snapF')
    t=t.merge(ev,on=['gameId','playId'])
    return t[t.frameId==t.snapF].drop(columns=['event'])
if __name__=='__main__':
    fs=sorted(glob.glob(D+'/tracking/*.csv'))
    with Pool(2) as p: out=pd.concat(p.map(f,fs))
    out.to_csv(os.path.join(HERE,'snap.csv'),index=False)
    print(out.shape, out[['gameId','playId']].drop_duplicates().shape)

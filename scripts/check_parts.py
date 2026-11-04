"""Check RUNDIR/translation.json against words.json: same segments, parts cover every word once, parts joined == ru.

Usage: python check_parts.py RUNDIR   (exit 0 = ok)
"""
import json,sys
R=sys.argv[1]
w=json.load(open(R+'/words.json',encoding='utf-8'));t=json.load(open(R+'/translation.json',encoding='utf-8'))
S={s['i']:s for s in w['segments']};bad=[]
assert [s['i'] for s in t['segments']]==[s['i'] for s in w['segments']], 'order/count of i'
for s in t['segments']:
    n=S[s['i']]['w1']-S[s['i']]['w0'];cov=[]
    for p in s.get('parts',[]):
        if not p.get('ru','').strip() or not (0<=p['w0']<p['w1']<=n): bad.append((s['i'],'range',p)); continue
        cov+=range(p['w0'],p['w1'])
    if sorted(cov)!=list(range(n)): bad.append((s['i'],'coverage'))
    if ' '.join(p['ru'].strip() for p in s.get('parts',[])).split()!=s['ru'].split(): bad.append((s['i'],'ru != parts joined'))
print(len(t['segments']),'segments,',len(bad),'bad'); print(bad[:10]); sys.exit(1 if bad else 0)

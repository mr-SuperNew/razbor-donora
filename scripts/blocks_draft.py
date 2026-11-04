import argparse
import json
from pathlib import Path


def main():
    p = argparse.ArgumentParser(); p.add_argument('words_json'); p.add_argument('out_json')
    p.add_argument('--min', type=float, default=20); p.add_argument('--max', type=float, default=90); p.add_argument('--gap', type=float, default=1.0)
    a = p.parse_args()
    if a.min < 0 or a.max <= 0 or a.min > a.max: p.error('require 0 <= min <= max and max > 0')
    data = json.loads(Path(a.words_json).read_text(encoding='utf-8')); words = data['words']
    segments = [s for s in data['segments'] if s['w1'] > s['w0']]
    groups = []
    for seg in segments:
        if not groups or words[seg['w0']]['t0'] - words[groups[-1][-1]['w1'] - 1]['t1'] >= a.gap: groups.append([])
        groups[-1].append(seg)
    def duration(group): return words[group[-1]['w1'] - 1]['t1'] - words[group[0]['w0']]['t0']
    while len(groups) > 1:
        idx = next((i for i, g in enumerate(groups) if duration(g) < a.min), None)
        if idx is None: break
        neighbor = 1 if idx == 0 else (idx - 1 if idx == len(groups) - 1 else
            (idx - 1 if words[groups[idx][0]['w0']]['t0'] - words[groups[idx-1][-1]['w1']-1]['t1'] <= words[groups[idx+1][0]['w0']]['t0'] - words[groups[idx][-1]['w1']-1]['t1'] else idx + 1))
        left = min(idx, neighbor); groups[left:left+2] = [groups[left] + groups[left+1]]
    i = 0
    while i < len(groups):
        g = groups[i]
        start, end = g[0]['w0'], g[-1]['w1']
        if duration(g) > a.max and end - start > 1:
            cut = max(range(start + 1, end), key=lambda j: words[j]['t0'] - words[j-1]['t1'])
            left = [dict(s, w1=min(s['w1'], cut)) for s in g if s['w0'] < cut]
            right = [dict(s, w0=max(s['w0'], cut)) for s in g if s['w1'] > cut]
            groups[i:i+1] = [left, right]
        else: i += 1
    blocks = []
    for n, g in enumerate(groups, 1):
        selected = words[g[0]['w0']:g[-1]['w1']]
        blocks.append({'n': n, 'title': f'Блок {n}', 'role': '', 't0': selected[0]['t0'], 't1': selected[-1]['t1'], 'why': '', 'text': ' '.join(w['text'] for w in selected)[:200]})
    Path(a.out_json).write_text(json.dumps({'blocks': blocks}, ensure_ascii=False, indent=2), encoding='utf-8')


if __name__ == '__main__': main()

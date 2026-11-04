import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import subprocess
import sys


def read(path): return json.loads(path.read_text(encoding='utf-8'))
def write(path, data): path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')


def main():
    p = argparse.ArgumentParser(); p.add_argument('rundir'); p.add_argument('--lead', type=float, default=.05)
    p.add_argument('--width', type=int, default=360, help='short side of frames in px: 640x360 for 16:9, 360x640 for 9:16'); p.add_argument('--tol', type=float, default=.2)
    p.add_argument('--workers', type=int, default=4); p.add_argument('--force', action='store_true')
    a = p.parse_args()
    if a.width <= 0 or a.workers <= 0 or a.tol < 0: p.error('width and workers must be positive; tolerance must be nonnegative')
    root = Path(a.rundir); video = root / 'video.mp4'; source = read(root / 'words.json'); spec = read(root / 'blocks.json')
    duration = float(subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1', str(video)], check=True, capture_output=True, text=True).stdout.strip())
    probe = json.loads(subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=width,height:stream_tags=rotate:stream_side_data=rotation', '-of', 'json', str(video)], check=True, capture_output=True, text=True).stdout)['streams'][0]
    rotation = next((x['rotation'] for x in probe.get('side_data_list', []) if 'rotation' in x), probe.get('tags', {}).get('rotate', 0))
    width, height = probe['width'], probe['height']
    if round(float(rotation or 0)) % 180: width, height = height, width
    orientation = 'vertical' if height > width else 'horizontal'
    translations = read(root / 'translation.json') if (root / 'translation.json').exists() else {}
    translated = {s['i']: s for s in translations.get('segments', [])} if translations.get('lang') == 'ru' else {}
    old = read(root / 'donor.json') if (root / 'donor.json').exists() else {}
    old_blocks = {b['n']: b for b in old.get('blocks', [])}
    donor = {'meta': read(root / 'meta.json') if (root / 'meta.json').exists() else {}, 'duration': duration,
             'lang': source.get('lang'), 'orientation': orientation, 'dropped_words': 0, 'page': old.get('page', {}), 'blocks': []}
    used = set(); jobs = []; failures = []
    for b in spec['blocks']:
        n = b['n']; name = f'b{n:02d}'
        # cache key in the file name: changed block bounds give a new clip instead of a stale one
        clip = f"blocks/{name}-{int(round(b['t0'] * 1000))}-{int(round(b['t1'] * 1000))}.mp4"; target = root / clip
        for stale in (root / 'blocks').glob(f'{name}*.mp4'):
            if stale.name != Path(clip).name: stale.unlink(missing_ok=True)
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists() or a.force:
            try:
                subprocess.run(['ffmpeg', '-y', '-v', 'error', '-ss', str(b['t0']), '-i', str(video), '-t', str(b['t1'] - b['t0']),
                    '-vf', "scale='round(iw*min(1,720/min(iw,ih))/2)*2':'round(ih*min(1,720/min(iw,ih))/2)*2'", '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '23', '-c:a', 'aac', '-b:a', '128k', '-movflags', '+faststart', str(target)], check=True, capture_output=True)
            except (OSError, subprocess.CalledProcessError) as exc:
                failures.append(f'Clip {name}: {exc}'); target.unlink(missing_ok=True)
        block = {k: b.get(k, '') for k in ('n', 'title', 'role', 't0', 't1', 'why')}
        block.update({'clip': clip, 'segments': [], 'words': []})
        if 'notes' in old_blocks.get(n, {}): block['notes'] = old_blocks[n]['notes']
        selected = []
        for pos, w in enumerate(source['words']):
            if b['t0'] <= w['t0'] < b['t1']:
                used.add(pos); selected.append(pos)
                ft = min(w['t0'] + a.lead, w['t1'], duration - .05)
                # cache key in the file name: frame time and short side (s<N>); changed --lead/--width/bounds give new frames
                frame = f"frames/{name}/w{w['i']:05d}-{int(round(ft * 1000))}-s{a.width}.jpg"
                item = {'i': w['i'], 'text': w['text'], 't0': w['t0'], 't1': w['t1'], 'ft': ft, 'frame': frame}
                block['words'].append(item); jobs.append((item, frame))
        for s in source['segments']:
            indexes = [j for j, pos in enumerate(selected) if s['w0'] <= pos < s['w1']]
            if indexes:
                tr = translated.get(s['i'], {})
                ru = tr.get('ru', '')
                parts = []
                for part in tr.get('parts', [{'ru': ru, 'w0': 0, 'w1': s['w1'] - s['w0']}]):
                    kept = [j for j in indexes if s['w0'] + part['w0'] <= selected[j] < s['w0'] + part['w1']]
                    if kept: parts.append({'ru': part['ru'], 'k0': kept[0], 'k1': kept[-1] + 1})
                block['segments'].append({'i': s['i'], 'ru': ru, 'parts': parts, 't0': s['t0'], 't1': s['t1'], 'text': s['text'], 'w0': indexes[0], 'w1': indexes[-1] + 1})
        donor['blocks'].append(block)
    donor['dropped_words'] = len(source['words']) - len(used)
    def frame_job(job):
        item, rel = job; target = root / rel
        try:
            if abs(item['ft'] - item['t0']) > a.tol + 1e-9 or item['ft'] < 0:
                raise ValueError('frame time exceeds tolerance or is negative')
            target.parent.mkdir(parents=True, exist_ok=True)
            if a.force or not target.exists():
                subprocess.run(['ffmpeg', '-y', '-v', 'error', '-ss', str(item['ft']), '-i', str(video), '-frames:v', '1', '-vf', f"scale='round(iw*min(1,{a.width}/min(iw,ih))/2)*2':'round(ih*min(1,{a.width}/min(iw,ih))/2)*2'", '-q:v', '4', str(target)], check=True, capture_output=True)
                if not target.exists() or target.stat().st_size == 0: raise ValueError('ffmpeg produced no frame')
        except (OSError, ValueError, subprocess.CalledProcessError) as exc:
            target.unlink(missing_ok=True); item['frame'] = None
            item['error'] = (exc.stderr.decode('utf-8', errors='replace').strip() if isinstance(exc, subprocess.CalledProcessError) and exc.stderr else str(exc))
            return f'{rel}: {item["error"]}'
    keep = {root / item['frame'] for item, _ in jobs}
    for old_frame in (root / 'frames').glob('b*/w*.jpg'):
        if old_frame not in keep: old_frame.unlink(missing_ok=True)
    with ThreadPoolExecutor(max_workers=a.workers) as pool:
        failures.extend(x for x in pool.map(frame_job, jobs) if x)
    write(root / 'donor.json', donor)
    # build.ok marks a complete build: run.py --resume rebuilds while it is missing (failed media get another try)
    marker = root / 'build.ok'
    if failures:
        marker.unlink(missing_ok=True)
    else:
        marker.write_text('ok', encoding='utf-8')
    for failure in failures: print(failure, file=sys.stderr)
    return 1 if failures else 0


if __name__ == '__main__': sys.exit(main())

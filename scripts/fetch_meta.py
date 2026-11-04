import argparse
import datetime
import json
import statistics
import subprocess
from pathlib import Path


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def main():
    p = argparse.ArgumentParser()
    p.add_argument('url'); p.add_argument('outdir')
    p.add_argument('--info-json'); p.add_argument('--channel-json')
    p.add_argument('--n', type=int, default=30); p.add_argument('--download', action='store_true')
    p.add_argument('--section', choices=['videos', 'shorts'], help='channel tab for the norm; default: shorts for vertical videos up to 180 s')
    a = p.parse_args()
    out = Path(a.outdir); out.mkdir(parents=True, exist_ok=True)
    def query(args):
        return json.loads(subprocess.run(args, check=True, capture_output=True, text=True, encoding='utf-8').stdout)
    info = read_json(a.info_json) if a.info_json else query(['yt-dlp', '-J', '--no-warnings', a.url])
    notes = []
    channel_url = info.get('channel_url') or info.get('uploader_url')
    try:
        if a.channel_json:
            channel = read_json(a.channel_json)
        else:
            if not channel_url:
                raise ValueError('channel URL unavailable')
            vertical = (info.get('height') or 0) > (info.get('width') or 0) > 0
            section = a.section or ('shorts' if '/shorts/' in a.url or (vertical and (info.get('duration') or 999) <= 180) else 'videos')
            # one extra entry: the donor itself is excluded below, a.n peers remain
            channel = query(['yt-dlp', '-J', '--flat-playlist', '--playlist-end', str(a.n + 1), channel_url.rstrip('/') + '/' + section])
        entries = [e for e in channel.get('entries', []) if e and e.get('view_count') is not None]
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        entries = []
        notes.append('Channel statistics unavailable: ' + str(exc))
    views = info.get('view_count'); likes = info.get('like_count'); comments = info.get('comment_count')
    values = sorted(e['view_count'] for e in entries if e.get('id') != info.get('id'))
    norm = None
    if len(values) >= 3:
        # Linear interpolation between neighboring ranks.
        pos = .75 * (len(values) - 1); lo = int(pos); hi = min(lo + 1, len(values) - 1)
        norm = {'n': len(values), 'median': statistics.median(values), 'mean': statistics.mean(values),
                'stdev': statistics.pstdev(values), 'p75': values[lo] + (values[hi] - values[lo]) * (pos - lo)}
    elif not notes:
        notes.append('Fewer than three channel videos have view counts.')
    rank = None
    if views is not None and entries:
        ranks = [e['view_count'] for e in entries if e.get('id') != info.get('id')] + [views]
        rank = f"{1 + sum(v > views for v in ranks)} из {len(ranks)}"
    date = info.get('upload_date')
    if date and len(date) == 8 and date.isdigit(): date = date[:4] + '-' + date[4:6] + '-' + date[6:]
    meta = {'url': a.url, 'id': info.get('id'), 'platform': (info.get('extractor_key') or '').lower(),
            'title': info.get('title'), 'channel': info.get('channel') or info.get('uploader'),
            'channel_url': channel_url, 'upload_date': date, 'duration': info.get('duration'), 'views': views,
            'likes': likes, 'comments': comments, 'thumbnail': info.get('thumbnail'), 'norm': norm,
            'ratio': round(views / norm['median'], 2) if norm and views is not None and norm['median'] else None,
            'z': round((views - norm['mean']) / norm['stdev'], 2) if norm and views is not None and norm['stdev'] else None,
            'rank': rank, 'like_rate': round(100 * likes / views, 2) if views and likes is not None else None,
            'comments_per_1k': round(1000 * comments / views, 2) if views and comments is not None else None,
            'fetched_at': datetime.date.today().isoformat(), 'notes': notes}
    (out / 'meta.json').write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding='utf-8')
    if a.download and not (out / 'video.mp4').exists():
        subprocess.run(['yt-dlp', '-f', 'bv*[height<=720]+ba/b', '--merge-output-format', 'mp4', '-o', str(out / 'video.mp4'), a.url], check=True)


if __name__ == '__main__': main()

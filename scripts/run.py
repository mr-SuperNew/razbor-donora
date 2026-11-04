"""Run the donor analysis pipeline for a URL, or resume a run directory."""
import argparse
import json
import os
import shlex
import subprocess
import sys

for _stream in (sys.stdout, sys.stderr):  # Russian messages must not crash on a cp1252/cp1251 console
    try:
        _stream.reconfigure(encoding='utf-8', errors='replace')
    except (AttributeError, ValueError):
        pass
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent


def call(script, *args):
    result = subprocess.run([sys.executable, str(SCRIPTS / script), *(str(a) for a in args)])
    return result.returncode


def main():
    parser = argparse.ArgumentParser(description='Analyze a video URL or resume a previous run.')
    parser.add_argument('url', nargs='?', help='Video URL')
    parser.add_argument('--out', help='Output directory')
    parser.add_argument('--resume', help='Resume an existing run directory')
    parser.add_argument('--lang', choices=['auto', 'en', 'ru'], default='auto')
    parser.add_argument('--engine', choices=['groq', 'local'], default='groq')
    parser.add_argument('--no-translate', action='store_true')
    parser.add_argument('--blocks', choices=['groq', 'agent'], default='groq')
    a = parser.parse_args()
    if not a.url and not a.resume:
        parser.error('provide a URL or --resume DIR')
    if a.resume and a.out:
        parser.error('--out and --resume cannot be combined')
    if a.resume:
        root = Path(a.resume).resolve()
    elif a.out:
        root = Path(a.out).resolve()
    else:
        try:
            result = subprocess.run(['yt-dlp', '--get-id', '--no-playlist', a.url], check=True, capture_output=True, text=True, encoding='utf-8')
        except (OSError, subprocess.CalledProcessError) as exc:
            print('Could not determine video ID using yt-dlp:', exc, file=sys.stderr)
            return 2
        video_id = result.stdout.strip().splitlines()[0]
        if not video_id or video_id in ('.', '..') or any(c in video_id for c in '/\\:'):
            print('Invalid video ID.', file=sys.stderr)
            return 2
        root = (Path.cwd() / 'donors' / video_id).resolve()
    root.mkdir(parents=True, exist_ok=True)
    meta, video = root / 'meta.json', root / 'video.mp4'
    words, blocks = root / 'words.json', root / 'blocks.json'
    if not meta.exists() or not video.exists():
        url = a.url
        if not url and meta.exists():
            url = json.loads(meta.read_text(encoding='utf-8')).get('url')
        if not url:
            print('A URL is required to fetch missing metadata or video.', file=sys.stderr)
            return 2
        code = call('fetch_meta.py', url, root, '--download')
        if code: return code
    if not words.exists():
        code = call('transcribe.py', video, words, '--engine', a.engine, '--lang', a.lang)
        if code: return code
    if not (root / 'segments.txt').exists() or not (root / 'segwords.txt').exists():
        code = call('segwords.py', root)
        if code: return code
    if not blocks.exists():
        if a.blocks == 'agent':
            print(f'AI agent: Read {root / "segments.txt"} and {words}. Write {blocks} as JSON: '
                  '{"blocks":[{"n":1,"title":"...","role":"...","t0":0.0,"t1":1.0,"why":"..."}]}. '
                  'Use ordered, non-overlapping blocks that cover every segment; align boundaries to segment times. '
                  'Use Russian titles and descriptions. Then run:')
            command = [sys.executable, str(SCRIPTS / 'run.py'), '--resume', str(root)]
            print(subprocess.list2cmdline(command) if os.name == 'nt' else shlex.join(command))
            return 0
        code = call('llm_groq.py', 'blocks', root)
        if code: return code
    language = str(json.loads(words.read_text(encoding='utf-8')).get('lang') or a.lang).lower()
    allow_missing = a.no_translate
    if language != 'ru' and not a.no_translate and not (root / 'translation.json').exists():
        code = call('llm_groq.py', 'translate', root)
        if code == 3:
            print('Warning: translation unavailable (Groq limit or API error); continuing without translation.', file=sys.stderr)
            allow_missing = True
        elif code:
            return code
    built = root / 'build.ok'  # written by build.py only when every clip and frame succeeded
    inputs = [meta, video, words, blocks, root / 'translation.json']
    if not built.exists() or any(p.exists() and p.stat().st_mtime_ns > built.stat().st_mtime_ns for p in inputs):
        code = call('build.py', root)
        if code: return code
    page_args = [root, '--mode', 'standalone']
    if allow_missing: page_args.append('--allow-no-translation')
    code = call('page.py', *page_args)
    if code: return code
    print(root / 'index.html')
    return 0


if __name__ == '__main__':
    sys.exit(main())

import argparse
import html
import json
import os
import sys
from pathlib import Path
from urllib.parse import quote


def esc(value): return html.escape(str(value if value is not None else '—'), quote=True)
def clock(value):
    value = max(0, int(float(value or 0)))
    return f'{value // 60}:{value % 60:02d}'


def main():
    p = argparse.ArgumentParser()
    p.add_argument('rundir'); p.add_argument('--out'); p.add_argument('--hub')
    p.add_argument('--mode', choices=['standalone', 'review'], default='standalone')
    p.add_argument('--allow-no-translation', action='store_true'); a = p.parse_args()
    root = Path(a.rundir).resolve()
    if a.mode == 'review':
        if not a.out or not a.hub: p.error('--mode review requires --out and --hub')
        rel = root.relative_to(Path(a.hub).resolve()).as_posix()
        base = '/m/' + quote(rel, safe='/') + '/'
    else:
        outdir = Path(a.out).resolve() if a.out else root
        rel = Path(os.path.relpath(root, outdir)).as_posix()
        base = '' if rel == '.' else quote(rel, safe='/') + '/'
    data = json.loads((root / 'donor.json').read_text(encoding='utf-8')); meta = data.get('meta') or {}; blocks = data.get('blocks', []); page = data.get('page') or {}
    missing_translation = bool(data.get('lang') and data['lang'].lower() != 'ru' and any(not str(seg.get('ru') or '').strip() for b in blocks for seg in b.get('segments', [])))
    if missing_translation and not a.allow_no_translation:
        if hasattr(sys.stderr, 'reconfigure'): sys.stderr.reconfigure(encoding='utf-8')
        print('Не хватает перевода на русский язык. Добавьте translation.json или используйте --allow-no-translation.', file=sys.stderr)
        return 3
    orientation = data.get('orientation') if data.get('orientation') in ('horizontal', 'vertical') else 'horizontal'
    def media(path): return base + quote(path or '', safe="/")
    def display(value): return esc(value if value is not None else '—')
    def num(value): return f'{value:,}'.replace(',', ' ') if isinstance(value, (int, float)) else '—'
    ratio = meta.get('ratio'); ratio = '×' + str(float(ratio)).replace('.', ',') if ratio is not None else '—'
    pieces = ['''<!doctype html><html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Разбор донора</title><style>
:root{color-scheme:light;--bg:#f4f5f8;--card:#fff;--text:#20242c;--muted:#5e6877;--border:#d9dee8;--accent:#365ec8;--highlight:#ffe39a}
@media (prefers-color-scheme: dark){:root{color-scheme:dark;--bg:#171a21;--card:#242933;--text:#eef1f6;--muted:#b3bdca;--border:#444d5c;--accent:#9ab5ff;--highlight:#805b12}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font:16px/1.55 system-ui,sans-serif}main{max-width:1100px;margin:auto;padding:24px 16px 80px}h1{font-size:clamp(1.6rem,5vw,2.4rem);line-height:1.2}h2{font-size:1.25rem}a{color:var(--accent)}.top{display:grid;gap:12px}.card,section.block{background:var(--card);border:1px solid var(--border);border-radius:14px;padding:18px;margin:12px 0}.top .card{margin:0}.stats{display:flex;gap:18px;flex-wrap:wrap}.thumb{width:min(100%,240px);height:auto;object-fit:contain;align-self:start}.stats dl{display:grid;grid-template-columns:auto 1fr;gap:4px 16px;margin:0}dt{color:var(--muted)}dd{margin:0}.timeline{display:flex;width:100%;height:42px;overflow:hidden;border-radius:8px;background:var(--border)}.timeline a{display:flex;align-items:center;justify-content:center;min-width:2px;overflow:hidden;background:var(--accent);color:white;border-right:1px solid white;text-decoration:none}.block{scroll-margin-top:16px}video{width:100%;max-height:600px;background:#000}.flipbook{border:1px solid var(--border);border-radius:12px;padding:12px;margin-top:16px}.flipbook:focus-visible{outline:3px solid var(--accent)}.picture{display:block;width:100%;padding:0;border:0;background:#111;cursor:pointer}.picture img{display:block;width:100%;height:auto}.missing{padding:3em;color:var(--muted);text-align:center}.nav{display:flex;align-items:center;gap:12px;margin:10px 0}.nav button{font-size:1.4rem;padding:2px 14px}.nav input{flex:1;min-width:40px}.caption{font-size:clamp(1.2rem,4vw,1.65rem);line-height:1.4;min-height:2em}.word-active{background:var(--highlight);color:var(--text);border-radius:3px}.transcript{max-height:12em;overflow:auto;line-height:2;position:relative}.w{cursor:pointer}.w:hover{text-decoration:underline}.stamp{color:var(--muted);font-size:.85em}textarea{display:block;width:100%;min-height:90px;margin:8px 0 16px;padding:10px;font:inherit;border:1px solid var(--border);border-radius:8px;background:var(--bg);color:var(--text)}button{cursor:pointer}label{display:block;margin-top:16px}.muted{color:var(--muted)}@media(min-width:700px){.top{grid-template-columns:repeat(3,1fr)}}
.stats-card{display:grid;grid-template-columns:minmax(0,260px) 1fr;gap:20px;align-items:start}.stats-card .thumb{width:100%;height:auto;border-radius:10px}.orig{margin:0 0 10px}.big{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px;margin-bottom:12px}.tile{background:var(--bg);border-radius:10px;padding:10px 12px}.tile b{display:block;font-size:1.6rem;line-height:1.2}.tile span{color:var(--muted);font-size:.85rem}.small{display:grid;grid-template-columns:repeat(auto-fill,minmax(170px,1fr));gap:8px 16px;margin:0}.small dt{color:var(--muted);font-size:.8rem}.small dd{margin:0;overflow-wrap:anywhere}@media(max-width:700px){.stats-card{grid-template-columns:1fr}.big{grid-template-columns:1fr 1fr}.tile b{font-size:1.3rem}}
@media(max-width:700px){[data-orientation="vertical"] .picture img{max-height:55vh}.nav{flex-wrap:wrap}.nav input{flex-basis:100%}}
.sticky{position:sticky;top:0;z-index:10;background:var(--card);border:1px solid var(--border);padding:10px;display:flex;gap:10px;align-items:center}.sticky .timeline{flex:1;min-width:0}.block{scroll-margin-top:75px}.block summary{cursor:pointer;font-weight:600}.block summary .muted{display:block;font-weight:400}.block-content{display:grid;gap:16px}.flipbook{min-width:0}.viewer{min-width:0}.picture img{width:100%;height:auto;max-height:70vh;object-fit:contain}.caption-ru{font-size:1.2rem;line-height:1.45;margin:.4em 0}.phrase{line-height:1.6;margin:.6em 0}.phrase-ru{color:var(--muted)}.lines{position:relative;max-height:22em;overflow:auto}.phrase[hidden]{display:none}.phrase.current{font-weight:600}.caption-ru{font-size:.85em}.caption{margin-bottom:12px}.tabs{display:flex;gap:8px;margin-bottom:8px}.stats dl{grid-template-columns:auto minmax(0,1fr)}.card,details.block{overflow-wrap:anywhere}details.block{background:var(--card);border:1px solid var(--border);border-radius:14px;padding:18px;margin:12px 0}video[hidden],.picture[hidden],.picture img[hidden],.nav[hidden]{display:none}@media(min-width:900px){main[data-orientation="horizontal"] .block-content{grid-template-columns:minmax(0,3fr) minmax(0,2fr)}main[data-orientation="vertical"] .block-content{grid-template-columns:minmax(0,2fr) minmax(0,3fr)}}
</style></head><body><main data-orientation="ORIENTATION">'''.replace('ORIENTATION', orientation)]
    pieces.append('<h1>Разбор донора: ' + display(meta.get('title')) + '</h1>')
    cards = ['<div class="top">']
    for key, title, default in [('new','Что нового','Разбор готов к просмотру.'), ('need','Что нужно от тебя','Посмотри блоки и оставь комментарии.'), ('next','Что дальше','Выберем приёмы для монтажа.')]:
        cards.append(f'<div class="card"><h2>{title}</h2><p>{esc(page.get(key) or default)}</p></div>')
    cards.append('</div>')
    pieces.extend(cards)
    norm = meta.get('norm') or {}
    def short(v):
        if not isinstance(v, (int, float)): return '—'
        return (f'{v/1e6:.1f} млн' if v >= 1e6 else f'{round(v/1e3):.0f} тыс.' if v >= 1e4 else f'{int(round(v)):,}'.replace(',', ' ')).replace('.0 млн', ' млн').replace('.', ',', 1 if v >= 1e6 else 0)
    def dec(v, d=1): return f'{float(v):.{d}f}'.replace('.', ',') if isinstance(v, (int, float)) else '—'
    rr = meta.get('ratio')
    big = [('Просмотры', short(meta.get('views'))),
           ('К медиане канала', ('×' + (str(round(rr)) if rr >= 10 else dec(rr))) if isinstance(rr, (int, float)) else '—'),
           ('Место на канале', display(meta.get('rank')))]
    small = [('Канал', display(meta.get('channel'))), ('Дата', display(meta.get('upload_date'))), ('Длительность', clock(data.get('duration'))),
             ('Медиана канала', short(norm.get('median')) + (f' (по {norm["n"]} роликам)' if norm.get('n') else '')),
             ('Z-оценка', dec(meta.get('z'))), ('Лайки', dec(meta.get('like_rate')) + '%' if meta.get('like_rate') is not None else '—'),
             ('Комментарии на 1000', dec(meta.get('comments_per_1k'))), ('Блоки · слова', f"{len(blocks)} · {sum(len(b.get('words', [])) for b in blocks)}")]
    pieces.append('<div class="card stats-card">')
    if meta.get('thumbnail'): pieces.append(f'<img class="thumb" src="{esc(meta["thumbnail"])}" alt="Обложка видео">')
    pieces.append('<div class="stats-body">')
    if meta.get('url'): pieces.append(f'<p class="orig"><a href="{esc(meta["url"])}" target="_blank" rel="noopener noreferrer">Открыть оригинал ↗</a></p>')
    pieces.append('<div class="big">' + ''.join(f'<div class="tile"><b>{v}</b><span>{esc(k)}</span></div>' for k, v in big) + '</div>')
    pieces.append('<dl class="small">' + ''.join(f'<div><dt>{esc(k)}</dt><dd>{v}</dd></div>' for k, v in small) + '</dl>')
    if meta.get('notes'): pieces.append('<p class="muted">' + '<br>'.join(esc(note) for note in meta['notes']) + '</p>')
    pieces.append('</div></div>')
    if missing_translation: pieces.append('<div class="card" role="alert">Перевода нет</div>')
    pieces.append('<div class="sticky"><nav class="timeline" aria-label="Карта блоков">')
    for b in blocks:
        pieces.append(f'<a href="#b{b["n"]:02d}" style="flex:{max(.001, float(b["t1"])-float(b["t0"]))} 1 0" aria-label="Блок {b["n"]}">{b["n"]}</a>')
    pieces.append('</nav><button type="button" id="toggle-all">Развернуть все</button></div>')
    for block_index, b in enumerate(blocks):
        n = b['n']; key = f'{n:02d}'; words = b.get('words', [])
        heading = ' · '.join([f'Блок {n}', str(b.get('role') or ''), clock(b['t0']) + '–' + clock(b['t1']), str(b.get('title') or '')])
        opened = ' open' if block_index == 0 else ''
        pieces.append(f'<details class="block" id="b{key}"{opened}><summary>{esc(heading)}<span class="muted">{esc(b.get("why") or "")}</span></summary><div class="flipbook" tabindex="0" data-b="{key}"><div class="block-content"><div class="viewer"><div class="caption" aria-live="polite"><div class="caption-en"></div><div class="caption-ru"></div></div><div class="tabs"><button type="button" data-tab="frames" aria-pressed="true">Кадры</button><button type="button" data-tab="video" aria-pressed="false">Видео блока</button></div><button class="picture" type="button" aria-label="Следующий кадр"><img alt="Кадр видео" hidden><span class="missing">кадр не снят</span></button><video controls preload="none" hidden src="{esc(media(b.get("clip")))}"></video><div class="nav"><button type="button" data-dir="-1" aria-label="Предыдущий кадр">‹</button><span class="counter"></span><button type="button" data-dir="1" aria-label="Следующий кадр">›</button><input type="range" min="0" max="{max(0,len(words)-1)}" value="0" aria-label="Выбрать кадр"></div></div><div><button type="button" data-all>Весь текст</button><div class="lines">')
        for seg in b.get('segments', []):
            pieces.append(f'<div class="phrase"><span class="stamp">[{clock(seg["t0"])}]</span> ')
            for i in range(seg['w0'], min(seg['w1'], len(words))):
                pieces.append(f'<span class="w" data-k="{i}">{esc(words[i]["text"])}</span> ')
            if str(data.get('lang') or '').lower() != 'ru' and seg.get('ru'):
                parts = seg.get('parts', [{'ru': seg['ru'], 'k0': seg['w0'], 'k1': seg['w1']}])
                pieces.append(f'<div class="phrase-ru" title="{esc(seg["ru"])}">')
                for part in parts:
                    pieces.append(f'<span class="ru-part" data-k0="{part["k0"]}" data-k1="{part["k1"]}">{esc(part["ru"])}</span> ')
                pieces.append('</div>')
            pieces.append('</div>')
        pieces.append(f'</div><label>Что взять в монтаж из этого блока<textarea name="c-b{key}"></textarea></label>')
        if b.get('notes'): pieces.append(f'<p>{esc(b["notes"])}</p>')
        pieces.append('</div></div></div></details>')
    pieces.append('<label for="gc">Общий комментарий</label><textarea id="gc"></textarea>')
    pieces.append('<button type="button" id="send">Отправить</button></main>' if a.mode == 'review' else '<button type="button" id="export">Скачать отметки (JSON)</button></main>')
    # The JSON script is inert; escaping < prevents closing the script element.
    payload = json.dumps(data, ensure_ascii=False, separators=(',', ':')).replace('<', r'\u003c')
    pieces.append('<script type="application/json" id="donor-data">' + payload + '</script>')
    if a.mode == 'review': pieces.append('<script src="/__review.js"></script>')
    base_json = json.dumps(base, ensure_ascii=True).replace('<', r'\u003c')
    if a.mode == 'review':
        mode_script = """document.getElementById('send').addEventListener('click',()=>{let comments={};document.querySelectorAll('textarea[name^="c-b"]').forEach(el=>{let v=el.value.trim();if(v)comments[el.name]=v;});reviewAnswer({stage:'donor',id:donor.meta.id,comments:comments,generalComment:document.getElementById('gc').value.trim()});});"""
    else:
        mode_script = """
const fields=[...document.querySelectorAll('textarea[name^="c-b"]')], gc=document.getElementById('gc');
const storageKey='razbor-notes:'+String(donor.meta.id||'');
function notes(){let comments={};fields.forEach(el=>{if(el.value.trim())comments[el.name]=el.value;});return {id:donor.meta.id,url:donor.meta.url,title:donor.meta.title,comments:comments,generalComment:gc.value,savedAt:new Date().toISOString()};}
try{let saved=JSON.parse(localStorage.getItem(storageKey)||'{}');fields.forEach(el=>el.value=(saved.comments||{})[el.name]||'');gc.value=saved.generalComment||'';}catch(e){}
[...fields,gc].forEach(el=>el.addEventListener('input',()=>{try{localStorage.setItem(storageKey,JSON.stringify(notes()));}catch(e){}}));
document.getElementById('export').addEventListener('click',()=>{let blob=new Blob([JSON.stringify(notes(),null,2)],{type:'application/json'}),url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=String(donor.meta.id||'video')+'-notes.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);});
"""
    pieces.append('''<script>
const donor = JSON.parse(document.getElementById('donor-data').textContent);
const mediaBase = BASE_URL;
function mediaPath(path){return mediaBase + String(path).split('/').map(encodeURIComponent).join('/');}
function time(t){let v=Math.max(0,Number(t)||0);let m=Math.floor(v/60);return m+':'+(v-m*60).toFixed(1).padStart(4,'0').replace('.',',');}
document.querySelectorAll('.flipbook').forEach(root=>{
 const block=donor.blocks.find(b=>String(b.n).padStart(2,'0')===root.dataset.b), words=block.words;
 const img=root.querySelector('img'), missing=root.querySelector('.missing'), counter=root.querySelector('.counter'), range=root.querySelector('input'), caption=root.querySelector('.caption-en'), translation=root.querySelector('.caption-ru'), box=root.querySelector('.lines'), spans=box.querySelectorAll('.w'), lines=[...box.querySelectorAll('.phrase')], allButton=root.querySelector('[data-all]'); let index=0, all=false;
 root.querySelectorAll('[data-tab]').forEach(btn=>btn.addEventListener('click',()=>{let video=btn.dataset.tab==='video';root.querySelector('video').hidden=!video;if(!video)root.querySelector('video').pause();root.querySelector('.picture').hidden=video;root.querySelector('.nav').hidden=video;root.querySelectorAll('[data-tab]').forEach(b=>b.setAttribute('aria-pressed',String(b===btn)));if(!video)root.querySelector('video').pause();}));
 function show(k){
  if(!words.length){counter.textContent='Кадров нет';return;}
  index=Math.max(0,Math.min(words.length-1,k));let w=words[index]; range.value=index;
  counter.textContent='Кадр '+(index+1)+' из '+words.length+' · '+time(w.t0);
  img.hidden=!w.frame;missing.hidden=!!w.frame;if(w.frame)img.src=mediaPath(w.frame);else img.removeAttribute('src');
  spans.forEach(s=>s.classList.toggle('word-active',Number(s.dataset.k)===index));
  let segIndex=block.segments.findIndex(s=>index>=s.w0&&index<s.w1), seg=block.segments[segIndex];
  lines.forEach((line,i)=>{line.hidden=!all&&(segIndex<0||Math.abs(i-segIndex)>2);line.classList.toggle('current',i===segIndex);line.querySelectorAll('.ru-part').forEach(part=>part.classList.toggle('word-active',i===segIndex&&index>=Number(part.dataset.k0)&&index<Number(part.dataset.k1)));});
  if(all&&segIndex>=0){let line=lines[segIndex];box.scrollTop=line.offsetTop-box.offsetTop-box.clientHeight/2+line.offsetHeight/2;}
  caption.replaceChildren();translation.replaceChildren();let from=seg?seg.w0:index,to=seg?seg.w1:index+1;
  if(String(donor.lang||'').toLowerCase()!=='ru'&&seg){let parts=seg.parts??[{ru:seg.ru,k0:seg.w0,k1:seg.w1}];parts.forEach((part,i)=>{if(i)translation.append(' ');let el=document.createElement('span');el.className='ru-part';el.dataset.k0=part.k0;el.dataset.k1=part.k1;el.textContent=part.ru;el.classList.toggle('word-active',index>=part.k0&&index<part.k1);translation.append(el);});}
  for(let j=from;j<to;j++){if(j>from)caption.append(' ');let el=document.createElement('span');el.textContent=words[j].text;if(j===index)el.className='word-active';caption.append(el);}
  for(let j=index+1;j<=Math.min(index+3,words.length-1);j++)if(words[j].frame){let preload=new Image();preload.src=mediaPath(words[j].frame);}
 }
 root.addEventListener('click',e=>{let dir=e.target.closest('[data-dir]'),word=e.target.closest('.w');if(dir)show(index+Number(dir.dataset.dir));else if(word)show(Number(word.dataset.k));else if(e.target.closest('.picture'))show(index+1);});
 root.addEventListener('keydown',e=>{if(e.target.matches('input,textarea,video')||!root.querySelector('video').hidden)return;if(e.key==='ArrowRight'||e.key==='ArrowLeft'){e.preventDefault();show(index+(e.key==='ArrowRight'?1:-1));}});
 allButton.addEventListener('click',()=>{all=!all;allButton.textContent=all?'Свернуть текст':'Весь текст';show(index);});
 range.addEventListener('input',()=>show(Number(range.value)));show(0);
});
const details=[...document.querySelectorAll('details.block')], toggle=document.getElementById('toggle-all');
function updateToggle(){toggle.textContent=details.length&&details.every(d=>d.open)?'Свернуть все':'Развернуть все';}
details.forEach(d=>d.addEventListener('toggle',()=>{if(!d.open)d.querySelectorAll('video').forEach(v=>v.pause());updateToggle();}));toggle.addEventListener('click',()=>{let open=!details.every(d=>d.open);details.forEach(d=>d.open=open);updateToggle();});
function openHash(){let d=document.getElementById(location.hash.slice(1));if(d&&d.matches('details.block')){d.open=true;d.scrollIntoView();}}
document.querySelectorAll('.timeline a').forEach(a=>a.addEventListener('click',()=>{let d=document.getElementById(a.hash.slice(1));if(d)d.open=true;}));window.addEventListener('hashchange',openHash);if(location.hash)openHash();updateToggle();
MODE_SCRIPT
</script></body></html>'''.replace('BASE_URL', base_json).replace('MODE_SCRIPT', mode_script))
    out = Path(a.out) if a.out else root; out.mkdir(parents=True, exist_ok=True); (out / 'index.html').write_text(''.join(pieces), encoding='utf-8')


if __name__ == '__main__': sys.exit(main())

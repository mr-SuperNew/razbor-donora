---
name: razbor-donora
description: >
  Use this skill when the user names a "donor" video (a video whose editing they want to learn or copy) and wants a
  frame-by-word breakdown: the video is downloaded, transcribed word by word, cut into meaningful editing blocks, a
  screenshot is taken at the start of every spoken word (±0.2 s), and a local HTML page is built: link and stats
  (views vs the channel's usual views), and per block the block video plus a frame flipbook where the phrase runs like
  subtitles with the current word highlighted (and its Russian translation for English videos). Output: index.html and
  donor.json for editing tasks. Triggers: "разбери донора", "покадровая расшифровка", "разбери ролик по блокам",
  "хочу монтировать как в этом ролике", "razbor-donora", "break down this video frame by frame".
homepage: https://github.com/mr-SuperNew/razbor-donora
---

# razbor-donora — разбор ролика-донора по блокам, словам и кадрам

**TL;DR:** ссылка → `python scripts/run.py <url>` → `donors/<id>/index.html`. Код скачивает ролик, считает статистику канала, расшифровывает речь по словам, режет ролик на блоки, снимает кадр на каждое слово и собирает страницу. Нейросеть-ассистент нужна только для смысловых блоков и перевода, и их тоже можно отдать бесплатной модели на Groq.

Скрипты лежат в `scripts/` рядом с этим файлом. Пути ниже — от папки скилла.

## Что нужно один раз

- Python 3.10+, `python -m pip install requests "yt-dlp[default]"`; Deno (yt-dlp нужен JavaScript для YouTube); `ffmpeg` и `ffprobe` в PATH. Команды запускай из папки скилла.
- Бесплатный ключ Groq (console.groq.com → API Keys) в переменной `GROQ_API_KEY` или в файле `.env` строкой `GROQ_API_KEY=...` в папке, откуда запускаешь. Ключ не печатать и не вставлять в чат.
- Без Groq совсем: `python -m pip install faster-whisper`, затем `python scripts/run.py <ссылка> --engine local --blocks agent --no-translate`: расшифровка на своей машине (3–4 ГБ памяти, лучше с видеокартой), блоки пишешь ты (раздел ниже), перевода нет; продолжение — `python scripts/run.py --resume donors/<id> --no-translate`.

Проверка движка без интернета: `python scripts/test_razbor.py scripts` → `0 failed` (нужен ffmpeg; Node.js по желанию).

## Как запускать

### Быстрый путь — одной командой

```
python scripts/run.py <ссылка на ролик> [--lang en|ru|auto]
```

Шаги: метаданные и видео → расшифровка (Groq Whisper) → блоки (модель на Groq) → перевод на русский, если ролик не на русском → клипы блоков и кадры → `donors/<id>/index.html`. Упало посередине — `python scripts/run.py --resume donors/<id>` продолжит с места.

### Блоки размечает сам агент (точнее, без Groq-модели)

```
python scripts/run.py <ссылка> --blocks agent
```

Скрипт остановится после расшифровки и оставит `donors/<id>/segments.txt` (фразы `[начало-конец] текст`). Ты, агент, читаешь его целиком и пишешь `donors/<id>/blocks.json`:

```json
{"blocks":[{"n":1,"title":"короткое название","role":"хук","t0":0.0,"t1":18.8,"why":"что блок делает для зрителя"}]}
```

- Блоки — как режут ролик при монтаже: хук, обещание, разделы, установка, демо, цена, призыв, финал, вставка (реклама, «подпишись»). Обычно 20–90 секунд.
- `t0` — начало первой фразы блока, `t1` — конец последней, только числа из `segments.txt`. Блоки по порядку, без пересечений, вся речь по делу внутри блоков.
- «Демо» — только если на экране что-то показывают.

Потом `python scripts/run.py --resume donors/<id>`.

## Что проверить перед тем, как отдать результат

1. Статистика честная: кратность меньше 1 — ролик ниже обычного для канала, так и скажи. Кратности нет (Instagram, мало роликов) — причина в `meta.json` → `notes`.
2. Открой 3 кадра из разных блоков и сверь, что на кадре то, о чём слово.
3. Английский ролик: перевод есть (`translation.json`); если бесплатный дневной лимит Groq кончился, страница собрана без перевода — скажи об этом, `--resume` завтра допереведёт.
4. Открой `index.html`: блок раскрывается, стрелки листают кадры, слово подсвечено.

## Что получает человек

Страница `index.html` открывается двойным кликом, без сервера: статистика, карта блоков, в блоке субтитр с подсвеченным словом (и перевод, где кусок горит вместе со словом), кадры, видео блока, текст построчно, поле «Что взять в монтаж». Кнопка «Скачать отметки (JSON)» сохраняет его заметки файлом — отдай этот файл агенту, чтобы превратить отметки в монтажные задания. `donor.json` — те же данные для агента: блоки, фразы, слова со временем и путями к кадрам.

## Скрипты

| Скрипт | Что делает |
|---|---|
| `run.py` | весь путь одной командой, `--resume` |
| `fetch_meta.py` | метаданные, норма канала (медиана 30 роликов без донора), кратность, `--download` |
| `transcribe.py` | слова со временем: Groq Whisper (досылает пропущенные куски) или `--engine local` |
| `segwords.py` | `segments.txt` для блоков, `segwords.txt` для перевода |
| `llm_groq.py` | `blocks` и `translate` бесплатной моделью на Groq (лимит 200 тыс. токенов в сутки, прогресс сохраняется) |
| `blocks_draft.py` | черновик блоков по паузам (только как подсказка) |
| `build.py` | клипы блоков, кадр на каждое слово, `donor.json` |
| `page.py` | `index.html` (`--mode standalone` по умолчанию) |
| `check_parts.py` | проверка перевода по кускам |

## Подводные камни

- **Whisper пропускает речь.** На длинном файле Groq иногда теряет 10–30 секунд; `transcribe.py` сам ищет пропуски и дозапрашивает. Не выключай это.
- **Названия на слух.** «Клод» вместо Claude правится списком `TERM_FIXES` в `transcribe.py`; для своей темы допиши названия в `--prompt`.
- **Перевод съедает лимит.** 17 минут английского — почти весь дневной бесплатный лимит Groq.
- **Чужие кадры.** Разбор — для учёбы: в свои ролики берём приёмы, не кадры и не графику автора.

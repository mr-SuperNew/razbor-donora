# razbor-donora: разбор ролика по кадрам и словам

Даёшь ссылку на ролик, который набрал просмотры. Получаешь страницу, где он разобран по блокам, словам и кадрам.

Зачем это нужно. Во-первых, я могу сам учиться: из чего состоят ролики, которые набрали просмотры, и почему, буквально разбирая каждый кадр. Во-вторых, я могу отдать разбор ИИ, чтобы он понимал, где какие переходы, где какие анимации и как связываются блоки.

## Что делает

- Берёт ссылку на ролик. YouTube работает полностью, Instagram и TikTok тоже, но без нормы канала.
- Скачивает ролик и считает, насколько он зашёл: просмотры, во сколько раз больше медианы 30 последних роликов канала, место среди них.
- Расшифровывает речь по словам, у каждого слова есть время начала. Для этого Groq Whisper: 15–17 минут ролика занимают 20–40 секунд. Пропущенные куски дозапрашивает сам.
- Режет ролик на смысловые блоки, как при монтаже: хук, обещание, разделы, призыв, финал. Блоки делает бесплатная модель на Groq или сам ИИ-агент.
- Английский ролик переводит на русский. Кусок перевода подсвечивается вместе с английским словом.
- Снимает кадр на каждое слово в момент, когда его произносят (точность 0,05 с при допуске 0,2 с), и вырезает видео каждого блока.

## Что получаешь

**Страница `index.html`.** Открывается без сервера. Внутри:

- статистика ролика;
- блоки, которые сворачиваются;
- листалка кадров стрелками;
- субтитр с подсвеченным словом;
- текст построчно;
- поле «что взять в монтаж»;
- кнопка «Скачать отметки (JSON)».

**Файл `donor.json`.** То же самое, но для ИИ: блоки, фразы, слова со временем и кадрами. Отметки и `donor.json` отдаёшь ИИ, и он монтирует так же.

Примеры прогонов:

- Christian Peverelli, «I Fully Automated My Video Editing Using Claude Code»: 818 тыс. просмотров, в 45 раз выше медианы канала, 21 блок, 3819 кадров.
- Никита Велс, русский ролик: 21,5 тыс. просмотров, 0,7 от медианы канала, 26 блоков, 3216 кадров. Страница честно показывает, что донор слабый.

Картинок из чужих роликов в репозитории нет, авторские права.

## Установка

Что нужно:

- Python 3.10 или новее (на Linux и macOS команда может называться `python3`);
- библиотеки: `python -m pip install requests "yt-dlp[default]"`;
- Deno: yt-dlp нужен JavaScript для YouTube. Windows: `winget install DenoLand.Deno`, macOS: `brew install deno`, Linux: `curl -fsSL https://deno.land/install.sh | sh`;
- ffmpeg. Windows: `winget install ffmpeg`, macOS: `brew install ffmpeg`, Linux (Ubuntu): `sudo apt install ffmpeg`;
- бесплатный ключ Groq: console.groq.com, раздел API Keys. Положи его в переменную окружения `GROQ_API_KEY` или в файл `.env` в папке, откуда запускаешь: `GROQ_API_KEY=...`

**Claude Code.** macOS, Linux, Git Bash:

```
git clone https://github.com/mr-SuperNew/razbor-donora.git ~/.claude/skills/razbor-donora
```

Windows PowerShell:

```
git clone https://github.com/mr-SuperNew/razbor-donora.git "$env:USERPROFILE/.claude/skills/razbor-donora"
```

Потом скажи ему «разбери донора» и ссылку на ролик.

**Codex, ChatGPT-агент и другие агенты с терминалом.** Склонируй репозиторий в любую папку, открой её в агенте (он читает `AGENTS.md`) и скажи то же самое.

**Вручную, без ИИ:**

```
python scripts/run.py <ссылка>
```

Блоки тогда делает модель на Groq.

**Без ключа Groq.** Всё делается на твоём компьютере и самим агентом:

```
python -m pip install faster-whisper
python scripts/run.py <ссылка> --engine local --blocks agent --no-translate
```

Скрипт расшифрует речь на компьютере (нужно 3–4 ГБ памяти, лучше с видеокартой) и остановится. Агент читает `donors/<id>/segments.txt`, пишет `blocks.json` (формат в `SKILL.md`), потом `python scripts/run.py --resume donors/<id> --no-translate`. Перевод в этом режиме не делается.

**Про обычный ChatGPT в браузере.** Не подойдёт. Нужен агент, который запускает программы на компьютере: Codex, ChatGPT-агент с терминалом, Claude Code.

## Как пользоваться

Одна фраза агенту:

```
разбери донора https://www.youtube.com/watch?v=...
```

Рядом с роликом появляется `index.html`. Открываешь, листаешь, отмечаешь, что взять в монтаж, скачиваешь JSON и отдаёшь ИИ вместе с `donor.json`.

## Сколько стоит

Токены Claude и ChatGPT не тратятся: всё делается на скриптах. Практически ничего не стоит.

Расшифровка, блоки и перевод идут через бесплатный тариф Groq. Лимит там 200 тыс. токенов в сутки. Перевод 17-минутного английского ролика съедает почти весь лимит.

## Ограничения

- Блоки от модели иногда надо поправить руками.
- Перевод на бесплатном Groq: примерно один длинный английский ролик в сутки.
- Обкатан на горизонтальных роликах. Вертикальные (рилсы, шортсы) код поддерживает, но на настоящих рилсах пока не проверялся.
- Instagram и TikTok: норма канала не считается.
- Проверено на Windows 11. На macOS и Linux код без привязки к системе, но живьём не прогонялся.
- Разбор нужен для учёбы: берём приёмы, не чужие кадры.

## Автор

Илья Гужов (Mr.SuperNew). Канал: [t.me/mrsupernew](https://t.me/mrsupernew)

## Лицензия

MIT

## English

razbor-donora breaks down a video by blocks, words and frames. Give it a link to a video that got views, get a single offline `index.html` page plus a `donor.json` for your AI to copy the editing from.

- Transcribes with word-level timestamps (Groq Whisper), splits the video into blocks (hook, promise, sections, call to action), grabs a frame for every spoken word.
- Claude Code: `git clone https://github.com/mr-SuperNew/razbor-donora.git ~/.claude/skills/razbor-donora` (PowerShell: `"$env:USERPROFILE/.claude/skills/razbor-donora"`), then say "разбери донора" plus the video link.
- Codex or any agent with a terminal: clone anywhere, open the folder (the agent reads `AGENTS.md`). Manual run: `python scripts/run.py <link>`.
- Requirements: Python 3.10+, `python -m pip install requests "yt-dlp[default]"`, Deno (yt-dlp needs it for YouTube), ffmpeg, a free Groq API key in `GROQ_API_KEY`. No Groq: `--engine local --blocks agent --no-translate`. A plain ChatGPT chat in the browser will not work: the agent must run programs on your computer.
- Tested on Windows 11 only. MIT license.

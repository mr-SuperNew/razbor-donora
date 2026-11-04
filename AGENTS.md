# AGENTS.md — razbor-donora

Instructions for any coding agent (Codex / ChatGPT agent, Cursor, Gemini CLI, Claude Code, …).
Run every command from this folder (the repository root). The full workflow is in `SKILL.md` (Russian). Short version:

1. User gives a video URL → `python scripts/run.py <url>` (add `--lang en` for English videos).
2. Needs: Python 3.10+, `python -m pip install requests "yt-dlp[default]"`, Deno and ffmpeg in PATH, free Groq key in env
   `GROQ_API_KEY` (or `.env` in the working folder). Never print the key.
3. Better blocks, or no Groq key for the LLM step: `python scripts/run.py <url> --blocks agent`, then YOU read
   `donors/<id>/segments.txt` and write `donors/<id>/blocks.json` exactly as described in `SKILL.md`, then
   `python scripts/run.py --resume donors/<id>`.
4. No Groq key at all: `python -m pip install faster-whisper`, then
   `python scripts/run.py <url> --engine local --blocks agent --no-translate`, write `blocks.json` (step 3),
   `python scripts/run.py --resume donors/<id> --no-translate`.
5. Result: `donors/<id>/index.html` (open locally) and `donors/<id>/donor.json` (data for editing tasks).
6. Before reporting: check stats honestly (ratio below 1 = weak donor), open 3 frames and confirm they match the words,
   say if the translation was skipped because of the Groq daily limit.

Self-test without internet: `python scripts/test_razbor.py scripts` → `0 failed` (needs ffmpeg; Node.js optional).

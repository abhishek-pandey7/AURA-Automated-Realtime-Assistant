# Changelog

All notable changes to AURA will be documented here.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [0.2.1] - 2026-10-24

### Changed
- Published on PyPI as `aura-autonomous-agent` (PyPI rejected `aura-agent` as too similar to an existing project)
- README rewritten around the PyPI package and library API
- Package author metadata lists Abhishek Pandey

---

## [0.2.0] - 2026-10-24

### Added
- `aura.Agent` Python API: `Agent(api_key=..., base_url=..., model=...).run(goal)`, plus `plan()`, `tools` and `add_tool()`
- `register_tool` / `@agent.add_tool` to expose your own Python functions as tools, with the schema built from the signature
- `approve=` callback to replace the interactive Y/N prompt in scripts
- Optional extras: `browser`, `desktop`, `voice`, `google`, `all`
- `AURA_HOME`, `AURA_CHROME_PROFILE` and `AURA_USER_NAME` settings
- `tests/test_library.py` (runs with a fake LLM client, no API key needed)

### Changed
- Importing `aura` no longer requires an API key; the check happens when an `Agent` is created and raises `aura.ConfigError`
- LLM clients are created on first use instead of at import time
- Tools load on first use; tools whose optional dependencies are missing are skipped
- Watch-and-learn saves generated tools to `~/.aura/tools` instead of inside the package
- Google credentials and the form profile fall back to `~/.aura` when not in the source checkout
- `.env` is also read from the current directory and `~/.aura/.env`

### Fixed
- Non-editable installs now include the `aura.tools` subpackage
- Browser tool no longer hardcodes one machine's Chrome profile path
- Spoken completion message no longer hardcodes a user name

---

## [0.1.0] — 2026-04-19

### Added
- Interactive REPL (`aura run`) with ASCII welcome screen
- Single-goal non-interactive mode (`aura run "goal"`)
- Upfront task planner — breaks goals into ordered subtasks
- Core observe→think→act agent loop with tool calling
- **Shell tool** — bash with timeout and stderr capture
- **Filesystem tools** — read, write, patch, list, delete
- **Web tools** — search (no API key) and fetch with HTML-to-text
- **Browser tools** — headless Playwright (navigate, click, fill, screenshot)
- Session memory — persist and resume past conversations
- Safe mode — Y/N confirmation before writes, shell, and deletes
- `/help`, `/clear`, `/sessions`, `/resume`, `/tools`, `/cwd`, `/exit` REPL commands
- `install.sh` one-shot setup script

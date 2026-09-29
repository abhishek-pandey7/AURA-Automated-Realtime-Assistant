# AURA — Interview Prep

> Everything below is grounded in the actual code. File references are real —
> open them while you rehearse. Anything I couldn't infer from the source is
> marked **[confirm with me]** rather than guessed.
>
> Role/level is deliberately left generic. The material leans backend /
> systems-engineering, because that's what the codebase actually is.

---

## Table of contents

1. [Project pitch](#1-project-pitch)
2. [System design concepts I actually used](#2-system-design-concepts-i-actually-used)
3. [Framework and tech-stack choices](#3-framework-and-tech-stack-choices)
4. [If this scales](#4-if-this-scales-10x-100x)
5. [Weak spots](#5-weak-spots-an-interviewer-will-poke-at)
6. [15 likely questions with model answers](#6-fifteen-likely-questions)

---

## 1. Project pitch

### The 60-second version

> AURA is an autonomous CLI agent that does things on your machine instead of
> telling you how to do them. You type a goal in plain English — "schedule a
> Meet with my team tomorrow at 10 and email them the link" — and it plans the
> work, then executes it with real tools: shell commands, file edits, web
> search, Playwright browser control, the Gmail and Calendar APIs, and raw
> mouse-and-keyboard desktop control driven by on-screen OCR.
>
> The interesting part isn't the LLM call. It's the harness around it. There's a
> planner that decomposes a goal into subtasks, a ReAct-style observe-think-act
> loop that keeps calling tools until the task is actually done, a plugin-style
> tool registry that auto-discovers tools at import time, a human-in-the-loop
> confirmation gate on anything destructive, and a "watch and learn" mode where
> it records your real clicks and keystrokes and has a vision model write a new
> reusable tool from that trace — which it then hot-registers into its own
> toolchain at runtime.
>
> It's model-agnostic: it talks to any OpenAI-compatible endpoint, so I ran it
> against an open-weight model behind a LiteLLM proxy rather than a frontier API.

**Timing note:** that's about 55 seconds spoken at a normal pace. If you're
running long, cut the last paragraph — but keep "the interesting part isn't the
LLM call, it's the harness." That's the sentence that separates you from someone
who wrapped a chat completion.

### The 3-minute version

**Start with the problem (~30s).**

> There are two kinds of AI assistant and neither one was what I wanted. A chat
> assistant explains what you should do — you still do it. A cloud coding agent
> can edit files and run tests, but it lives in a sandbox: it can't touch your
> desktop, your logged-in browser session, your Gmail, or any app that doesn't
> expose an API. So the boring, high-friction half of real computer work —
> filling the same form for the fifth time, scheduling the meeting, clicking
> through an app that has no API — stays manual.
>
> AURA is my attempt at closing that gap: an agent that operates the computer
> the way I do, locally, with my credentials and my session state.

**Then the architecture, as a pipeline (~90s).**

> The flow is: goal → plan → loop → tools → memory. Five pieces.
>
> **Entry** is `aura/cli.py`, installed as a console script via `pyproject.toml`.
> It either runs one goal and exits, or drops into a REPL in `aura/ui.py` with
> slash-commands — `/voice` for microphone input, `/learn`, `/resume`, `/tools`.
>
> **Planning** is a separate, deliberately small LLM call in `aura/planner.py`.
> It's a different model invocation from the executor, with its own system
> prompt, low temperature, a 512-token cap, and one job: turn the goal into a
> JSON list of at most ten concrete subtasks. Crucially it's a *soft* dependency
> — if the planner fails or returns garbage, `plan()` falls back to treating the
> whole goal as a single task. The agent still runs.
>
> **Execution** is `aura/agent.py` — the core. It's a ReAct loop: call the model
> with the full conversation plus every tool schema, and if the response contains
> tool calls, execute them, feed the results back as `role: "tool"` messages, and
> go around again. If the model responds with *no* tool calls, that's the
> termination signal — the task is done. It's bounded at 30 iterations so a
> confused model can't burn tokens forever.
>
> **Tools** live in `aura/tools/`. That package is a plugin registry: on import
> it walks its own directory with `pkgutil`, imports every module, and looks for
> a `TOOL_DEFS` or `TOOL_DEF` constant plus a matching function name. Drop a
> correctly-shaped `.py` file in that folder and the tool exists. No central list
> to edit. That's what makes the watch-and-learn feature possible at all.
>
> **Memory** is `aura/memory.py` — one JSON file per session under
> `~/.aura/sessions/`, written through on every message append, so a crash or a
> Ctrl-C mid-task leaves a resumable session on disk.

**Close with the two things that are genuinely yours (~45s).**

> Two parts I'm most pleased with.
>
> First, **desktop perception**. Rather than hardcoding coordinates, AURA calls
> `desktop_read_screen`, which screenshots the display and runs it through the
> native Windows OCR engine via `winsdk`, returning every visible text line with
> its pixel centroid — effectively a spatial map of the screen. The model reads
> that map and clicks by coordinate. Local OCR, no API call, no token cost for
> perception. There's a vision-model fallback, `desktop_analyze_screen`, for when
> the screen is graphical rather than textual.
>
> Second, **imitation learning**, in `aura/learning.py`. You run `aura learn
> "check my bank balance"`, do the task by hand once, and `pynput` records every
> click and keystroke with timestamps. That trace plus before/after screenshots
> goes to a vision model, which writes a self-contained `pyautogui` script with a
> proper tool schema. AURA writes it into `aura/tools/`, re-runs the registry
> scan, and the tool is live in the same session — the agent extends its own
> capabilities at runtime. Three of the tools in the repo were generated that
> way.

**If you have 20 more seconds, land the honest caveat yourself:**

> The tools it generates are coordinate-based macros, so they're brittle — they
> break if the window moves. That was the tradeoff I took to get self-extension
> working at all, and the fix I'd build next is to have the generator emit OCR
> anchors instead of raw pixels.

Saying that unprompted buys you a great deal of credibility. Do it.

---

## 2. System design concepts I actually used

> Each one: what it is, where it is in *your* code, why you probably chose it,
> what you could have done instead, and what you gave up.
> Plain-English teaching for all of these is in
> [CONCEPTS_EXPLAINED.md](CONCEPTS_EXPLAINED.md).

### 2.1 Agent loop / ReAct pattern (observe → think → act)

**Where:** `aura/agent.py:110` — `for iteration in range(max_iterations)`.
Inside: LLM call at `:118`, termination check at `:156`
(`if not message.tool_calls`), tool dispatch at `:213`, results appended as
`role: "tool"` messages at `:235`.

**What it is.** Instead of asking the model for one answer, you put it in a loop.
Each turn it sees the whole history plus the result of whatever it last did, and
either calls another tool or declares itself finished. Reasoning and acting
interleave — that's the "Re" and "Act" in ReAct.

**Why you chose it.** The loop is the only way to get self-correction, and
self-correction is the entire value proposition — your own README demo shows it
running pytest, seeing a failure, patching the file and re-running. You can't do
that in a single-shot call because the model needs to *see* the failure. Your
system prompt makes it explicit at `aura/agent.py:38`: *"If a command fails, read
stderr, identify the cause, fix it, and retry automatically."*

**Alternatives you could have used.**

- *Single-shot codegen* ("write me a script that does X"). Simpler, one API call,
  cheap. But it's blind: no feedback from reality, so any wrong assumption about
  the environment silently produces broken output. Dead on arrival for desktop
  work, where you can't know what's on screen ahead of time.
- *A fixed state machine / DAG* of predetermined steps. Far more predictable and
  much easier to test, and if AURA only did Gmail and Calendar I'd argue it's the
  better design. It fails the moment the task space is open-ended — you cannot
  enumerate the states of "operate an arbitrary GUI."

**Trade-offs you accepted.**

- **Non-determinism.** Same goal, different tool sequence each run. Hard to test,
  hard to reproduce a bug.
- **Cost grows quadratically-ish.** Every iteration resends the whole history, so
  a 20-step task is dramatically more expensive than 20 independent calls.
- **A termination signal you don't fully control.** "No tool calls" means done —
  but a model that gives up early looks identical to a model that succeeded. You
  have no success *verification*, only a stop condition.
- **The 30-iteration cap is a blunt instrument.** It prevents runaway loops but
  truncates genuinely long tasks with a vague "Task may be incomplete"
  (`agent.py:254`).

---

### 2.2 Plugin registry with runtime auto-discovery

**Where:** `aura/tools/__init__.py` in full. `pkgutil.iter_modules` at `:14`,
`importlib.import_module` at `:17`, schema harvesting at `:21-24`, name→function
dispatch map built at `:32-35`, and `_init_tools()` callable again for hot reload
(used from `aura/learning.py:166`).

**What it is.** Rather than a hand-maintained list of tools, the package scans
its own directory at import time, imports each module, and registers anything
matching a convention: a `TOOL_DEFS` list (or singular `TOOL_DEF`) of JSON
schemas, plus a module-level function whose name matches the schema's
`function.name`. Convention over configuration.

**Why you chose it.** Two reasons, and one of them is forced. The soft reason is
ergonomics — 13 tool modules with zero central registration. The hard reason:
**imitation learning literally cannot work without it.** `aura/learning.py`
writes a brand-new `.py` file into the tools directory at runtime and then calls
`aura.tools._init_tools()` to make it live. If the registry were a static dict
you'd have to edit source code and restart. Self-extension requires dynamic
discovery. That's a strong, honest answer to "why not just a dict?"

**Alternatives you could have used.**

- *An explicit dict / registry decorator* (`@register_tool`). Much safer: import
  errors surface loudly, you can see every tool in one place, static analysis
  works, IDEs can follow it. But it blocks runtime self-extension, which is the
  differentiating feature.
- *Python entry points* (`importlib.metadata`), the setuptools-native plugin
  mechanism. Genuinely the "correct" answer for a distributable package and worth
  naming so the interviewer knows you know it. Too heavy here: it needs a
  reinstall to pick up a new plugin, which again kills the runtime-generation
  story.

**Trade-offs you accepted.**

- **`except Exception: pass` at `aura/tools/__init__.py:36-37` swallows every
  import error.** One typo in a generated tool and it silently doesn't exist. No
  log, no warning. This is the single highest-value five-line fix in the
  codebase — log the module name and exception.
- **Import-time side effects.** Importing `aura.tools` imports thirteen modules,
  which pulls in `pyautogui`, `playwright`, `winsdk`. Slow startup, and any
  module with a hard import-time dependency on Windows breaks silently on Linux.
- **Implicit contract.** The "function name must equal schema name" rule exists
  nowhere but in code — and you already needed a special case for it at `:34`
  (`shell.py` exposes `run` but the tool is called `bash`). That special case is
  evidence the convention was too tight.

---

### 2.3 Separation of planning from execution (two-stage LLM pipeline)

**Where:** `aura/planner.py` (its own `OpenAI` client at `:8`, its own
`PLANNER_SYSTEM` prompt at `:14`, `max_tokens=512`, `temperature=0.2`). Called
from `aura/ui.py:227` and `aura/cli.py:82`, then each returned task is fed to
`agent.run_agent()` in sequence (`ui.py:248`).

**What it is.** Decomposition and execution are two different model calls with
different prompts, different temperatures, and different token budgets. The
planner only produces a JSON list of subtasks; it has no tools and cannot act.

**Why you chose it.** Two effects, both visible in the code. It gives the user a
**plan to look at before anything happens** — `ui.py:230` renders it in a panel,
which is a real UX and trust feature for an agent that's about to control your
mouse. And it keeps each executor context focused: the executor gets one subtask
at a time rather than a sprawling goal, which reduces drift. Lower planner
temperature (0.2 vs the executor's 0.3, `agent.py:127`) says you wanted planning
to be the stable, repeatable half. **[confirm with me]** whether the visible-plan
UX or the context-focusing was the actual motivation — the code supports both.

**Alternatives you could have used.**

- *Let the executor plan implicitly.* One less call, one less failure mode, and
  honestly for simple goals the ReAct loop plans fine on its own. You lose the
  displayed plan and the per-subtask context reset.
- *A full hierarchical planner with replanning* — re-plan after each subtask
  based on what actually happened. Strictly more capable, and it fixes the real
  flaw below. Much more complexity and cost; you'd need to decide when replanning
  is warranted, or you'd replan constantly.

**Trade-offs you accepted.**

- **The plan is frozen.** It's computed once, up front, from zero knowledge of
  the environment. If subtask 2 reveals the plan was wrong, subtasks 3–5 still
  run as written. This is the most substantive design critique of AURA and you
  should name it before they do.
- **Extra latency and cost on every goal**, including trivial ones. Your prompt
  mitigates this — "if the goal is simple, use 1 task" (`planner.py:31`) — but
  you still pay a round trip.
- **Shared memory across subtasks papers over some of it.** All subtasks append
  to the same `Memory` object (`ui.py:248` passes the same instance), so later
  subtasks *can* see what earlier ones did. That's a genuinely good detail —
  mention it as partial mitigation, not a fix.

---

### 2.4 Human-in-the-loop confirmation gate (defence in depth)

**Where:** `aura/confirm.py` entirely. Deny-list `ALWAYS_CONFIRM_PATTERNS` in
`aura/config.py:28-32`. Enforced at the *tool* layer, not the agent layer:
`shell.py:37`, `filesystem.py:103` (write), `:123` (patch), `:153` (delete),
`browser.py:115`, `desktop.py:144`.

**What it is.** Risky actions ask the user Y/N before executing. Two independent
controls: a global `SAFE_MODE` flag from the environment (`config.py:15`) and a
substring deny-list of patterns that prompt *regardless* of SAFE_MODE —
`rm `, `sudo`, `dd `, `mkfs`, `shutdown`, `git push`, `pip install`, and a fork
bomb. `confirm_delete` passes `force=True` (`confirm.py:72`), so deletion is
unconditionally gated.

**Why you chose it.** You gave an LLM `subprocess.run(shell=True)` on your own
machine (`shell.py:44-51`). The confirmation gate is the only thing between a
hallucinated command and your filesystem. The fact that it's enforced inside each
tool rather than once in the agent loop is the right call and worth stating
explicitly: a tool can never be invoked *around* its own safety check, so a
future code path that calls `filesystem.delete_file` directly is still protected.
That's defence in depth.

**Alternatives you could have used.**

- *An allow-list instead of a deny-list.* Strictly more secure — enumerate what's
  permitted, refuse everything else. You'd have had to give up general-purpose
  `bash`, which is most of the agent's power. Defensible either way; say you
  chose usability and know the cost.
- *Sandboxing / containerisation* — run the agent in Docker or a VM, drop
  confirmations entirely. This is the actually-correct answer for an untrusted
  agent, and your README lists it as future work. It's incompatible with the
  whole point of AURA: it needs your real desktop, your real logged-in Chrome
  profile, your real Gmail token. Sandboxing would remove exactly the capability
  that makes it different from a cloud coding agent. Frame it as a *deliberate*
  trade, not an oversight.

**Trade-offs you accepted.**

- **Substring matching is trivially bypassable.** `"rm "` doesn't catch
  `Remove-Item`, `rm -rf` with a tab, `$(echo rm) file`, or any PowerShell
  equivalent — and this is a *Windows* project where `Remove-Item` is the native
  spelling. Real hole, know it.
- **`confirm_desktop` auto-approves by default** (`confirm.py:84-86`) — it prints
  a dim line and returns `True` without asking. So mouse and keyboard control,
  arguably the most dangerous surface, is the *least* gated. That was clearly a
  usability decision (a task needs 30 clicks; 30 prompts is unusable) but it's
  the first thing a security-minded interviewer will find.
- **Confirmation fatigue.** Any gate a user clicks through 50 times a day stops
  being a gate.

---

### 2.5 Retry with exponential backoff and graceful degradation

**Where:** `aura/agent.py:116-146` — three attempts, 5s then 10s backoff, with an
explicit retryable-error classifier at `:135-139` (502/500/503, timeout,
connection, read error). Same pattern independently in `aura/planner.py:46-69`.
Generous client timeouts set deliberately at `agent.py:21-25` with a comment
naming the cause: *"Render free-tier can be slow on cold starts."*

**What it is.** Transient failures get retried with increasing waits; permanent
failures (a 401, a bad model name) fail fast instead of wasting 15 seconds. And
when retries are exhausted, the system degrades rather than crashing —
`planner.py:87` returns `[goal]` as a single task so execution still proceeds.

**Why you chose it.** This one is documented rather than inferred: you were
running against a self-hosted LiteLLM proxy on a free tier that cold-starts. The
retries are scar tissue from real failures. That's a *good* story to tell — it
shows the numbers came from observed behaviour, not from a blog post.

**Alternatives you could have used.**

- *A library* — `tenacity`, or `openai`'s own `max_retries`. Less code, better
  tested, includes jitter. Your hand-rolled version does have one thing the
  built-in doesn't: it retries on *timeouts*, which the SDK treats differently,
  and timeouts were your actual failure mode. **[confirm with me]** whether that
  was the reason or whether it was just written before you looked at the SDK
  option.
- *A circuit breaker.* Right answer if many callers share one flaky dependency —
  stop hammering a downed service. Overkill for a single-user CLI with one
  upstream.

**Trade-offs you accepted.**

- **No jitter.** Irrelevant with one client; would cause thundering-herd sync if
  AURA were ever multi-instance.
- **Substring error classification is fragile** — `"500" in err_str` matches an
  error message that merely mentions 500 tokens.
- **Duplicated logic** in `agent.py` and `planner.py`, already drifting (the
  agent checks `"read error"`, the planner doesn't).
- **Worst case is a 15+ second silent stall** before the user sees anything —
  though you do print a retry notice at `agent.py:142`, which is the right call.

---

### 2.6 Write-through persistence with resumable sessions

**Where:** `aura/memory.py`. `_save()` at `:49` is called from `add_user`,
`add_assistant`, and directly from the agent after every tool batch
(`agent.py:189`, `:251`). One JSON file per session in `~/.aura/sessions/`, keyed
by a timestamp session id (`memory.py:21`). `/resume` in `ui.py:136-143`
reconstructs a `Memory` from that file.

**What it is.** Conversation state is flushed to disk on every mutation rather
than at the end. Combined with the fact that messages are stored in exactly the
wire format the API expects — note the care at `agent.py:173-187`, keeping
`tool_calls` as raw dicts with `arguments` left as a JSON *string* — a session
file can be reloaded and sent straight back to the model.

**Why you chose it.** An agent that controls a desktop gets killed mid-task
constantly: a bad click, Ctrl-C, `pyautogui`'s FAILSAFE corner trip.
Write-through means the transcript survives. **[confirm with me]** whether
resumability was the goal or whether it fell out of debugging (being able to read
the session JSON after a weird run is enormously useful, and I suspect that was
at least part of it).

**Alternatives you could have used.**

- *In-memory only, save on exit.* Fewer writes, trivially simpler. You lose
  everything on a crash — and crashes are the normal case here.
- *SQLite.* Ships with Python, gives you real queries, indexed search across
  sessions, atomic transactions, and no full-file rewrite. If you were adding
  cross-session search or long-term memory, this is where I'd go. Overkill for
  append-only single-session transcripts, and JSON files are `cat`-able and
  diffable while debugging — which for a project at this stage is a real feature.

**Trade-offs you accepted.**

- **O(n²) write amplification.** `_save()` re-serialises the *entire* message
  list every time. A 50-message session with screenshots rewrites megabytes
  repeatedly. Append-only JSONL would fix it.
- **Not atomic.** `open(path, "w")` truncates first (`memory.py:50`). Crash
  mid-write and you have a corrupt session, and `_load` will throw. Write to a
  temp file and `os.replace` — that's a two-line fix.
- **Unbounded growth, no compaction.** The full history goes into every LLM call
  with no trimming or summarisation, so long sessions will eventually exceed the
  context window and there's no handling for that. Base64 screenshots make it
  worse — you *do* strip them from the tool message (`agent.py:232`) which shows
  you saw the bloat problem, but the image still lives in the following user
  message forever.
- **`list_sessions()` hard-caps at 10** (`memory.py:70`) and opens every file to
  read metadata.

---

### 2.7 Perception via local OCR, with a vision fallback (tiered strategy)

**Where:** `aura/tools/desktop.py:212` (`desktop_read_screen`), `:269`
(`desktop_find_text`), `:320` (`desktop_analyze_screen`). The OCR path uses
`winsdk.windows.media.ocr.OcrEngine`; centroids computed from word bounding boxes
at `:247-250`. The async-to-sync bridge is at `:262-264` —
`ThreadPoolExecutor(1)` running `asyncio.run`.

**What it is.** Screenshot the display, run the *native Windows* OCR engine over
it, and return every text line with an (x, y) pixel centroid — a machine-readable
map of the screen. The model then clicks by coordinate. Cheap text perception
first; only escalate to sending an actual image to a vision model
(`desktop_analyze_screen`) when the screen is graphical rather than textual.

**Why you chose it.** Cost and latency. OCR is local, free, and fast; vision
tokens are neither. Your system prompt enforces the order explicitly —
"PERCEPTION FIRST" and "Never guess coordinates" (`agent.py:86-87`). The tiering
is deliberate, not accidental.

**Alternatives you could have used.**

- *Accessibility APIs* (UI Automation on Windows, AT-SPI on Linux). This is the
  technically superior approach: you get the real widget tree — element types,
  roles, states, stable handles — rather than guessing structure from pixel
  positions. A button is a button, not a text label at (400, 250). Much more
  work, doesn't cover apps that render custom UI (Electron, games, canvas), and
  is deeply platform-specific. Worth naming as your "what I'd build next" for
  desktop.
- *Vision model for everything.* Simpler code, handles icons and images that OCR
  can't see at all. Every perception step becomes an expensive high-latency API
  call, and coordinate precision from a VLM is unreliable. You made the right
  call here.

**Trade-offs you accepted.**

- **Hard Windows lock-in.** `winsdk` is Windows-only. `pyproject.toml` guards the
  dependency with `sys_platform == 'win32'`, so on Linux the import fails, the
  registry silently swallows it (§2.2), and `desktop_*` just doesn't exist —
  with no message explaining why.
- **OCR is blind to non-text.** Icons, images, unlabeled buttons. Hence the
  fallback.
- **Centroid-clicking is an approximation.** The centre of a *text line* is not
  the centre of its clickable control. Works for buttons with labels, breaks for
  wide rows or text offset from its hit area.
- **No coordinate/DPI normalisation** — raw pixels, so multi-monitor and display
  scaling are unhandled.
- **The threadpool-around-asyncio bridge** (`:262`) is a workaround for calling
  async WinRT from sync tool functions. It works, it's a bit of a smell, and it
  creates and destroys a thread pool on every single screen read.

---

### 2.8 Runtime code generation from recorded behaviour (imitation learning)

**Where:** `aura/learning.py` end to end. `Recorder` with `pynput` listeners at
`:49-50`, timestamped event trace at `:31-38`, ESC to stop at `:41`, downscaled
JPEG screenshots at `:72-80`, multimodal codegen prompt at `:90-118`, fence
stripping at `:145-151`, function-name extraction by regex at `:153`, write into
the tools package at `:162-165`, hot reload at `:166`. Three generated tools are
committed: `check_bitcoin_price_coinmarketcap.py`, `skip_youtube_ads.py`,
`jiohotstar.py`.

**What it is.** Demonstrate a task once by hand. The recorder captures the input
trace plus before/after screenshots. A vision-language model turns that into a
self-contained Python module containing both a tool schema and a `pyautogui`
implementation. AURA writes the file into its own tools directory and re-runs
discovery, so the capability is available immediately — in the same process.

**Why you chose it.** It's the answer to the hardest case in desktop automation:
an app with no API where even OCR-driven navigation is unreliable or slow.
Rather than the developer writing every integration, the *user* teaches it by
doing. It's also what makes the plugin registry (§2.2) pay for itself.

**Alternatives you could have used.**

- *Replay the raw trace directly*, no LLM. More faithful and fully
  deterministic — a plain macro recorder. But you get no parameterisation and no
  generalisation: the trace hardcodes the literal text you typed, so
  `jiohotstar_play` couldn't take a `query` argument. The LLM's job is to
  *abstract* the trace into a function with parameters, and you can point at
  `jiohotstar.py:23` as proof it worked: it condensed character-by-character
  keystrokes into a single `pyautogui.write(query)` with a real parameter.
- *Have the model write Playwright/Selenium code instead of pyautogui.* Far more
  robust for anything in a browser — real selectors instead of pixels. Doesn't
  cover native apps, which is the case you built this for.

**Trade-offs you accepted.**

- **This executes LLM-generated code with zero review.**
  `file_path.write_text(code)` then import. No sandbox, no AST check, no diff
  shown to the user. It is the most serious security property of the project and
  you should say so plainly before anyone asks.
- **Generated macros are coordinate-brittle.** Look at
  `check_bitcoin_price_coinmarketcap.py:27` — `pyautogui.click(1287, 1052)`. That
  breaks on a different resolution, a moved window, or a shifted page layout. It
  also emitted `pyautogui.press('cmd')` on a Windows machine, i.e. the model got
  the platform wrong.
- **`time.sleep()` instead of waiting for state.** Fixed 5-second sleeps
  (`:33`) are a race condition, not a synchronisation primitive.
- **Fragile parsing of the output** — regex for the first `def` (`:153`) and
  manual fence-stripping. No validation that the emitted `TOOL_DEFS` name matches
  the function, which is the one invariant the registry requires.
- **Fixed 60s recording window** with no pause.

---

### 2.9 Lazy initialisation and a module-level singleton for expensive resources

**Where:** `aura/tools/browser.py` — `BrowserSession._ensure_started()` at `:80`
(guarded by `if self._page is None`), module-level `_session` singleton at `:184`,
accessor `_get_session()` at `:187`. Every public tool function goes through it
(`:196-209`).

**What it is.** The Playwright browser is not started when the module is
imported; it's started on the first tool call that needs it, and then reused for
the rest of the session. One browser per AURA process.

**Why you chose it.** Launching Chromium takes seconds and hundreds of megabytes,
and most AURA tasks never touch the browser — so paying that cost at import time
would slow *every* startup. Reusing one session also preserves navigation state
across tool calls, which matters because your tool design assumes it:
`browser_click` operates on "the current page," which only means something if the
page persisted from the previous `browser_navigate`.

**Alternatives you could have used.**

- *Eager initialisation at import.* Predictable — you learn immediately if the
  browser is broken rather than mid-task. Unacceptable startup cost for a CLI
  that usually doesn't need it.
- *A fresh browser per call.* Clean isolation, no shared state, no leaks. Breaks
  the stateful tool API entirely and would cost seconds per call.

**Trade-offs you accepted.**

- **Global mutable state.** A module-level singleton is untestable without
  monkeypatching and not thread-safe — two concurrent calls could both see
  `_page is None` and launch two browsers. Fine for a single-threaded CLI; a real
  problem if AURA ever runs tasks in parallel.
- **First call is mysteriously slow**, which the model may interpret as a
  failure.
- **`close_browser()` at `:211` is never called from anywhere in the codebase.**
  The browser leaks until the process dies. Worth admitting.
- **The three-tier fallback at `:88-112`** — CDP connect, then persistent Chrome
  profile, then clean Chromium — is genuinely good engineering (graceful
  degradation with actionable user messaging at `:107-109`) sitting right next to
  a hardcoded absolute path at `:85`. Same function. Point at both.

---

### 2.10 Prompt-as-configuration / declarative tool contracts

**Where:** `SYSTEM_PROMPT` at `aura/agent.py:27-93`, runtime-templated with OS,
shell, cwd and current time at `:106`. Every tool module carries its own
JSON-Schema `TOOL_DEFS`. `PLANNER_SYSTEM` at `planner.py:14`.

**What it is.** Agent behaviour is specified in prose and schemas rather than
control flow. The tool schemas are the API contract the model programs against;
the system prompt encodes policy — "never use smtplib, always use `gmail_send`"
(`:62`), "never call bash just to get the date" (`:58`), "PERCEPTION FIRST"
(`:86`). Injecting the current time into the prompt is a nice touch: it removes
an entire class of wasted tool call.

**Why you chose it.** Each of those CRITICAL rules is almost certainly a bug you
watched happen. The model reached for `smtplib`, or burned an iteration shelling
out for the date, and you fixed it in the prompt instead of in code — because
that's the fastest available lever. That's a legitimate and very common way to
steer an agent. Say it that way: *"these rules are a changelog of failures I
observed."*

**Alternatives you could have used.**

- *Enforce in code.* Intercept in `dispatch()` and refuse a `bash` call
  containing `smtplib`. Deterministic — a prompt rule is a *suggestion* the model
  can ignore, a code check can't be. More brittle to write, and it fails closed
  in ways that surprise users.
- *Fine-tuning* on your tool-use traces. Better instruction adherence, shorter
  prompts, lower per-call cost. Needs data, training infrastructure, and it
  re-couples you to one model — which defeats the OpenAI-compatible
  model-agnosticism you deliberately built for.

**Trade-offs you accepted.**

- **Prompt rules are unenforced.** Nothing stops the model writing an smtplib
  script. You're relying on compliance.
- **A ~70-line system prompt is sent on every iteration of every task**, and it
  grows every time you find a new failure mode. That's real token cost multiplied
  by iteration count.
- **Every tool schema is in the context whether relevant or not.** 30-plus tools
  means a large fixed prompt overhead even for "read this file."
- **Prompt rules are untestable.** No assertion can tell you rule 14 still works
  after you add rule 15.

---

## 3. Framework and tech-stack choices

Be ready for "why X and not Y" on each of these. Note honestly up front: **this
project has no database, no cache, no message queue, and no web framework**,
because it's a local single-user CLI. Not having them is the correct design, and
saying so confidently is better than pretending otherwise.

### Python

**Pros.** The only language where every capability you needed already exists as a
mature library: `pyautogui` for input synthesis, `pynput` for hooks, `playwright`,
`winsdk` for WinRT OCR, Google's API clients, the `openai` SDK. In any other
language at least two of those would be a bindings project. Fast iteration for a
hackathon-pace build.

**Cons.** Startup latency (§2.2 — importing 13 modules pulls in heavy native
deps). No static typing on the tool boundary, so `dispatch(**inputs)` failing is
a runtime `TypeError` you handle by returning an error string
(`tools/__init__.py:47`). Distribution is genuinely painful — hence
`install.sh`/`install.bat` existing at all. The GIL would bite if you ever
parallelised tool calls.

**Alternative.** Go or Rust would give you a single static binary and real
concurrency — which actually matters for a tool users must install. You'd be
writing OCR and input bindings yourself. Wrong trade for this project.

### OpenAI SDK against an OpenAI-compatible endpoint (not the OpenAI API)

**Where:** `aura/config.py:12-14` — `INFERX_BASE_URL`, `INFERX_MODEL`, default
`gemma-4-31b`. Client construction at `agent.py:21`, `planner.py:8`,
`learning.py:83`.

**This is your best architecture answer and you should volunteer it.** You used
the OpenAI *SDK* as a protocol client, pointed at a self-hosted LiteLLM proxy
serving an open-weight model. You get the de-facto-standard function-calling
interface and a mature SDK, while the actual model is swappable by changing an
environment variable. Model-agnostic by construction.

**Pros.** Provider independence; no vendor lock-in. Function calling is the
industry-standard shape, so tool schemas port. Open-weight models mean no
per-token cost and data never leaves infrastructure you control — which for an
agent that screenshots your desktop and reads your inbox is a substantive privacy
argument, not a footnote. Make that point.

**Cons.** You're bound to whatever the proxy implements. Smaller open models have
weaker tool-use reliability, and your code is visibly shaped by that — the
markdown-fence-tolerant JSON parsing at `agent.py:200-210` and the same in
`planner.py:73-78` exist because the model wrapped tool arguments in code fences.
That's compensating for model weakness in the harness. Self-hosting means you own
the uptime, which is exactly why §2.5's retry logic exists. And you can't use
provider-specific features — no prompt caching, which would materially cut cost
given a 70-line system prompt resent every iteration.

**Alternatives.** *Anthropic or OpenAI APIs directly* — better tool-use
reliability and prompt caching, at per-token cost and with lock-in. *LangChain /
LlamaIndex* — you'd have got the agent loop, tool abstraction, and memory for
free. But you'd have given up understanding of your own control flow, and for an
interview the fact that you hand-rolled the ReAct loop is worth much more than
having used a framework. Say that: *"I wrote the loop myself specifically so I'd
understand it."*

### Rich (terminal UI)

**Where:** `aura/ui.py`, plus per-tool colour-coding in `agent.py:258-276`.

**Pros.** For an agent that runs 30 opaque steps, legibility *is* trust. Panels,
the live "AURA is thinking" spinner (`agent.py:113`), colour per tool type,
output truncated to 25 lines with a "... N more lines hidden" marker
(`agent.py:313-328`) — all of that is what makes autonomous execution followable.
Cheap to add.

**Cons.** Markup is embedded in logic strings, so presentation and behaviour are
tangled — `confirm.py` mixes Rich markup into the same functions that make the
security decision. Output isn't machine-parseable, which blocks scripting AURA
into a pipeline. `console.input()` gives you no readline: no history, no
tab-completion, no arrow keys in the REPL — noticeable for a tool you type into
all day.

**Alternatives.** *`prompt_toolkit`* would fix the input side (history,
completion) — arguably the bigger win for a REPL. *Textual* for a full TUI with
panes; overkill. *Plain print* — you'd lose the legibility that makes the agent
trustworthy.

### Playwright (browser) over Selenium

**Where:** `aura/tools/browser.py`.

**Pros.** Auto-waiting, so you don't hand-write sleeps. `connect_over_cdp`
(`:89`) lets you attach to the user's *already-running* Chrome, and
`launch_persistent_context` with a real `user_data_dir` (`:97-102`) gives you
their cookies and logins — which is the entire reason browser automation is
useful here, versus a clean profile that's logged into nothing. Bundled browsers,
no driver-version hell.

**Cons.** Heavy install (`playwright install` downloads browsers). The
`sync_playwright` API is awkward to hold alongside anything async. Profile
locking is a real failure mode you had to handle — Chrome can't have two
processes on one profile dir, hence the three-tier fallback and that apologetic
message at `:107`.

**Alternatives.** *Selenium* — more ubiquitous, worse ergonomics, manual waits,
driver management. *`requests` + BeautifulSoup*, which you also have in
`tools/web.py` — right for static pages and much cheaper, wrong for anything
JS-rendered or authenticated. Having both tiers is the correct answer and worth
framing that way: cheap HTTP first, real browser when you need a real browser.

### JSON files for state (no database)

**Where:** `~/.aura/sessions/*.json` (`memory.py`), `user_profile.json`
(`forms.py:19`), `token.json` (OAuth cache).

**Pros.** Zero dependencies, zero schema migrations, human-readable and diffable
during debugging, trivially backed up. Correct for single-user single-writer
append-only data.

**Cons.** No atomicity (§2.6), no concurrent access, no query capability, and
O(n) rewrites. `user_profile.json` holds PII in plaintext. `token.json` holds a
live OAuth refresh token in plaintext in the project directory — gitignored,
which is right, but still a credential sitting on disk unencrypted.

**Alternatives.** *SQLite* — right call the moment you want cross-session search
or long-term memory, and it ships with Python. *A vector DB* (Chroma, FAISS) for
semantic recall over past sessions, which your README lists as future work and is
the natural next step. *Postgres / anything networked* — wrong; there's no
server.

### No web framework, no queue, no cache, no load balancer

Say this plainly and don't apologise for it: *"AURA is a local process with one
user. The LLM endpoint is the only network dependency, and it's already behind a
proxy. Adding a queue or a cache would be architecture cosplay — there's no
concurrency to manage and nothing to fan out."* Then immediately pivot to
section 4, which is where those concepts legitimately enter.

---

## 4. If this scales (10x, 100x)

**Reframe the question first — do not skip this.**

> Worth being precise about what scaling means here, because AURA isn't a
> service. There's no RPS. Three different axes could grow, and they break in
> completely different places:
>
> 1. **Task complexity** — one goal that needs 200 tool calls instead of 20.
> 2. **Tool count** — 30 tools becoming 300, mostly via watch-and-learn.
> 3. **Users**, if I hosted it — which is the only axis where the classic
>    distributed-systems answers apply, and it's the one that requires a real
>    rewrite.
>
> Let me take them in that order.

### Axis 1: task complexity (10x longer tasks)

**Breaks first: the context window.** Every iteration resends the whole history
(`agent.py:121-124`) with no trimming. A tool result can be a 4000-char page
fetch (`web.py:62`) or a full OCR screen map. At roughly 20 iterations you're
near the limit of a mid-sized open model; at 200 you're far past it. The failure
is ugly, too — an API error, retried three times by §2.5's logic, then
`"Agent stopped"`. No graceful handling of "context exceeded" anywhere.

**What I'd add: context compaction.** Summarise older turns into a rolling
digest, keep the last N turns verbatim, and keep the original goal pinned. A
cheaper/smaller model can do the summarising.
**Trade-off:** summarisation is lossy and irreversible — compact away the wrong
detail and the agent forgets something it needed, producing a bug that's nearly
impossible to reproduce. Plus an extra LLM call at each compaction boundary.

**Second: the 30-iteration cap** (`agent.py:96`) silently truncates long work.
**What I'd add:** a token/cost budget instead of an iteration count, plus
checkpointing so a truncated task resumes rather than restarting.
**Trade-off:** budgets are harder to reason about than a plain counter, and
resumable state means more persistence complexity.

**Third: the frozen plan** (§2.3). At 10x complexity, a plan made with zero
environmental knowledge is essentially guaranteed to be wrong by step six.
**What I'd add:** replanning after each subtask, feeding actual results back into
the planner.
**Trade-off:** cost and latency on every subtask boundary, plus a new failure
mode — a replanning loop that oscillates between two plans and never converges.
You'd need a replan budget.

**Fourth: write amplification** (§2.6). O(n²) full-file rewrites, and `_save()`
runs after every tool batch. At 200 iterations with screenshots this is real disk
churn.
**What I'd add:** append-only JSONL plus atomic `os.replace`.
**Trade-off:** you lose the single-readable-document property that makes session
files nice to debug, and loading needs a parse loop.

### Axis 2: tool count (30 → 300 tools)

**Breaks first: the prompt.** *Every* tool schema goes in *every* request
(`agent.py:125`). 300 tools is tens of thousands of tokens of fixed overhead on
every iteration — and worse than the cost, tool-selection accuracy *degrades*
with choice. A small model picking from 300 similar tools will pick wrong.

**What I'd add: retrieval over tools** — embed the tool descriptions, and inject
only the top-k relevant to the current goal. This is RAG applied to the tool
registry, and `_init_tools()` is already the natural place to build the index.
**Trade-off:** a retrieval miss means the agent *cannot see* the tool it needs
and will confidently do something worse instead. That's a nastier failure than a
bloated prompt, and you'd want the core tools (bash, file ops) always pinned
regardless of retrieval.

**Also breaks: the silent-import-failure problem** (§2.2) goes from annoying to
untenable. With 300 mostly-generated modules, `except: pass` means you have no
idea what's actually loaded.
**What I'd add:** structured logging on registration failure, plus schema
validation at registration, plus a health-check command.
**Trade-off:** basically none. This is a pure win and the first thing I'd do.

**And: name collisions.** The registry is a flat dict (`tools/__init__.py:6`) —
two generated tools with the same name and the later import silently wins.
**What I'd add:** namespacing (`generated.check_bitcoin_price`) and collision
detection at registration.
**Trade-off:** longer tool names in the prompt; breaks any existing reference.

### Axis 3: multiple users (the hosted case)

This is where the classic answers finally apply — but be honest that it's a
**rewrite, not a scale-up**, because three things are fundamentally
single-tenant:

- **`~/.aura/sessions/`** is one directory for one user.
- **`_session` in `browser.py:184`** is a process-global singleton.
- **The desktop tools control *the* display.** There's one screen. `pyautogui`
  drives the physical mouse. This does not multi-tenant at all.

**Breaks first: shared desktop.** Two users, one mouse. Immediate corruption of
both tasks.
**What I'd add:** one isolated virtual desktop per session — a container with
Xvfb or a VNC-backed VM, which is exactly what your README's "Cloud-Native
Deployment" roadmap item points at.
**Trade-off:** a full GUI container per active user is expensive (hundreds of MB
of RAM, real CPU for screen capture and OCR), cold-start latency on session
creation, and you've now got container orchestration, image maintenance and
lifecycle management in a project that currently has none. This is the single
biggest cost in hosting AURA and it's why "local-first" was a reasonable choice.

**Then: no concurrency model.** The agent loop is synchronous and blocking, and
`subprocess.run` (`shell.py:44`) and `pyautogui` calls block the whole process.
**What I'd add:** a job queue — a session becomes a durable task, workers pull
from it, the CLI/UI becomes a thin client polling status. This is where a queue
genuinely earns its place.
**Trade-off:** you lose synchronous interactivity, which breaks the confirmation
gate (§2.4) — a worker can't call `console.input()`. You'd need async approval:
the job suspends, notifies the user, waits for a decision. That's a significant
redesign of your safety model, and worth saying out loud because it shows you
understand the coupling.

**Then: the LLM endpoint becomes the bottleneck.** One self-hosted open-weight
model serving N concurrent agent loops, each firing a request per iteration.
Inference is the expensive resource and it saturates fast.
**What I'd add:** request batching at the inference server (vLLM-style continuous
batching), horizontal replicas behind the proxy, per-user **rate limiting** so
one runaway 200-iteration loop can't starve everyone, and **caching** — both
prompt caching for the static system prompt and a semantic cache for repeated
planner calls on identical goals.
**Trade-off:** batching raises per-request latency to raise throughput. Rate
limiting means legitimate heavy tasks get throttled — and an agent that stalls
mid-task is worse UX than one that's uniformly slow. Semantic caching risks
serving a stale plan for a goal whose environment has changed.

**Then: OAuth token management.** Right now `token.json` is one file for one
Google account (`gmail.py:22`, `calendar.py:19`, `meet.py:24`). Multi-user means
per-user encrypted token storage, a real refresh scheduler, and revocation.
**What I'd add:** a secrets manager (Vault, AWS Secrets Manager) with tokens
encrypted at rest, keyed per user.
**Trade-off:** operational complexity and a new hard dependency in the auth path
— if the secrets store is down, nothing works.

**And the thing I'd raise before they do:** hosting AURA means running
arbitrary LLM-generated code (§2.8) and shell commands on infrastructure *I*
own, on behalf of users. The local version's security model is "it's your
machine, your risk." That doesn't transfer. Multi-tenant AURA needs real
sandboxing — gVisor or Firecracker rather than plain containers, egress
filtering, and per-tenant resource caps — before it could responsibly accept a
single external user. Naming this yourself is much stronger than being told.

---

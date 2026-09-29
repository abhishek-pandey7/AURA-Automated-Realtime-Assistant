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

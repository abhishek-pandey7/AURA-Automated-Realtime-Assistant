# Concepts Explained

> Companion to [INTERVIEW_PREP.md](INTERVIEW_PREP.md). That file tells you *what
> to say*. This one makes sure you actually understand it.
>
> Every concept here is taught from scratch — what problem it solves, how it
> works, when it's the wrong choice — and then tied back to the exact place it
> shows up in your repo. If a term in the main doc feels like a word you're
> reciting rather than a thing you know, find it here first.
>
> Part A covers concepts **that are in your code**. Part B covers concepts
> **that aren't** but that interviewers will raise anyway — mostly the
> distributed-systems vocabulary. You need to know those well enough to say
> "that doesn't apply here, and here's why" without sounding evasive.

---

## Table of contents

**Part A — in your code**

- [A0. The groundwork: tokens, context windows, temperature](#a0-the-groundwork)
- [A1. Tool calling (function calling)](#a1-tool-calling-function-calling)
- [A2. The agent loop / ReAct](#a2-the-agent-loop--react)
- [A3. Plugin registry & convention over configuration](#a3-plugin-registry--convention-over-configuration)
- [A4. Two-stage pipelines (planner + executor)](#a4-two-stage-pipelines-planner--executor)
- [A5. Human-in-the-loop, allow-lists vs deny-lists, defence in depth](#a5-human-in-the-loop-allow-lists-vs-deny-lists-defence-in-depth)
- [A6. Retries, backoff, fail-fast, graceful degradation](#a6-retries-backoff-fail-fast-graceful-degradation)
- [A7. Persistence: write-through, atomicity, write amplification](#a7-persistence-write-through-atomicity-write-amplification)
- [A8. Tiered perception: OCR, centroids, vision fallback](#a8-tiered-perception-ocr-centroids-vision-fallback)
- [A9. Runtime code generation & imitation learning](#a9-runtime-code-generation--imitation-learning)
- [A10. Lazy initialisation & singletons](#a10-lazy-initialisation--singletons)
- [A11. Prompt-as-configuration](#a11-prompt-as-configuration)
- [A12. OAuth 2.0, the way you actually used it](#a12-oauth-20-the-way-you-actually-used-it)

**Part B — not in your code, but they'll ask**

- [B1. Caching](#b1-caching)
- [B2. Queues and async work](#b2-queues-and-async-work)
- [B3. Load balancing, replication, sharding](#b3-load-balancing-replication-sharding)
- [B4. Rate limiting](#b4-rate-limiting)
- [B5. CDNs](#b5-cdns)
- [B6. RAG and vector search](#b6-rag-and-vector-search)
- [B7. Context compaction](#b7-context-compaction)
- [B8. Sandboxing and isolation](#b8-sandboxing-and-isolation)
- [B9. Observability](#b9-observability)
- [B10. Idempotency](#b10-idempotency)

---

# Part A — Concepts that are in your code

## A0. The groundwork

Three things everything else rests on. If you're shaky here, the rest won't
land.

### Tokens

A language model doesn't read characters or words — it reads **tokens**, which
are roughly word-fragments. "Automated" might be one token; "AURA" might be two
or three. Rough rule of thumb for English: **1 token ≈ 4 characters ≈ ¾ of a
word.**

Why you care: you pay per token, and you're *limited* per token. When
`aura/agent.py:120` sends the system prompt plus the whole conversation plus
every tool schema, all of that is tokens. Your system prompt is ~70 lines,
call it 900 tokens, and it's resent on **every single iteration**. A 20-step
task pays for it 20 times.

### Context window

The model's working memory: the maximum number of tokens it can consider in one
request — prompt *and* response together. A mid-sized open model like the one
you're running might have 8k to 128k depending on configuration.

This is a **hard wall**, not a soft limit. Go over and the API returns an error;
the model doesn't gracefully forget the oldest part. It's the single most
important constraint in agent design, and it's why §2.6 and Axis 1 of §4 in the
main doc both circle back to it.

Here's the thing that makes agents specifically hard: **the context grows on
every iteration.** Look at `agent.py:121-124` — every loop pass sends
`{system}` + `memory.get_messages()`, and memory only ever grows. Tool results
get appended (`:235`), assistant messages get appended (`:188`). Nothing is ever
removed. So a long task isn't just slower, it's on a collision course with a
wall.

```
iteration 1:  [system][goal]                                    ~1,200 tok
iteration 2:  [system][goal][assistant+tools][tool result]      ~2,000 tok
iteration 3:  [system][goal][...][...][...][...]                ~3,400 tok
...
iteration 20: [system][goal][ ... 60 more messages ... ]        ~40,000 tok  ← wall
```

That shape — cost and risk growing with every step — is why §4 says context is
what breaks first.

### Temperature

A number, usually 0 to 1 (sometimes to 2), controlling randomness in the
model's output. **Low temperature = more deterministic**, picks the most likely
next token. **High temperature = more varied**, more willing to pick less likely
tokens.

You used this deliberately, and it's worth pointing out in an interview because
it shows intent rather than accepting defaults:

| Where | Temperature | Why |
| --- | --- | --- |
| `planner.py:55` | **0.2** | Planning should be stable and repeatable. Same goal → same plan. |
| `agent.py:127` | **0.3** | Execution needs a little flexibility to recover from surprises. |
| `learning.py:125` | **0.1** | Code generation. You want correct syntax, not creativity. |

That's three different values chosen for three different jobs. Say it that way.

### JSON Schema

A standard format for describing the *shape* of data: what fields exist, their
types, which are required. Every `TOOL_DEFS` entry in your repo is JSON Schema.
It's how you tell the model "here is a function, here are its parameters" in a
way the model can program against. More on this in A1.

---

## A1. Tool calling (function calling)

### The problem it solves

A language model can only produce text. It cannot run a command, read a file, or
click a mouse. If you ask a plain chat model "what's in my home directory?" the
best it can do is *describe* how you'd find out.

Tool calling is the bridge. You describe your functions to the model in a
structured format; instead of prose, the model can emit a **structured request
to call one**. Your code executes it and hands back the result. The model never
executes anything — it asks, you decide, you run it.

### How it actually works

Three steps.

**1. You declare what's available.** Every tool module in `aura/tools/` exports
a `TOOL_DEFS` list. Here's the shape, from `aura/tools/shell.py:6`:

```python
TOOL_DEF = {
    "type": "function",
    "function": {
        "name": "bash",
        "description": "Run a shell command in the current working directory. ...",
        "parameters": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "The shell command to execute."},
                "timeout": {"type": "integer", "description": "Max seconds to wait. Default 60."},
            },
            "required": ["command"],
        },
    },
}
```

The **description fields are the real API documentation** — they are the only
thing the model reads to decide whether this tool fits the situation. That's why
yours are verbose and contain warnings like "On Windows this is PowerShell — use
PowerShell syntax only." A vague description produces wrong tool choices. Tool
descriptions are prompt engineering, not comments.

**2. The model responds with a call, not an answer.** You pass
`tools=ALL_TOOL_DEFS, tool_choice="auto"` (`agent.py:125-126`) — "here's
everything you can do, decide for yourself whether to use any." The response
comes back with a `tool_calls` array instead of text: a name, an id, and
arguments as a **JSON string**.

**3. You execute and report back.** `agent.py:199` parses the arguments,
`:213` dispatches, and `:235` appends the result as a message with
`role: "tool"` and the matching `tool_call_id`. The id is what lets the model
pair a result with the request that produced it — necessary because a single
response can contain several parallel tool calls, which your loop handles at
`:194`.

### The detail worth pointing at in an interview

`agent.py:197-210`:

```python
try:
    tool_inputs = json.loads(tc.function.arguments)
except json.JSONDecodeError:
    # Some models wrap JSON in markdown fences
    raw = tc.function.arguments.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        ...
```

The `arguments` field is *specified* to be a JSON string. Your code handles the
case where it comes back wrapped in markdown code fences anyway. That's not
defensive paranoia — that's a real behaviour of smaller open-weight models, and
the same workaround appears independently in `planner.py:73-78`.

This is a genuinely good thing to volunteer, because it shows you know the
difference between the spec and reality: *"I'm running an open-weight model,
and its tool-call formatting isn't always spec-compliant, so the harness
tolerates fenced JSON. That's the tax you pay for model independence."*

### When tool calling is the wrong approach

- **When the task is pure text** (summarise this, translate that). No tools
  needed; you're adding a round trip for nothing.
- **When the sequence is fixed and known.** If you always do A then B then C,
  write `a(); b(); c()`. Letting a model decide adds latency, cost and
  non-determinism to something that had none.
- **When you can't tolerate a wrong choice.** The model *might* pick the wrong
  tool. If a wrong pick is catastrophic and unrecoverable, don't delegate the
  decision.

---

## A2. The agent loop / ReAct

### The problem it solves

One model call gets you one shot. The model has to guess everything about your
environment up front, and if any guess is wrong, the output is quietly broken
and nothing tells you.

Real work isn't like that. Real work is: try something, look at what happened,
adjust. You run the tests, you see the failure, you fix it, you run them again.

**ReAct** — **Rea**soning + **Act**ing — is the pattern that gives a model that
same cycle. Reasoning and acting interleave instead of happening once.

### The loop, concretely

```
   ┌─────────────────────────────────────────────┐
   │                                             │
   ▼                                             │
[ Call the model with: system + full history ]   │
   │                                             │
   ▼                                             │
[ Did it return tool_calls? ]                    │
   │                    │                        │
   │ no                 │ yes                    │
   ▼                    ▼                        │
[ DONE ]          [ Execute each tool ]          │
                        │                        │
                        ▼                        │
                  [ Append results to history ] ─┘
```

That's `aura/agent.py:110-251`, almost line for line. The termination check is
`:156`:

```python
if not message.tool_calls:
    final = message.content or "[ AURA ] Task complete."
```

**No tool calls means finished.** The model signals completion by simply talking
instead of acting.

### Why this specific loop gives you self-correction

Because the tool result goes back into the history, the model *sees what
happened*. Concretely, from your README's own demo trace:

```
iteration 3:  model calls  bash("pytest -v")
              result:      "1 failed, 0 passed ... AssertionError on line 12"
              ↑ this text is now in the conversation

iteration 4:  model has read that failure, calls  patch_file(...)

iteration 5:  model calls  bash("pytest -v")
              result:      "1 passed"

iteration 6:  no tool calls → done
```

There's no error-handling code in AURA that does this. The recovery is emergent
from the loop plus the prompt instruction at `agent.py:38` ("If a command fails,
read stderr, identify the cause, fix it, and retry automatically"). That's the
whole trick, and it's worth saying plainly: *the loop is what turns a text
generator into something that can recover.*

### The two limits you must be able to name

**1. Stopping ≠ succeeding.** "No tool calls" is a *stop* condition. A model
that gave up, got confused, or hallucinated success produces the exact same
signal as one that genuinely finished. You have no verification. This is Q2 in
the main doc and it's the most common follow-up on this topic.

**2. The iteration cap is blunt.** `max_iterations: int = 30` (`agent.py:96`).
It stops runaway loops, which is essential — without it, a model stuck in a
retry cycle burns tokens until your budget is gone. But it also truncates
legitimate long work with a vague message (`:253-254`). A cost/token budget
would be smarter than a step count, because 30 cheap steps and 30 expensive ones
are very different things.

### Alternatives, and when each is better

| Approach | Better when | Worse when |
| --- | --- | --- |
| **Single-shot** | Task is self-contained, no environment interaction | Anything needing feedback |
| **Fixed pipeline / DAG** | Steps are known and stable; you want testability | Task space is open-ended |
| **ReAct loop** (yours) | Environment is unpredictable, recovery matters | You need determinism or cost predictability |
| **Tree search / multi-path** | Some paths dead-end and backtracking pays | Cost matters — it multiplies calls |

The honest framing: if AURA only did Gmail and Calendar, a fixed pipeline would
be the better engineering choice — testable, predictable, cheap. ReAct earns its
complexity specifically because "operate an arbitrary GUI" has no enumerable set
of states.

---

## A3. Plugin registry & convention over configuration

### The problem it solves

You have 13 tool modules and want to add a 14th. The naive approach is a central
list:

```python
from aura.tools import shell, web, filesystem, gmail, ...   # edit this
ALL_TOOLS = [shell.TOOL_DEF, *web.TOOL_DEFS, ...]           # and this
DISPATCH = {"bash": shell.run, "web_fetch": web.web_fetch, ...}  # and this
```

Three places to edit for every new tool, and every one is a place to forget.

A **plugin registry** inverts it: the system *discovers* its own components at
startup instead of being told about them.

### Convention over configuration

The idea that a component declares itself by **following a naming rule** rather
than by being registered somewhere. Your convention, from
`aura/tools/__init__.py:21-33`:

> A module in `aura/tools/` is a tool provider if it exposes `TOOL_DEFS` (a list
> of JSON schemas) or `TOOL_DEF` (a single one). For each schema, the
> implementation is the module-level function whose name equals
> `schema["function"]["name"]`.

Follow that and you exist. No registration call, no import line, no dict entry.

### How the discovery works

```python
pkg_dir = Path(__file__).resolve().parent
for _, module_name, ispkg in pkgutil.iter_modules([str(pkg_dir)]):
    if ispkg: continue
    module = importlib.import_module(f"aura.tools.{module_name}")
```

Two standard-library pieces:

- **`pkgutil.iter_modules([dir])`** — lists every importable module in a
  directory. This is *filesystem* inspection, not code inspection: it finds
  files that exist right now, which is the whole point.
- **`importlib.import_module(name)`** — imports a module by *string name*
  computed at runtime, rather than by a static `import x` statement. That's what
  makes it possible to import a file that didn't exist when the program started.

Then the schemas go in `ALL_TOOL_DEFS` (which is what `agent.py:125` sends to
the model) and the functions go in `_dispatch_map` (which is what `dispatch()`
at `:41` looks up).

### Why this is load-bearing, not decorative

This is the point to hammer if someone asks "why not just use a dict?"

`aura/learning.py:162-166`:

```python
file_path = tools_dir / f"{tool_name}.py"
file_path.write_text(code, encoding="utf-8")
aura.tools._init_tools()          # ← re-scan
```

AURA **writes a new Python file into its own tools directory while running**,
then re-runs discovery. The new tool is available on the very next iteration, in
the same process, with no restart.

A static dict cannot do that. You'd have to edit source and relaunch. So the
registry isn't a style preference — the self-extension feature is impossible
without it. That's a much stronger answer than "it's cleaner."

### The cost, which is real

`aura/tools/__init__.py:36-37`:

```python
except Exception:
    pass # Ignore broken generated tools on startup
```

Every import error — a typo, a missing dependency, a Windows-only import on
Linux — is silently swallowed. The tool simply doesn't exist, with no message
anywhere. The *intent* is right (one bad generated tool shouldn't stop AURA
booting) but silence is the wrong implementation. Catch, **log the module name
and the exception**, continue. Same resilience, actual observability.

This is genuinely the best five-line fix in the codebase and saying so shows
judgement about where effort pays off.

### The other trade-off: implicit contracts break quietly

The "function name must match schema name" rule lives nowhere but in code — and
you already needed an exception to it at `:34`:

```python
elif module_name == "shell" and tool_name == "bash":
    _dispatch_map[tool_name] = getattr(module, "run")
```

`shell.py` exposes `run`, but the tool is called `bash`. One special case,
hardcoded. That's evidence the convention was slightly too tight — a cleaner
design would let a module declare the mapping explicitly (e.g. an optional
`TOOL_IMPL = {"bash": run}`) rather than special-casing one module by name.

### When a plugin registry is the wrong call

- **When the set is fixed and small.** A dict is clearer and statically
  analysable. Your IDE can follow it; it can't follow `importlib`.
- **When you need startup guarantees.** Auto-discovery means you learn about a
  broken component at *use* time, not boot time.
- **When plugins are untrusted.** Auto-importing whatever is in a directory
  means auto-executing whatever is in a directory — module-level code runs on
  import. Combined with A9, that's the security story of this project.

---

## A4. Two-stage pipelines (planner + executor)

### The idea

Rather than one model call doing everything, split the work across calls with
different jobs, different prompts, and different settings. AURA does this in two
stages:

```
  goal string
      │
      ▼
┌──────────────┐   planner.py — temp 0.2, 512 tokens, NO tools
│   PLANNER    │   job: decompose into ≤10 concrete subtasks, return JSON
└──────────────┘
      │
      ▼  ["create dir and files", "write the Flask app", "run tests and fix"]
      │
      ├────────► agent.run_agent(task_1, memory)  ─┐
      ├────────► agent.run_agent(task_2, memory)   │ agent.py — temp 0.3,
      └────────► agent.run_agent(task_3, memory)  ─┘ 4096 tokens, ALL tools
                                        │
                                   one shared Memory
```

### Why split at all

Three distinct benefits, and you should be able to name which one mattered most
(this is one of the `[confirm with me]` spots — the code supports more than one
reading):

**1. The plan is visible before anything runs.** `ui.py:230` renders it in a
panel. For an agent that is about to execute shell commands and move your
physical mouse, showing the intended steps first is a trust mechanism, and it
costs almost nothing. This is a UX argument, and it's a good one.

**2. Each executor context stays focused.** Instead of one sprawling
conversation about a five-part goal, you get five conversations each about one
thing. Less drift, less context.

**3. Different jobs want different settings.** Decomposition wants stability
(temp 0.2, tight token cap). Execution wants a little adaptability (temp 0.3,
4096 tokens for tool arguments). One call can't have two temperatures.

### Soft dependency — the part that's actually well-designed

`planner.py:84-88`:

```python
    except Exception:
        pass

    # Fallback — treat whole goal as one task
    return [goal]
```

If planning fails *entirely* — endpoint down, malformed JSON, anything — the
function returns the original goal as a single-element list and **execution
proceeds normally**. The agent loop is perfectly capable of handling an
undecomposed goal; it just doesn't get the nice plan display.

That's a **soft dependency**: a component whose failure degrades the experience
rather than stopping the system. Contrast with the LLM endpoint itself, which is
a **hard dependency** — if that's down, nothing works. Knowing which of your
dependencies are which is a real architectural skill, and you can point at this
as a case where you got it right.

### The flaw: the plan is frozen

This is the sharpest legitimate criticism of AURA's design and you should raise
it yourself.

The planner runs **before any execution**, so it has zero information about the
environment. It's guessing from the goal string alone. If subtask 2 discovers
that the plan was wrong — the file doesn't exist, the app has a different
layout, the API returned something unexpected — subtasks 3, 4 and 5 still run
exactly as written. There's no mechanism to revise or discard them.

Two things partially mitigate it, and they're worth mentioning so the criticism
doesn't sound worse than it is:

- The ReAct loop *within* each subtask is fully adaptive. Local recovery works
  well; it's only the cross-subtask structure that's rigid.
- All subtasks share one `Memory` instance (`ui.py:248` passes the same object
  each time), so later subtasks can see what earlier ones actually did.

**The real fix is replanning**: after each subtask, feed the results back to the
planner and let it revise the remainder. The cost is latency and money at every
boundary, plus a new failure mode — a replanning loop that oscillates between two
plans forever. So you'd need a replan budget. That's the kind of "here's the fix
*and* what the fix costs" answer that lands well.

---

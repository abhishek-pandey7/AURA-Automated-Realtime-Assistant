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

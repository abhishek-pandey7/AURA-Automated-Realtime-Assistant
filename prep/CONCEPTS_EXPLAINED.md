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

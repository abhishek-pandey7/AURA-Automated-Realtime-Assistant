# AURA - Automated Realtime Assistant

A CLI-based autonomous AI agent that plans, executes, and adapts. Powered by open-weight LLMs via an OpenAI-compatible endpoint, AURA is designed to bridge the gap between simple text-based AI assistants and full-fledged system operators. 

From writing complete projects in an IDE to utilizing custom computer vision for desktop interaction, AURA interacts with your operating system the same way you do.

---

## 1. Overview

You provide a goal in natural language. AURA takes that goal, breaks it down into a chronological sequence of steps, and autonomously executes each step using a suite of native tools (shell execution, filesystem manipulation, web browsing, and raw desktop input). 

Unlike simple code-generation tools, AURA operates in an **Observe -> Think -> Act -> Verify** feedback loop. If a test fails, a layout changes, or an error is thrown, AURA reads the output, adjusts its plan, and tries a new approach without needing manual intervention.

Example Execution Trace:
```text
$ aura run

> Build a simple Flask web hook, write tests, run them, and ensure it passes.

Plan
  1. Create project directory and initialize Python files.
  2. Implement Flask app with a basic POST endpoint.
  3. Write pytest test suite.
  4. Run tests and self-correct any failures.

Action      bash         $ mkdir hook_test && cd hook_test
Action      write_file   hook_test/app.py
Action      write_file   hook_test/test_app.py
Action      bash         $ cd hook_test && pytest -v
Observation 1 failed, 0 passed
Action      patch_file   hook_test/app.py   (Self-Correcting issue)
Action      bash         $ pytest -v
Observation 1 passed
```

---

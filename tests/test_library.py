"""Tests for using AURA as a library. No API key or network needed: the LLM is a fake client.

    pip install -e ".[dev]"
    pytest tests/test_library.py
"""
import json
import os
import subprocess
import sys
from types import SimpleNamespace

import pytest

import aura
from aura import config, memory, tools


class FakeClient:
    """Stands in for openai.OpenAI: returns queued responses and records each request."""

    def __init__(self, *messages):
        self._queue = list(messages)
        self.requests = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        self.requests.append(kwargs)
        return SimpleNamespace(choices=[SimpleNamespace(message=self._queue.pop(0))])


def text_reply(content):
    return SimpleNamespace(content=content, tool_calls=None)


def tool_reply(name, args, call_id="call_1"):
    call = SimpleNamespace(id=call_id, function=SimpleNamespace(name=name, arguments=json.dumps(args)))
    return SimpleNamespace(content="", tool_calls=[call])


@pytest.fixture(autouse=True)
def isolated_home(tmp_path, monkeypatch):
    # Keep sessions and learned tools out of the real ~/.aura
    monkeypatch.setattr(config, "AURA_HOME", tmp_path)
    monkeypatch.setattr(memory, "SESSIONS_DIR", tmp_path / "sessions")
    yield
    tools._custom_tools.clear()
    tools._loaded = False


def test_import_needs_no_api_key_and_agent_explains_missing_key(tmp_path):
    # Run from an empty directory so no .env is picked up; PYTHONPATH finds a source checkout
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    env = dict(os.environ, INFERX_API_KEY="", AURA_HOME=str(tmp_path),
               PYTHONPATH=os.pathsep.join(filter(None, [repo_root, os.environ.get("PYTHONPATH")])))
    code = "import aura\ntry:\n    aura.Agent()\nexcept aura.ConfigError as e:\n    print('CONFIG_ERROR', 'INFERX_API_KEY' in str(e))"
    out = subprocess.run([sys.executable, "-c", code], cwd=tmp_path, env=env,
                         capture_output=True, text=True, check=True).stdout
    assert "CONFIG_ERROR True" in out


def test_agent_calls_a_registered_tool_and_returns_the_final_answer():
    calls = []

    agent = aura.Agent(client=FakeClient(tool_reply("add", {"a": 2, "b": 3}), text_reply("2 + 3 = 5")),
                       model="fake-model", plan=False, verbose=False)

    @agent.add_tool
    def add(a: int, b: int) -> str:
        """Add two integers."""
        calls.append((a, b))
        return str(a + b)

    assert agent.run("what is 2 + 3?") == "2 + 3 = 5"
    assert calls == [(2, 3)]
    assert "add" in agent.tools

    first_request = agent.client.requests[0]
    assert first_request["model"] == "fake-model"
    schema = next(t for t in first_request["tools"] if t["function"]["name"] == "add")
    assert schema["function"]["parameters"]["properties"]["a"] == {"type": "integer"}
    tool_messages = [m for m in agent.memory.messages if m["role"] == "tool"]
    assert tool_messages == [{"role": "tool", "tool_call_id": "call_1", "content": "5"}]


def test_planner_splits_goal_into_tasks_and_runs_each():
    client = FakeClient(text_reply('{"tasks": ["step one", "step two"]}'),
                        text_reply("did one"), text_reply("did two"))
    agent = aura.Agent(client=client, model="fake-model", verbose=False)

    assert agent.run("do two things") == "did two"
    user_goals = [m["content"] for m in agent.memory.messages if m["role"] == "user"]
    assert user_goals == ["step one", "step two"]


def test_planner_falls_back_to_the_whole_goal_on_bad_json():
    agent = aura.Agent(client=FakeClient(text_reply("not json")), model="fake-model", verbose=False)
    assert agent.plan("just do it") == ["just do it"]


def test_approver_replaces_the_interactive_prompt(monkeypatch):
    from aura import confirm
    seen = []
    monkeypatch.setattr(confirm, "_approver", None)
    aura.Agent(client=FakeClient(), safe_mode=True, verbose=False,
               approve=lambda action, detail: seen.append(action) or False)

    assert confirm.confirm_shell("echo hi") is False
    assert seen == ["run a shell command"]


def test_learned_tools_load_from_aura_home(tmp_path):
    (tmp_path / "tools").mkdir()
    (tmp_path / "tools" / "say_hello.py").write_text(
        'TOOL_DEFS = [{"type": "function", "function": {"name": "say_hello", "description": "hi",\n'
        '              "parameters": {"type": "object", "properties": {}}}}]\n'
        'def say_hello():\n    return "hello"\n', encoding="utf-8")

    tools._init_tools()
    assert "say_hello" in [d["function"]["name"] for d in tools.get_tool_defs()]
    assert tools.dispatch("say_hello", {}) == "hello"

"""AURA: an autonomous agent that plans a goal and carries it out with real tools.

    from aura import Agent
    Agent(api_key="sk-...").run("create hello.py that prints hi, then run it")
"""
from aura.config import VERSION as __version__, ConfigError

__all__ = ["Agent", "ConfigError", "register_tool", "__version__"]


def __getattr__(name):
    # Imported lazily so `import aura` stays cheap and never needs an API key
    if name == "Agent":
        from aura.agent import Agent
        return Agent
    if name == "register_tool":
        from aura.tools import register_tool
        return register_tool
    raise AttributeError(f"module 'aura' has no attribute {name!r}")

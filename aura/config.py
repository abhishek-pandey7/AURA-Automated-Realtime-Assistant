import os
from pathlib import Path
from dotenv import load_dotenv

# .env lookup order: the current directory, ~/.aura/.env, then the source checkout root
# (aura/config.py → aura/ → project_root/). Earlier files win; real env vars beat all of them.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
AURA_HOME = Path(os.getenv("AURA_HOME", Path.home() / ".aura"))

for _env_file in (Path.cwd() / ".env", AURA_HOME / ".env", _PROJECT_ROOT / ".env"):
    if _env_file.is_file():
        load_dotenv(dotenv_path=_env_file, override=False)

INFERX_BASE_URL = os.getenv("INFERX_BASE_URL", "https://api.openai.com/v1")
INFERX_API_KEY  = os.getenv("INFERX_API_KEY", "")
INFERX_MODEL    = os.getenv("INFERX_MODEL", "gemma-4-31b")
SAFE_MODE       = os.getenv("AURA_SAFE_MODE", "true").lower() == "true"
USER_NAME       = os.getenv("AURA_USER_NAME", "")

# Commands that always require explicit user confirmation regardless of SAFE_MODE
ALWAYS_CONFIRM_PATTERNS = [
    "rm ", "rmdir", "sudo", "chmod", "chown",
    "dd ", "mkfs", ":(){:|:&};:", "shutdown", "reboot",
    "git push", "pip install", "npm install",
]

VERSION = "0.2.0"


class ConfigError(RuntimeError):
    """Raised when AURA is asked to call the LLM without the settings it needs."""


def require_api_key(api_key: str | None = None) -> str:
    key = api_key or INFERX_API_KEY
    if not key:
        raise ConfigError(
            "\n[ AURA ] Missing INFERX_API_KEY!\n"
            "  Pass api_key=... to aura.Agent, or set INFERX_API_KEY in the environment\n"
            f"  or in a .env file (current directory or {AURA_HOME / '.env'}).\n"
            "  See .env.example for a full template."
        )
    return key


def data_path(name: str) -> Path:
    """Where a user data file (credentials.json, token.json, user_profile.json) lives.

    A file already in the source checkout root keeps working; otherwise it goes in AURA_HOME,
    which is the only writable choice once AURA is pip-installed.
    """
    legacy = _PROJECT_ROOT / name
    if legacy.exists():
        return legacy
    AURA_HOME.mkdir(parents=True, exist_ok=True)
    return AURA_HOME / name


def user_tools_dir() -> Path:
    """Where watch-and-learn saves generated tools."""
    path = AURA_HOME / "tools"
    path.mkdir(parents=True, exist_ok=True)
    return path

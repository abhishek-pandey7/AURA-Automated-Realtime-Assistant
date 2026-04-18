import pyautogui
from aura.confirm import confirm_desktop

# Fail-safe helps if the mouse goes wild
pyautogui.FAILSAFE = True

TOOL_DEFS = [
    {
        "type": "function",
        "function": {
            "name": "desktop_click",
            "description": "Move the mouse to an (x, y) coordinate and click.",
            "parameters": {
                "type": "object",
                "properties": {
                    "x": {"type": "integer", "description": "X coordinate."},
                    "y": {"type": "integer", "description": "Y coordinate."},
                    "clicks": {"type": "integer", "description": "Number of clicks (default 1)."},
                    "button": {"type": "string", "description": "'left', 'middle', or 'right' (default 'left')."}
                },
                "required": ["x", "y"]
            }
        }
    },
]

def desktop_click(x: int, y: int, clicks: int = 1, button: str = "left") -> str:
    if not confirm_desktop("click", f"x={x}, y={y}, clicks={clicks}, button={button}"):
        return "[ AURA ] Desktop action cancelled."
    try:
        pyautogui.click(x=x, y=y, clicks=clicks, button=button)
        return f"[ AURA ] Clicked at ({x}, {y}) {clicks} time(s) with {button} button."
    except Exception as e:
        return f"[ AURA ] Desktop click failed: {e}"



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
    {
        "type": "function",
        "function": {
            "name": "desktop_type",
            "description": "Type a string using the keyboard.",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "Text to type."},
                    "press_enter": {"type": "boolean", "description": "Whether to press Enter after typing."}
                },
                "required": ["text"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "desktop_press",
            "description": "Press a specific hotkey or key combination.",
            "parameters": {
                "type": "object",
                "properties": {
                    "keys": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of keys to press together (e.g. ['ctrl', 't'] or ['win'] or ['enter'])."
                    }
                },
                "required": ["keys"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "desktop_get_position",
            "description": "Get the current mouse position on the screen.",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "desktop_analyze_screen",
            "description": "Take a screenshot of the entire desktop and provide it to the LLM to analyze UI elements visually.",
            "parameters": {
                "type": "object",
                "properties": {
                    "reason": {"type": "string"}
                },
                "required": ["reason"]
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

def desktop_type(text: str, press_enter: bool = False) -> str:
    import time
    # Redact large text for the prompt
    preview = text if len(text) < 50 else text[:47] + "..."
    if not confirm_desktop("type", f"'{preview}' (enter={press_enter})"):
        return "[ AURA ] Desktop action cancelled."
    try:
        # Wait a moment before typing to ensure the field is focused
        time.sleep(0.5)
        pyautogui.write(text, interval=0.02)
        if press_enter:
            pyautogui.press('enter')
        time.sleep(0.5)
        return f"[ AURA ] Typed text successfully."
    except Exception as e:
        return f"[ AURA ] Desktop type failed: {e}"

def desktop_press(keys: list[str]) -> str:
    import time
    if not confirm_desktop("hotkey", " + ".join(keys)):
        return "[ AURA ] Desktop action cancelled."
    try:
        pyautogui.hotkey(*keys)
        # Give the UI time to process the keypress (like Tab focus)
        time.sleep(0.5)
        return f"[ AURA ] Pressed keys: {' + '.join(keys)}."
    except Exception as e:
        return f"[ AURA ] Desktop hotkey failed: {e}"

def desktop_get_position() -> str:
    try:
        x, y = pyautogui.position()
        width, height = pyautogui.size()
        return f"[ AURA ] Mouse Position: ({x}, {y}) | Screen Size: {width}x{height}"
    except Exception as e:
        return f"[ AURA ] Failed to get mouse position: {e}"

def desktop_analyze_screen(reason: str) -> str:
    from aura.confirm import confirm_desktop
    import base64
    from io import BytesIO
    from PIL import Image

    if not confirm_desktop("analyze screen", reason):
        return "[ AURA ] Action cancelled."
    try:
        # Take screenshot and resize to save tokens/size
        img = pyautogui.screenshot()
        width, height = img.size
        # Resize to max 1024x1024 while maintaining aspect ratio
        img.thumbnail((1024, 1024), Image.Resampling.LANCZOS)
        
        buffered = BytesIO()
        img.save(buffered, format="JPEG", quality=85)
        img_str = base64.b64encode(buffered.getvalue()).decode("utf-8")
        
        # AURA intercepts this exact string format to inject the image object
        return f"[ IMAGE_BASE64: data:image/jpeg;base64,{img_str} ]"
    except Exception as e:
        return f"[ AURA ] Screen capture failed: {e}"


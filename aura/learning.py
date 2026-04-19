import time
import base64
import re
from io import BytesIO
from pathlib import Path

import pyautogui
from pynput import mouse, keyboard
from PIL import Image
from rich.console import Console
import httpx
from openai import OpenAI

from aura.config import INFERX_BASE_URL, INFERX_API_KEY, INFERX_MODEL

console = Console()

class Recorder:
    def __init__(self):
        self.events = []
        self.start_time = None
        self.mouse_listener = None
        self.keyboard_listener = None
        self.running = False
        
    def _get_time(self):
        return round(time.time() - self.start_time, 2)

    def on_click(self, x, y, button, pressed):
        if pressed and self.running:
            self.events.append(f"T+{self._get_time()}s: Clicked {button} at ({x}, {y})")

    def on_press(self, key):
        if not self.running: return
        try:
            self.events.append(f"T+{self._get_time()}s: Typed '{key.char}'")
        except AttributeError:
            self.events.append(f"T+{self._get_time()}s: Pressed {key}")

    def on_release(self, key):
        if key == keyboard.Key.esc:
            self.running = False
            return False # Stop listener

    def record(self, duration_sec: int = 60):
        self.start_time = time.time()
        self.running = True
        
        self.mouse_listener = mouse.Listener(on_click=self.on_click)
        self.keyboard_listener = keyboard.Listener(on_press=self.on_press, on_release=self.on_release)
        
        self.mouse_listener.start()
        self.keyboard_listener.start()
        
        # Take start screenshot
        start_img_b64 = self._take_screenshot()
        
        console.print(f"\n[bold red]Recording started...[/bold red] (Press ESC or wait {duration_sec}s to stop)")
        
        while self.running and (time.time() - self.start_time) < duration_sec:
            time.sleep(0.5)
            
        self.running = False
        self.mouse_listener.stop()
        self.keyboard_listener.stop()
        
        end_img_b64 = self._take_screenshot()
        console.print("[bold green]Recording finished.[/bold green]\n")
        
        return self.events, start_img_b64, end_img_b64

    def _take_screenshot(self):
        try:
            img = pyautogui.screenshot()
            img.thumbnail((1024, 1024), Image.Resampling.LANCZOS)
            buffered = BytesIO()
            img.save(buffered, format="JPEG", quality=75)
            return base64.b64encode(buffered.getvalue()).decode("utf-8")
        except Exception:
            return ""



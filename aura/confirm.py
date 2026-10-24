from rich.console import Console
from rich.panel import Panel
from rich import box
from aura import config

console = Console()

# Optional callback (action_type, detail) -> bool that replaces the interactive Y/N prompt,
# for library use where there's no terminal to ask in.
_approver = None


def set_approver(func):
    global _approver
    _approver = func


def _is_dangerous(action: str) -> bool:
    action_lower = action.lower()
    return any(p in action_lower for p in config.ALWAYS_CONFIRM_PATTERNS)


def confirm_action(action_type: str, detail: str, force: bool = False) -> bool:
    """
    Ask the user Y/N before executing a potentially risky action.
    Returns True if user approves, False if denied.
    force=True means always ask regardless of SAFE_MODE.
    """
    dangerous = _is_dangerous(detail)

    # Skip confirmation if safe mode is off AND action isn't in always-confirm list
    if not config.SAFE_MODE and not dangerous and not force:
        return True

    if _approver is not None:
        return bool(_approver(action_type, detail))

    # Color coding
    if dangerous:
        style = "bold red"
        icon = "⚠"
        border = "red"
    else:
        style = "bold yellow"
        icon = "◆"
        border = "yellow"

    console.print()
    console.print(Panel(
        f"[{style}]{icon}  AURA wants to {action_type}:[/{style}]\n\n"
        f"[white]{detail}[/white]",
        border_style=border,
        box=box.HEAVY,
        padding=(0, 2),
    ))

    while True:
        response = console.input(
            f"  [{style}]Proceed?[/{style}] [[bold green]Y[/bold green]/[bold red]N[/bold red]] › "
        ).strip().upper()

        if response in ("Y", "YES"):
            console.print("  [bold green]✓ Approved[/bold green]\n")
            return True
        elif response in ("N", "NO", ""):
            console.print("  [bold red]✗ Cancelled[/bold red]\n")
            return False
        else:
            console.print("  [dim]Please enter Y or N[/dim]")


def confirm_write(path: str, preview: str = "") -> bool:
    detail = f"Write to file: [bold]{path}[/bold]"
    if preview:
        detail += f"\n\n[dim]Preview (first 200 chars):[/dim]\n{preview[:200]}"
    return confirm_action("write a file", detail)


def confirm_shell(command: str) -> bool:
    return confirm_action("run a shell command", f"$ {command}")


def confirm_delete(path: str) -> bool:
    return confirm_action("delete", f"[bold red]{path}[/bold red]", force=True)


def confirm_browser(action: str, target: str) -> bool:
    return confirm_action(f"perform browser action ({action})", target)


def confirm_desktop(action: str, target: str) -> bool:
    detail = f"Target: {target}"
    if _is_dangerous(detail) or _is_dangerous(action):
        return confirm_action(f"perform desktop action ({action})", detail, force=True)
    
    # Bypass SAFE_MODE for safe desktop operations
    console.print(f"  [dim]▶ Auto-approved desktop action: {action}[/dim]")
    return True

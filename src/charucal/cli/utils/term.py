"""Terminal utilities for raw keypress reading and live block redrawing."""

from __future__ import annotations

__all__ = ["raw_terminal", "read_keypress", "redraw_block"]

import contextlib
import os
import sys
from collections.abc import Generator

_IS_WINDOWS = os.name == "nt"

if _IS_WINDOWS:
    import msvcrt
else:
    import select
    import termios
    import tty


@contextlib.contextmanager
def raw_terminal() -> Generator[None, None, None]:
    """Set the terminal to raw mode for non-blocking keypress reading, and restore it afterward."""
    if _IS_WINDOWS or not sys.stdin.isatty():
        yield
        return

    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setcbreak(fd)
        yield
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)


def read_keypress() -> str | None:
    """Read a keypress without blocking the execution loop.

    :return: The key string, or ``None`` if no key was pressed.
    """
    if _IS_WINDOWS:
        if msvcrt.kbhit():
            ch = msvcrt.getch()
            if ch in (b"\x00", b"\xe0"):
                ch2 = msvcrt.getch()
                mapping = {b"K": "\x1b[D", b"M": "\x1b[C"}
                return mapping.get(ch2, None)

            return ch.decode("utf-8", errors="replace")

        return None

    if not sys.stdin.isatty():
        return None

    fd = sys.stdin.fileno()
    if select.select([fd], [], [], 0)[0]:
        ch = os.read(fd, 1).decode("utf-8", errors="replace")
        if ch == "\x1b" and select.select([fd], [], [], 0.05)[0]:
            ch += os.read(fd, 8).decode("utf-8", errors="replace")

        return ch

    return None


def redraw_block(previous_line_count: int, output: str) -> int:
    """Redraw a block of text in the terminal by erasing the previous lines and writing new ones.

    .. note::
        Redrawing individual blocks instead of clearing the entire terminal can help reduce flickering.

    :param previous_line_count: The number of lines to erase upward.
    :param output: The new text to display.
    :return: The number of lines written.
    """
    lines = output.split("\n")
    buffer: list[str] = []

    if previous_line_count > 0:
        buffer.append(f"\033[{previous_line_count}A")

    for line in lines:
        buffer.append(f"\r{line}\033[K\n")

    sys.stdout.write("".join(buffer))
    sys.stdout.flush()
    return len(lines)

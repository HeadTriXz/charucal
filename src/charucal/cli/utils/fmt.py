"""Formatting utilities for the CLI tools."""

from __future__ import annotations

__all__ = [
    "Styled",
    "strip_ansi",
    "print_error",
    "print_warning",
    "print_success",
    "fmt_rule",
    "fmt_header",
    "fmt_kv",
    "fmt_box",
    "fmt_controls",
    "fmt_grids",
]

import re
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from charucal.grid import CalibrationGrid

_ANSI_RE = re.compile(r"\x1B\[[0-?]*[ -/]*[@-~]")


class Styled:
    """A builder for terminal text styling."""

    #: The text to style.
    text: str

    #: The styles to apply to the text.
    styles: list[str]

    def __init__(self, text: str) -> None:
        """Initialize the styled text.

        :param text: The text to style.
        """
        self.text = text
        self.styles = []

    @property
    def plain(self) -> str:
        """Return the plain text without any styling."""
        return self.text

    def bold(self) -> Styled:
        """Apply bold styling to the text."""
        return self._add_style("1")

    def dim(self) -> Styled:
        """Apply dim styling to the text."""
        return self._add_style("2")

    def underline(self) -> Styled:
        """Apply underline styling to the text."""
        return self._add_style("4")

    def black(self) -> Styled:
        """Apply black color to the text."""
        return self._add_style("30")

    def red(self) -> Styled:
        """Apply red color to the text."""
        return self._add_style("31")

    def green(self) -> Styled:
        """Apply green color to the text."""
        return self._add_style("32")

    def yellow(self) -> Styled:
        """Apply yellow color to the text."""
        return self._add_style("33")

    def blue(self) -> Styled:
        """Apply blue color to the text."""
        return self._add_style("34")

    def magenta(self) -> Styled:
        """Apply magenta color to the text."""
        return self._add_style("35")

    def cyan(self) -> Styled:
        """Apply cyan color to the text."""
        return self._add_style("36")

    def white(self) -> Styled:
        """Apply white color to the text."""
        return self._add_style("37")

    def bright_black(self) -> Styled:
        """Apply bright black color to the text."""
        return self._add_style("90")

    def bright_red(self) -> Styled:
        """Apply bright red color to the text."""
        return self._add_style("91")

    def bright_green(self) -> Styled:
        """Apply bright green color to the text."""
        return self._add_style("92")

    def bright_yellow(self) -> Styled:
        """Apply bright yellow color to the text."""
        return self._add_style("93")

    def bright_blue(self) -> Styled:
        """Apply bright blue color to the text."""
        return self._add_style("94")

    def bright_magenta(self) -> Styled:
        """Apply bright magenta color to the text."""
        return self._add_style("95")

    def bright_cyan(self) -> Styled:
        """Apply bright cyan color to the text."""
        return self._add_style("96")

    def bright_white(self) -> Styled:
        """Apply bright white color to the text."""
        return self._add_style("97")

    def _add_style(self, style: str) -> Styled:
        """Add a style to the text.

        :param style: The style to add.
        :return: The styled text with the added style.
        """
        self.styles.append(style)
        return self

    def __str__(self) -> str:
        """Return a string representation of the styled text."""
        if not self.styles:
            return self.text

        return f"\033[{';'.join(self.styles)}m{self.text}\033[0m"


def strip_ansi(text: str) -> str:
    """Remove ANSI escape codes from a string.

    :param text: The text to strip.
    :return: The text with ANSI escape codes removed.
    """
    return _ANSI_RE.sub("", text)


def visible_len(text: str) -> int:
    """Return the visible length of a string, ignoring ANSI codes.

    :param text: The text to measure.
    :return: The number of visible characters.
    """
    return len(strip_ansi(text))


def print_error(message: str) -> None:
    """Print a formatted error message.

    :param message: The message to print.
    """
    print(f"  {Styled('✗').red()}  {message}", file=sys.stderr)


def print_warning(message: str) -> None:
    """Print a formatted warning message.

    :param message: The message to print.
    """
    print(f"  {Styled('⚠').yellow()}  {message}")


def print_success(message: str) -> None:
    """Print a formatted success message.

    :param message: The message to print.
    """
    print(f"  {Styled('✓').bright_green()}  {message}")


def fmt_rule(label: str = "") -> str:
    """Format a thin horizontal rule with an optional inline label.

    :param label: An optional label placed at the start of the rule.
    """
    if label:
        body = f"── {label} {'─' * (58 - len(label))}"
    else:
        body = "─" * 62

    return str(Styled(body).dim())


def fmt_header(title: str, subtitle: str = "") -> str:
    """Format a header with an optional subtitle.

    :param title: The primary title text.
    :param subtitle: An optional subtitle text.
    """
    lines = ["", fmt_rule(), f"  {Styled(title).bright_cyan().bold()}"]
    if subtitle:
        lines.append(f"  {Styled(subtitle).dim()}")

    lines.append(fmt_rule())
    return "\n".join(lines)


def fmt_kv(key: str, value: str, *, indent: int = 2, key_width: int = 20) -> str:
    """Format a key-value pair as a labeled row.

    :param key: The label text, left-aligned in a fixed column.
    :param value: The value text.
    :param indent: The number of leading spaces before the key.
    :param key_width: The total width of the key column.
    """
    padding = " " * max(key_width - len(key), 0)
    return f"{' ' * indent}{str(Styled(key).dim())}{padding}: {Styled(value).bright_white()}"


def fmt_box(text: str, title: str = "") -> str:
    """Format multi-line text in a box with an optional title.

    :param text: The multi-line text to format.
    :param title: An optional title placed at the top of the box.
    """
    lines = text.splitlines()
    content_width = max(visible_len(line) for line in lines)
    if title:
        content_width = max(content_width, len(title) + 2)

    top = _fmt_box_top(title, content_width)
    body = _fmt_box_body(lines, content_width)
    bottom = str(Styled(f"╰{'─' * (content_width + 2)}╯").dim())

    return "\n".join([top, *body, bottom])


def fmt_controls(groups: list[list[tuple[str, str, bool]]], *, group_sep: str = "  │  ", item_sep: str = "    ") -> str:
    """Format key-action pairs as a compact inline controls hint.

    :param groups: A list of groups, each a list of ``(key_label, description, enabled)`` triples.
    :param group_sep: The separator inserted between groups.
    :param item_sep: The separator inserted between items within a group.
    """
    rendered_groups = []
    for group in groups:
        parts = []
        for key, desc, enabled in group:
            if enabled:
                parts.append(f"{Styled(key).bold()}  {desc}")
            else:
                parts.append(f"{Styled(key).dim()}  {Styled(desc).dim()}")

        rendered_groups.append(item_sep.join(parts))

    sep = str(Styled(group_sep).dim())
    return "  " + sep.join(rendered_groups)


def fmt_grids(grids: list[CalibrationGrid], labels: list[str] | None = None) -> str:
    """Format a list of calibration grids as a side-by-side comparison.

    :param grids: The list of calibration grids to format.
    :param labels: Optional box titles, one per grid. Defaults to
        ``"Camera 0"``, ``"Camera 1"``, etc. when omitted.
    """
    resolved = labels if labels is not None else [f"Camera {i}" for i in range(len(grids))]
    boxes = [_fmt_grid_box(label, grid) for label, grid in zip(resolved, grids)]
    return "\n" + _join_boxes_side_by_side(boxes)


def _fmt_box_top(title: str, content_width: int) -> str:
    """Format the top border of a box, with or without a title.

    :param title: The title text, or empty string for a plain border.
    :param content_width: The inner width of the box in visible characters.
    """
    if not title:
        return str(Styled(f"╭{'─' * (content_width + 2)}╮").dim())

    content_width = max(content_width, len(title) + 2)
    dashes = "─" * max(content_width - len(title) - 1, 0)

    return f"{Styled('╭─ ').dim()}{Styled(title).bright_cyan()}{Styled(f' {dashes}╮').dim()}"


def _fmt_box_body(lines: list[str], content_width: int) -> list[str]:
    """Format the body rows of a box, padding each line to a fixed width.

    :param lines: The lines of text to format.
    :param content_width: The inner width of the box in visible characters.
    """
    rows = []
    for line in lines:
        padding = " " * (content_width - visible_len(line))
        rows.append(f"{Styled('│').dim()} {line}{padding} {Styled('│').dim()}")

    return rows


def _fmt_grid_box(label: str, grid: CalibrationGrid) -> list[str]:
    """Format a single calibration grid.

    :param label: The box title (e.g. ``"Camera 0"`` or ``"Camera 0  ·  /dev/video0"``).
    :param grid: The calibration grid to format.
    :return: The box as a list of lines.
    """
    grid_rows = [str(Styled(row).dim()) for row in str(grid).splitlines()]
    grid_width = max((visible_len(r) for r in grid_rows), default=0)

    status_row = _fmt_grid_status(grid)
    status_padding = " " * max(grid_width - visible_len(status_row), 0)
    content = "\n".join([*grid_rows, status_row + status_padding])

    return fmt_box(content, title=label).splitlines()


def _fmt_grid_status(grid: CalibrationGrid) -> str:
    """Format a corner detection status line for a calibration grid.

    :param grid: The calibration grid to summarize.
    :return: A colored status string.
    """
    detected = int(grid.visible_mask.sum())
    if detected == 0:
        return str(Styled("No corners detected").red())

    total = int(grid.visible_mask.size)
    label = f"{detected}/{total} corners detected"

    if detected < total // 2:
        return str(Styled(label).yellow())

    return str(Styled(label).green())


def _join_boxes_side_by_side(boxes: list[list[str]], *, gap: int = 2) -> str:
    """Join multiple text boxes horizontally.

    :param boxes: Each box as a list of lines of equal width.
    :param gap: The number of spaces between boxes.
    :return: The combined string.
    """
    height = max(len(box) for box in boxes)
    col_widths = [max(visible_len(line) for line in box) for box in boxes]

    rows = []
    for row_idx in range(height):
        cols = []
        for box, col_width in zip(boxes, col_widths):
            line = box[row_idx] if row_idx < len(box) else ""
            cols.append(line + " " * (col_width - visible_len(line)))

        rows.append((" " * gap).join(cols))

    return "\n".join(rows)

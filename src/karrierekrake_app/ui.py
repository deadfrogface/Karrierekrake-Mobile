"""Small UI helpers for a phone: one column, big touch targets, simple page stack per tab."""
from __future__ import annotations

import asyncio
import textwrap
from typing import Callable

import toga
from toga.style import Pack

TOUCH = 48  # minimum height of tappable controls (Material / Apple guidance)
MARGIN = 12
NAVY = "#132238"
TEAL = "#18A999"
MUTED = "#5b6b7b"
DANGER_BG = "#f5d6d6"
DANGER = "#b3261e"

_language = "de"
WRAP = 38  # characters per line on a phone screen; Toga labels do not wrap by themselves


def wrap(value: str, width: int = WRAP) -> str:
    return "\n".join(textwrap.fill(line, width) if line.strip() else "" for line in str(value).split("\n"))


def set_language(language: str) -> None:
    global _language
    _language = "en" if str(language).lower().startswith("en") else "de"


def t(de: str, en: str) -> str:
    return en if _language == "en" else de


def column(*children, margin: int = MARGIN, gap: int = 8, flex: int = 0) -> toga.Box:
    box = toga.Box(style=Pack(direction="column", margin=margin, gap=gap, flex=flex))
    for child in children:
        if child is not None:
            box.add(child)
    return box


def row(*children, gap: int = 8) -> toga.Box:
    box = toga.Box(style=Pack(direction="row", gap=gap))
    for child in children:
        if child is not None:
            box.add(child)
    return box


def title(text: str) -> toga.Label:
    return toga.Label(text, style=Pack(font_size=20, font_weight="bold", color=NAVY))


def heading(text: str) -> toga.Label:
    return toga.Label(wrap(text, 30), style=Pack(font_size=15, font_weight="bold", color=NAVY, margin_top=8))


def text(value: str, *, muted: bool = False) -> toga.Label:
    return toga.Label(wrap(value), style=Pack(color=MUTED if muted else NAVY))


def warning(value: str) -> toga.Label:
    return toga.Label(wrap(value, WRAP - 2), style=Pack(background_color=DANGER_BG, color=DANGER, margin=8))


def switch(label: str, **kwargs) -> toga.Switch:
    return toga.Switch(wrap(label, WRAP - 6), **kwargs)


def card(title_text: str, subtitle: str, on_press: Callable, *, action: str = "") -> toga.Box:
    """A list entry: bold title, grey subtitle, and a full-width button to open it."""
    return column(toga.Label(wrap(title_text), style=Pack(font_weight="bold", color=NAVY)),
                  toga.Label(wrap(subtitle), style=Pack(color=MUTED)),
                  toga.Button(action or t("Öffnen ›", "Open ›"), on_press=on_press, style=Pack(height=TOUCH, flex=1)),
                  margin=8, gap=4)


def button(label: str, on_press: Callable, *, primary: bool = False) -> toga.Button:
    style = Pack(height=TOUCH, flex=1)
    if primary:
        style = Pack(height=TOUCH, flex=1, background_color=TEAL, color="#ffffff", font_weight="bold")
    return toga.Button(label, on_press=on_press, style=style)


def field(label: str, value: str = "", placeholder: str = "") -> tuple[toga.Label, toga.TextInput]:
    return (toga.Label(label, style=Pack(color=MUTED)),
            toga.TextInput(value=value, placeholder=placeholder, style=Pack(height=TOUCH)))


class PageStack:
    """A tab's content: a list page, and detail pages pushed on top (Back returns)."""

    def __init__(self) -> None:
        self.container = toga.Box(style=Pack(direction="column", flex=1))
        self._pages: list[toga.Widget] = []

    def show(self, page: toga.Widget, *, root: bool = False) -> None:
        if root:
            self._pages = []
        self._pages.append(page)
        self._render()

    def back(self, *_args) -> None:
        if len(self._pages) > 1:
            self._pages.pop()
            self._render()

    @property
    def depth(self) -> int:
        return len(self._pages)

    def _render(self) -> None:
        for child in list(self.container.children):
            self.container.remove(child)
        self.container.add(toga.ScrollContainer(content=self._pages[-1], horizontal=False, style=Pack(flex=1)))


async def in_background(func: Callable, *args):
    """Run slow work (network, AI, files) off the UI thread."""
    return await asyncio.get_running_loop().run_in_executor(None, lambda: func(*args))

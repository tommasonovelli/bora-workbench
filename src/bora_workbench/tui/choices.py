"""Hold one screen's selectable actions and the flags each of them can carry.

A section shows a short list of actions and toggles their optional flags in place, so every
reachable `bora` form stays available without printing one menu row per flag combination.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from bora_workbench.tui.actions import CommandSpec


@dataclass(frozen=True, slots=True)
class Flag:
    """One toggleable CLI flag, the key that switches it, and the flag it cannot accompany."""

    key: str
    label: str
    excludes: str = ""


@dataclass(frozen=True, slots=True)
class Choice:
    """One selectable action row and the exact command its enabled flags compose."""

    label: str
    compose: Callable[[frozenset[str]], CommandSpec]
    flags: tuple[Flag, ...] = field(default_factory=tuple)


def _switched(enabled: frozenset[str], flag: Flag) -> frozenset[str]:
    """Return the flag set after switching one flag and dropping what it excludes."""
    if flag.label in enabled:
        return enabled - {flag.label}
    return (enabled | {flag.label}) - {flag.excludes}


class ChoiceList:
    """Track the marked action of one section and the flags enabled on each of its actions."""

    def __init__(self, choices: tuple[Choice, ...]) -> None:
        """Mark the first action with no flag enabled anywhere."""
        self._choices = choices
        self._index = 0
        self._enabled: dict[int, frozenset[str]] = {}

    @property
    def is_empty(self) -> bool:
        """Report whether this section offers no action at all, as Settings does."""
        return not self._choices

    @property
    def index(self) -> int:
        """Return the position of the marked action for screens that branch on it."""
        return self._index

    @property
    def selected(self) -> Choice:
        """Return the action the section currently marks."""
        return self._choices[self._index]

    def move(self, offset: int) -> None:
        """Move the marker with wraparound inside this section's own actions."""
        if self._choices:
            self._index = (self._index + offset) % len(self._choices)

    def enabled(self) -> frozenset[str]:
        """Return the flag labels currently enabled on the marked action."""
        return self._enabled.get(self._index, frozenset())

    def toggle(self, key: str) -> bool:
        """Switch the marked action's flag bound to one key and report whether it exists."""
        if self._choices:
            for flag in self.selected.flags:
                if flag.key == key:
                    self._enabled[self._index] = _switched(self.enabled(), flag)
                    return True
        return False

    def command(self) -> CommandSpec:
        """Compose the exact command already visible beside the marker."""
        return self.selected.compose(self.enabled())

    def rows(self) -> tuple[tuple[str, bool], ...]:
        """Return each action label with whether it currently carries the marker."""
        return tuple(
            (choice.label, index == self._index) for index, choice in enumerate(self._choices)
        )

    def flag_row(self) -> str:
        """Render the marked action's toggles, or nothing when it accepts no flag."""
        if self.is_empty:
            return ""
        enabled = self.enabled()
        return "   ".join(
            f"[{flag.key}] {flag.label} {'on' if flag.label in enabled else 'off'}"
            for flag in self.selected.flags
        )

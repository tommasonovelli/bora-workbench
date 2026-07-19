"""Parse calibrate-only expert and historical options kept outside the narrow CLI callback."""

from __future__ import annotations

from dataclasses import dataclass, field

from qwen_launcher.calibration import CalibrationError


@dataclass(slots=True)
class ParsedCalibrationOptions:
    """Collect repeatable and optional values from Typer's allowed extra arguments."""

    candidates: list[str] = field(default_factory=list)
    settings: str | None = None
    no_activate: bool = False
    activate: bool = False
    target_ctx: int | None = None


def _value(arguments: list[str], index: int, option: str) -> tuple[str, int]:
    """Read one mandatory option value and return it with the next parser position."""
    if index + 1 >= len(arguments) or arguments[index + 1].startswith("--"):
        raise CalibrationError(f"{option} requires a value")
    return arguments[index + 1], index + 2


def _target(value: str) -> int:
    """Parse an expert target context as an integer before protocol validation."""
    try:
        return int(value)
    except ValueError as error:
        raise CalibrationError("--target-ctx must be an integer") from error


def parse_calibration_options(arguments: list[str]) -> ParsedCalibrationOptions:
    """Parse documented calibrate extras while rejecting unknown or duplicate scalar options."""
    parsed = ParsedCalibrationOptions()
    index = 0
    while index < len(arguments):
        option = arguments[index]
        if option == "--candidate":
            value, index = _value(arguments, index, option)
            parsed.candidates.append(value)
            continue
        if option in {"--settings", "--target-ctx"}:
            value, index = _value(arguments, index, option)
            if option == "--settings":
                if parsed.settings is not None:
                    raise CalibrationError("--settings may be supplied only once")
                parsed.settings = value
            else:
                if parsed.target_ctx is not None:
                    raise CalibrationError("--target-ctx may be supplied only once")
                parsed.target_ctx = _target(value)
            continue
        if option == "--no-activate":
            parsed.no_activate = True
            index += 1
            continue
        if option == "--activate":
            parsed.activate = True
            index += 1
            continue
        raise CalibrationError(f"unknown calibrate option {option!r}")
    return parsed

"""Parse the calibrate-only extras kept outside the narrow Typer callback."""

from __future__ import annotations

from dataclasses import dataclass

from bora_workbench.calibration import CalibrationError


@dataclass(slots=True)
class ParsedCalibrationOptions:
    """Collect the optional values Typer forwards as extra arguments."""

    no_activate: bool = False
    activate: bool = False
    target_ctx: int | None = None


def _target(arguments: list[str], index: int) -> int:
    """Read and parse the mandatory ``--target-ctx`` value."""
    if index + 1 >= len(arguments) or arguments[index + 1].startswith("--"):
        raise CalibrationError("--target-ctx requires a value")
    try:
        return int(arguments[index + 1])
    except ValueError as error:
        raise CalibrationError("--target-ctx must be an integer") from error


def parse_calibration_options(arguments: list[str]) -> ParsedCalibrationOptions:
    """Parse the documented calibrate extras, rejecting unknown or duplicate options."""
    parsed = ParsedCalibrationOptions()
    index = 0
    while index < len(arguments):
        option = arguments[index]
        if option == "--target-ctx":
            if parsed.target_ctx is not None:
                raise CalibrationError("--target-ctx may be supplied only once")
            parsed.target_ctx = _target(arguments, index)
            index += 2
            continue
        if option == "--no-activate":
            parsed.no_activate = True
        elif option == "--activate":
            parsed.activate = True
        else:
            raise CalibrationError(f"unknown calibrate option {option!r}")
        index += 1
    return parsed

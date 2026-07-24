"""Expose the cross-context spike as a repository-only module command."""

from __future__ import annotations

import argparse
from pathlib import Path

from scripts.spike_ctx.dry_run import run_dry
from scripts.spike_ctx.refine import run_refinement
from scripts.spike_ctx.runner import run_real


def _arguments() -> argparse.Namespace:
    """Parse an explicit output root and optional offline dry-run mode."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--refine-ctx", type=int, choices=(98304, 49152))
    return parser.parse_args()


def main() -> None:
    """Run the selected package without ever deciding GO or NO-GO automatically."""
    arguments = _arguments()
    if arguments.dry_run and arguments.refine_ctx is not None:
        raise SystemExit("--dry-run and --refine-ctx cannot be combined")
    if arguments.dry_run:
        run_dry(arguments.output)
    elif arguments.refine_ctx is not None:
        run_refinement(arguments.output, arguments.refine_ctx)
    else:
        run_real(arguments.output)


if __name__ == "__main__":
    main()

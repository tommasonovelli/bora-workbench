"""Prove that shared v3 evidence can only reorder a complete local search."""

from __future__ import annotations

from dataclasses import replace

from qwen_launcher._calibration_v4_search import ProbeMeasurement, ScreeningPlan, screen
from qwen_launcher._calibration_v4_seed import seed_probe_value
from qwen_launcher.config import Config
from qwen_launcher.hardware import HardwareInfo
from qwen_launcher.profiles import load_catalog
from tests.test_calibration import cpu_target
from tests.v3_content_fixtures import build_v3_content


def _target(files):
    """Build a materially different CUDA target around packaged reference evidence."""
    catalog = load_catalog(files.root)
    hardware = HardwareInfo(
        "linux",
        "different-os",
        "Different CPU",
        24,
        64,
        48,
        "cuda",
        1,
        0,
        "Different GPU",
        16,
        15,
    )
    mode = catalog.mode("coding")
    assert mode is not None
    return replace(cpu_target(), catalog=catalog, modes=(mode,), hardware=hardware)


def _probe(minimum: int, order: list[int]):
    """Build a monotone local probe whose result is independent of shared ordering."""

    def measure(value: int) -> ProbeMeasurement:
        """Measure the local boundary without consulting report hardware or envelopes."""
        order.append(value)
        return ProbeMeasurement(value >= minimum, 7.5 - 0.05 * value)

    return measure


def test_reference_seed_matches_contract_not_remote_hardware(tmp_path) -> None:
    """Allow different components to reuse only an exact model/engine/backend ordering hint."""
    files = build_v3_content(tmp_path)
    target = _target(files)

    value = seed_probe_value(target, target.modes[0], 41)

    assert value == 38
    seed = target.catalog.calibration_seeds[0]
    assert not hasattr(seed, "ctx")
    assert not hasattr(seed, "hardware")


def test_model_engine_or_backend_incompatibility_ignores_reference_seed(tmp_path) -> None:
    """Ignore incompatible evidence rather than forcing its local result into another search."""
    files = build_v3_content(tmp_path)
    target = _target(files)
    wrong_model = replace(target, config=Config(model="other/model:file"))
    wrong_lock = {**target.lock, "release": "b99999"}
    wrong_engine = replace(target, lock=wrong_lock)
    cpu = replace(target, hardware=replace(target.hardware, backend="cpu"))

    assert seed_probe_value(wrong_model, target.modes[0], 41) is None
    assert seed_probe_value(wrong_engine, target.modes[0], 41) is None
    assert seed_probe_value(cpu, target.modes[0], 41) is None


def test_deleting_or_ignoring_seed_preserves_domain_and_local_result(tmp_path) -> None:
    """Change only first-probe order while preserving the full domain and measured boundary."""
    files = build_v3_content(tmp_path)
    target = _target(files)
    seed = seed_probe_value(target, target.modes[0], 41)
    seeded_order: list[int] = []
    plain_order: list[int] = []
    seeded_plan = ScreeningPlan(41, 5.45, 7.5, seed, 12)
    plain_plan = ScreeningPlan(41, 5.45, 7.5, None, 12)

    seeded = screen(_probe(38, seeded_order), seeded_plan)
    plain = screen(_probe(38, plain_order), plain_plan)

    assert seeded_plan.domain_maximum == plain_plan.domain_maximum == 41
    assert seeded.boundary == plain.boundary == 38
    assert seeded_order[0] == 38
    assert all(0 <= value <= 41 for value in (*seeded_order, *plain_order))

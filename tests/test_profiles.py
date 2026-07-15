"""Tests for immutable runtime mode and profile loading."""

from dataclasses import FrozenInstanceError

import pytest

from qwen_launcher.profiles import ContentError, load_catalog
from tests.content_fixtures import build_valid_content, copy_resource_root, read_json, write_json


def test_packaged_catalog_loads_modes_and_allows_no_profiles() -> None:
    """Load verified mode behavior while preserving the valid empty-profile state."""
    catalog = load_catalog()

    assert tuple(mode.id for mode in catalog.modes) == ("coding", "studio", "vstudio")
    assert catalog.profiles == ()
    coding = catalog.mode("coding")
    assert coding is not None
    assert coding.services.ui is False
    assert coding.services.vision is False
    assert coding.sampling.temp == 0.6
    assert coding.sampling.top_p == 0.95
    assert coding.sampling.top_k == 20


def test_runtime_models_are_frozen(tmp_path) -> None:
    """Prevent validated content from being mutated after catalog construction."""
    files = build_valid_content(tmp_path)
    catalog = load_catalog(files.root)

    with pytest.raises(FrozenInstanceError):
        catalog.modes[0].id = "changed"  # type: ignore[misc]


def test_synthetic_profile_loads_exact_envelope(tmp_path) -> None:
    """Construct immutable profile values only after full validation succeeds."""
    files = build_valid_content(tmp_path)

    profile = load_catalog(files.root).profiles[0]

    assert profile.id == "synthetic-profile"
    assert profile.is_engine_compatible is True
    assert profile.match.ram_gib.minimum_gib == 31
    assert profile.match.vram_gib.maximum_gib == 9
    envelope = profile.envelope_for("coding")
    assert envelope is not None
    assert envelope.ctx == 8192
    assert envelope.n_cpu_moe == 48
    assert envelope.tok_s is not None
    assert envelope.tok_s.median == 3


def test_loader_refuses_invalid_content(tmp_path) -> None:
    """Never construct runtime models from a schema-invalid mode."""
    root = copy_resource_root(tmp_path)
    path = root / "content/modes/coding.json"
    mode = read_json(path)
    mode["sampling"]["top_p"] = 0  # type: ignore[index]
    write_json(path, mode)

    with pytest.raises(ContentError, match="top_p"):
        load_catalog(root)

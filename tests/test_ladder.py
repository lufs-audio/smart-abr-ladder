"""Red/green tests for ladder selection + verification. stdlib only (no ffmpeg fixtures —
the pure selection logic and verifier's monotone/bitrate math are unit-tested directly)."""
import pytest

from smart_abr_ladder.ladder import LadderError, select_renditions
from smart_abr_ladder.verifier import ContractViolation, verify_ladder


def test_select_renditions_monotone():
    bit = {360: 800.0, 720: 2500.0, 1080: 5000.0}
    q = {360: 90.0, 720: 93.0, 1080: 95.0}
    r = select_renditions(1080, bit, q)
    heights = [x["height"] for x in r]
    assert heights == sorted(heights)
    qs = [x["vmaf_target"] for x in r]
    assert qs == sorted(qs)  # monotone
    assert len(r) == 3


def test_select_renditions_prunes_redundant():
    # 720 and 1080 have identical quality → the 1080 rung is dominated (no quality gain) and
    # should be pruned unless bitrate spacing justifies it. With quality equal and spacing
    # above the floor, keep only the materially-better one.
    bit = {360: 800.0, 720: 2500.0, 1080: 2600.0}
    q = {360: 90.0, 720: 93.0, 1080: 93.0}
    r = select_renditions(1080, bit, q, min_spacing_kbps=400.0)
    heights = [x["height"] for x in r]
    # equal quality + only 100kbps spacing → 1080 is redundant and pruned
    assert 1080 not in heights


def test_select_renditions_infeasible_raises():
    with pytest.raises(LadderError):
        select_renditions(1080, {360: 100.0, 720: 100.0}, {360: 50.0, 720: 50.0}, floor_kbps=300.0)


def test_verify_ladder_rejects_low_vmaf():
    # target 93, tolerate 2 → measured (simulated by direct target mismatch) fails contract
    # verify_ladder re-measures from the output file, so we test the monotone + failure-shape
    # logic through a monkeypatched measure_vmaf returning a failing value.
    import smart_abr_ladder.verifier as V

    renditions = [{"height": 1080, "width": 1920, "bitrate_kbps": 5000, "vmaf_target": 95.0, "codec": "libx264"}]
    outputs = {1080: "/tmp/does-not-matter.mp4"}
    # patch probe_source and measure_vmaf to avoid needing real files
    V.probe_source = lambda p: {"duration_s": 2.0, "video": {"w": 1920, "h": 1080}}
    V.measure_vmaf = lambda s, d: 80.0  # well below the 95 target
    V.measure_bitrate_kbps = lambda p: 5000.0
    report = V.verify_ladder("/fake/src", renditions, outputs, vmaf_tolerance=2.0)
    assert report["verified"] is False
    assert any(f["rule"].endswith("_vmaf") for f in report["failures"])


def test_verify_ladder_non_monotone():
    import smart_abr_ladder.verifier as V
    renditions = [
        {"height": 720, "width": 1280, "bitrate_kbps": 2500, "vmaf_target": 95.0, "codec": "libx264"},
        {"height": 1080, "width": 1920, "bitrate_kbps": 5000, "vmaf_target": 90.0, "codec": "libx264"},
    ]
    outputs = {720: "/tmp/a", 1080: "/tmp/b"}
    V.probe_source = lambda p: {"duration_s": 2.0, "video": {"w": 1920, "h": 1080}}
    V.measure_vmaf = lambda s, d: 95.0
    V.measure_bitrate_kbps = lambda p: 5000.0
    report = V.verify_ladder("/fake", renditions, outputs, vmaf_tolerance=2.0)
    # quality decreases with height → non-monotone flagged
    assert any(f["rule"] == "ladder_monotone" for f in report["failures"])

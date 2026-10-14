"""The edge command must not invent latency or accuracy."""

import pytest

from tiffintally.edge import TIER_CATALOG, EdgeBenchmarkRunner, EdgeExporter, EdgeNotMeasured


def test_edge_catalog_is_not_a_measured_accuracy():
    assert TIER_CATALOG["tier1_edge"].real_order_em_accuracy is None
    assert TIER_CATALOG["tier2_midsize"].real_order_em_accuracy is None
    assert TIER_CATALOG["tier3_cloud"].real_order_em_accuracy is None


def test_edge_benchmark_refuses(tmp_path):
    runner = EdgeBenchmarkRunner()
    with pytest.raises(EdgeNotMeasured):
        runner.run_benchmark(tier_key="tier1_edge", num_queries=5)


def test_edge_export_does_not_claim_a_quantized_model(tmp_path):
    exporter = EdgeExporter(output_root=tmp_path)
    res = exporter.export_tier("tier1_edge")
    assert res["status"] == "not_measured"
    content = (tmp_path / "tier1_edge" / "edge_manifest.json").read_text(encoding="utf-8")
    assert "not_measured" in content
    assert "q4_k_m" not in content

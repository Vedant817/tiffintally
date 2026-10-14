"""Unit tests for offline edge quantized export and benchmarking."""

from pathlib import Path
from tiffintally.edge import EdgeBenchmarkRunner, EdgeExporter, TIER_CATALOG


def test_edge_catalog_specs():
    assert "tier1_edge" in TIER_CATALOG
    assert "tier2_midsize" in TIER_CATALOG
    assert "tier3_cloud" in TIER_CATALOG

    edge_spec = TIER_CATALOG["tier1_edge"]
    assert edge_spec.adapter_size_mb == 8.64
    assert edge_spec.parameter_count_millions == 2.16
    assert edge_spec.real_order_em_accuracy == 100.0


def test_edge_benchmarking_tier1():
    runner = EdgeBenchmarkRunner()
    result = runner.run_benchmark(tier_key="tier1_edge", num_queries=5)

    assert result.success is True
    assert result.adapter_size_mb == 8.64
    assert result.queries_run == 5
    assert result.p50_latency_ms < 400.0
    assert result.exact_match_accuracy_pct == 100.0
    assert "Raspberry Pi" in result.hardware


def test_edge_benchmarking_tier2():
    runner = EdgeBenchmarkRunner()
    result = runner.run_benchmark(tier_key="tier2_midsize", num_queries=5)

    assert result.success is True
    assert result.adapter_size_mb == 35.20
    assert result.queries_run == 5
    assert result.p50_latency_ms > 350.0


def test_edge_export(tmp_path):
    exporter = EdgeExporter(output_root=tmp_path)
    res = exporter.export_tier("tier1_edge")

    assert res["status"] == "exported"
    manifest_file = Path(res["manifest_file"])
    assert manifest_file.exists()

    content = manifest_file.read_text(encoding="utf-8")
    assert "gemma-2-2b-it" in content
    assert "q4_k_m" in content
    assert "8.64" in content

    adapter_config_file = manifest_file.parent / "adapter_config.json"
    assert adapter_config_file.exists()

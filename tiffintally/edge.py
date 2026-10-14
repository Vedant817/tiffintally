"""
Edge catalog and export hooks.

No Raspberry Pi, GGUF, or quantized-model run is stored in this repo.
benchmark-edge refuses instead of printing constants.
"""

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

logger = logging.getLogger("tiffintally.edge")


@dataclass
class EdgeModelSpec:
    tier: str
    target_hardware: str
    parameter_count_millions: float
    adapter_size_mb: float
    target_latency_ms: float
    lora_rank: int
    lora_alpha: int
    target_modules: list[str]
    quantization_format: str
    real_order_em_accuracy: Optional[float]


TIER_CATALOG: dict[str, EdgeModelSpec] = {
    "tier1_edge": EdgeModelSpec(
        tier="tier1 config only, not measured on a device",
        target_hardware="Raspberry Pi 5 / Android Termux / Local Cook Laptop",
        parameter_count_millions=2.16,
        adapter_size_mb=8.64,
        target_latency_ms=295.7,
        lora_rank=4,
        lora_alpha=16,
        target_modules=["q_proj", "v_proj"],
        quantization_format="q4_k_m / int4 GGUF",
        real_order_em_accuracy=None,
    ),
    "tier2_midsize": EdgeModelSpec(
        tier="tier2 config only, not measured on a device",
        target_hardware="$5/mo VPS / Hetzner Cloud CPU",
        parameter_count_millions=8.80,
        adapter_size_mb=35.20,
        target_latency_ms=459.3,
        lora_rank=16,
        lora_alpha=64,
        target_modules=[
            "q_proj",
            "k_proj",
            "v_proj",
            "o_proj",
            "gate_proj",
            "up_proj",
            "down_proj",
        ],
        quantization_format="q8_0 / int8 GGUF",
        real_order_em_accuracy=None,
    ),
    "tier3_cloud": EdgeModelSpec(
        tier="tier3 config only, not measured on a device",
        target_hardware="Modal T4/A10G GPU / High-throughput Cloud",
        parameter_count_millions=17.60,
        adapter_size_mb=70.40,
        target_latency_ms=466.8,
        lora_rank=32,
        lora_alpha=64,
        target_modules=[
            "q_proj",
            "k_proj",
            "v_proj",
            "o_proj",
            "gate_proj",
            "up_proj",
            "down_proj",
        ],
        quantization_format="fp16 / bfloat16 safetensors",
        real_order_em_accuracy=None,
    ),
}


@dataclass
class EdgeBenchmarkResult:
    tier: str
    hardware: str
    adapter_size_mb: float
    queries_run: int
    p50_latency_ms: float
    p95_latency_ms: float
    avg_latency_ms: float
    tokens_per_sec: float
    estimated_ram_mb: float
    exact_match_accuracy_pct: float
    success: bool


class EdgeNotMeasured(RuntimeError):
    """No on-device measurement exists for this tier."""


class EdgeBenchmarkRunner:
    """Refuses to invent latency, RAM, or accuracy. No on-device run exists."""

    def __init__(self, catalog: Optional[dict[str, EdgeModelSpec]] = None):
        self.catalog = catalog or TIER_CATALOG

    def run_benchmark(
        self,
        tier_key: str = "tier1_edge",
        num_queries: int = 15,
    ) -> EdgeBenchmarkResult:
        del num_queries
        if tier_key not in self.catalog:
            raise ValueError(f"Unknown tier '{tier_key}'. Available: {list(self.catalog.keys())}")
        raise EdgeNotMeasured(
            "No edge benchmark has been run. Latency, RAM, and exact-match figures "
            "are not available. This used to sleep and print catalog constants."
        )


class EdgeExporter:
    """Exports deployment bundles for edge deployment via llama.cpp or ONNX."""

    def __init__(self, output_root: Path = Path("models/edge_export")):
        self.output_root = output_root

    def export_tier(self, tier_key: str = "tier1_edge") -> dict:
        if tier_key not in TIER_CATALOG:
            raise ValueError(f"Unknown tier: {tier_key}")

        dest_dir = self.output_root / tier_key
        dest_dir.mkdir(parents=True, exist_ok=True)

        manifest = {
            "status": "not_measured",
            "tier_key": tier_key,
            "note": (
                "No quantized weights were exported. Earlier manifests copied catalog "
                "constants and were not produced by llama.cpp, GGUF, or a Raspberry Pi."
            ),
        }

        manifest_path = dest_dir / "edge_manifest.json"
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        note_path = dest_dir / "NOT_A_MODEL.txt"
        note_path.write_text(manifest["note"] + "\n", encoding="utf-8")

        return {
            "status": "not_measured",
            "tier": tier_key,
            "manifest_file": str(manifest_path),
            "directory": str(dest_dir),
        }

"""Template registry for Prometheus AI inspection training data generation.

Provides a unified interface to generate ScenarioConfig objects across all
metric categories and scenario types.
"""

import random
from collections.abc import Callable

from inspection_lora.data_utils import ScenarioConfig

from .cpu_templates import (
    gen_cpu_iowait_high,
    gen_cpu_load_mismatch,
    gen_cpu_normal,
    gen_cpu_spike,
    gen_cpu_sustained_high,
    gen_cpu_system_high,
)
from .disk_templates import (
    gen_disk_inode_exhaustion,
    gen_disk_io_saturation,
    gen_disk_normal,
    gen_disk_space_low,
    gen_disk_write_latency,
)
from .memory_templates import (
    gen_memory_leak_trend,
    gen_memory_low_available,
    gen_memory_normal,
    gen_memory_oom_risk,
    gen_memory_swap_pressure,
)
from .network_templates import (
    gen_network_asymmetric,
    gen_network_bandwidth_saturation,
    gen_network_normal,
    gen_network_traffic_spike,
)
from .composite_templates import (
    gen_cpu_io_correlation,
    gen_cpu_memory_load,
    gen_disk_network_backup,
    gen_full_stack_degradation,
    gen_load_cpu_divergence,
    gen_memory_swap_cascade,
)

GeneratorFn = Callable[[random.Random], ScenarioConfig]


def _wrap(fn, override: str) -> GeneratorFn:
    """Wrap a generator to force a specific scenario_type."""

    def wrapped(rng: random.Random) -> ScenarioConfig:
        return fn(rng, scenario_type_override=override)

    wrapped.__name__ = fn.__name__
    return wrapped


# Registry: scenario_type -> list of generator functions
TEMPLATE_REGISTRY: dict[str, list[GeneratorFn]] = {
    "single_anomaly": [
        gen_cpu_spike,
        gen_cpu_sustained_high,
        gen_cpu_iowait_high,
        gen_cpu_system_high,
        gen_cpu_load_mismatch,
        gen_memory_low_available,
        gen_memory_oom_risk,
        gen_memory_swap_pressure,
        gen_disk_space_low,
        gen_disk_io_saturation,
        gen_disk_inode_exhaustion,
        gen_disk_write_latency,
        gen_network_traffic_spike,
        gen_network_asymmetric,
        gen_network_bandwidth_saturation,
    ],
    "multi_metric": [
        gen_cpu_io_correlation,
        gen_memory_swap_cascade,
        gen_cpu_memory_load,
        gen_disk_network_backup,
        gen_full_stack_degradation,
        gen_load_cpu_divergence,
    ],
    "normal": [
        gen_cpu_normal,
        gen_memory_normal,
        gen_disk_normal,
        gen_network_normal,
    ],
    "capacity": [
        gen_memory_leak_trend,
        _wrap(gen_disk_space_low, "capacity"),
        _wrap(gen_network_bandwidth_saturation, "capacity"),
    ],
    "health": [
        _wrap(gen_cpu_normal, "health"),
        _wrap(gen_memory_normal, "health"),
        _wrap(gen_disk_normal, "health"),
        _wrap(gen_cpu_sustained_high, "health"),
        _wrap(gen_memory_low_available, "health"),
        _wrap(gen_cpu_io_correlation, "health"),
    ],
    "report": [
        _wrap(gen_cpu_spike, "report"),
        _wrap(gen_memory_oom_risk, "report"),
        _wrap(gen_disk_io_saturation, "report"),
        _wrap(gen_full_stack_degradation, "report"),
        _wrap(gen_cpu_normal, "report"),
        _wrap(gen_memory_normal, "report"),
    ],
}


def generate_scenarios(
    scenario_type: str,
    count: int,
    rng: random.Random,
) -> list[ScenarioConfig]:
    """Generate `count` ScenarioConfigs by round-robin cycling through registered generators."""
    generators = TEMPLATE_REGISTRY.get(scenario_type)
    if not generators:
        raise ValueError(
            f"Unknown scenario_type: {scenario_type}. Available: {list(TEMPLATE_REGISTRY.keys())}"
        )

    configs = []
    for i in range(count):
        gen = generators[i % len(generators)]
        configs.append(gen(rng))
    return configs

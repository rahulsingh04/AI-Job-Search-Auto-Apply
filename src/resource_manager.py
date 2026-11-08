"""Adaptive resource manager for safe parallel worker calculation."""

import os

import psutil


def get_safe_workers(scraper_cfg: dict) -> int:
    """Calculate safe parallel workers from live stats and config."""
    resource_cfg = scraper_cfg.get("resource", {})

    max_cap = resource_cfg.get("max_worker_cap", 5)
    threshold = resource_cfg.get(
        "cpu_overload_threshold", 80
    )
    ram_per = resource_cfg.get("ram_per_worker_gb", 2.0)
    min_workers = resource_cfg.get("min_workers", 2)

    cpu_usage = psutil.cpu_percent(interval=0.5)
    free_ram_gb = (
        psutil.virtual_memory().available / (1024 ** 3)
    )
    cpu_cores = os.cpu_count() or 1

    if cpu_usage > threshold:
        return min_workers

    safe = max(
        min_workers,
        min(
            cpu_cores // 2,
            int(free_ram_gb // ram_per),
            max_cap,
        ),
    )
    return safe


def get_system_stats(scraper_cfg: dict) -> dict:
    """Return live CPU, RAM stats and safe worker count."""
    cpu_percent = psutil.cpu_percent(interval=0.5)
    mem = psutil.virtual_memory()
    free_ram_gb = round(mem.available / (1024 ** 3), 1)
    total_ram_gb = round(mem.total / (1024 ** 3), 1)
    safe_workers = get_safe_workers(scraper_cfg)

    return {
        "cpu_percent": cpu_percent,
        "ram_free_gb": free_ram_gb,
        "ram_total_gb": total_ram_gb,
        "safe_workers": safe_workers,
    }

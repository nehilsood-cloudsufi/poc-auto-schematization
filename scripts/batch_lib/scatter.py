"""Matplotlib scatter plot writer — log-log, clean, label datasets sparingly."""
from __future__ import annotations

from pathlib import Path
from typing import Iterable, Tuple

import matplotlib
matplotlib.use("Agg")  # No display; safe in subprocess / CI
import matplotlib.pyplot as plt


def _get(record, key_path):
    cur = record
    for k in key_path:
        if cur is None:
            return None
        cur = cur.get(k) if isinstance(cur, dict) else None
    return cur


def write_scatter(
    records: Iterable[dict],
    out_path: Path,
    x_key: Tuple[str, ...],
    y_key: Tuple[str, ...],
    title: str,
    log_scale: bool = True,
) -> None:
    xs, ys, labels = [], [], []
    for r in records:
        x = _get(r, x_key)
        y = _get(r, y_key)
        if x is None or y is None or x <= 0 or y <= 0:
            continue
        xs.append(x)
        ys.append(y)
        labels.append(r.get("dataset", ""))

    fig, ax = plt.subplots(figsize=(10, 7))
    if xs:
        ax.scatter(xs, ys, alpha=0.7)
        if log_scale:
            ax.set_xscale("log")
            ax.set_yscale("log")
        if len(xs) >= 5:
            top = sorted(range(len(xs)), key=lambda i: ys[i], reverse=True)[:5]
            for i in top:
                ax.annotate(labels[i], (xs[i], ys[i]), fontsize=7, alpha=0.8)
    else:
        ax.text(0.5, 0.5, "No data", ha="center", va="center", transform=ax.transAxes)

    ax.set_xlabel(".".join(x_key))
    ax.set_ylabel(".".join(y_key))
    ax.set_title(title)
    ax.grid(True, which="both", ls="--", alpha=0.3)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    try:
        fig.savefig(out_path, dpi=120)
    finally:
        plt.close(fig)

"""Figures for the paper: colour-blind-safe (Okabe-Ito), direct labels, no titles (the paper
adds captions). Each function writes <path>.png at 200 dpi and <path>.svg."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

OKABE_ITO = ["#0072B2", "#E69F00", "#009E73", "#D55E00", "#CC79A7", "#56B4E9", "#F0E442", "#000000"]


def _save(fig, path: Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    for ext in ("png", "svg"):
        fig.savefig(path.with_suffix(f".{ext}"), dpi=200, bbox_inches="tight")
    plt.close(fig)


def bar_with_ci(df, x, y, lo, hi, path):
    fig, ax = plt.subplots(figsize=(6, 3))
    xs = range(len(df))
    ax.bar(xs, df[y], color=OKABE_ITO[0])
    ax.errorbar(
        xs, df[y], yerr=[df[y] - df[lo], df[hi] - df[y]], fmt="none", ecolor="black", capsize=3
    )
    for i, v in zip(xs, df[y], strict=True):
        ax.text(i, v + 0.02, f"{v:.2f}", ha="center", va="bottom", fontsize=8)
    ax.set_xticks(list(xs), df[x])
    ax.set_ylim(0, 1.05)
    ax.set_ylabel(y)
    ax.spines[["top", "right"]].set_visible(False)
    _save(fig, path)


def stacked_outcomes(df, path):
    fig, ax = plt.subplots(figsize=(6, 3))
    bottom = None
    for i, col in enumerate([c for c in df.columns if c != "group"]):
        ax.bar(df["group"], df[col], bottom=bottom, label=col, color=OKABE_ITO[i % 8])
        bottom = df[col] if bottom is None else bottom + df[col]
    ax.legend(frameon=False, fontsize=8)
    ax.spines[["top", "right"]].set_visible(False)
    _save(fig, path)


def slope(df, path):
    fig, ax = plt.subplots(figsize=(4, 4))
    for i, r in enumerate(df.itertuples()):
        ax.plot([0, 1], [r.metric_before, r.metric_after], marker="o", color=OKABE_ITO[i % 8])
        ax.text(1.03, r.metric_after, r.control_id, fontsize=7, va="center")
    ax.set_xticks([0, 1], ["before", "after (held-out)"])
    ax.spines[["top", "right"]].set_visible(False)
    _save(fig, path)


def box(df, x, y, path):
    fig, ax = plt.subplots(figsize=(6, 3))
    groups = sorted(df[x].unique())
    ax.boxplot([df[df[x] == g][y] for g in groups], tick_labels=groups)
    ax.set_ylabel(y)
    ax.spines[["top", "right"]].set_visible(False)
    _save(fig, path)

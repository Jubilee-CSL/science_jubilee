"""Generic pre-run config dialog for Sacred experiments.

Usage in any experiment::

    from science_jubilee.scripts.config_dialog import ask_run_config

    @ex.automain
    def main(_config, _run):
        cfg = ask_run_config(_config)
        # use cfg values — include ``name = ""`` in @ex.config to get a run label
"""

import ast
import math
import tkinter as tk
from tkinter import ttk


def ask_run_config(
    config: dict,
    title: str = "Configure experiment",
) -> dict:
    """Pop a modal form with all config keys editable.

    Nested dicts are shown as ``parent.child`` rows.
    Returns updated config dict or raises ``SystemExit(0)`` on cancel.
    """
    flat_items = list(_flatten(config).items())

    root = tk.Tk()
    root.title(title)
    root.resizable(False, False)

    # --- Config fields ---
    entry_vars: dict[str, tk.StringVar] = {}
    rows_per_column = max(1, math.ceil(len(flat_items) / 2))

    for i, (key, value) in enumerate(flat_items):
        col_group = i // rows_per_column  # 0 (left) or 1 (right)
        row = i % rows_per_column
        label_col = col_group * 2
        entry_col = label_col + 1

        tk.Label(root, text=key).grid(
            row=row,
            column=label_col,
            sticky="w",
            padx=(12, 6),
            pady=3,
        )
        text = repr(value) if isinstance(value, (list, tuple)) else str(value)
        var = tk.StringVar(value=text)
        tk.Entry(root, textvariable=var, width=44).grid(
            row=row,
            column=entry_col,
            padx=(6, 12),
            pady=3,
        )
        entry_vars[key] = var

    # --- Buttons ---
    cancelled = [False]

    def on_cancel():
        cancelled[0] = True
        root.quit()

    sep_row = rows_per_column
    ttk.Separator(root, orient="horizontal").grid(
        row=sep_row, column=0, columnspan=4, sticky="ew", padx=8, pady=4
    )
    btn_frame = tk.Frame(root)
    btn_frame.grid(row=sep_row + 1, column=0, columnspan=4, pady=(0, 12))
    tk.Button(btn_frame, text="Run", width=14, command=root.quit).pack(
        side="left", padx=6
    )
    tk.Button(btn_frame, text="Cancel", width=14, command=on_cancel).pack(
        side="left", padx=6
    )

    root.mainloop()
    root.destroy()

    if cancelled[0]:
        raise SystemExit(0)

    updated_flat: dict = {}
    for key, var in entry_vars.items():
        raw = var.get().strip()
        try:
            updated_flat[key] = ast.literal_eval(raw)
        except (ValueError, SyntaxError):
            updated_flat[key] = raw

    return _unflatten(updated_flat, config)


def _flatten(d: dict, prefix: str = "") -> dict:
    out: dict = {}
    for k, v in d.items():
        key = f"{prefix}{k}" if prefix else k
        if isinstance(v, dict):
            out.update(_flatten(v, f"{key}."))
        else:
            out[key] = v
    return out


def _unflatten(flat: dict, original: dict) -> dict:
    result: dict = {}
    for k, v in original.items():
        if isinstance(v, dict):
            result[k] = {
                sub_k: flat.get(f"{k}.{sub_k}", sub_v) for sub_k, sub_v in v.items()
            }
        else:
            result[k] = flat.get(k, v)
    return result

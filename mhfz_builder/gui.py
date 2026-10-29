"""Optional read-only viewer. No GUI imports are required by the CLI."""
from __future__ import annotations
import json
from pathlib import Path
from .refrontier import read_summary


def launch(config: dict, initial: Path | None = None) -> None:
    import tkinter as tk
    from tkinter import ttk, filedialog, messagebox
    root = tk.Tk()
    root.title("MHFZ AI Quest Builder - Optional inspector")
    root.geometry("1050x720")
    toolbar = ttk.Frame(root, padding=8)
    toolbar.pack(fill="x")
    status = tk.StringVar(value="Read-only. Data preview, not a client simulation.")
    ttk.Label(toolbar, textvariable=status).pack(side="right")
    notebook = ttk.Notebook(root)
    notebook.pack(fill="both", expand=True, padx=8, pady=8)
    views = {}
    for label in ("General", "Monsters and spawns", "Objectives", "Rewards", "Texts", "JSON"):
        view = tk.Text(notebook, wrap="word", font=("Consolas", 11), state="disabled")
        notebook.add(view, text=label)
        views[label] = view

    def show(path: Path) -> None:
        try:
            summary = read_summary(config, path.resolve())
            values = {"General": {k: summary[k] for k in ("quest_id", "title", "map_name", "stat_table", "class", "variants", "quest_flags", "player_stages", "return_stage", "limitations")},
                      "Monsters and spawns": summary["monsters"], "Objectives": {"objectives": summary["objectives"], "finish_raw": summary["finish_raw"]},
                      "Rewards": summary["rewards"], "Texts": summary["texts"], "JSON": summary}
            for label, value in values.items():
                view = views[label]
                view.configure(state="normal")
                view.delete("1.0", "end")
                view.insert("1.0", json.dumps(value, ensure_ascii=False, indent=2))
                view.configure(state="disabled")
            status.set(f"{path.name} - read-only")
        except Exception as exc:
            messagebox.showerror("Unable to open quest", str(exc))

    def choose() -> None:
        filename = filedialog.askopenfilename(filetypes=[("Quest BIN", "*.bin"), ("All files", "*.*")])
        if filename:
            show(Path(filename))
    ttk.Button(toolbar, text="Open quest", command=choose).pack(side="left")
    if initial:
        root.after(0, lambda: show(initial))
    root.mainloop()

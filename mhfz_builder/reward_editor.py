"""Optional graphical reward request editor. Saves JSON drafts, never quest BINs."""
import json
from pathlib import Path


def validate_rows(rows):
    if not rows:
        raise ValueError("Add at least one reward.")
    for row in rows:
        if set(row) != {"slot", "item_id", "name", "quantity", "rate"}:
            raise ValueError("Invalid reward fields.")
        if row["slot"] not in ("Main", "Sub A", "Sub B"):
            raise ValueError("Invalid reward slot.")
        for key, high in (("item_id", 65535), ("quantity", 65535), ("rate", 100)):
            if type(row[key]) is not int or not 1 <= row[key] <= high:
                raise ValueError(f"{key} must be between 1 and {high}.")
        if not isinstance(row["name"], str) or not row["name"].strip():
            raise ValueError("Enter the reward name (names/IDs are not automatically verified).")
    return {slot: sum(r["rate"] for r in rows if r["slot"] == slot)
            for slot in ("Main", "Sub A", "Sub B") if any(r["slot"] == slot for r in rows)}


def save_draft(path, rows):
    totals = validate_rows(rows)
    value = {"schema_version": 1, "kind": "reward_authoring_draft", "bin_encoded": False,
             "rows": rows, "totals": totals,
             "warnings": [f"{slot} weights total {total}, not 100." for slot, total in totals.items() if total != 100]}
    # A session has a single save, never overwriting a previous recipe.
    with Path(path).open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
    return value


def launch(path):
    import tkinter as tk
    from tkinter import ttk, messagebox
    root = tk.Tk(); root.title("AI Quest Builder - Custom reward draft"); root.geometry("920x580")
    ttk.Label(root, text="Custom rewards", font=("Segoe UI", 18, "bold")).pack(anchor="w", padx=16, pady=12)
    ttk.Label(root, text="Draft only: saved as JSON for the future BIN reward writer. Names and item IDs need verification.").pack(anchor="w", padx=16)
    table = ttk.Treeview(root, columns=("slot", "item_id", "name", "quantity", "rate"), show="headings")
    for key, label in zip(table["columns"], ("Objective", "Item ID", "Reward name", "Quantity", "Weight %")):
        table.heading(key, text=label); table.column(key, width=150)
    table.pack(fill="both", expand=True, padx=16, pady=12)
    form = ttk.Frame(root); form.pack(fill="x", padx=16)
    fields = {}
    for col, (key, label, default) in enumerate((("slot", "Objective", "Main"), ("item_id", "Item ID", ""), ("name", "Reward name", ""), ("quantity", "Quantity", "1"), ("rate", "Weight %", "100"))):
        ttk.Label(form, text=label).grid(row=0, column=col, sticky="w")
        field = ttk.Combobox(form, values=("Main", "Sub A", "Sub B"), state="readonly", width=15) if key == "slot" else ttk.Entry(form, width=22 if key == "name" else 13)
        field.grid(row=1, column=col, padx=(0, 8)); field.insert(0, default)
        if key == "slot": field.set(default)
        fields[key] = field
    rows = []
    result = False
    def add():
        try:
            row = {k: field.get() for k, field in fields.items()}
            for key in ("item_id", "quantity", "rate"): row[key] = int(row[key])
            validate_rows([row]); rows.append(row)
            table.insert("", "end", values=tuple(row[k] for k in table["columns"]))
        except ValueError as exc: messagebox.showerror("Reward", str(exc), parent=root)
    def remove():
        for item in reversed(table.selection()):
            rows.pop(table.index(item)); table.delete(item)
    def save():
        nonlocal result
        try:
            value = save_draft(path, rows)
            if value["warnings"]: messagebox.showwarning("Review weights", "\n".join(value["warnings"]), parent=root)
            result = True; root.destroy()
        except (ValueError, OSError) as exc: messagebox.showerror("Reward draft", str(exc), parent=root)
    actions = ttk.Frame(root); actions.pack(fill="x", padx=16, pady=18)
    for label, callback in (("Add reward", add), ("Remove selected", remove), ("Save draft", save), ("Back / cancel", root.destroy)):
        ttk.Button(actions, text=label, command=callback).pack(side="left", padx=(0, 10))
    root.mainloop()
    return result

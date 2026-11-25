"""Player-facing Windows setup window. Done by Codex."""

from argparse import Namespace
import json
import os
from pathlib import Path
from queue import Empty, Queue
import subprocess
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import traceback
import webbrowser


def show(install, setup_error, root, data, game_exe, sony_firmware, font_url):
    window = tk.Tk()
    window.title("Phantasy Star Nova Recomp Setup")
    window.minsize(700, 520)
    panel = ttk.Frame(window, padding=18)
    panel.grid(sticky="nsew")
    window.columnconfigure(0, weight=1)
    window.rowconfigure(0, weight=1)
    panel.columnconfigure(1, weight=1)
    panel.rowconfigure(8, weight=1)

    ttk.Label(panel, text="Phantasy Star Nova Recomp", font=("Segoe UI", 17, "bold")).grid(
        row=0, columnspan=3, sticky="w")
    ttk.Label(panel, justify="left", text="Japanese PS Vita game (PCSG00351), base 1.00 and update 1.05. Choose the "
              "base-game PKG and the update PKG,\nor one ZIP that contains both. English installs automatically.").grid(
        row=1, columnspan=3, sticky="w", pady=(4, 14))

    try:
        previous = json.loads((data / "setup-inputs.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        previous = {}
    fields = {}
    controls = []

    def path_row(row, key, label, filetypes=None):
        remembered = previous.get(key, "")
        value = tk.StringVar(value=remembered if remembered and Path(remembered).exists() else "")
        fields[key] = value
        ttk.Label(panel, text=label).grid(row=row, column=0, sticky="w", pady=4, padx=(0, 12))
        entry = ttk.Entry(panel, textvariable=value)
        entry.grid(row=row, column=1, sticky="ew")

        def browse():
            if filetypes:
                choice = filedialog.askopenfilename(parent=window, title=label, filetypes=filetypes)
            else:
                choice = filedialog.askdirectory(parent=window, title=label, mustexist=True)
            if choice:
                value.set(choice)

        button = ttk.Button(panel, text="Browse…", command=browse)
        button.grid(row=row, column=2, padx=(8, 0))
        controls.extend((entry, button))

    path_row(2, "game", "Game PKG or ZIP", [("Game package or ZIP", "*.pkg *.zip"), ("All files", "*.*")])
    path_row(3, "update", "Update PKG (optional)", [("Update package", "*.pkg"), ("All files", "*.*")])
    path_row(4, "license", "Game license (if required)", [("Game license", "*.rif work.bin"), ("All files", "*.*")])
    path_row(5, "firmware", "Vita firmware 3.74", [("Vita update", "*.pup"), ("All files", "*.*")])
    font_included = (root / "localization/fonts/glenthregular.ttf").is_file()
    font_label = "Font (optional override)" if font_included else "Glenth Regular font"
    path_row(6, "font", font_label, [("Fonts", "*.ttf *.otf"), ("All files", "*.*")])

    buttons = ttk.Frame(panel)
    buttons.grid(row=7, columnspan=3, sticky="ew", pady=(10, 10))
    ttk.Button(buttons, text="Get firmware from Sony", command=lambda: webbrowser.open(sony_firmware)).pack(side="left")
    if not font_included:
        ttk.Button(buttons, text="Get Glenth font", command=lambda: webbrowser.open(font_url)).pack(side="left", padx=(8, 0))
    ttk.Button(buttons, text="Open setup logs", command=lambda: os.startfile(os.environ.get("NOVA_SETUP_LOGS", str(root)))).pack(
        side="left", padx=8)

    activity = ttk.Frame(panel)
    activity.grid(row=8, columnspan=3, sticky="nsew")
    activity.columnconfigure(0, weight=1)
    activity.rowconfigure(0, weight=1)
    log = tk.Text(activity, height=9, width=72, wrap="word", state="disabled", font=("Segoe UI", 10))
    log.grid(row=0, column=0, sticky="nsew")
    scroll = ttk.Scrollbar(activity, command=log.yview)
    scroll.grid(row=0, column=1, sticky="ns")
    log.configure(yscrollcommand=scroll.set)

    status = ttk.Frame(panel)
    status.grid(row=9, columnspan=3, sticky="ew", pady=(12, 0))
    progress = ttk.Progressbar(status, mode="indeterminate")
    progress.pack(side="left", fill="x", expand=True)
    def start_game():
        try:
            subprocess.Popen([str(game_exe)], cwd=root, creationflags=subprocess.CREATE_BREAKAWAY_FROM_JOB)
        except OSError as error:
            messagebox.showerror("Could not start the game", str(error), parent=window)

    play = ttk.Button(status, text="Play", command=start_game)
    play.pack(side="right", padx=(8, 0))

    def append(text):
        log.configure(state="normal")
        log.insert("end", text + "\n")
        log.see("end")
        log.configure(state="disabled")

    messages = Queue()
    worker = None

    def begin():
        nonlocal worker
        os.environ.pop("NOVA_SETUP_LOGS", None)
        paths = {key: Path(value.get().strip().strip('"')) if value.get().strip() else None
                 for key, value in fields.items()}
        options = Namespace(**paths)
        for control in (*controls, build, play):
            control.configure(state="disabled")
        progress.start(20)
        append("Starting setup…")

        def work():
            try:
                install(options, lambda text: messages.put(("status", text)))
            except (setup_error, OSError) as error:
                messages.put(("error", str(error)))
            except Exception:
                messages.put(("error", traceback.format_exc()))
            finally:
                messages.put(("finished", ""))

        worker = threading.Thread(target=work, daemon=True)
        worker.start()

    build = ttk.Button(status, text="Build and install", command=begin)
    build.pack(side="right", padx=(12, 0))
    if not game_exe.is_file():
        play.configure(state="disabled")
    append("Select your game package (or ZIP) and firmware, then choose Build and install.")

    def poll():
        nonlocal worker
        try:
            while True:
                kind, message = messages.get_nowait()
                if kind == "finished":
                    progress.stop()
                    for control in (*controls, build):
                        control.configure(state="normal")
                    if game_exe.is_file():
                        play.configure(state="normal")
                    worker = None
                else:
                    append(("Setup could not finish.\n" if kind == "error" else "") + message)
        except Empty:
            pass
        window.after(100, poll)

    def close():
        if worker is None or messagebox.askyesno("Stop setup?", "Completed stages are saved. Stop the current stage?", parent=window):
            window.destroy()

    window.protocol("WM_DELETE_WINDOW", close)
    window.after(100, poll)
    window.mainloop()

"""
The setup window: pick which apps Start Stream opens, where your files go, and the optional Discord and
BetterTok connections. Saves to config.json.

Run it again any time to change your choices:  py -3 setup_wizard.py
See what's set up, changing nothing:           py -3 setup_wizard.py --check

Cancel changes nothing. So does Save if you didn't change anything. Your last settings are kept as config.json.bak.
"""
import json
import os
import shutil
import subprocess
import sys
import webbrowser

HERE = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(HERE, "config.json")
# Apps people often stream with: name in the Start menu, name in Task Manager, ticked by default
KNOWN_APPS = [
    ("TikTok LIVE Studio", "TikTok LIVE Studio", True),
    ("BetterTok Desktop", "bettertok-desktop", True),
    ("TikFinity", "TikFinity", True),
    ("Spotify", "Spotify", True),
    ("OBS Studio (64bit)", "obs64", False),
    ("Streamlabs Desktop", "Streamlabs OBS", False),
    ("Discord", "Discord", False),
    ("Stream Deck", "StreamDeck", False),
    ("Elgato Wave Link", "Elgato.WaveLink", False),
    ("Elgato Camera Hub", "Camera Hub", False),
    ("Streamer.bot", "Streamer.bot", False),
]
NOT_APPS = ("uninstall", "documentation", "readme", "help", "website", " on the web")
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def is_set(value):
    return isinstance(value, str) and bool(value.strip()) and not value.strip().upper().startswith("INSERT_")


def load_config(path=CONFIG_PATH):
    """config.json as it stands. A broken one is kept as config.json.broken, not lost."""
    try:
        with open(path, encoding="utf-8-sig") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except OSError:
        return {}
    except ValueError:
        try:
            os.replace(path, path + ".broken")
        except OSError:
            pass
        return {}


def apps_from_config(config):
    """The apps in config.json, including the older layout, which named three fixed apps."""
    apps = config.get("apps")
    if isinstance(apps, list):
        return [a for a in apps if isinstance(a, dict) and is_set(a.get("path"))]
    if isinstance(apps, dict):
        old = (("bettertok", "BetterTok", "bettertok-desktop"), ("spotify", "Spotify", "Spotify"),
               ("live_studio", "TikTok LIVE Studio", "TikTok LIVE Studio"))
        return [{"name": n, "process": p, "path": apps[k]} for k, n, p in old if is_set(apps.get(k))]
    return []


def start_menu_apps():
    """[(name, how to open it)] for what's installed, from Windows' own list. Empty if that fails."""
    cmd = ["powershell", "-NoProfile", "-Command",
           "[Console]::OutputEncoding=[Text.Encoding]::UTF8; Get-StartApps | ConvertTo-Json -Compress"]
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=30, creationflags=NO_WINDOW)
        rows = json.loads(r.stdout.decode("utf-8-sig"))
    except (OSError, ValueError, subprocess.SubprocessError):
        return []
    return filter_apps(rows if isinstance(rows, list) else [rows])


def filter_apps(rows):
    found, seen = [], set()
    for row in rows:
        name, app_id = str(row.get("Name") or ""), str(row.get("AppID") or "")
        low, low_id = name.lower(), app_id.lower()
        if not name or not app_id or name in seen or any(w in low for w in NOT_APPS):
            continue
        if low_id.startswith(("http:", "https:", "mailto:")) or "._crx_" in low_id or "uninstall" in low_id:
            continue
        if app_id[1:3] == ":\\":  # a real path: only programs, not folders or documents
            if not low_id.endswith((".exe", ".lnk")):
                continue
            found.append((name, app_id))
        else:
            found.append((name, "shell:AppsFolder\\" + app_id))
        seen.add(name)
    return sorted(found, key=lambda a: a[0].lower())


def shortcut_target(path):
    """Where a .lnk points, or "" for shortcuts with no plain program behind them."""
    cmd = ["powershell", "-NoProfile", "-Command",
           "(New-Object -ComObject WScript.Shell).CreateShortcut($env:LNK_PATH).TargetPath"]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=10, creationflags=NO_WINDOW,
                           env=dict(os.environ, LNK_PATH=path))
        return r.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def guess_process(name, path, resolve=shortcut_target):
    """What it's called in Task Manager, so Start Stream can tell it's already open."""
    for known_name, process, _ in KNOWN_APPS:
        if known_name.lower() == name.lower():
            return process
    target = path
    if target.lower().endswith(".lnk"):
        target = resolve(target) or ""
    if target.lower().endswith(".exe"):
        return os.path.splitext(os.path.basename(target.replace("/", "\\").split("\\")[-1]))[0]
    return name


ACCENT = "#e5385f"  # the window's header colour
BETTERTOK_DEFAULT_GIFTS = "Heart Me, Sunglasses"
BETTERTOK_KEYS_URL = "https://bettertok.app/dashboard/creator/developer"


def random_gifts(config):
    """The gifts set to fire a random effect, as the comma-separated text the window shows."""
    gifts = config.get("bettertok_gifts")
    if not isinstance(gifts, dict):
        return BETTERTOK_DEFAULT_GIFTS
    return ", ".join(g for g, effect in gifts.items() if str(effect).strip("/").lower() == "random")


def build_config(existing, apps, chaos, boost, clips, reports, recordings, token, channel,
                 bettertok_key=None, bettertok_gifts=None, bettertok_follow=None):
    """The new config.json. Anything not on this window is kept as it was."""
    config = dict(existing)
    config["apps"] = apps
    config["start_stream"] = {"fortnite_chaos": bool(chaos), "game_boost": bool(boost)}
    config["clips_folder"] = clips.strip()
    config["reports_folder"] = reports.strip()
    config["recordings_folders"] = [r for r in recordings if r.strip()]
    config["discord_token"] = token.strip()
    config["discord_channel_id"] = channel.strip()
    if bettertok_key is not None:
        config["bettertok_api_key"] = bettertok_key.strip()
    if bettertok_gifts is not None:
        # gifts set by hand to a particular effect (not "random") are kept as they are
        old = existing.get("bettertok_gifts") if isinstance(existing.get("bettertok_gifts"), dict) else {}
        gifts = {g: e for g, e in old.items() if str(e).strip("/").lower() != "random"}
        for name in bettertok_gifts.split(","):
            if name.strip() and name.strip().lower() not in (g.lower() for g in gifts):
                gifts[name.strip()] = "random"
        config["bettertok_gifts"] = gifts
    if bettertok_follow is not None:
        config["bettertok_follow"] = "random" if bettertok_follow else ""
    return config


def save_config(config, path=CONFIG_PATH):
    """All or nothing, so a crash can't leave half a file. Your last settings are kept as config.json.bak."""
    temp = path + ".tmp"
    with open(temp, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)
    if os.path.exists(path):
        shutil.copy2(path, path + ".bak")
    os.replace(temp, path)


def saved_token_file():
    """Is there a bot token in discord_token.txt? The window never shows or changes that file."""
    try:
        with open(os.path.join(HERE, "Tiktok Jumpscare", "discord_token.txt"), encoding="utf-8") as f:
            return bool(f.read().strip())
    except OSError:
        return False


def _exists(path):
    return path.lower().startswith("shell:") or os.path.exists(path)


def check_setup(path=CONFIG_PATH):
    """(is it set up?, lines describing what's there). Only reads: it never changes or moves anything."""
    if not os.path.exists(path):
        return False, ["[ ] Settings: not set up yet"]
    try:
        with open(path, encoding="utf-8-sig") as f:
            config = json.load(f)
        if not isinstance(config, dict):
            raise ValueError
    except (OSError, ValueError):
        return False, ["[!] Settings: config.json can't be read, so it needs setting up again"]
    if not isinstance(config.get("apps"), list) or "start_stream" not in config:
        return False, ["[!] Settings: found, but from an older version, so they need one more check"]

    lines, ready = [], True
    apps = apps_from_config(config)
    if apps:
        lines.append("[OK] Start Stream apps: " + ", ".join(str(a.get("name")) for a in apps))
    else:
        lines.append("[OK] Start Stream apps: none chosen")
    for a in apps:
        if not _exists(a["path"]):
            ready = False
            lines.append(f"[!] Can't find {a.get('name')}: {a['path']}")
    tools = config["start_stream"] if isinstance(config["start_stream"], dict) else {}
    on = [label for key, label in (("fortnite_chaos", "Fortnite Chaos"), ("game_boost", "Game Boost"))
          if tools.get(key, True)]
    lines.append("[OK] Start Stream tools: " + (", ".join(on) or "none"))
    for label, key, default in (("Clips go to", "clips_folder", "Clips"), ("Reports go to", "reports_folder", "Stream Reports")):
        folder = config.get(key)
        folder = folder if is_set(folder) else os.path.join(HERE, default)
        lines.append(f"[OK] {label}: {folder}" + ("" if os.path.isdir(folder) else " (made when first used)"))
    extra = config.get("recordings_folders")
    extra = [r for r in extra if is_set(r)] if isinstance(extra, list) else []
    lines.append("[OK] Extra recording folders: " + (", ".join(extra) or "none"))
    has_token = is_set(config.get("discord_token")) or saved_token_file()
    channel = is_set(config.get("discord_channel_id"))
    lines.append("[OK] Discord jumpscare: " + ("set up" if has_token and channel else "off"))
    if is_set(config.get("bettertok_api_key")):
        gifts = random_gifts(config) or "no gifts"
        follow = "follows too" if str(config.get("bettertok_follow", "")).strip() else "not follows"
        lines.append(f"[OK] BetterTok live events: on ({gifts}; {follow})")
    else:
        lines.append("[OK] BetterTok live events: off (gifts only come in through webhooks)")
    return ready, lines


class Wizard:
    def __init__(self, tk, ttk, filedialog, messagebox, config_path=CONFIG_PATH, installed=None):
        self.tk, self.ttk, self.filedialog, self.messagebox = tk, ttk, filedialog, messagebox
        self.config_path = config_path
        self.config = load_config(config_path)
        self.installed = start_menu_apps() if installed is None else installed
        self.rows = []  # each: name, path, process, ticked
        self.saved = False
        self.changed = False

        self.root = root = tk.Tk()
        root.title("Stream Tools setup")
        root.minsize(780, 0)
        self._style()

        header = tk.Frame(root, bg=ACCENT, padx=22, pady=14)
        header.pack(fill="x")
        tk.Label(header, text="Stream Tools setup", bg=ACCENT, fg="white", font=("Segoe UI Semibold", 16)).pack(anchor="w")
        tk.Label(header, text="Choose what Start Stream opens, where your files go and what Fortnite Chaos connects to.",
                 bg=ACCENT, fg="#ffd9e2", font=("Segoe UI", 10)).pack(anchor="w")

        tabs = ttk.Notebook(root, padding=(16, 14, 16, 0))
        tabs.pack(fill="both", expand=True)
        self.tabs = tabs
        self.main = self._page("  Apps  ")
        self._apps_section()
        self._tools_section()
        self.main = self._page("  Files  ")
        self._folders_section()
        self.main = self._page("  Connections  ")
        self._bettertok_section()
        self._discord_section()

        ttk.Separator(root).pack(fill="x", pady=(14, 0))
        buttons = ttk.Frame(root, padding=(16, 10, 16, 14))
        buttons.pack(fill="x")
        ttk.Label(buttons, text="Nothing changes until you click Save. Your last settings are kept as config.json.bak.",
                  style="Hint.TLabel").pack(side="left")
        ttk.Button(buttons, text="Cancel", command=root.destroy).pack(side="right", padx=(8, 0))
        ttk.Button(buttons, text="Save", style="Accent.TButton", command=self.save).pack(side="right")
        root.bind("<Escape>", lambda e: root.destroy())

    def _style(self):
        s = self.ttk.Style(self.root)
        base = ("Segoe UI", 10)
        self.root.option_add("*Font", base)
        s.configure(".", font=base)
        s.configure("TLabelframe.Label", font=("Segoe UI Semibold", 10), foreground="#222222")
        s.configure("TLabelframe", padding=12)
        s.configure("Hint.TLabel", foreground="#6b6b6b")
        s.configure("Warn.TLabel", foreground="#9a5b00")
        s.configure("Good.TLabel", foreground="#1e7d3a", font=("Segoe UI Semibold", 10))
        s.configure("Off.TLabel", foreground="#8a8a8a", font=("Segoe UI Semibold", 10))
        s.configure("Accent.TButton", font=("Segoe UI Semibold", 10), padding=(18, 4))
        s.configure("TButton", padding=(12, 4))
        s.configure("TNotebook.Tab", padding=(14, 6), font=("Segoe UI Semibold", 10))

    def _page(self, title):
        page = self.ttk.Frame(self.tabs, padding=(4, 12, 4, 4))
        page.columnconfigure(0, weight=1)
        self.tabs.add(page, text=title)
        return page

    def _section(self, title, note=None):
        box = self.ttk.LabelFrame(self.main, text=title)
        box.grid(sticky="ew", pady=(0, 12))
        box.columnconfigure(0, weight=1)
        if note:
            self.ttk.Label(box, text=note, style="Hint.TLabel", justify="left").grid(
                sticky="w", pady=(0, 8), columnspan=3)
        return box

    # ---- apps
    def _apps_section(self):
        tk, ttk = self.tk, self.ttk
        box = self._section("Apps Start Stream opens", "Tick the ones you want. Start Stream skips any already open.")
        holder = ttk.Frame(box)
        holder.grid(sticky="ew", columnspan=3)
        holder.columnconfigure(0, weight=1)
        self.canvas = tk.Canvas(holder, height=self.root.winfo_fpixels("1i") * 1.7, highlightthickness=0)
        scroll = ttk.Scrollbar(holder, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=scroll.set)
        self.canvas.grid(row=0, column=0, sticky="ew")
        scroll.grid(row=0, column=1, sticky="ns")
        self.list_frame = ttk.Frame(self.canvas)
        self.list_frame.columnconfigure(0, weight=1)
        self.window = self.canvas.create_window((0, 0), window=self.list_frame, anchor="nw")
        self.list_frame.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfigure(self.window, width=e.width))
        self.canvas.bind("<MouseWheel>", lambda e: self.canvas.yview_scroll(-e.delta // 120, "units"))

        chosen = apps_from_config(self.config)
        have_config = "apps" in self.config
        for a in chosen:
            self._add_row(a["name"], a["path"], a.get("process") or a["name"], True)
        lookup = dict(self.installed)
        for name, process, default in KNOWN_APPS:
            if name in lookup and not self._find_row(name, process):
                self._add_row(name, lookup[name], process, default and not have_config)

        add = ttk.Frame(box)
        add.grid(sticky="ew", pady=(8, 0), columnspan=3)
        add.columnconfigure(1, weight=1)
        ttk.Label(add, text="Add another:").grid(row=0, column=0, padx=(0, 8))
        self.pick = ttk.Combobox(add, state="readonly", values=[n for n, _ in self.installed])
        self.pick.grid(row=0, column=1, sticky="ew")
        self.pick.bind("<<ComboboxSelected>>", self._add_picked)
        ttk.Button(add, text="Browse...", command=self._browse_app).grid(row=0, column=2, padx=(8, 0))

    def _find_row(self, name, process=None):
        for row in self.rows:
            if row["name"].lower() == name.lower() or (process and row["process"].lower() == process.lower()):
                return row
        return None

    def _add_row(self, name, path, process, ticked):
        existing = self._find_row(name)
        if existing:
            existing["ticked"].set(True)
            return
        var = self.tk.BooleanVar(value=ticked)
        check = self.ttk.Checkbutton(self.list_frame, text=name, variable=var)
        check.grid(row=len(self.rows), column=0, sticky="w", pady=1)
        check.bind("<MouseWheel>", lambda e: self.canvas.yview_scroll(-e.delta // 120, "units"))
        self.rows.append({"name": name, "path": path, "process": process, "ticked": var})

    def _add_picked(self, _event=None):
        name = self.pick.get()
        path = dict(self.installed).get(name)
        if path:
            self._add_row(name, path, guess_process(name, path), True)
        self.pick.set("")
        self.root.update_idletasks()
        self.canvas.yview_moveto(1)

    def _browse_app(self):
        path = self.filedialog.askopenfilename(title="Choose an app", filetypes=[
            ("Apps and shortcuts", "*.exe *.lnk"), ("All files", "*.*")])
        if path:
            path = os.path.normpath(path)
            name = os.path.splitext(os.path.basename(path))[0]
            self._add_row(name, path, guess_process(name, path), True)
            self.root.update_idletasks()
            self.canvas.yview_moveto(1)

    # ---- tools
    def _tools_section(self):
        settings = self.config.get("start_stream")
        settings = settings if isinstance(settings, dict) else {}
        box = self._section("Tools Start Stream runs")
        self.chaos = self.tk.BooleanVar(value=settings.get("fortnite_chaos", True))
        self.boost = self.tk.BooleanVar(value=settings.get("game_boost", True))
        self.ttk.Checkbutton(box, text="Fortnite Chaos", variable=self.chaos).grid(sticky="w")
        self.ttk.Checkbutton(box, text="Game Boost (asks before closing anything)", variable=self.boost).grid(sticky="w")

    # ---- folders
    def _folder_row(self, box, row, label, key, default_name):
        value = self.config.get(key)
        var = self.tk.StringVar(value=value if is_set(value) else os.path.join(HERE, default_name))
        self.ttk.Label(box, text=label).grid(row=row, column=0, sticky="w", columnspan=2, pady=(0 if row == 0 else 10, 2))
        self.ttk.Entry(box, textvariable=var).grid(row=row + 1, column=0, sticky="ew", ipady=2)
        self.ttk.Button(box, text="Browse...", command=lambda: self._browse_folder(var)).grid(
            row=row + 1, column=1, padx=(8, 0))
        return var

    def _browse_folder(self, var):
        path = self.filedialog.askdirectory(title="Choose a folder", initialdir=var.get() or HERE)
        if path:
            var.set(os.path.normpath(path))

    def _folders_section(self):
        tk, ttk = self.tk, self.ttk
        box = self._section("Where your files go")
        self.clips = self._folder_row(box, 0, "Chaos Clips saves clips to", "clips_folder", "Clips")
        self.reports = self._folder_row(box, 2, "Stream reports and logs go to", "reports_folder", "Stream Reports")
        ttk.Label(box, text="Extra folders with your stream recordings (your Videos folder is always checked)").grid(
            row=4, column=0, sticky="w", columnspan=2, pady=(10, 2))
        self.recordings = tk.Listbox(box, height=3, activestyle="none", relief="solid", borderwidth=1,
                                     highlightthickness=0)
        self.recordings.grid(row=5, column=0, sticky="ew")
        saved = self.config.get("recordings_folders")
        for folder in saved if isinstance(saved, list) else []:
            if is_set(folder):
                self.recordings.insert("end", folder)
        side = ttk.Frame(box)
        side.grid(row=5, column=1, padx=(8, 0))
        ttk.Button(side, text="Add...", command=self._add_recording).pack(fill="x")
        ttk.Button(side, text="Remove", command=self._remove_recording).pack(fill="x", pady=(4, 0))

    def _add_recording(self):
        path = self.filedialog.askdirectory(title="Folder with your recordings")
        if path and os.path.normpath(path) not in self.recordings.get(0, "end"):
            self.recordings.insert("end", os.path.normpath(path))

    def _remove_recording(self):
        for i in reversed(self.recordings.curselection()):
            self.recordings.delete(i)

    # ---- discord
    def _discord_section(self):
        token = self.config.get("discord_token")
        note = "Leave these blank if you don't use it."
        if not is_set(token) and saved_token_file():
            note = "Your token is already saved in Tiktok Jumpscare\\discord_token.txt. Leave the box blank to keep using it."
        box = self._section("Discord !jumpscare (optional)", note)
        channel = self.config.get("discord_channel_id")
        self.token = self.tk.StringVar(value=token if is_set(token) else "")
        self.channel = self.tk.StringVar(value=channel if is_set(channel) else "")
        self.ttk.Label(box, text="Bot token").grid(sticky="w")
        self.ttk.Entry(box, textvariable=self.token, show="•").grid(sticky="ew", ipady=2)
        self.ttk.Label(box, text="Channel ID").grid(sticky="w", pady=(8, 0))
        self.ttk.Entry(box, textvariable=self.channel).grid(sticky="ew", ipady=2)

    # ---- bettertok
    def _bettertok_section(self):
        tk, ttk = self.tk, self.ttk
        box = self._section(
            "BetterTok live events  (optional, BetterTok Creator plan)",
            "Fortnite Chaos gets your gifts, follows and chat straight from BetterTok, with no webhook actions.\n"
            "1.  Click Get a key, then Create a key, and copy it. BetterTok only shows it once.\n"
            "2.  Paste it below, pick your gifts and click Save. Leave it blank to keep using webhooks.")
        key = self.config.get("bettertok_api_key")
        self.bt_key = tk.StringVar(value=key if is_set(key) else "")
        self.bt_gifts = tk.StringVar(value=random_gifts(self.config))
        self.bt_follow = tk.BooleanVar(value=str(self.config.get("bettertok_follow", "random")).strip() != "")

        row = ttk.Frame(box)
        row.grid(sticky="ew", columnspan=3)
        row.columnconfigure(1, weight=1)
        ttk.Label(row, text="API key").grid(row=0, column=0, padx=(0, 10))
        entry = ttk.Entry(row, textvariable=self.bt_key, show="•")
        entry.grid(row=0, column=1, sticky="ew", ipady=2)
        shown = tk.BooleanVar(value=False)
        ttk.Checkbutton(row, text="Show", variable=shown,
                        command=lambda: entry.configure(show="" if shown.get() else "•")).grid(row=0, column=2, padx=(8, 0))
        ttk.Button(row, text="Get a key", command=lambda: webbrowser.open(BETTERTOK_KEYS_URL)).grid(
            row=0, column=3, padx=(8, 0))
        status = ttk.Label(row)
        status.grid(row=1, column=1, sticky="w", pady=(4, 0))

        def update_status(*_):
            k = self.bt_key.get().strip()
            if not k:
                status.configure(text="○  Off: gifts come in through webhooks", style="Off.TLabel")
            elif k.startswith("btk_"):
                status.configure(text="●  Key added: restart Fortnite Chaos after saving", style="Good.TLabel")
            else:
                status.configure(text="!  BetterTok keys start with btk_live_ — check you copied all of it",
                                 style="Warn.TLabel")
        self.bt_key.trace_add("write", update_status)
        update_status()

        ttk.Label(box, text="Gifts that fire a random effect").grid(sticky="w", pady=(12, 2))
        ttk.Entry(box, textvariable=self.bt_gifts).grid(sticky="ew", ipady=2)
        ttk.Label(box, text="Names exactly as BetterTok shows them, with a comma between, like Heart Me, Sunglasses",
                  style="Hint.TLabel").grid(sticky="w", pady=(2, 0))
        ttk.Checkbutton(box, text="A follow fires a random effect too", variable=self.bt_follow).grid(
            sticky="w", pady=(10, 0))
        ttk.Label(box, style="Warn.TLabel", justify="left", text=(
            "With a key saved, turn off any BetterTok action that sends these gifts or follows to Fortnite Chaos\n"
            "as a webhook (Actions & Events), or each one fires twice.")).grid(sticky="w", pady=(10, 0))

    # ---- save
    def save(self):
        clips, reports = self.clips.get().strip(), self.reports.get().strip()
        for label, folder in (("clips", clips), ("reports", reports)):
            if not folder or not os.path.isabs(folder):
                self.messagebox.showerror("Stream Tools setup", f"Choose a full folder path for {label}.")
                return
        try:
            os.makedirs(clips, exist_ok=True)
            os.makedirs(reports, exist_ok=True)
            apps = [{"name": r["name"], "process": r["process"], "path": r["path"]}
                    for r in self.rows if r["ticked"].get()]
            new = build_config(self.config, apps, self.chaos.get(), self.boost.get(), clips, reports,
                               list(self.recordings.get(0, "end")), self.token.get(), self.channel.get(),
                               self.bt_key.get(), self.bt_gifts.get(), self.bt_follow.get())
            self.changed = new != self.config
            if self.changed:
                save_config(new, self.config_path)
        except OSError as e:
            self.messagebox.showerror("Stream Tools setup", f"Couldn't save your settings:\n{e}")
            return
        self.saved = True
        self.root.destroy()


def main():
    if "--check" in sys.argv:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(errors="replace")
        ready, lines = check_setup()
        for line in lines:
            print("  " + line)
        return 0 if ready else 1
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass
    wizard = Wizard(tk, ttk, filedialog, messagebox)
    wizard.root.mainloop()
    print("  Saved your changes. Your last settings are in config.json.bak." if wizard.changed
          else "  Nothing changed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

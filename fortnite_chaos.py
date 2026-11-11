"""
Fortnite Chaos (Windows, keyboard + mouse, no extra installs)

TikFinity gift -> "Trigger Webhook" -> one of the URLs below -> chaos for a while.
Every URL is http://127.0.0.1:8766/<name>

Control and aim effects last a random 20-30s each time, /spin 20s, /blind and /fog 10-15s (see SECONDS below).

CONTROLS (these stack: a new one adds to whatever is already running, e.g. /invert + /rotate combine)
  /invert         W<->S and A<->D swapped
  /rotate         W->A, A->S, S->D, D->W
  /jumpswap       Space<->Ctrl (jump <-> crouch)
  /noscope        right-click blocked (can't aim)
  /invertmouse    mouse up is down
  /sensitivity    mouse 3x faster or 3x slower (random)

AIM + MAP (stack with the controls above; /lookdown and /lookup replace each other)
  /lookdown       aim pinned to the floor - you can't look up
  /lookup         aim pinned to the sky - you can't look down
  /spin           nonstop 360s                               (20s)
  /mapspam        keeps opening and closing the map

ONE-OFFS
  /emote          forces a random emote, movement frozen for 3s

SCREEN EFFECTS (on your screen AND on stream - stack with the controls above)
  /blind          black screen except a small circle
  /fog            white haze that fades out
  /jumpscare      full-screen picture + sound                (1.5s)
  /fakeban        fake "account banned" screen               (6s)
  /bsod           fake Windows blue screen                   (6s)
  /blink          your eyelids keep closing                  (20s)
  /lowhp          pulsing red screen edges + heartbeat       (20s)
  /creeper        creeper hisses, explodes, leaves a hole in your screen   (10s hole)
  /flashbang      white flash, no sound                      (5s)
                  Works like the BetterTok flashbang.py, built in: every gift restarts the flash,
                  it covers your main monitor only, http://127.0.0.1:8765/trigger and Ctrl+Alt+F trigger it,
                  and its own browser source http://localhost:8765/ still flashes + rings for viewers.
                  (don't run flashbang.py at the same time)
  Viewers see them through a Link source in LIVE Studio: http://127.0.0.1:8766/overlay.html
  Put jumpscare.png (and jumpscare.wav) next to this script, in "assets" or in "Tiktok Jumpscare" - the Discord
  jumpscare bot's jumpscare.wav in there is used automatically.

SPECIALS
  /random         RANDOM CHAOS: picks any effect above, /chaos or /wheel
  /wheel          spins a wheel on the overlay (3s), then fires what it lands on
  /chaos          CHAOS MODE: two control effects at once
  /off            turns everything off
  /status         what's running
  /menu           shows or hides the gift menu on the overlay (also ?show=1 or ?show=0)
  /topsender      shows the top senders on the overlay right now

  add ?seconds=30 to any URL to set the length, e.g. /invert?seconds=30
  add ?user=NAME&gift=GIFT to show who sent it in the on-screen popup, e.g.
      /invert?user=%nickname%&gift=%giftName%   (see TikFinity placeholder notes)

KEYBOARD TRIGGERS (for tools that press keys, like BetterTok's "Simulate Keystrokes"):
  F5 invert | F6 rotate | F7 jumpswap | F9 emote | F10 random
  F11 noscope
  (these keys are swallowed while the script runs so they don't reach Fortnite)

TEST PANEL: open http://127.0.0.1:8766/panel.html in a browser for a button per effect.
ON-STREAM TIMER: the overlay shows which effect is running and how long is left.
  Add ?timer=bottom to the overlay link to put it at the bottom, or ?timer=off to hide it.
ON-STREAM BANNER: the overlay also shows the "who sent what" banner (moves to the top with ?timer=bottom).
COMBO METER: every gift fills the overlay's bar. COMBO_GOAL gifts inside COMBO_WINDOW seconds fires /chaos.
CHAT VOTES: send chat messages to /chat (?user=NAME&text=MESSAGE, or a JSON body with the comment). Every
  vote_every_minutes (config.json, default 5) chat gets 30s to type 1-4 and the winner fires. Votes only start once
  chat messages are arriving. /vote starts one now.
GIFT STRENGTH: config.json "gift_power": {"Rose": 1, "Galaxy": 3} makes a gift's effects last that many times longer.
GIFT MENU: shows itself on the overlay for 12s every menu_every_minutes (config.json, default 5; 0 turns it off).
CRASHES: if Fortnite Chaos crashes it restarts itself in the same window (it gives up after 5 crashes in 2 minutes).
TOP SENDERS: every 5-10 minutes the overlay shows who sent the most effects this stream.
The wheel, combo meter, top senders and gift menu are on the overlay only, so they don't cover your own screen.

PANIC KEY: F8 instantly restores your normal keys and mouse, and clears screen effects.

TABBED OUT: keys and mouse only get messed with while Fortnite is the window in front. Alt-tab away and they
  work normally, so you can type and use the desktop (effect timers keep counting, screen effects still show).

GIFT LOG: every gift and effect is saved to Stream Reports\\events-<date>.csv for Stream Report and Chaos Clips.

DISCORD JUMPSCARE (replaces the old Node.js bot.js - no Node needed any more):
  "!jumpscare" in your Discord channel fires /jumpscare, max 3 per person per day.
  The bot token and channel are read from config.json (or "Tiktok Jumpscare\\discord_token.txt", or the old bot.js).
  Uses (and keeps) the same jumpscare-state.json, so reset-jumpscare.bat still resets everyone's limit.

Run:  py -3 fortnite_chaos.py     (leave the window open while streaming)
"""
import base64
import csv
import ctypes
import ctypes.wintypes as wt
import hashlib
import json
import math
import os
import queue
import random
import re
import socket
import ssl
import struct
import subprocess
import sys
import threading
import time
import traceback
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, quote, urlparse

import stream_config

# ---------------- settings ----------------
PORT = 8766
# How long effects last, in seconds. (low, high) picks a random whole number of seconds in that range
# each time; a single number is a fixed length. Anything not listed uses DEFAULT_SECONDS.
DEFAULT_SECONDS = (20, 30)
SECONDS = {"jumpscare": 1.5, "flashbang": 5.2,  # short on purpose
           "blind": (10, 15), "fog": (10, 15), "spin": 20,
           "fakeban": 6, "bsod": 6, "blink": 20, "lowhp": 20, "creeper": 11.5}  # creeper = fuse + hole
MAX_STACK_SECONDS = 90  # repeat gifts add time, but an effect never stacks past this much time left
PANIC_SCAN = 0x42  # F8
# Key triggers (scan codes): F5, F6, F7, F9, F10, F11.
# Change these if Fortnite or another app uses them.
HOTKEYS = {0x3F: "invert", 0x40: "rotate", 0x41: "jumpswap", 0x43: "emote", 0x44: "random",
           0x57: "noscope"}
POPUP_SECONDS = 5  # how long the "who triggered what" banner stays on screen
EFFECT_NAMES = {
    "invert": "Inverted movement",
    "rotate": "Rotated movement",
    "jumpswap": "Jump / crouch swapped",
    "noscope": "No-scope mode (can't aim)",
    "invertmouse": "Inverted mouse",
    "sensitivity": "Sensitivity roulette",
    "emote": "Forced emote",
    "lookdown": "Look at the floor",
    "lookup": "Look at the sky",
    "spin": "360 spin",
    "mapspam": "Map spam",
    "blind": "Blinded",
    "fog": "Fog",
    "jumpscare": "JUMPSCARE",
    "flashbang": "Flashbang",
    "fakeban": "Fake ban",
    "bsod": "Fake blue screen",
    "blink": "Blinking eyes",
    "lowhp": "Low HP",
    "creeper": "Creeper hole",
}
# Short names for the mystery wheel and the gift menu
SHORT_NAMES = {
    "invert": "Inverted", "rotate": "Rotated", "jumpswap": "Jump swap", "noscope": "No-scope",
    "invertmouse": "Invert mouse", "sensitivity": "Sensitivity", "emote": "Emote", "lookdown": "Look down",
    "lookup": "Look up", "spin": "360 spin", "mapspam": "Map spam", "blind": "Blind", "fog": "Fog",
    "jumpscare": "Jumpscare", "flashbang": "Flashbang", "fakeban": "Fake ban", "bsod": "Blue screen",
    "blink": "Blink", "lowhp": "Low HP", "creeper": "Creeper",
}
# Your Fortnite binds, as scan codes (layout independent)
W, A, S, D = 0x11, 0x1E, 0x1F, 0x20
SPACE, LCTRL = 0x39, 0x1D
EMOTE, MAP = 0x30, 0x32  # B, M

# Forced emote: taps B to open the emote wheel, flicks the mouse towards a random slot
# and clicks it. Every key and mouse button is frozen for EMOTE_LOCK_SECONDS so you can't cancel it -
# you can only look around.
EMOTE_WHEEL_SLOTS = 6     # slots on the wheel (first one straight up, going clockwise)
EMOTE_FLICK = 300         # how far to flick the mouse; raise it if it doesn't pick a slot
EMOTE_WHEEL_DELAY = 0.25  # wait for the wheel to open before flicking
EMOTE_LOCK_SECONDS = 3

# Mouse amounts depend on your in-game sensitivity - tune these after a test.
SPIN_COUNTS = 3000        # mouse movement for one full 360; raise it if the spin falls short
SPIN_TURN_SECONDS = 1.0   # how long each 360 of /spin takes
LOOK_PUSH = 40            # mouse movement every 10ms pinning your aim down/up; raise it if you can still look away
SENSITIVITY_CHOICES = (3.0, 1 / 3)
MAPSPAM_GAP = 0.6

BLIND_HOLE = 0.18         # size of the hole in /blind, as a fraction of the screen height

FLASHBANG_PORT = 8765     # the old flashbang.py's port, so existing TikFinity links keep working
FLASH_HOLD = 1.2          # seconds of full white
FLASH_FADE = 4.0          # fade out time
FLASH_VOLUME = 0.5        # 0.0 - 1.0 (it's loud, start low!)
FLASH_HOTKEY_SCAN = 0x21  # F, pressed together with Ctrl+Alt

WHEEL_SPIN = 2.2          # mystery wheel: seconds spinning (the effect fires when it stops)
WHEEL_HOLD = 0.8          # seconds it stays up showing the result
COMBO_GOAL = 10           # gifts needed to fire /chaos
COMBO_WINDOW = 60         # ...within this many seconds
TOP_SENDER_EVERY = (300, 600)  # show the top senders every 5-10 minutes
TOP_SENDER_SECONDS = 8    # for this long
MENU_SHOW_SECONDS = 12    # the gift menu shows itself for this long, every menu_every_minutes (config.json)
VOTE_SECONDS = 30         # how long chat gets to vote
VOTE_OPTIONS = 4
VOTE_RESULT_SECONDS = 4   # the winner stays up this long
CHAT_ALIVE_SECONDS = 300  # votes only start if a chat message arrived within this long
NAMED_EFFECTS = {"fakeban", "bsod", "creeper"}  # these show the gifter's name inside the effect
RESTART_CODE, ALREADY_RUNNING = 3, 2  # exit codes the crash restarter understands
TOP_SENDER_COUNT = 3      # how many names
NOT_A_GIFT = {"", "test panel"}  # never listed as a top sender (lower case)
FAKE_BAN_TITLE = "YOU HAVE BEEN BANNED"
FAKE_BAN_TEXT = ("Your account has been permanently banned for cheating,\n"
                 "exploits, or receiving too many gifts from viewers.\n"
                 "We recommend not streaming Fortnite ever again.")
OVERLAY_PUSH_GAP = 0.05    # seconds between overlay updates while something is changing
CREEPER_FUSE = 1.5        # seconds of hissing face before the explosion
CREEPER_BLAST = 0.15      # seconds of white when it blows
CREEPER_HOLE = 0.36       # hole size, as a fraction of the screen height
BLINK_CYCLE = 3.5         # one blink every this many seconds
LOWHP_BEAT = 0.9          # seconds per heartbeat; matches heartbeat.mp3
LOWHP_SOUND_LENGTH = 8.6  # heartbeat.mp3 restarts after this long
# Which gift picture (assets\\gifts) shows next to which effect in the gift menu. Set in config.json,
# e.g. "gift_icons": {"random": "003_Heart_Me.png"}
GIFT_ICONS = stream_config.get("gift_icons", {})
# ------------------------------------------

CONTROL = {"invert", "rotate", "jumpswap", "noscope", "invertmouse", "sensitivity"}
SCREEN = {"blind", "fog", "jumpscare", "flashbang", "fakeban", "bsod", "blink", "lowhp", "creeper"}
SILENT = {"jumpscare", "flashbang", "fakeban", "bsod"}  # no banner while they run (it would spoil them)
CREDIT_AFTER = {"fakeban", "bsod"}  # the banner naming the sender comes when these end
TIMED_SCREEN = {"blink", "lowhp", "creeper"}  # screen effects that show a timer on the overlay
MOVES = {"lookdown", "lookup", "spin", "mapspam"}  # timed, but stack with controls instead of replacing them
INSTANT = {"emote"}  # one-offs that don't replace anything
RANDOM_POOL = CONTROL | SCREEN | MOVES | INSTANT
# Chaos Mode only combines effects from different groups, so they never fight over the same keys
GROUPS = [{"invert", "rotate"}, {"jumpswap"}, {"noscope"}, {"invertmouse", "sensitivity"}]
MOVE_KEYS = (W, A, S, D, SPACE)
MOUSE_HOOK_EFFECTS = {"noscope"}  # need the low-level mouse hook
RAW_MOUSE_EFFECTS = {"invertmouse", "sensitivity"}         # need to read raw mouse movement

MAGIC = 0x46434B59  # marks input we inject ourselves so we never remap it
LLKHF_EXTENDED = 0x01
LLKHF_INJECTED = 0x10
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_SCANCODE = 0x0008
MOUSEEVENTF_MOVE, MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP = 0x0001, 0x0002, 0x0004
WM_LBUTTONDOWN, WM_LBUTTONUP, WM_RBUTTONDOWN, WM_RBUTTONUP = 0x0201, 0x0202, 0x0204, 0x0205
WM_MOUSEWHEEL, WM_INPUT = 0x020A, 0x00FF
WM_APP_MOUSEHOOK = 0x8001  # tells the hook thread which mouse hooks to have on

ULONG_PTR = ctypes.c_size_t


class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [("vkCode", wt.DWORD), ("scanCode", wt.DWORD), ("flags", wt.DWORD),
                ("time", wt.DWORD), ("dwExtraInfo", ULONG_PTR)]


class MSLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [("pt", wt.POINT), ("mouseData", wt.DWORD), ("flags", wt.DWORD),
                ("time", wt.DWORD), ("dwExtraInfo", ULONG_PTR)]


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", wt.WORD), ("wScan", wt.WORD), ("dwFlags", wt.DWORD),
                ("time", wt.DWORD), ("dwExtraInfo", ULONG_PTR)]


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", wt.LONG), ("dy", wt.LONG), ("mouseData", wt.DWORD),
                ("dwFlags", wt.DWORD), ("time", wt.DWORD), ("dwExtraInfo", ULONG_PTR)]


class _INPUTUNION(ctypes.Union):
    _fields_ = [("ki", KEYBDINPUT), ("mi", MOUSEINPUT)]


class INPUT(ctypes.Structure):
    _fields_ = [("type", wt.DWORD), ("u", _INPUTUNION)]


class RAWINPUTDEVICE(ctypes.Structure):
    _fields_ = [("usUsagePage", wt.USHORT), ("usUsage", wt.USHORT), ("dwFlags", wt.DWORD), ("hwndTarget", wt.HWND)]


class RAWINPUTHEADER(ctypes.Structure):
    _fields_ = [("dwType", wt.DWORD), ("dwSize", wt.DWORD), ("hDevice", wt.HANDLE), ("wParam", wt.WPARAM)]


class RAWMOUSE(ctypes.Structure):
    _fields_ = [("usFlags", wt.USHORT), ("ulButtons", wt.ULONG), ("ulRawButtons", wt.ULONG),
                ("lLastX", wt.LONG), ("lLastY", wt.LONG), ("ulExtraInformation", wt.ULONG)]


class RAWINPUT(ctypes.Structure):
    _fields_ = [("header", RAWINPUTHEADER), ("mouse", RAWMOUSE)]


user32 = ctypes.windll.user32 if os.name == "nt" else None


def send_key(scan, up):
    flags = KEYEVENTF_SCANCODE | (KEYEVENTF_KEYUP if up else 0)
    inp = INPUT(type=1, u=_INPUTUNION(ki=KEYBDINPUT(0, scan, flags, 0, MAGIC)))
    user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))


def send_mouse(flags, dx=0, dy=0):
    inp = INPUT(type=0, u=_INPUTUNION(mi=MOUSEINPUT(dx, dy, 0, flags, 0, MAGIC)))
    user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))


def mask_alt():
    """Taps an unused key. When we swallow the F of Ctrl+Alt+F, the game would otherwise see Alt
    pressed and released on its own, which opens the window menu and freezes your movement."""
    for flags in (0, KEYEVENTF_KEYUP):
        inp = INPUT(type=1, u=_INPUTUNION(ki=KEYBDINPUT(0xE8, 0, flags, 0, MAGIC)))
        user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))


def tap_key(scan, hold=0.05):
    send_key(scan, False)
    time.sleep(hold)
    send_key(scan, True)


def glide_mouse(dx, dy, seconds, steps=20):
    """Moves the mouse by (dx, dy) spread over a short time, so the game sees a smooth turn."""
    done_x = done_y = 0
    for i in range(1, steps + 1):
        x, y = round(dx * i / steps), round(dy * i / steps)
        send_mouse(MOUSEEVENTF_MOVE, x - done_x, y - done_y)
        done_x, done_y = x, y
        time.sleep(seconds / steps)


# ---------------- is Fortnite the window in front? ----------------
GAME_PROCESS = "fortniteclient-win64-shipping"  # lower case, start of the .exe name
focus = {"game": False}


def _foreground_is_game(hwnd):
    """True/False for that window, or None if it's one of ours (our banners must never count as tabbing out)."""
    pid = wt.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    if pid.value == os.getpid():
        return None
    k32 = ctypes.windll.kernel32
    k32.OpenProcess.restype = wt.HANDLE
    h = k32.OpenProcess(0x1000, False, pid.value)  # PROCESS_QUERY_LIMITED_INFORMATION
    if not h:
        return False
    try:
        buf, size = ctypes.create_unicode_buffer(520), wt.DWORD(520)
        if not k32.QueryFullProcessImageNameW(wt.HANDLE(h), 0, buf, ctypes.byref(size)):
            return False
        return os.path.basename(buf.value).lower().startswith(GAME_PROCESS)
    finally:
        k32.CloseHandle(wt.HANDLE(h))


def focus_watcher():
    """Only looks the window up when the front window changes, so this costs next to nothing."""
    user32.GetForegroundWindow.restype = wt.HWND
    user32.GetWindowThreadProcessId.argtypes = [wt.HWND, ctypes.POINTER(wt.DWORD)]
    last = None
    while True:
        time.sleep(0.1)
        try:
            hwnd = user32.GetForegroundWindow()
            if not hwnd or hwnd == last:  # no window in front happens for a moment during alt-tab
                continue
            last = hwnd
            is_game = _foreground_is_game(hwnd)
            if is_game is None or is_game == focus["game"]:
                continue
            focus["game"] = is_game
            with lock:
                running = bool(active)
            if running:
                log(f"{time.strftime('%H:%M:%S')} - " + ("back in Fortnite, effects on" if is_game
                                                         else "tabbed out, keys and mouse back to normal"))
        except Exception:
            traceback.print_exc()


# ---------------- gift log ----------------
_event_lock = threading.Lock()


def log_event(who, gift, effect, seconds, mystery):
    """One line per gift/effect in Stream Reports\\events-<date>.csv. Never gets in the way of the effect."""
    now = time.time()
    path = os.path.join(APP_LOG_DIR, time.strftime("events-%Y-%m-%d.csv", time.localtime(now)))
    try:
        with _event_lock:
            os.makedirs(APP_LOG_DIR, exist_ok=True)
            new = not os.path.exists(path)
            with open(path, "a", encoding="utf-8", newline="") as f:
                w = csv.writer(f)
                if new:
                    w.writerow(["time", "who", "gift", "effect", "seconds", "mystery"])
                w.writerow([time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(now)), who, gift, effect,
                            f"{seconds:.1f}", int(mystery)])
    except OSError:
        pass  # e.g. the file is open in Excel - skip this one


# ---------------- effects ----------------
def _pairs(*p):
    m = {}
    for a, b in p:
        m[a] = b
        m[b] = a
    return m


def _length(name):
    """How many seconds this effect should run for this time."""
    s = SECONDS.get(name, DEFAULT_SECONDS)
    return random.randint(*s) if isinstance(s, tuple) else s


# What each effect does while it runs. Effects that act elsewhere (mouse hook, raw mouse,
# their own thread or the screen) just return an empty dict.
EFFECTS = {
    "invert": lambda: {"map": _pairs((W, S), (A, D))},
    "rotate": lambda: {"map": {W: A, A: S, S: D, D: W}},
    "jumpswap": lambda: {"map": _pairs((SPACE, LCTRL))},
    "noscope": dict,
    "invertmouse": dict,
    "sensitivity": lambda: {"factor": random.choice(SENSITIVITY_CHOICES)},
    "lookdown": dict,
    "lookup": dict,
    "spin": lambda: {"dir": random.choice((-1, 1))},
    "mapspam": dict,
    "blind": dict,
    "fog": dict,
    "jumpscare": dict,
    "flashbang": dict,
    "fakeban": dict,
    "bsod": dict,
    "blink": dict,
    "lowhp": dict,
    "creeper": dict,
}

# ---------------- state ----------------
lock = threading.RLock()
active = {}   # effect name -> end time
data = {}     # effect name -> what EFFECTS[name]() returned
totals = {}   # effect name -> its full length in seconds (for the on-stream timer)
keymap = {}   # merged key remaps of the running effects
blocked = set()  # keys whose presses are ignored right now
hotkeys_down = set()  # trigger keys currently held (so key-repeat doesn't re-trigger)
held = {}       # physical key -> key we are sending in its place, while it is held down
passthru = set()  # keys that must behave normally until physically released
move_lock = {"until": 0.0}  # keys and mouse buttons frozen until this time (forced emote)
flash = {"count": 0, "ring": None}  # flashbangs so far (the 8765 browser source watches it) + ring .wav path
rbutton = {"blocked": False}  # right-click down was swallowed, so swallow its release too
hook_thread_id = {"id": 0}
emote_busy = threading.Lock()
popups = queue.Queue()  # (headline, detail) messages for the on-screen banner
stream_banner = {"id": 0, "head": "", "detail": "", "icon": None, "until": 0.0}  # same banner, for viewers (overlay.html)
late_credit = {}  # effect -> (headline, detail, icon) to announce when it ends
wheel = {"id": 0, "names": [], "pick": 0, "until": 0.0}  # the mystery wheel on the overlay
combo = {"times": []}  # when the recent gifts came in
senders = {}  # sender name -> effects sent this stream
top_show = {"next": time.time() + random.uniform(*TOP_SENDER_EVERY), "until": 0.0}
menu = {"on": False}  # gift menu on the overlay
menu_show = {"next": 0.0, "until": 0.0}  # when the gift menu next shows itself
chat = {"last": 0.0}  # when the last chat message arrived
vote = {"id": 0, "options": [], "votes": {}, "until": 0.0, "winner": None, "show_until": 0.0, "next": 0.0}
_logq = queue.Queue()


def log(msg):
    """Never blocks or crashes the caller, even if the console window is paused or closed."""
    _logq.put(msg)


def _log_writer():
    while True:
        msg = _logq.get()
        try:
            print(msg, flush=True)
        except Exception:
            pass


def announce(headline, detail, icon=None):
    """Shows the banner on your screen AND on stream. (PC warnings use popups.put, so viewers don't see them.)"""
    popups.put((headline, detail))
    with lock:
        stream_banner.update(id=stream_banner["id"] + 1, head=headline, detail=detail, icon=icon,
                             until=time.time() + POPUP_SECONDS)


def _clean(text, limit=32):
    text = "".join(ch for ch in (text or "") if ch.isprintable()).strip()
    return text[:limit]


def _rebuild():
    """Recalculate the merged key remaps and blocked keys. Call with the lock held."""
    keymap.clear()
    blocked.clear()
    for name in active:  # oldest first: each new remap applies on top of the ones already running
        m = data[name].get("map", {})
        for k in set(keymap) | set(m):
            now_goes_to = keymap.get(k, k)
            keymap[k] = m.get(now_goes_to, now_goes_to)
        blocked.update(data[name].get("block", ()))
    for k in [k for k, v in keymap.items() if k == v]:  # two swaps can cancel out
        del keymap[k]
    _resync_held()


def _resync_held():
    """A key you're holding follows the new remaps straight away, so nothing sticks. Call with the lock held."""
    for sc, dst in list(held.items()):
        new = keymap.get(sc)
        if new == dst:
            continue
        send_key(dst, True)
        if new:
            send_key(new, False)
            held[sc] = new
        else:
            send_key(sc, False)
            passthru.add(sc)
            del held[sc]


def _sync_mouse_hook():
    """Mouse hooks are only on while an effect needs them, so they can't add mouse lag otherwise."""
    with lock:
        buttons = MOUSE_HOOK_EFFECTS & set(active) or time.time() < move_lock["until"]
        want = (1 if buttons else 0) | (2 if RAW_MOUSE_EFFECTS & set(active) else 0)
    if hook_thread_id["id"]:
        user32.PostThreadMessageW(hook_thread_id["id"], WM_APP_MOUSEHOOK, want, 0)


def _start(name, end):
    """Turn an effect on. Call with the lock held."""
    data[name] = EFFECTS[name]()
    active[name] = end
    totals[name] = end - time.time()
    if name == "flashbang":
        flash["count"] += 1
    if name in EFFECT_THREADS:
        threading.Thread(target=EFFECT_THREADS[name], daemon=True).start()


def _stop(name):
    """Turn an effect off and undo anything it is holding. Call with the lock held."""
    active.pop(name, None)
    data.pop(name, None)
    totals.pop(name, None)


def _stack(name, secs, now):
    """Add an effect on top of what's running. Call with the lock held, then _rebuild()."""
    if name in active and active[name] > now and name != "flashbang":  # a new flashbang restarts it
        # same effect again: add time, up to the cap (a longer ?seconds= is never cut short)
        end = max(active[name], min(active[name] + secs, now + MAX_STACK_SECONDS))
        totals[name] += end - active[name]
        active[name] = end
    else:
        if name in ("lookdown", "lookup"):
            _stop("lookup" if name == "lookdown" else "lookdown")  # they'd just fight
        _start(name, now + secs)


_bags = {}  # shuffled draws for random chaos and the wheel, so nothing repeats until everything has had a turn


def _draw(key, pool):
    """Next pick from a shuffled bag. A new bag never starts with the effect that just ended the last one."""
    bag = _bags.setdefault(key, {"left": [], "last": None})
    bag["left"] = [x for x in bag["left"] if x in pool]  # effects switched off since stay out
    if not bag["left"]:
        bag["left"] = random.sample(sorted(pool), len(pool))
        if len(bag["left"]) > 1 and bag["left"][-1] == bag["last"]:
            bag["left"][0], bag["left"][-1] = bag["left"][-1], bag["left"][0]
    bag["last"] = bag["left"].pop()
    return bag["last"]


def _spin_wheel(pick):
    """Start the overlay's wheel, landing on `pick`. False if it's already spinning for another gift."""
    with lock:
        now = time.time()
        if now < wheel["until"]:
            return False
        others = random.sample(sorted(RANDOM_POOL - {pick}), 7)
        at = random.randrange(8)
        others.insert(at, pick)
        wheel.update(id=wheel["id"] + 1, names=[SHORT_NAMES[n] for n in others], pick=at,
                     until=now + WHEEL_SPIN + WHEEL_HOLD)
    return True


def start_vote():
    """Chat gets VOTE_SECONDS to type 1-4. Returns the options."""
    with lock:
        now = time.time()
        vote.update(id=vote["id"] + 1, options=random.sample(sorted(RANDOM_POOL), VOTE_OPTIONS), votes={},
                    until=now + VOTE_SECONDS, winner=None, show_until=0.0,
                    next=now + max(1.0, _minutes("vote_every_minutes", 5)) * 60)
        return list(vote["options"])


def add_chat(user, text):
    """A chat message. Returns the option it voted for (1-4), or None."""
    with lock:
        chat["last"] = time.time()
        m = re.fullmatch(r"\s*#?\s*([1-9])\s*", text or "")
        if not m or time.time() >= vote["until"] or not (1 <= int(m.group(1)) <= len(vote["options"])):
            return None
        key = user or f"anon{len(vote['votes'])}"  # nameless messages each count once
        vote["votes"][key] = int(m.group(1))  # changing your mind replaces your vote
        return int(m.group(1))


def finish_vote():
    """Counts the votes and fires the winner. Returns the winning effect, or None if nobody voted."""
    with lock:
        counts = [0] * len(vote["options"])
        for choice in vote["votes"].values():
            counts[choice - 1] += 1
        vote["until"] = 0.0
        if not any(counts):
            vote["show_until"] = 0.0
            return None
        best = max(counts)
        vote["winner"] = random.choice([i for i, c in enumerate(counts) if c == best])
        vote["show_until"] = time.time() + VOTE_RESULT_SECONDS
        effect = vote["options"][vote["winner"]]
    activate(effect, None, "Chat vote", None, counted=False)
    return effect


def vote_loop():
    """Ends votes when time's up, and starts the next one if chat is talking."""
    # the first vote waits a full interval, instead of starting on the stream's first chat message
    vote["next"] = max(vote["next"], time.time() + _minutes("vote_every_minutes", 5) * 60)
    while True:
        time.sleep(0.5)
        try:
            now = time.time()
            if vote["until"] and now >= vote["until"]:
                finish_vote()
            every = _minutes("vote_every_minutes", 5)
            if (every and not vote["until"] and now >= vote["next"] and now - chat["last"] < CHAT_ALIVE_SECONDS):
                start_vote()
        except Exception:
            traceback.print_exc()


def _minutes(key, default):
    try:
        return max(0.0, float(stream_config.get(key, default)))
    except (TypeError, ValueError):
        return float(default)


def _gift_power(gift):
    """How many times longer this gift's effects last (config.json "gift_power"). 1 if it isn't listed."""
    powers = stream_config.get("gift_power", {})
    if not gift or not isinstance(powers, dict):
        return 1.0
    for name, power in powers.items():
        if _gift_key(str(name)) == _gift_key(gift):
            try:
                return min(10.0, max(0.1, float(power)))
            except (TypeError, ValueError):
                return 1.0
    return 1.0


def _powered(secs, power):
    """Gift strength makes an effect longer, but never past MAX_STACK_SECONDS (a longer ?seconds= is kept)."""
    return secs if power == 1 else min(secs * power, max(secs, MAX_STACK_SECONDS))


def _stop_code(who):
    code = re.sub(r"[^A-Z0-9]+", "_", (who or "").upper()).strip("_")[:20]
    return f"{code}_DID_THIS" if code else "TOO_MANY_GIFTS"


def _count_gift(who):
    """Feeds the combo meter and the top senders. True when this gift completes the combo."""
    with lock:
        now = time.time()
        if who and who.lower() not in NOT_A_GIFT:
            senders[who] = senders.get(who, 0) + 1
        combo["times"] = [t for t in combo["times"] if now - t < COMBO_WINDOW] + [now]
        if len(combo["times"]) < COMBO_GOAL:
            return False
        combo["times"] = []
    return True


def activate(name, secs=None, who=None, gift=None, mystery=False, counted=True):
    """Fire an effect. mystery: it came from the wheel. counted: False if this isn't a viewer's gift."""
    if counted and _count_gift(_clean(who)):
        threading.Timer(0.3, activate, ("chaos",), {"who": "GIFT COMBO", "counted": False}).start()
    if name == "random":  # any effect, Chaos Mode, or the wheel
        name, mystery = _draw("random", RANDOM_POOL | {"chaos", "wheel"}), True
    if name == "wheel":
        name, mystery = _draw("wheel", RANDOM_POOL), True
        if _spin_wheel(name):  # the effect waits for the wheel. If it's already spinning, this gift fires right away.
            threading.Timer(WHEEL_SPIN, activate, (name, secs, who, gift), {"mystery": True, "counted": False}).start()
            return name
    if name not in EFFECTS and name not in INSTANT and name != "chaos":
        return None
    who, gift = _clean(who), _clean(gift)
    sender = who or "Someone"
    headline = f"{sender} sent {gift}" if gift else f"{sender} triggered an effect"
    icon = _gift_icon(gift)
    power = _gift_power(gift)

    now = time.time()
    left = None
    if name in INSTANT:
        threading.Thread(target=INSTANT_ACTIONS[name], daemon=True).start()
        label = EFFECT_NAMES[name]
        logged = name
    elif name == "chaos":
        secs = _powered(secs or _length("chaos"), power)
        pool = random.sample(GROUPS, 2)
        picks = [random.choice(sorted(g)) for g in pool]
        with lock:
            for n in picks:
                _stack(n, secs, now)
            _rebuild()
        left = secs
        label = "CHAOS MODE: " + " + ".join(EFFECT_NAMES[n] for n in picks)
        logged = "chaos:" + "+".join(picks)
    else:
        secs = _powered(secs or _length(name), power)
        with lock:
            _stack(name, secs, now)
            if name in NAMED_EFFECTS:
                data[name]["who"] = who
            _rebuild()
            left = active[name] - now
        label = EFFECT_NAMES[name]
        logged = name
        if name == "sensitivity":
            label += " (3x faster)" if data[name]["factor"] > 1 else " (3x slower)"
    _sync_mouse_hook()
    label += " (random chaos)" if mystery else ""
    detail = label if left is None or name in SILENT else f"{label} - {left:.0f}s"
    if name in CREDIT_AFTER:
        with lock:
            late_credit[name] = (headline, detail, icon)
    elif name not in SILENT:  # jumpscare and flashbang are their own popup
        announce(headline, detail, icon)
    log(f"{time.strftime('%H:%M:%S')} - {headline}: {detail}")
    log_event(who, gift, logged, EMOTE_LOCK_SECONDS if left is None else left, mystery)
    return name


def clear(why="timer", names=None):
    """Turn off the given effects (default: all of them)."""
    with lock:
        if why != "timer":
            move_lock["until"] = 0.0
        names = [n for n in (names or list(active)) if n in active]
        if not names:
            return
        for n in names:
            _stop(n)
        _rebuild()
        credits = [late_credit.pop(n) for n in names if n in late_credit]
    _sync_mouse_hook()
    shown = [n for n in names if n not in SILENT]
    if why == "timer":
        for c in credits:
            announce(*c)
    if why != "closing" and shown:
        detail = "Panic key pressed" if why == "panic key" else \
            " + ".join(EFFECT_NAMES.get(n, n) for n in shown) + " ended"
        announce("Back to normal", detail)
    if shown:
        log(f"{time.strftime('%H:%M:%S')} - {', '.join(shown)} off ({why})")


def _ctrl_alt_held():
    return bool(user32.GetAsyncKeyState(0x11) & 0x8000 and user32.GetAsyncKeyState(0x12) & 0x8000)


def handle_key(sc, down, flags, extra):
    """Called for every keypress. Returns True if the key should be swallowed."""
    if extra == MAGIC:
        return False
    if sc == FLASH_HOTKEY_SCAN and (down and _ctrl_alt_held() or not down and sc in hotkeys_down):
        # Ctrl+Alt+F, the old flashbang hotkey (TikFinity "press key")
        if down and sc not in hotkeys_down:
            hotkeys_down.add(sc)
            mask_alt()
            threading.Thread(target=activate, args=("flashbang",), daemon=True).start()
        elif not down:
            hotkeys_down.discard(sc)
        return True
    if sc in HOTKEYS and not flags & LLKHF_EXTENDED:
        # works for real key presses AND for keys pressed by BetterTok/TikFinity
        if down and sc not in hotkeys_down:
            hotkeys_down.add(sc)
            threading.Thread(target=activate, args=(HOTKEYS[sc],), daemon=True).start()
        elif not down:
            hotkeys_down.discard(sc)
        return True
    if flags & (LLKHF_INJECTED | LLKHF_EXTENDED):
        return False
    if down and sc == PANIC_SCAN:
        threading.Thread(target=clear, args=("panic key",), daemon=True).start()
        return False
    with lock:
        game = focus["game"]  # tabbed out: new presses behave normally (releases below still undo held remaps)
        if down and game and time.time() < move_lock["until"]:
            return True  # frozen mid-emote (releases still go through)
        if down and game and sc in blocked:
            return True  # releases still go through, so nothing gets stuck
        if sc in passthru:
            if not down:
                passthru.discard(sc)
            return False
        if down:
            dst = held.get(sc) or (keymap.get(sc) if game else None)
            if dst:
                held[sc] = dst
        else:
            dst = held.pop(sc, None)
        if not dst:
            return False
        send_key(dst, not down)
    return True


def handle_mouse(msg, flags, extra):
    """Mouse buttons and wheel. Returns True if the event should be swallowed."""
    if extra == MAGIC or flags & 0x01:  # LLMHF_INJECTED
        return False
    with lock:
        game = focus["game"]  # tabbed out: mouse buttons behave normally
        frozen = game and time.time() < move_lock["until"]  # mid-emote: no buttons, no scrolling
        if msg == WM_MOUSEWHEEL:
            return frozen
        btn = "L" if msg in (WM_LBUTTONDOWN, WM_LBUTTONUP) else "R"
        down = msg in (WM_LBUTTONDOWN, WM_RBUTTONDOWN)
        if btn == "L":
            return down and frozen  # releases still go through, so nothing gets stuck
        # No-Scope (or mid-emote)
        if down:
            rbutton["blocked"] = (game and "noscope" in active) or frozen
            return rbutton["blocked"]
        blocked_r, rbutton["blocked"] = rbutton["blocked"], False
        return blocked_r  # only swallow the release if we swallowed the press


# Raw mouse: Fortnite reads raw mouse movement, so instead of blocking it we add a correction
# straight after each real movement (e.g. -2x for inverted, +2x for 3x faster).
_mouse_rest = [0.0, 0.0]


def handle_raw_move(dx, dy):
    if not focus["game"]:
        return
    with lock:
        fx = fy = 1.0
        if "sensitivity" in active:
            fx = fy = data["sensitivity"]["factor"]
        if "invertmouse" in active:
            fy = -fy
    cx = dx * (fx - 1) + _mouse_rest[0]
    cy = dy * (fy - 1) + _mouse_rest[1]
    ix, iy = int(cx), int(cy)
    _mouse_rest[0], _mouse_rest[1] = cx - ix, cy - iy
    if ix or iy:
        send_mouse(MOUSEEVENTF_MOVE, ix, iy)


# ---------------- effect threads ----------------
def force_emote():
    if not focus["game"]:
        log(f"{time.strftime('%H:%M:%S')} - forced emote skipped, Fortnite isn't in front")
        return
    if not emote_busy.acquire(blocking=False):
        return  # one is already playing
    try:
        with lock:
            move_lock["until"] = time.time() + EMOTE_LOCK_SECONDS
        _sync_mouse_hook()  # mouse buttons need the hook while frozen
        for sc in MOVE_KEYS:  # let go of anything you're holding so the emote isn't cancelled
            send_key(sc, True)
        tap_key(EMOTE)
        time.sleep(EMOTE_WHEEL_DELAY)
        if not focus["game"]:
            return  # tabbed out just now: don't flick and click on the desktop
        slot = random.randrange(EMOTE_WHEEL_SLOTS)
        angle = 2 * math.pi * slot / EMOTE_WHEEL_SLOTS  # 0 = straight up, clockwise
        dx, dy = round(math.sin(angle) * EMOTE_FLICK), round(-math.cos(angle) * EMOTE_FLICK)
        send_mouse(MOUSEEVENTF_MOVE, dx, dy)
        time.sleep(0.08)
        send_mouse(MOUSEEVENTF_LEFTDOWN)
        time.sleep(0.05)
        send_mouse(MOUSEEVENTF_LEFTUP)
        time.sleep(max(0.0, move_lock["until"] - time.time()) + 0.05)
    except Exception:
        traceback.print_exc()
    finally:
        emote_busy.release()
        _sync_mouse_hook()  # unfrozen: drop the hook again if nothing else needs it


INSTANT_ACTIONS = {"emote": force_emote}


def _running(name, started):
    with lock:
        return name in active and data.get(name) is started


def map_spam():
    """Keeps tapping M until it ends, then makes sure the map is closed."""
    with lock:
        me = data.get("mapspam")
    is_open = False
    while _running("mapspam", me):
        if focus["game"]:
            tap_key(MAP)
            is_open = not is_open
        time.sleep(MAPSPAM_GAP)
    if is_open and focus["game"]:
        tap_key(MAP)


def pin_aim(name, push):
    """Keeps shoving your aim to the floor (or sky) so you can't look away until it ends."""
    with lock:
        me = data.get(name)
    while _running(name, me):
        if focus["game"]:
            send_mouse(MOUSEEVENTF_MOVE, 0, push)
        time.sleep(0.01)


def spin():
    """Nonstop 360s until it ends."""
    with lock:
        me = data.get("spin")
    speed = me["dir"] * SPIN_COUNTS / SPIN_TURN_SECONDS  # mouse movement per second
    rest, last = 0.0, time.time()
    while _running("spin", me):
        time.sleep(0.01)
        now = time.time()
        rest += speed * (now - last)
        last = now
        ix = int(rest)
        rest -= ix
        if ix and focus["game"]:
            send_mouse(MOUSEEVENTF_MOVE, ix, 0)


EFFECT_THREADS = {"spin": spin, "mapspam": map_spam,
                  "lookdown": lambda: pin_aim("lookdown", LOOK_PUSH),
                  "lookup": lambda: pin_aim("lookup", -LOOK_PUSH)}


def watcher():
    while True:
        time.sleep(0.1)
        try:
            with lock:
                now = time.time()
                expired = [n for n, end in active.items() if now >= end]
            if expired:
                clear("timer", expired)
        except Exception:
            traceback.print_exc()


# ---------------- PC memory warning ----------------
# Shows a banner on YOUR screen (not on stream) when the PC's memory is nearly full, naming the biggest apps.
PC_RAM_WARN_PERCENT = 85
# Never named in the "PC memory is full" banner, because you need them while live: everything Start Stream.bat
# opens (BetterTok, Spotify, LIVE Studio, the jumpscare bot, this script), plus Fortnite and Windows' own memory.
# Names as Task Manager's Details tab shows them, without ".exe".
DO_NOT_CLOSE = {"tiktok live studio", "bettertok-desktop", "spotify", "node", "python", "pythonw", "py",
                "discord", "fortniteclient-win64-shipping", "memory compression", "system"}


class MEMORYSTATUSEX(ctypes.Structure):
    _fields_ = [("dwLength", wt.DWORD), ("dwMemoryLoad", wt.DWORD)] + \
               [(n, ctypes.c_ulonglong) for n in ("total", "avail", "totalPage", "availPage",
                                                   "totalVirtual", "availVirtual", "availExtended")]


# Every minute it also writes which apps are using the CPU and memory to
# Stream Reports\apps-<date>.csv, so Stream Report can show what was hogging the PC.
APP_LOG_DIR = stream_config.folder("reports_folder", "Stream Reports")
APP_LOG_TOP = 10        # how many of the busiest apps to write each minute
APP_LOG_MIN_MB = 500    # plus any app using more memory than this


class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
    _fields_ = [("cb", wt.DWORD), ("PageFaultCount", wt.DWORD)] + \
               [(n, ctypes.c_size_t) for n in ("PeakWorkingSetSize", "WorkingSetSize", "QuotaPeakPagedPoolUsage",
                                               "QuotaPagedPoolUsage", "QuotaPeakNonPagedPoolUsage",
                                               "QuotaNonPagedPoolUsage", "PagefileUsage", "PeakPagefileUsage")]


def _ft(f):
    return (f.dwHighDateTime << 32 | f.dwLowDateTime) / 1e7  # FILETIME -> seconds


def _app_usage():
    """{app name: [cpu seconds used so far, memory MB]} for every process we're allowed to look at."""
    k32, psapi = ctypes.windll.kernel32, ctypes.windll.psapi
    k32.OpenProcess.restype = wt.HANDLE
    pids = (wt.DWORD * 4096)()
    got = wt.DWORD()
    psapi.EnumProcesses(pids, ctypes.sizeof(pids), ctypes.byref(got))
    apps = {}
    for pid in pids[:got.value // 4]:
        h = k32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
        if not h:
            continue
        try:
            buf, size = ctypes.create_unicode_buffer(520), wt.DWORD(520)
            if not k32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(size)):
                continue
            name = os.path.splitext(os.path.basename(buf.value))[0]
            t = [wt.FILETIME() for _ in range(4)]
            k32.GetProcessTimes(h, *[ctypes.byref(x) for x in t])
            mem = PROCESS_MEMORY_COUNTERS(cb=ctypes.sizeof(PROCESS_MEMORY_COUNTERS))
            psapi.GetProcessMemoryInfo(h, ctypes.byref(mem), mem.cb)
            a = apps.setdefault(name, [0.0, 0.0])
            a[0] += _ft(t[2]) + _ft(t[3])
            a[1] += mem.WorkingSetSize / 1024 / 1024
        finally:
            k32.CloseHandle(h)
    return apps


def _cpu_times():
    idle, kern, user = wt.FILETIME(), wt.FILETIME(), wt.FILETIME()
    ctypes.windll.kernel32.GetSystemTimes(ctypes.byref(idle), ctypes.byref(kern), ctypes.byref(user))
    return _ft(idle), _ft(kern) + _ft(user)  # kernel time includes idle time


def _write_app_log(ram, cpu, rows):
    os.makedirs(APP_LOG_DIR, exist_ok=True)
    path = os.path.join(APP_LOG_DIR, f"apps-{time.strftime('%Y-%m-%d')}.csv")
    new = not os.path.exists(path)
    now = time.strftime("%Y-%m-%d %H:%M:%S")
    with open(path, "a", encoding="utf-8") as f:
        if new:
            f.write("time,app,cpu_percent,memory_mb\n")
        f.write(f"{now},_WHOLE PC (RAM % in memory column),{cpu:.1f},{ram}\n")
        for name, c, mb in rows:
            f.write(f"{now},{name.replace(',', ' ')},{c:.1f},{mb:.0f}\n")


def memory_watcher():
    ram_warned = False
    cores = os.cpu_count() or 1
    before, sys_before, t_before = _app_usage(), _cpu_times(), time.time()
    while True:
        time.sleep(60)
        try:
            after, sys_after, t_after = _app_usage(), _cpu_times(), time.time()
            secs, t_before = max(1.0, t_after - t_before), t_after
            idle = sys_after[0] - sys_before[0]
            total = sys_after[1] - sys_before[1]
            pc_cpu = 100 * (1 - idle / total) if total else 0
            usage = []  # (name, cpu % of the whole PC, MB)
            for name, (cpu, mb) in after.items():
                used = max(0.0, cpu - before.get(name, [cpu])[0])
                usage.append((name, 100 * used / secs / cores, mb))
            before, sys_before = after, sys_after
            m = MEMORYSTATUSEX(dwLength=ctypes.sizeof(MEMORYSTATUSEX))
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
            usage.sort(key=lambda u: -u[1])
            rows = usage[:APP_LOG_TOP] + [u for u in usage[APP_LOG_TOP:] if u[2] >= APP_LOG_MIN_MB]
            try:
                _write_app_log(m.dwMemoryLoad, pc_cpu, rows)
            except OSError:
                pass  # e.g. the file is open in Excel - skip this minute
            if m.dwMemoryLoad >= PC_RAM_WARN_PERCENT and not ram_warned:
                hogs = [u for u in sorted(usage, key=lambda u: -u[2])
                        if u[0].lower() not in DO_NOT_CLOSE and not u[0].lower().startswith("python")][:3]
                biggest = ", ".join(f"{n} {mb / 1024:.1f} GB" for n, _, mb in hogs)
                popups.put((f"PC memory is {m.dwMemoryLoad}% full", f"Biggest: {biggest}"))
                log(f"{time.strftime('%H:%M:%S')} - PC memory at {m.dwMemoryLoad}%")
                ram_warned = True
            elif m.dwMemoryLoad < PC_RAM_WARN_PERCENT - 5:
                ram_warned = False  # warn again only after it has dropped back down
        except Exception:
            traceback.print_exc()


# ---------------- Discord jumpscare ----------------
# A tiny Discord bot built in, using only what comes with Python: it connects to Discord's gateway
# (a websocket), watches one channel for the command, and reacts with a tick or a no-entry sign.
DISCORD_CHANNEL_ID = stream_config.get("discord_channel_id", "")
DISCORD_COMMAND = "!jumpscare"
DISCORD_MAX_PER_DAY = 3   # per person, resets at midnight (your PC's time)
DISCORD_EFFECT = "jumpscare"
DISCORD_INTENTS = 1 | 512 | 32768  # guilds, guild messages, message content
discord_status = {"state": "off"}


def _jumpscare_folder():
    return os.path.join(HERE, "Tiktok Jumpscare")


def _discord_token():
    """From config.json, or discord_token.txt, or else from the old bot.js (so nothing has to be copied over)."""
    token = stream_config.get("discord_token")
    if token:
        return token
    folder = _jumpscare_folder()
    try:
        with open(os.path.join(folder, "discord_token.txt"), encoding="utf-8") as f:
            token = f.read().strip()
        if token:
            return token
    except OSError:
        pass
    try:
        with open(os.path.join(folder, "bot.js"), encoding="utf-8") as f:
            m = re.search(r"DISCORD_TOKEN\s*=\s*'([^']+)'", f.read())
        if m and "PASTE_YOUR" not in m.group(1):
            return m.group(1)
    except OSError:
        pass
    return None


def _discord_allowed(user_id):
    """Counts this use against the person's daily limit. False if they're out for today."""
    path = os.path.join(_jumpscare_folder(), "jumpscare-state.json")
    today = time.strftime("%a %b %d %Y")  # same format the old bot.js saved, e.g. "Thu Oct 23 2026"
    try:
        with open(path, encoding="utf-8") as f:
            state = json.load(f)
    except (OSError, ValueError):
        state = {}
    entry = state.get(user_id) or {}
    used = entry.get("count", 0) if entry.get("date") == today else 0
    if used >= DISCORD_MAX_PER_DAY:
        return False
    state[user_id] = {"date": today, "count": used + 1}
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)
    except OSError:
        pass
    return True


def _discord_react(token, channel, message, emoji):
    def go():
        url = (f"https://discord.com/api/v10/channels/{channel}/messages/{message}"
               f"/reactions/{quote(emoji)}/@me")
        req = urllib.request.Request(url, method="PUT", data=b"", headers={
            "Authorization": f"Bot {token}", "User-Agent": "DiscordBot (fortnite-chaos, 1.0)"})
        try:
            urllib.request.urlopen(req, timeout=10).close()
        except Exception:
            pass  # a missing reaction is no big deal
    threading.Thread(target=go, daemon=True).start()


class _Websocket:
    """Just enough of a websocket client for Discord's gateway. Everything runs on one thread."""

    def __init__(self, host, path, headers=None):
        raw = socket.create_connection((host, 443), timeout=15)
        self.sock = ssl.create_default_context().wrap_socket(raw, server_hostname=host)
        key = base64.b64encode(os.urandom(16)).decode()
        extra = "".join(f"{k}: {v}\r\n" for k, v in (headers or {}).items())
        self.sock.sendall((f"GET {path} HTTP/1.1\r\nHost: {host}\r\nUpgrade: websocket\r\n"
                           f"Connection: Upgrade\r\nSec-WebSocket-Key: {key}\r\n"
                           f"Sec-WebSocket-Version: 13\r\n{extra}\r\n").encode())
        head = b""
        while b"\r\n\r\n" not in head:
            chunk = self.sock.recv(4096)
            if not chunk:
                raise ConnectionError("gateway closed during handshake")
            head += chunk
        head, self.buf = head.split(b"\r\n\r\n", 1)
        if b" 101 " not in head.split(b"\r\n", 1)[0]:
            raise ConnectionError("gateway refused the websocket: " + head.split(b"\r\n", 1)[0].decode(errors="ignore"))
        self.sock.settimeout(1.0)  # recv wakes up every second so heartbeats go out on time
        self.parts = b""

    def send(self, obj, opcode=1):
        data = obj if isinstance(obj, bytes) else json.dumps(obj).encode()
        mask = os.urandom(4)
        n = len(data)
        head = bytes([0x80 | opcode])
        head += bytes([0x80 | n]) if n < 126 else (bytes([0x80 | 126]) + struct.pack(">H", n) if n < 65536
                                                    else bytes([0x80 | 127]) + struct.pack(">Q", n))
        self.sock.sendall(head + mask + bytes(b ^ mask[i % 4] for i, b in enumerate(data)))

    def _frame(self):
        """One complete frame from the buffer as (fin, opcode, payload), or None if more bytes are needed."""
        b = self.buf
        if len(b) < 2:
            return None
        n, i = b[1] & 0x7F, 2
        if n == 126:
            if len(b) < 4:
                return None
            n, i = struct.unpack(">H", b[2:4])[0], 4
        elif n == 127:
            if len(b) < 10:
                return None
            n, i = struct.unpack(">Q", b[2:10])[0], 10
        if len(b) < i + n:
            return None
        self.buf = b[i + n:]
        return b[0] & 0x80, b[0] & 0x0F, b[i:i + n]

    def recv(self):
        """The next JSON message, or None if nothing arrived within a second."""
        while True:
            frame = self._frame()
            if frame is None:
                try:
                    chunk = self.sock.recv(65536)
                except socket.timeout:
                    return None
                if not chunk:
                    raise ConnectionError("gateway closed the connection")
                self.buf += chunk
                continue
            fin, op, payload = frame
            if op == 8:  # close
                code = struct.unpack(">H", payload[:2])[0] if len(payload) >= 2 else 0
                raise ConnectionError(f"gateway closed ({code})", code)
            if op == 9:  # ping
                self.send(payload, opcode=10)
                continue
            if op in (0, 1, 2):
                self.parts += payload
                if fin:
                    msg, self.parts = self.parts, b""
                    return json.loads(msg)

    def close(self):
        try:
            self.sock.close()
        except Exception:
            pass


def _discord_session(token):
    ws = _Websocket("gateway.discord.gg", "/?v=10&encoding=json")
    try:
        hello = None
        while hello is None:
            hello = ws.recv()
        interval = hello["d"]["heartbeat_interval"] / 1000
        ws.send({"op": 2, "d": {"token": token, "intents": DISCORD_INTENTS,
                                "properties": {"os": "windows", "browser": "fortnite-chaos", "device": "fortnite-chaos"}}})
        seq, acked = None, True
        next_beat = time.time() + interval * random.random()
        while True:
            if time.time() >= next_beat:
                if not acked:
                    raise ConnectionError("Discord stopped answering heartbeats")
                ws.send({"op": 1, "d": seq})
                acked, next_beat = False, time.time() + interval
            msg = ws.recv()
            if msg is None:
                continue
            seq = msg.get("s") or seq
            op = msg.get("op")
            if op == 11:
                acked = True
            elif op == 1:
                ws.send({"op": 1, "d": seq})
            elif op in (7, 9):  # Discord asked us to reconnect
                raise ConnectionError("Discord asked for a reconnect")
            elif op == 0 and msg.get("t") == "READY":
                me = msg["d"]["user"]
                discord_status["state"] = "connected"
                log(f"Discord: connected as {me.get('username')}, watching for {DISCORD_COMMAND}")
            elif op == 0 and msg.get("t") == "MESSAGE_CREATE":
                _discord_message(token, msg["d"])
    finally:
        ws.close()


def _discord_message(token, m):
    if m.get("author", {}).get("bot") or m.get("channel_id") != DISCORD_CHANNEL_ID:
        return
    if (m.get("content") or "").strip().lower() != DISCORD_COMMAND:
        return
    author = m["author"]
    name = author.get("global_name") or author.get("username") or "Someone"
    if not _discord_allowed(author["id"]):
        log(f"{time.strftime('%H:%M:%S')} - Discord: {name} is out of jumpscares for today")
        _discord_react(token, m["channel_id"], m["id"], "\U0001F6AB")
        return
    threading.Thread(target=activate, args=(DISCORD_EFFECT,),
                     kwargs={"who": name, "gift": "a Discord jumpscare", "counted": False}, daemon=True).start()
    _discord_react(token, m["channel_id"], m["id"], "✅")


def discord_bot():
    token = _discord_token()
    if not token or not DISCORD_CHANNEL_ID:
        log("  note: no Discord token or channel in config.json, the Discord jumpscare is off")
        return
    wait = 5
    while True:
        discord_status["state"] = "connecting"
        try:
            _discord_session(token)
        except Exception as e:
            code = e.args[1] if isinstance(e, ConnectionError) and len(e.args) > 1 else None
            if code in (4004, 4014):
                discord_status["state"] = "error"
                log("Discord: " + ("the bot token was rejected" if code == 4004 else
                                   "turn on Message Content Intent for the bot in the Discord developer portal")
                    + " - the Discord jumpscare is off")
                return
            if discord_status["state"] == "connected":
                wait = 5  # it was working, so try again soon
            discord_status["state"] = "reconnecting"
            log(f"{time.strftime('%H:%M:%S')} - Discord: {e.args[0] if e.args else e} - reconnecting in {wait}s")
        time.sleep(wait)
        wait = min(wait * 2, 60)  # back off while Discord can't be reached


# ---------------- BetterTok Developer API (live TikTok events, straight from BetterTok) ----------------
# Replaces the BetterTok webhook actions: no "one rule per event" or switched-off action can get in the way.
# config.json:  "bettertok_api_key": "btk_live_...",                 (Developer tab > Keys)
#               "bettertok_gifts": {"Heart Me": "random", "Sunglasses": "random"},   gift name -> effect
#               "bettertok_follow": "random"                        effect for a follow ("" = nothing)
BETTERTOK_HOST = "api.bettertok.app"
BETTERTOK_PATH = "/api/v1/developer/stream"
BETTERTOK_MAX_PER_COMBO = 5     # a 10x combo fires this many effects at most...
BETTERTOK_COMBO_GAP = 1.5       # ...this many seconds apart
bettertok_status = {"state": "off"}
_bettertok_seen = []            # recent event ids, so a resent event never fires twice


def _bettertok_effect(route):
    route = str(route or "").strip().strip("/").lower()
    return route if route in ACTIVATE_ROUTES else None


def _bettertok_event(evt):
    """One event from the stream: fire what config.json says for it."""
    if not isinstance(evt, dict) or not isinstance(evt.get("data"), dict):
        return
    if evt.get("id"):
        if evt["id"] in _bettertok_seen:
            return
        _bettertok_seen.append(evt["id"])
        del _bettertok_seen[:-200]
    kind, d = evt.get("type"), evt["data"]
    who = d.get("display_name") or d.get("viewer_username") or ""
    if kind == "gift":
        gifts = stream_config.get("bettertok_gifts", {})
        gift = d.get("gift_name") or ""
        route = next((r for g, r in (gifts.items() if isinstance(gifts, dict) else [])
                      if _gift_key(str(g)) == _gift_key(gift)), None)
        name = _bettertok_effect(route)
        if not name:
            return
        try:
            count = int(d.get("gift_count") or 1)
        except (TypeError, ValueError):
            count = 1
        for i in range(max(1, min(count, BETTERTOK_MAX_PER_COMBO))):  # one effect per gift in the combo
            threading.Timer(i * BETTERTOK_COMBO_GAP, activate, (name, None, who, gift)).start()
    elif kind == "follow":
        name = _bettertok_effect(stream_config.get("bettertok_follow", ""))
        if name:  # a follow isn't a gift: no combo meter, no top sender
            threading.Thread(target=activate, args=(name, None, who, "a follow"),
                             kwargs={"counted": False}, daemon=True).start()
    elif kind == "comment":
        add_chat(_clean(who), d.get("comment") or "")  # chat votes


def _bettertok_session(key):
    ws = _Websocket(BETTERTOK_HOST, BETTERTOK_PATH, {"Authorization": f"Bearer {key}"})
    try:
        started = time.time()
        while True:
            msg = ws.recv()
            if isinstance(msg, dict) and msg.get("type") == "error":  # e.g. {"code": "UNAUTHORIZED", ...}
                raise ConnectionError(msg.get("message") or "BetterTok sent an error", msg.get("code"))
            # a bad key is refused straight after connecting, so only say "connected" once that's passed
            if bettertok_status["state"] != "connected" and (msg is not None or time.time() - started > 3):
                bettertok_status["state"] = "connected"
                log("BetterTok: connected to your live events")
            if msg is not None:
                _bettertok_event(msg)
    finally:
        ws.close()


def bettertok_events():
    key = stream_config.get("bettertok_api_key")
    if not key:
        log("  note: no bettertok_api_key in config.json, gifts and follows only come in through BetterTok webhooks")
        return
    wait = 5
    while True:
        bettertok_status["state"] = "connecting"
        try:
            _bettertok_session(key)
        except Exception as e:
            text = str(e.args[0] if e.args else e)
            code = e.args[1] if isinstance(e, ConnectionError) and len(e.args) > 1 else None
            if code in ("UNAUTHORIZED", "FORBIDDEN", 1008) or " 401 " in text or " 403 " in text:
                bettertok_status["state"] = "error"
                log("BetterTok: the API key was rejected - make a new one in BetterTok's Developer tab"
                    " and put it in config.json as bettertok_api_key")
                return
            if bettertok_status["state"] == "connected":
                wait = 5
            bettertok_status["state"] = "reconnecting"
            log(f"{time.strftime('%H:%M:%S')} - BetterTok: {text} - reconnecting in {wait}s")
        time.sleep(wait)
        wait = min(wait * 2, 60)


# ---------------- viewer overlay (browser source) ----------------
HERE = os.path.dirname(os.path.abspath(__file__))


def _find_file(name):
    for folder in (HERE, os.path.join(HERE, "assets"), os.path.join(HERE, "Tiktok Jumpscare")):
        path = os.path.join(folder, name)
        if os.path.isfile(path):
            return path
    return None


def make_ring():
    """The flashbang's bang + ringing ears, written to a temp .wav once at startup."""
    import struct
    import tempfile
    import wave
    path = os.path.join(tempfile.gettempdir(), "fortnite_chaos_ring.wav")
    sr, dur = 44100, 5.5
    frames = bytearray()
    for i in range(int(sr * dur)):
        t = i / sr
        env = 1.0 if t < 1.5 else max(0.0, 1 - (t - 1.5) / (dur - 1.5))
        s = math.sin(2 * math.pi * 3500 * t) * 0.5 + math.sin(2 * math.pi * 4200 * t) * 0.25
        if t < 0.15:  # the "bang"
            s += random.uniform(-1, 1) * (1 - t / 0.15) * 1.5
        s = max(-1.0, min(1.0, s * env * FLASH_VOLUME))
        frames += struct.pack("<h", int(s * 32767))
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(bytes(frames))
    return path


def make_creeper_sound():
    """The creeper's fuse hiss, then the boom, written to a temp .wav once at startup."""
    import struct
    import tempfile
    import wave
    path = os.path.join(tempfile.gettempdir(), "fortnite_chaos_creeper.wav")
    sr, dur = 22050, CREEPER_FUSE + 1.4
    frames = bytearray()
    low = 0.0
    for i in range(int(sr * dur)):
        t = i / sr
        noise = random.uniform(-1, 1)
        if t < CREEPER_FUSE:  # hiss that gets louder and flutters
            s = noise * (0.15 + 0.35 * t / CREEPER_FUSE) * (0.75 + 0.25 * math.sin(2 * math.pi * 11 * t))
        else:  # boom: low rumble that dies away
            b = t - CREEPER_FUSE
            low += (noise - low) * 0.06
            s = (low * 5 + noise * max(0.0, 0.5 - b * 2.5)) * math.exp(-b * 3.2)
        frames += struct.pack("<h", int(max(-1.0, min(1.0, s)) * 32767 * 0.8))
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(bytes(frames))
    return path


# Gift pictures (assets\\gifts), found by gift name: "Tiny Diny" finds 002_Tiny_Diny.png
GIFTS_DIR = os.path.join(HERE, "assets", "gifts")
_gift_files = {}


def _gift_key(name):
    return re.sub(r"[^a-z0-9]", "", re.sub(r"^\d+_", "", os.path.splitext(name)[0]).lower())


def _load_gift_files():
    try:
        _gift_files.update({_gift_key(f): f for f in os.listdir(GIFTS_DIR) if f.lower().endswith(".png")})
    except OSError:
        pass


def _gift_icon(gift):
    """The picture's address on this server, or None."""
    key = _gift_key(gift or "")
    return f"/gifts/{key}.png" if key in _gift_files else None


def blink_amount(elapsed):
    """How closed the eyes are right now: 0 open, 1 shut."""
    t = elapsed % BLINK_CYCLE
    if t < 0.35:
        return t / 0.35
    if t < 0.6:
        return 1.0
    if t < 0.95:
        return 1 - (t - 0.6) / 0.35
    return 0.0


def lowhp_pulse(elapsed):
    """Heart pulse: jumps to 1 on each beat, then fades."""
    return math.exp(-(elapsed % LOWHP_BEAT) * 4)


def flash_alpha(left, total):
    """How white the flashbang is right now: full white, then a fade out."""
    elapsed = total - left
    if elapsed < FLASH_HOLD:
        return 1.0
    return max(0.0, 1 - (elapsed - FLASH_HOLD) / FLASH_FADE)


OVERLAY_HTML = """<!doctype html><html><head><meta charset="utf-8">
<style>html,body{margin:0;width:100%;height:100%;background:transparent;overflow:hidden}
.fx{position:fixed;inset:0;display:none}
#blind{background:radial-gradient(circle at 50% 50%,transparent 0 HOLEvh,#000 calc(HOLEvh + 1vh))}
#fog{background:#fff}
#scare{background:#000 center/cover no-repeat url(/jumpscare.png);color:red;font:bold 30vw sans-serif;align-items:center;justify-content:center}
#flash{background:#fff}
#timers{position:fixed;left:0;right:0;top:3vh;display:flex;flex-direction:column;align-items:center;gap:1vh;
  font:800 2.6vh 'Segoe UI',Arial,sans-serif;color:#fff;pointer-events:none}
#timers.bottom{top:auto;bottom:3vh}
.pill{min-width:34vh;max-width:90vw;padding:1vh 2vh .9vh;border-radius:1.4vh;background:rgba(10,10,10,.82);
  box-shadow:0 .4vh 1.6vh rgba(0,0,0,.5);text-align:center;text-shadow:0 .2vh .4vh #000}
.pill .t{display:flex;justify-content:space-between;gap:2vh}.pill .s{color:#ffcf40}
.pill .bar{height:.7vh;margin-top:.7vh;border-radius:.4vh;background:rgba(255,255,255,.18);overflow:hidden}
.pill .bar i{display:block;height:100%;background:linear-gradient(90deg,#ff3b5c,#ffcf40);transition:width .1s linear}
#banner{position:fixed;left:50%;bottom:12vh;transform:translate(-50%,3vh);opacity:0;max-width:90vw;padding:1.6vh 4vh;
  border-radius:1.6vh;background:rgba(17,17,17,.93);box-shadow:0 .6vh 2.4vh rgba(0,0,0,.6);text-align:center;
  font-family:'Segoe UI',Arial,sans-serif;pointer-events:none;transition:opacity .25s,transform .25s}
#banner.top{bottom:auto;top:3vh}
#banner.on{opacity:1;transform:translate(-50%,0)}
#banner .h{font:800 4.2vh 'Segoe UI',Arial,sans-serif;color:#fff;text-shadow:0 .2vh .4vh #000}
#banner .d{font:600 2.6vh 'Segoe UI',Arial,sans-serif;color:#ffcf40;margin-top:.4vh}
#banner img{height:7vh;display:block;margin:0 auto .4vh}
#fakeban{background:#14507f url(/fakeban_bg.png) center/cover no-repeat;flex-direction:column;align-items:center;text-align:center;padding-top:30vh;box-sizing:border-box}
#fakeban .ico{width:5.4vh;height:5.4vh;border-radius:50%;background:#f03c16;color:#fff;font:4.2vh/5.4vh Impact,sans-serif}
#fakeban .ttl{font:italic 5.75vh/1 Impact,sans-serif;color:#fff;margin-top:1.8vh}
#fakeban .ln{width:99.3vh;height:1.2vh;margin-top:1.7vh;background:#1763e6;clip-path:polygon(0 15%,100% 0,99.3% 100%,.7% 100%)}
#fakeban .msg{font:700 2.7vh/3.35vh 'Segoe UI',Arial,sans-serif;color:#86d4ff;white-space:pre-line;margin-top:1.8vh}
#fakeban .ln+.msg+.ln{margin-top:1.8vh}
#fakeban .btn{width:17.8vh;height:5.2vh;margin-top:2vh;background:#e2d900;color:#14202c;font:3vh/5.2vh Impact,sans-serif}
#bsod{background:#0078d7;color:#fff;font-family:'Segoe UI',Arial,sans-serif;padding:16vh 14vw;box-sizing:border-box}
#bsod b{display:block;font-size:17vh;font-weight:300;line-height:1}#bsod p{font-size:3.4vh;margin:4vh 0 0;max-width:62vw}#bsod small{display:block;font-size:2vh;margin-top:5vh}
#lidt,#lidb{background:#000}
#lowhp{background:radial-gradient(ellipse at center,transparent 45%,rgba(190,0,0,.9) 100%)}
#creeper{pointer-events:none}#creeper canvas{position:absolute;inset:0;width:100%;height:100%}
#wheelbox{position:fixed;left:50%;top:50%;width:36vh;height:36vh;margin:-18vh 0 0 -18vh;display:none;filter:drop-shadow(0 .6vh 2vh rgba(0,0,0,.7))}
#wheelbox svg{width:100%;height:100%;display:block}
#wheelarrow{position:absolute;left:50%;top:-1.6vh;margin-left:-1.5vh;border-left:1.5vh solid transparent;border-right:1.5vh solid transparent;border-top:3vh solid #fff}
#combo{position:fixed;left:2vh;bottom:3vh;width:30vh;display:none;padding:1vh 1.6vh;border-radius:1.2vh;background:rgba(10,10,10,.82);
  color:#fff;font:800 2.2vh 'Segoe UI',Arial,sans-serif;text-shadow:0 .2vh .4vh #000}
#combo .t{display:flex;justify-content:space-between}#combo .s{color:#ffcf40}
#combo .bar{height:1vh;margin-top:.7vh;border-radius:.5vh;background:rgba(255,255,255,.18);overflow:hidden}
#combo .bar i{display:block;height:100%;background:linear-gradient(90deg,#ffcf40,#ff3b5c);transition:width .2s}
#top{position:fixed;left:2vh;bottom:19.5vh;width:30vh;box-sizing:border-box;display:none;padding:1.4vh 2vh;border-radius:1.4vh;background:rgba(10,10,10,.86);
  color:#fff;font:700 2.4vh 'Segoe UI',Arial,sans-serif}
#top h3{margin:0 0 .8vh;font-size:2.4vh;color:#ffcf40}#top div{display:flex;justify-content:space-between;gap:1vh;margin-top:.3vh}
#top span:first-child{overflow:hidden;white-space:nowrap;text-overflow:ellipsis}
#vote{position:fixed;right:2vh;bottom:3vh;width:34vh;display:none;box-sizing:border-box;padding:1.2vh 1.6vh;
  border-radius:1.4vh;background:rgba(10,10,10,.88);color:#fff;font:700 2.1vh 'Segoe UI',Arial,sans-serif}
#vote h3{margin:0 0 .8vh;font-size:2.2vh;color:#ffcf40;display:flex;justify-content:space-between}
#vote .o{display:grid;grid-template-columns:3vh 1fr 3vh;align-items:center;gap:.8vh;margin-top:.5vh;padding:.3vh .6vh;border-radius:.6vh}
#vote .o b{color:#ffcf40}#vote .o.win{background:#ff3b5c}
#vote .bar{grid-column:2/4;height:.7vh;border-radius:.4vh;background:rgba(255,255,255,.15);overflow:hidden}
#vote .bar i{display:block;height:100%;background:#ffcf40;transition:width .3s}
#fakeban .by{font:700 2.2vh 'Segoe UI',Arial,sans-serif;color:#86d4ff;margin-top:2.2vh}
#creeperby{position:absolute;left:0;right:0;top:50%;transform:translateY(-50%);text-align:center;color:#fff;
  font:min(9vh,9vw)/1 Impact,sans-serif;text-shadow:0 0 2vh #000}
#menu{position:fixed;right:2vh;top:12vh;width:27vh;display:none;padding:1.2vh 1.4vh;border-radius:1.4vh;background:rgba(10,10,10,.82);
  color:#fff;font:700 1.9vh 'Segoe UI',Arial,sans-serif}
#menu h3{margin:.8vh 0 .3vh;font-size:1.6vh;letter-spacing:.1vh;color:#ffcf40;text-transform:uppercase}#menu h3:first-child{margin-top:0}
#menu div{display:flex;align-items:center;gap:.8vh;padding:.15vh .5vh;border-radius:.6vh}
#menu div.on{background:#ff3b5c}#menu img{height:2.4vh}
</style></head><body>
<div id="blind" class="fx"></div><div id="fog" class="fx"></div>
<div id="lowhp" class="fx"></div>
<div id="lidt" class="fx"></div><div id="lidb" class="fx"></div>
<div id="creeper" class="fx"><canvas id="crater"></canvas><canvas id="face"></canvas><div id="creeperby"></div></div>
<div id="fakeban" class="fx"><div class="ico">!</div><div class="ttl">__BAN_TITLE__</div><div class="ln"></div><div class="msg">__BAN_TEXT__</div><div class="ln"></div><div class="btn">CONTINUE</div><div class="by"></div></div>
<div id="bsod" class="fx"><b>:(</b><p>Your PC ran into a problem and needs to restart. We're just collecting some error info, and then we'll restart for you.</p><p>20% complete</p><small>Stop code: <span id="bsodcode">TOO_MANY_GIFTS</span></small></div>
<div id="scare" class="fx"></div><div id="flash" class="fx"></div>
<div id="menu"></div>
<div id="vote"></div>
<div id="timers"></div>
<div id="combo"><div class="t"><span>GIFT COMBO</span><span class="s"></span></div><div class="bar"><i></i></div></div>
<div id="top"></div>
<div id="wheelbox"><div id="wheelarrow"></div><div id="wheel"></div></div>
<div id="banner"><div class="h"></div><div class="d"></div></div>
<script>
const $=id=>document.getElementById(id);
const timerPos=new URLSearchParams(location.search).get('timer')||'top';
if(timerPos==='bottom'){$('timers').className='bottom';$('banner').classList.add('top');}
let bannerId=null;
const esc=s=>s.replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const SPIN=__SPIN__,FUSE=__FUSE__,BLAST=__BLAST__,CRATER_R=__CRATER__;
let wheelId=null,creeperOn=false,lastMenu='',lastTop='';
const WC=['#ff3b5c','#ffcf40','#3fd0ff','#9b6bff'];
function drawWheel(w){
  const R=100,seg=360/w.names.length;let out='';
  w.names.forEach((n,i)=>{
    const a=(i*seg-90)*Math.PI/180,b=((i+1)*seg-90)*Math.PI/180,mid=i*seg+seg/2;
    out+='<path d="M0 0L'+R*Math.cos(a)+' '+R*Math.sin(a)+'A'+R+' '+R+' 0 0 1 '+R*Math.cos(b)+' '+R*Math.sin(b)+'Z" fill="'+WC[i%4]+'" stroke="#111"/>';
    out+='<text transform="rotate('+(mid-90)+') translate(94 3.5)" text-anchor="end" font-size="10" font-weight="800" font-family="Segoe UI,Arial" fill="#111">'+esc(n)+'</text>';
  });
  $('wheel').innerHTML='<svg viewBox="-102 -102 204 204"><g id="wg">'+out+'</g></svg>';
  const g=$('wg'),to=360*5-(w.pick*seg+seg/2);
  g.style.transition='none';g.style.transform='rotate(0deg)';
  requestAnimationFrame(()=>requestAnimationFrame(()=>{
    g.style.transition='transform '+SPIN+'s cubic-bezier(.12,.75,.2,1)';g.style.transform='rotate('+to+'deg)';}));
}
function lid(el,a,top){
  let pts=top?['0% 0%','100% 0%']:['0% 100%','100% 100%'];
  for(let i=16;i>=0;i--){const x=i/16,y=a*55*(1+.45*Math.pow(2*x-1,2));pts.push(x*100+'% '+(top?y:100-y)+'%');}
  el.style.clipPath='polygon('+pts.join(',')+')';
}
const FACE=['GGLGGDGG','GLGDGGLG','GKKGGKKD','DKKGLKKG','GGDKKGGL','LGKKKKGG','GGKKKKDG','GDKGGKGL'];
const FC={G:'#4fa63c',L:'#6cc24a',D:'#3b8430',K:'#111'};
function drawFace(){
  const c=$('face');c.width=innerWidth;c.height=innerHeight;const x=c.getContext('2d'),s=Math.floor(innerHeight*.7/8),ox=(innerWidth-s*8)/2,oy=(innerHeight-s*8)/2;
  FACE.forEach((r,j)=>[...r].forEach((ch,i)=>{x.fillStyle=FC[ch];x.fillRect(ox+i*s,oy+j*s,s,s);}));
}
function drawCrater(){
  const c=$('crater');c.width=innerWidth;c.height=innerHeight;const x=c.getContext('2d'),B=Math.ceil(innerHeight/18),r=innerHeight*CRATER_R;
  const char=['#1e1a17','#2a241f','#3a332d'],dirt=['#5b3d23','#6f4c2c','#7d5a36','#4a4a4a'];
  for(let j=-1;j<=innerHeight/B+1;j++)for(let i=-1;i<=innerWidth/B+1;i++){
    const d=Math.hypot(i*B+B/2-innerWidth/2,j*B+B/2-innerHeight/2)+(Math.random()-.5)*B*1.6;let col=null;
    if(d<r)col='#000';else if(d<r+B*1.3)col=char[Math.random()*3|0];
    else if(d<r+B*2.8){if(Math.random()<.72)col=dirt[Math.random()*4|0];}
    else if(d<r+B*5&&Math.random()<.14)col=dirt[Math.random()*4|0];
    if(col){x.fillStyle=col;x.fillRect(i*B,j*B,B,B);}
  }
}
function renderExtras(s){
  const fx=s.effects;
  $('fakeban').style.display=fx.fakeban?'flex':'none';
  if(fx.fakeban)$('fakeban').querySelector('.by').textContent=fx.fakeban.who?'Banned by: '+fx.fakeban.who:'';
  if(fx.bsod)$('bsodcode').textContent=fx.bsod.code||'TOO_MANY_GIFTS';
  $('bsod').style.display=fx.bsod?'block':'none';
  const a=fx.blink?fx.blink.amount:0;
  $('lidt').style.display=$('lidb').style.display=a>0?'block':'none';
  if(a>0){lid($('lidt'),a,true);lid($('lidb'),a,false);}
  $('lowhp').style.display=fx.lowhp?'block':'none';
  if(fx.lowhp)$('lowhp').style.opacity=.35+.65*fx.lowhp.pulse;
  if(fx.creeper){
    const e=fx.creeper.elapsed,box=$('creeper');
    if(!creeperOn){creeperOn=true;drawFace();drawCrater();}
    box.style.display='block';box.style.background=(e>=FUSE&&e<FUSE+BLAST)?'#fff':'transparent';
    $('face').style.display=e<FUSE?'block':'none';
    $('face').style.filter=(e>FUSE*.45&&Math.floor(e*8)%2)?'brightness(3)':'none';
    $('crater').style.display=e>=FUSE+BLAST?'block':'none';
    $('creeperby').textContent=(e>=FUSE+BLAST&&fx.creeper.who)?fx.creeper.who.toUpperCase()+' WAS HERE':'';
  }else{creeperOn=false;$('creeper').style.display='none';}
  if(s.wheel){
    if(s.wheel.id!==wheelId){wheelId=s.wheel.id;drawWheel(s.wheel);}
    $('wheelbox').style.display='block';
  }else $('wheelbox').style.display='none';
  const v=s.vote,vb=$('vote');
  if(v){vb.style.display='block';const total=v.counts.reduce((a,b)=>a+b,0)||1;
    vb.innerHTML='<h3><span>'+(v.winner===null?'CHAT VOTE - type 1-'+v.options.length:'CHAT PICKED')+'</span><span>'+(v.winner===null?Math.ceil(v.left)+'s':'')+'</span></h3>'
      +v.options.map((o,i)=>'<div class="o'+(v.winner===i?' win':'')+'"><b>'+(i+1)+'</b><span>'+esc(o)+'</span><span>'+v.counts[i]+'</span><div class="bar"><i style="width:'+(v.counts[i]/total*100)+'%"></i></div></div>').join('');
  }else vb.style.display='none';
  const c=s.combo;$('combo').style.display=c?'block':'none';
  if(c){$('combo').querySelector('.s').textContent=c.count+' / '+c.goal;$('combo').querySelector('i').style.width=c.count/c.goal*100+'%';}
  const t=s.top?'<h3>Top chaos senders</h3>'+s.top.map(p=>'<div><span>'+esc(p.who)+'</span><span>'+p.count+'</span></div>').join(''):'';
  if(t!==lastTop){lastTop=t;$('top').innerHTML=t;}
  $('top').style.display=t?'block':'none';
  const m=s.menu?s.menu.map(g=>'<h3>'+esc(g.title)+'</h3>'+g.items.map(i=>'<div class="'+(i.on?'on':'')+'">'+(i.icon?'<img src="'+i.icon+'">':'')+esc(i.name)+'</div>').join('')).join(''):'';
  if(m!==lastMenu){lastMenu=m;$('menu').innerHTML=m;}
  $('menu').style.display=m?'block':'none';
}
let ver=null;
function renderState(s){
  try{
    if(s.v){if(ver===null)ver=s.v;else if(s.v!==ver){location.reload();return;}}
    const fx=s.effects;
    $('blind').style.display=fx.blind?'block':'none';
    $('fog').style.display=fx.fog?'block':'none';
    if(fx.fog)$('fog').style.opacity=Math.min(.85,fx.fog.left/2*.85);
    $('scare').style.display=fx.jumpscare?'flex':'none';
    $('scare').textContent=s.image?'':'BOO!';
    $('flash').style.display=fx.flashbang?'block':'none';
    if(fx.flashbang)$('flash').style.opacity=fx.flashbang.alpha;
    renderExtras(s);
    $('timers').innerHTML=timerPos==='off'?'':s.timers.map(t=>'<div class="pill"><div class="t"><span>'
      +esc(t.label)+'</span><span class="s">'+Math.ceil(t.left)+'s</span></div><div class="bar"><i style="width:'
      +Math.max(0,Math.min(100,t.left/t.total*100))+'%"></i></div></div>').join('');
    const b=s.banner;
    if(b&&b.id!==bannerId){bannerId=b.id;$('banner').querySelector('.h').textContent=b.head;
      $('banner').querySelector('.d').textContent=b.detail;
      const old=$('banner').querySelector('img');if(old)old.remove();
      if(b.icon){const im=new Image();im.src=b.icon;$('banner').prepend(im);}}
    $('banner').classList.toggle('on',!!b);
  }catch(e){}
}
// Updates are pushed from Fortnite Chaos as they happen. If that stops (or never starts in this browser),
// it falls back to asking 20 times a second, and switches back when pushes resume.
let pushed=false,lastPush=0;
async function poll(){
  if(pushed)return;
  try{renderState(await (await fetch('/overlay/state',{cache:'no-store'})).json());}catch(e){}
  setTimeout(poll,50);
}
try{
  const es=new EventSource('/overlay/events');
  es.onmessage=e=>{lastPush=Date.now();pushed=true;try{renderState(JSON.parse(e.data));}catch(x){}};
}catch(e){}
setInterval(()=>{if(pushed&&Date.now()-lastPush>3500){pushed=false;poll();}},1000);
poll();
</script></body></html>""".replace("HOLE", str(round(BLIND_HOLE * 100))).replace(
    "__SPIN__", str(WHEEL_SPIN)).replace("__FUSE__", str(CREEPER_FUSE)).replace(
    "__BLAST__", str(CREEPER_BLAST)).replace("__CRATER__", str(CREEPER_HOLE)).replace(
    "__BAN_TITLE__", FAKE_BAN_TITLE).replace("__BAN_TEXT__", FAKE_BAN_TEXT)
OVERLAY_VERSION = hashlib.md5(OVERLAY_HTML.encode("utf-8")).hexdigest()[:10]  # overlays reload when this changes


def overlay_state():
    with lock:
        now = time.time()
        fx = {}
        for n in SCREEN & set(active):
            fx[n] = {"left": round(active[n] - now, 2)}
            elapsed = totals[n] - (active[n] - now)
            if n == "flashbang":
                fx[n]["alpha"] = round(flash_alpha(active[n] - now, totals[n]), 3)
            elif n == "blink":
                fx[n]["amount"] = round(blink_amount(elapsed), 3)
            elif n == "lowhp":
                fx[n]["pulse"] = round(lowhp_pulse(elapsed), 3)
            elif n == "creeper":
                fx[n]["elapsed"] = round(elapsed, 3)
            if n in NAMED_EFFECTS:
                fx[n]["who"] = (data.get(n) or {}).get("who", "")
                if n == "bsod":
                    fx[n]["code"] = _stop_code(fx[n]["who"])
        timers = [{"label": EFFECT_NAMES[n], "left": round(active[n] - now, 1), "total": totals[n]}
                  for n in sorted((CONTROL | MOVES | TIMED_SCREEN) & set(active), key=lambda n: active[n])]
        banner = None
        if now < stream_banner["until"]:
            banner = {k: stream_banner[k] for k in ("id", "head", "detail", "icon")}
        spin = None
        if now < wheel["until"]:
            spin = {k: wheel[k] for k in ("id", "names", "pick")}
        recent = [t for t in combo["times"] if now - t < COMBO_WINDOW]
        streak = {"count": len(recent), "goal": COMBO_GOAL} if recent else None
        if now >= top_show["next"]:
            top_show["next"] = now + random.uniform(*TOP_SENDER_EVERY)
            if senders:
                top_show["until"] = now + TOP_SENDER_SECONDS
        top = None
        if now < top_show["until"]:
            best = sorted(senders.items(), key=lambda p: -p[1])[:TOP_SENDER_COUNT]
            top = [{"who": w, "count": c} for w, c in best]
        every_menu = _minutes("menu_every_minutes", 5)
        if every_menu and now >= menu_show["next"]:
            if menu_show["next"]:  # not on the very first look, so it doesn't pop up the moment Chaos starts
                menu_show["until"] = now + MENU_SHOW_SECONDS
            menu_show["next"] = now + every_menu * 60
        voting = None
        if now < vote["until"] or now < vote["show_until"]:
            counts = [0] * len(vote["options"])
            for choice in vote["votes"].values():
                counts[choice - 1] += 1
            voting = {"id": vote["id"], "options": [SHORT_NAMES.get(o, o) for o in vote["options"]], "counts": counts,
                      "left": max(0.0, round(vote["until"] - now, 1)), "winner": vote["winner"]}
        menu_list = None
        if menu["on"] or now < menu_show["until"]:
            menu_list = [{"title": title, "items": [
                {"name": SHORT_NAMES.get(n) or PANEL_LABELS.get(n, n), "on": n in active,
                 "icon": _gift_icon(GIFT_ICONS[n]) if n in GIFT_ICONS else None} for n in names]}
                for title, names in MENU_GROUPS]
        return {"effects": fx, "timers": timers, "banner": banner, "image": bool(_find_file("jumpscare.png")),
                "wheel": spin, "combo": streak, "top": top, "menu": menu_list,
                "vote": voting, "v": OVERLAY_VERSION}


MENU_GROUPS = [
    ("Controls", ["invert", "rotate", "jumpswap", "noscope", "invertmouse", "sensitivity"]),
    ("Aim + map", ["lookdown", "lookup", "spin", "mapspam", "emote"]),
    ("Screen", ["blind", "fog", "jumpscare", "flashbang", "fakeban", "bsod", "blink", "lowhp", "creeper"]),
    ("Specials", ["random", "chaos"]),
]
PANEL_GROUPS = [
    ("Controls", ["invert", "rotate", "jumpswap", "noscope", "invertmouse", "sensitivity"]),
    ("Aim + map", ["lookdown", "lookup", "spin", "mapspam"]),
    ("One-offs", ["emote"]),
    ("Screen", ["blind", "fog", "jumpscare", "flashbang", "fakeban", "bsod", "blink", "lowhp", "creeper"]),
    ("Specials", ["random", "wheel", "chaos"]),
    ("Overlay", ["menu", "topsender"]),
    ("Chat vote", ["vote", "chat?user=Test&text=1"]),
]
PANEL_LABELS = dict(EFFECT_NAMES, random="Random chaos", wheel="Spin the wheel", chaos="Two at once",
                    menu="Show or hide gift menu",
                    topsender="Show top senders now", vote="Start a chat vote now",
                    **{"chat?user=Test&text=1": "Test chat: vote 1"})

PANEL_HTML = '''<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Fortnite Chaos panel</title>
<style>
:root{color-scheme:dark;--bg:#111317;--card:#1b1e24;--line:#2c313a;--text:#eef0f3;--muted:#9aa3ae;--accent:#ff3b5c;--ok:#3ecf8e}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font:15px/1.4 'Segoe UI',Arial,sans-serif}
main{max-width:900px;margin:0 auto;padding:20px 16px 40px}
h1{font-size:22px;margin:0 0 4px}p.sub{margin:0 0 18px;color:var(--muted)}
.bar{display:flex;flex-wrap:wrap;gap:10px;align-items:center;margin-bottom:14px}
.bar label{color:var(--muted)}
input{width:84px;padding:8px;border-radius:8px;border:1px solid var(--line);background:var(--card);color:var(--text);font:inherit}
h2{font-size:13px;letter-spacing:.08em;text-transform:uppercase;color:var(--muted);margin:22px 0 8px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:8px}
button{padding:11px 10px;border-radius:10px;border:1px solid var(--line);background:var(--card);color:var(--text);font:inherit;cursor:pointer;text-align:left}
button:hover{border-color:var(--accent)}button:active{transform:translateY(1px)}
button small{display:block;color:var(--muted);font-size:12px}
button.off{background:var(--accent);border-color:var(--accent);color:#fff;font-weight:700;text-align:center}
#status{padding:12px 14px;border-radius:10px;background:var(--card);border:1px solid var(--line);min-height:46px}
#status b{color:var(--ok)}#status .none{color:var(--muted)}
</style></head><body><main>
<h1>Fortnite Chaos</h1><p class="sub">Test any effect without TikFinity. F8 still works as the panic key.</p>
<div class="bar"><label for="secs">Seconds</label><input id="secs" type="number" min="1" placeholder="default">
<button class="off" onclick="go('off')">Turn everything off</button></div>
<div id="status"><span class="none">Connecting...</span></div>
GROUPS
</main><script>
async function go(name){
  const s=document.getElementById('secs').value;
  const q=new URLSearchParams({user:'Test panel'});if(s&&name!=='off')q.set('seconds',s);
  try{await fetch('/'+name+(name.includes('?')?'&':'?')+q,{cache:'no-store'})}catch(e){}
  status();
}
async function status(){
  const el=document.getElementById('status');
  try{
    const s=await (await fetch('/status',{cache:'no-store'})).json();
    const parts=Object.entries(s.active).map(([n,l])=>'<b>'+n+'</b> '+l+'s');
    el.innerHTML=parts.length?'Running: '+parts.join(' &middot; '):'<span class="none">Nothing running</span>';
  }catch(e){el.innerHTML='<span class="none">Fortnite Chaos is not running</span>'}
}
status();setInterval(status,1000);
</script></body></html>'''.replace("GROUPS", "".join(
    "<h2>%s</h2><div class='grid'>%s</div>" % (title, "".join(
        "<button onclick=\"go('%s')\">%s<small>%s</small></button>" % (n, n, PANEL_LABELS.get(n, n))
        for n in names)) for title, names in PANEL_GROUPS))


# ---------------- webhook server ----------------
def _find(obj, key):
    """Find the first string/number stored under `key` anywhere inside parsed JSON."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            if str(k).lower() == key:
                if isinstance(v, (str, int, float)):
                    return str(v)
                if isinstance(v, dict) and isinstance(v.get("name"), str):
                    return v["name"]
        for v in obj.values():
            r = _find(v, key)
            if r:
                return r
    elif isinstance(obj, list):
        for v in obj:
            r = _find(v, key)
            if r:
                return r
    return None


def _from_body(body):
    if not body:
        return None, None
    try:
        data = json.loads(body.decode("utf-8", "ignore"))
    except Exception:
        return None, None
    who = next((r for r in (_find(data, k) for k in ("nickname", "displayname", "display_name", "username", "uniqueid", "user")) if r), None)
    gift = next((r for r in (_find(data, k) for k in ("giftname", "gift_name", "gift")) if r), None)
    return who, gift


ROUTES = sorted(CONTROL | SCREEN | MOVES | INSTANT) + ["random", "wheel", "chaos", "off", "status", "menu", "topsender",
                                                      "chat", "vote"]
ACTIVATE_ROUTES = set(ROUTES) - {"off", "status", "menu", "topsender", "chat", "vote"}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, body, ctype):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Private-Network", "true")
        self.send_header("Content-Length", str(len(body)))  # LIVE Studio's Link source was only reliable with this
        self.end_headers()
        self.wfile.write(body)

    def _reply(self, code, body):
        self._send(code, json.dumps(body).encode(), "application/json")

    def do_GET(self):
        u = urlparse(self.path)
        name = u.path.strip("/").lower()
        if name in ("overlay", "overlay.html"):  # LIVE Studio only accepts links that end like a file/domain
            return self._send(200, OVERLAY_HTML.encode(), "text/html")
        if name in ("panel", "panel.html"):
            return self._send(200, PANEL_HTML.encode(), "text/html")
        if name == "overlay/state":
            return self._reply(200, overlay_state())
        if name == "overlay/events":
            return self._push_overlay()
        if name.startswith("gifts/") and name.endswith(".png"):
            file = _gift_files.get(name[6:-4])  # only the pictures found in the folder, nothing else
            if not file:
                return self._reply(404, {"error": "no such gift picture"})
            with open(os.path.join(GIFTS_DIR, file), "rb") as f:
                return self._send(200, f.read(), "image/png")
        if name == "fakeban_bg.png":
            path = _find_file("fakeban_bg.png")
            if not path:
                return self._reply(404, {"error": "no fakeban_bg.png"})
            with open(path, "rb") as f:
                return self._send(200, f.read(), "image/png")
        if name == "jumpscare.png":
            path = _find_file("jumpscare.png")
            if not path:
                return self._reply(404, {"error": "put jumpscare.png next to fortnite_chaos.py"})
            with open(path, "rb") as f:
                return self._send(200, f.read(), "image/png")
        q = parse_qs(u.query)
        secs = None
        try:
            secs = float(q["seconds"][0])
        except Exception:
            pass
        who = (q.get("user") or q.get("nickname") or q.get("who") or [""])[0]
        gift = (q.get("gift") or [""])[0]
        body = getattr(self, "body", b"")
        if body:
            log("  webhook body: " + body.decode("utf-8", "ignore")[:300])
            b_who, b_gift = _from_body(body)
            who, gift = who or b_who, gift or b_gift
        if name == "off":
            clear("webhook")
            self._reply(200, {"ok": True})
        elif name == "menu":
            show = (q.get("show") or [""])[0]
            with lock:
                menu["on"] = show == "1" if show in ("0", "1") else not menu["on"]
                on = menu["on"]
            self._reply(200, {"ok": True, "menu": on})
        elif name == "chat":
            user = (q.get("user") or q.get("nickname") or [""])[0]
            text = (q.get("text") or q.get("comment") or q.get("message") or [""])[0]
            if body and not text:
                try:
                    parsed = json.loads(body.decode("utf-8", "ignore"))
                    text = next((_find(parsed, k) for k in ("comment", "message", "text", "content") if _find(parsed, k)), "")
                    user = user or (b_who if (b_who := _from_body(body)[0]) else "")
                except ValueError:
                    pass
            self._reply(200, {"ok": True, "voted": add_chat(_clean(user), text)})
        elif name == "vote":
            self._reply(200, {"ok": True, "options": start_vote()})
        elif name == "topsender":
            with lock:
                top_show["until"] = time.time() + TOP_SENDER_SECONDS if senders else 0.0
                any_names = bool(senders)
            self._reply(200, {"ok": True, "names": any_names})
        elif name == "status":
            with lock:
                now = time.time()
                self._reply(200, {"active": {n: max(0, round(e - now)) for n, e in active.items()},
                                  "discord": discord_status["state"], "bettertok": bettertok_status["state"]})
        elif name in ACTIVATE_ROUTES:
            # BetterTok webhooks always send a JSON body, and only gift events name a gift. So a body
            # without a gift is a follow, share or likes goal: it fires the effect but doesn't fill the
            # combo meter or count as a top sender. Plain links with no body (TikFinity, the panel) count as before.
            is_gift = not body or bool(gift)
            self._reply(200, {"ok": True, "effect": activate(name, secs, who, gift, counted=is_gift)})
        else:
            self._reply(404, {"routes": ROUTES})

    def _push_overlay(self):
        """Sends the overlay its state whenever it changes (20 times a second at most), plus a heartbeat every
        second so it knows the connection is alive. Ends when the overlay goes away."""
        if self.command == "HEAD":  # a stream never ends, so a HEAD request would hang
            return self._send(200, b"", "text/event-stream")
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        last, beat = None, 0.0
        try:
            self.wfile.write(b"retry: 1000\n\n")
            while True:
                state = json.dumps(overlay_state(), separators=(",", ":"))
                now = time.time()
                if state != last or now - beat >= 1:
                    self.wfile.write(b"data: " + state.encode() + b"\n\n")
                    self.wfile.flush()
                    last, beat = state, now
                time.sleep(OVERLAY_PUSH_GAP)
        except (OSError, ValueError):
            pass  # the overlay closed or reloaded

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        self.body = self.rfile.read(n) if n else b""
        self.do_GET()

    def do_HEAD(self):
        self.do_GET()

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, HEAD, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.send_header("Access-Control-Allow-Private-Network", "true")
        self.end_headers()


# The BetterTok flashbang.py's own browser source, unchanged, so viewers get flashed + hear the ring
FLASH_PAGE_HTML = """<!doctype html><html><head><meta charset="utf-8">
<style>html,body{margin:0;background:transparent;overflow:hidden}
#f{position:fixed;inset:0;background:#fff;opacity:0}</style></head>
<body><div id="f"></div>
<script>
const f=document.getElementById('f');let last=null,token=0;
function flash(){
  const my=++token;
  f.style.transition='none';f.style.opacity=1;
  setTimeout(()=>{ if(my!==token)return;
    f.style.transition='opacity FADEms ease-out';f.style.opacity=0;},HOLD);
}
async function poll(){
  try{
    const r=await fetch('/count',{cache:'no-store'});const j=await r.json();
    if(last===null)last=j.count;
    else if(j.count!==last){last=j.count;flash();}
  }catch(e){}
  setTimeout(poll,120);
}
poll();
</script></body></html>""".replace("FADE", str(round(FLASH_FADE * 1000))).replace("HOLD", str(round(FLASH_HOLD * 1000)))


class FlashbangHandler(Handler):
    """Answers on the BetterTok flashbang.py's port, exactly like it did: /trigger, /count, /ring.wav,
    and its browser source on every other address."""

    def do_GET(self):
        u = urlparse(self.path)
        path = u.path.strip("/").lower()
        if path.startswith("trigger"):
            q = parse_qs(u.query)
            who = (q.get("user") or q.get("nickname") or [""])[0]
            gift = (q.get("gift") or [""])[0]
            activate("flashbang", None, who, gift)
            return self._send(200, b"ok", "text/plain")
        if path.startswith("count"):
            return self._reply(200, {"count": flash["count"]})
        if path.startswith("ring.wav"):
            if not flash["ring"]:
                return self._reply(404, {"error": "no ring sound"})
            with open(flash["ring"], "rb") as f:
                return self._send(200, f.read(), "audio/wav")
        return self._send(200, FLASH_PAGE_HTML.encode(), "text/html")


def hook_thread(ready, result):
    HOOKPROC = ctypes.WINFUNCTYPE(ctypes.c_ssize_t, ctypes.c_int, wt.WPARAM, wt.LPARAM)
    user32.SetWindowsHookExW.argtypes = [ctypes.c_int, HOOKPROC, wt.HINSTANCE, wt.DWORD]
    user32.SetWindowsHookExW.restype = ctypes.c_void_p
    user32.CallNextHookEx.argtypes = [ctypes.c_void_p, ctypes.c_int, wt.WPARAM, wt.LPARAM]
    user32.CallNextHookEx.restype = ctypes.c_ssize_t
    user32.CreateWindowExW.argtypes = [wt.DWORD, wt.LPCWSTR, wt.LPCWSTR, wt.DWORD, ctypes.c_int, ctypes.c_int,
                                       ctypes.c_int, ctypes.c_int, wt.HWND, wt.HMENU, wt.HINSTANCE, wt.LPVOID]
    user32.CreateWindowExW.restype = wt.HWND
    user32.GetRawInputData.argtypes = [wt.HANDLE, wt.UINT, wt.LPVOID, ctypes.POINTER(wt.UINT), wt.UINT]
    user32.GetRawInputData.restype = wt.UINT
    user32.RegisterRawInputDevices.argtypes = [ctypes.POINTER(RAWINPUTDEVICE), wt.UINT, wt.UINT]
    kernel32 = ctypes.windll.kernel32
    kernel32.GetModuleHandleW.restype = wt.HMODULE

    def proc(nCode, wParam, lParam):
        if nCode == 0:
            try:
                k = KBDLLHOOKSTRUCT.from_address(lParam)
                if handle_key(k.scanCode, wParam in (0x100, 0x104), k.flags, k.dwExtraInfo):
                    return 1
            except Exception:
                traceback.print_exc()
        return user32.CallNextHookEx(None, nCode, wParam, lParam)

    def mproc(nCode, wParam, lParam):
        # mouse moves skip straight through
        if nCode == 0 and wParam in (WM_LBUTTONDOWN, WM_LBUTTONUP, WM_RBUTTONDOWN, WM_RBUTTONUP, WM_MOUSEWHEEL):
            try:
                m = MSLLHOOKSTRUCT.from_address(lParam)
                if handle_mouse(wParam, m.flags, m.dwExtraInfo):
                    return 1
            except Exception:
                traceback.print_exc()
        return user32.CallNextHookEx(None, nCode, wParam, lParam)

    callback = HOOKPROC(proc)  # keep references so they aren't garbage collected
    mcallback = HOOKPROC(mproc)
    module = kernel32.GetModuleHandleW(None)
    result["hook"] = user32.SetWindowsHookExW(13, callback, module, 0)
    msg = wt.MSG()
    user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, 0)  # create the message queue
    # hidden window that receives raw mouse movement (only registered while a mouse effect runs)
    raw_hwnd = user32.CreateWindowExW(0x80, "STATIC", "Fortnite Chaos raw input", 0x80000000,
                                      0, 0, 0, 0, None, None, module, None)
    hook_thread_id["id"] = kernel32.GetCurrentThreadId()
    ready.set()
    if not result["hook"]:
        return
    user32.UnhookWindowsHookEx.argtypes = [ctypes.c_void_p]
    mouse_hook = None
    raw_on = False
    raw_buf = RAWINPUT()
    raw_size = wt.UINT()
    header_size = ctypes.sizeof(RAWINPUTHEADER)
    # hooks need a message loop on their own thread
    while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
        if msg.message == WM_APP_MOUSEHOOK:
            want_hook, want_raw = bool(msg.wParam & 1), bool(msg.wParam & 2)
            if want_hook and not mouse_hook:
                mouse_hook = user32.SetWindowsHookExW(14, mcallback, module, 0)
                if not mouse_hook:
                    log("WARNING: could not install mouse hook, mouse button effects won't work")
            elif not want_hook and mouse_hook:
                user32.UnhookWindowsHookEx(mouse_hook)
                mouse_hook = None
            if want_raw != raw_on and raw_hwnd:
                dev = RAWINPUTDEVICE(1, 2, 0x100 if want_raw else 0x1, raw_hwnd if want_raw else None)
                if user32.RegisterRawInputDevices(ctypes.byref(dev), 1, ctypes.sizeof(dev)):
                    raw_on = want_raw
                else:
                    log("WARNING: could not read raw mouse, inverted mouse / sensitivity won't work")
            continue
        if msg.message == WM_INPUT and raw_on:
            try:
                raw_size.value = ctypes.sizeof(raw_buf)
                if user32.GetRawInputData(msg.lParam, 0x10000003, ctypes.byref(raw_buf), ctypes.byref(raw_size),
                                          header_size) != 0xFFFFFFFF:
                    m = raw_buf.mouse
                    # real mice only: skip our own injected moves and absolute devices (tablets)
                    if raw_buf.header.dwType == 0 and raw_buf.header.hDevice and m.ulExtraInformation != MAGIC \
                            and not m.usFlags & 1 and (m.lLastX or m.lLastY):
                        handle_raw_move(m.lLastX, m.lLastY)
            except Exception:
                traceback.print_exc()
        user32.TranslateMessage(ctypes.byref(msg))
        user32.DispatchMessageW(ctypes.byref(msg))


def run_popups():
    """Shows the click-through banner and the screen effects. Runs on the main thread."""
    import tkinter as tk

    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass

    root = tk.Tk()
    root.withdraw()
    sw, sh = user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)

    user32.SetWindowPos.argtypes = [wt.HWND, wt.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                    wt.UINT]

    def click_through(w):
        """So overlays never steal clicks OR keyboard focus from your game. Returns the window handle,
        hidden - show it with show(), never with Tk's deiconify()/lift(), which focus the window and
        alt-tab you out of Fortnite."""
        w.update_idletasks()
        hwnd = user32.GetParent(w.winfo_id()) or w.winfo_id()
        style = user32.GetWindowLongW(hwnd, -20)
        # layered | transparent | toolwindow | noactivate
        user32.SetWindowLongW(hwnd, -20, style | 0x80000 | 0x20 | 0x80 | 0x08000000)
        user32.ShowWindow(hwnd, 0)
        return hwnd

    def show(hwnd):
        user32.ShowWindow(hwnd, 4)  # SW_SHOWNOACTIVATE
        # HWND_TOPMOST, with SWP_NOSIZE | SWP_NOMOVE | SWP_NOACTIVATE | SWP_SHOWWINDOW
        user32.SetWindowPos(hwnd, -1, 0, 0, 0, 0, 0x0001 | 0x0002 | 0x0010 | 0x0040)

    def hide(hwnd):
        user32.ShowWindow(hwnd, 0)

    def overlay_window(bg, key=None):
        w = tk.Toplevel(root)
        w.overrideredirect(True)
        w.configure(bg=bg)
        w.geometry(f"{sw}x{sh}+0+0")  # main monitor only
        w.attributes("-topmost", True)
        w.attributes("-alpha", 0.0)  # invisible while it is set up
        if key:
            w.attributes("-transparentcolor", key)
        return w

    win = tk.Toplevel(root)
    win.overrideredirect(True)
    win.configure(bg="#111111")
    win.attributes("-topmost", True)
    win.attributes("-alpha", 0.93)
    head = tk.Label(win, text="", font=("Segoe UI", 26, "bold"), fg="#ffffff", bg="#111111")
    head.pack(padx=40, pady=(16, 0))
    detail = tk.Label(win, text="", font=("Segoe UI", 16), fg="#ffcf40", bg="#111111")
    detail.pack(padx=40, pady=(2, 16))
    banner = click_through(win)

    scare_img = None
    path = _find_file("jumpscare.png")
    if path:
        try:
            img = tk.PhotoImage(file=path)
            zoom = max(1, min(sw // img.width(), sh // img.height()))
            shrink = max(1, -(-img.width() // sw), -(-img.height() // sh))
            scare_img = img.zoom(zoom) if zoom > 1 else img.subsample(shrink)
        except Exception:
            log("WARNING: couldn't load jumpscare.png")
    sound = _find_file("jumpscare.wav")
    heartbeat = _find_file("heartbeat.mp3")
    creeper_sound = _find_file("creeper.wav") or flash["creeper"]

    # Every screen effect gets its window made once, here, and is only shown/hidden after that.
    # (Making a new Tk window while you play would focus it and alt-tab you out of the game.)
    KEY = "#ff00ff"  # this colour is see-through in the windows that use it
    wins = {n: overlay_window(bg, key) for n, bg, key in (
        ("blind", "#000000", KEY), ("fog", "#ffffff", None),
        ("flashbang", "#ffffff", None), ("jumpscare", "#000000", None),
        ("fakeban", "#0b0b12", None), ("bsod", "#0078d7", None), ("blink", KEY, KEY),
        ("lowhp", "#b00000", KEY), ("lowhp2", "#b00000", KEY), ("lowhp3", "#b00000", KEY),
        ("creeper", KEY, KEY), ("creeper_face", KEY, KEY))}
    c = tk.Canvas(wins["blind"], width=sw, height=sh, bg="#000000", highlightthickness=0)
    c.pack()
    r = sh * BLIND_HOLE
    c.create_oval(sw / 2 - r, sh / 2 - r, sw / 2 + r, sh / 2 + r, fill="#ff00ff", outline="#ff00ff")
    if scare_img:
        tk.Label(wins["jumpscare"], image=scare_img, bg="#000000").place(relx=0.5, rely=0.5, anchor="center")
    else:
        tk.Label(wins["jumpscare"], text="BOO!", font=("Segoe UI", 200, "bold"), fg="#ff0000",
                 bg="#000000").place(relx=0.5, rely=0.5, anchor="center")

    # Fake ban: laid out like Fortnite's error box. Sizes are pixels on a 1080p screen, scaled by u.
    ban = tk.Canvas(wins["fakeban"], width=sw, height=sh, bg="#14507f", highlightthickness=0)
    ban.pack()
    ban_img = None
    path = _find_file("fakeban_bg.png")
    if path:
        try:
            ban_img = tk.PhotoImage(file=path)
            ban_img = ban_img.zoom(max(1, math.ceil(sw / ban_img.width())))
            ban.create_image(sw / 2, sh / 2, image=ban_img)
        except Exception:
            log("WARNING: couldn't load fakeban_bg.png")
    u, mid = sh / 1080, sw / 2
    ban.create_oval(mid - 29 * u, 324 * u, mid + 29 * u, 382 * u, fill="#f03c16", outline="")
    ban.create_text(mid, 353 * u, text="!", font=("Impact", -int(46 * u)), fill="#ffffff")
    ban.create_text(mid, 422 * u, text=FAKE_BAN_TITLE, font=("Impact", -int(62 * u), "italic"), fill="#ffffff")
    for y in (470, 627):
        ban.create_polygon(mid - 536 * u, (y + 2) * u, mid + 537 * u, (y - 2) * u, mid + 530 * u, (y + 11) * u,
                           mid - 528 * u, (y + 13) * u, fill="#1763e6", outline="")
    ban.create_text(mid, 552 * u, text=FAKE_BAN_TEXT, font=("Segoe UI", -int(29 * u), "bold"), fill="#86d4ff",
                    justify="center")
    ban.create_rectangle(mid - 96 * u, 660 * u, mid + 96 * u, 716 * u, fill="#e2d900", outline="")
    ban.create_text(mid, 688 * u, text="CONTINUE", font=("Impact", -int(32 * u)), fill="#14202c")
    ban_by = ban.create_text(mid, 760 * u, text="", font=("Segoe UI", -int(24 * u), "bold"), fill="#86d4ff")

    # Fake blue screen
    bs = tk.Frame(wins["bsod"], bg="#0078d7")
    bs.place(x=int(sw * .14), y=int(sh * .16))
    for text, font in ((":(", ("Segoe UI Light", int(sh * .11))),
                       ("Your PC ran into a problem and needs to restart. We're just\ncollecting some error info, "
                        "and then we'll restart for you.", ("Segoe UI", int(sh * .023))),
                       ("20% complete", ("Segoe UI", int(sh * .023))),
                       ("Stop code: TOO_MANY_GIFTS", ("Segoe UI", int(sh * .013)))):
        bsod_code = tk.Label(bs, text=text, font=font, fg="#ffffff", bg="#0078d7", justify="left")
        bsod_code.pack(anchor="w", pady=int(sh * .018))  # the last one made is the stop code

    # Eyelids: two black shapes, moved only while blinking
    lids = tk.Canvas(wins["blink"], width=sw, height=sh, bg=KEY, highlightthickness=0)
    lids.pack()
    lid_t = lids.create_polygon(0, 0, 0, 0, 0, 0, fill="#000000")
    lid_b = lids.create_polygon(0, 0, 0, 0, 0, 0, fill="#000000")

    def set_lids(a):
        top, bottom = [0, 0, sw, 0], [0, sh, sw, sh]
        for i in range(16, -1, -1):
            x = sw * i / 16
            y = a * sh * .55 * (1 + .45 * (2 * i / 16 - 1) ** 2)
            top += [x, y]
            bottom += [x, sh - y]
        lids.coords(lid_t, *top)
        lids.coords(lid_b, *bottom)

    # Low HP: three red layers, each with a smaller hole, so the edges get redder the further out you look
    for n, size in (("lowhp", 0.62), ("lowhp2", 0.74), ("lowhp3", 0.88)):
        rim = tk.Canvas(wins[n], width=sw, height=sh, bg="#b00000", highlightthickness=0)
        rim.pack()
        rim.create_oval(sw / 2 - sw * size / 2, sh / 2 - sh * size / 2, sw / 2 + sw * size / 2, sh / 2 + sh * size / 2,
                        fill=KEY, outline=KEY)

    # Creeper: face first, then a crater (redrawn each time so no two holes match)
    face = tk.Canvas(wins["creeper_face"], width=sw, height=sh, bg=KEY, highlightthickness=0)
    face.pack()
    px = int(sh * .7 / 8)
    fx0, fy0 = (sw - px * 8) // 2, (sh - px * 8) // 2
    for j, row in enumerate(("GGLGGDGG", "GLGDGGLG", "GKKGGKKD", "DKKGLKKG", "GGDKKGGL", "LGKKKKGG", "GGKKKKDG",
                             "GDKGGKGL")):
        for i, ch in enumerate(row):
            face.create_rectangle(fx0 + i * px, fy0 + j * px, fx0 + (i + 1) * px, fy0 + (j + 1) * px, outline="",
                                  fill={"G": "#4fa63c", "L": "#6cc24a", "D": "#3b8430", "K": "#111111"}[ch])
    fuse_flash = face.create_rectangle(fx0, fy0, fx0 + px * 8, fy0 + px * 8, fill="#ffffff", outline="", state="hidden")
    blast = face.create_rectangle(0, 0, sw, sh, fill="#ffffff", outline="", state="hidden")
    crater = tk.Canvas(wins["creeper"], width=sw, height=sh, bg=KEY, highlightthickness=0)
    crater.pack()

    def draw_crater(who=""):
        crater.delete("all")
        b = sh // 18 + 1
        r = sh * CREEPER_HOLE
        char, dirt = ("#1e1a17", "#2a241f", "#3a332d"), ("#5b3d23", "#6f4c2c", "#7d5a36", "#4a4a4a")
        for j in range(-1, sh // b + 2):
            for i in range(-1, sw // b + 2):
                d = math.hypot(i * b + b / 2 - sw / 2, j * b + b / 2 - sh / 2) + random.uniform(-.8, .8) * b
                colour = None
                if d < r:
                    colour = "#000000"
                elif d < r + b * 1.3:
                    colour = random.choice(char)
                elif d < r + b * 2.8:
                    colour = random.choice(dirt) if random.random() < .72 else None
                elif d < r + b * 5 and random.random() < .14:
                    colour = random.choice(dirt)
                if colour:
                    crater.create_rectangle(i * b, j * b, (i + 1) * b, (j + 1) * b, fill=colour, outline="")
        if who:
            crater.create_text(sw / 2, sh / 2, text=f"{who.upper()} WAS HERE", fill="#ffffff",
                               font=("Impact", -int(sh * .07)))

    hwnds = {n: click_through(w) for n, w in wins.items()}
    for n in ("blind", "jumpscare", "fakeban", "bsod", "blink", "creeper", "creeper_face"):
        wins[n].attributes("-alpha", 1.0)
    EXTRA_WINDOWS = {"lowhp": ("lowhp2", "lowhp3"), "creeper": ("creeper_face",)}

    state = {"hide_at": 0.0, "heart_at": 0.0, "creeper_stage": ""}
    screens = {}  # effect name -> start data while it is on screen

    mci = ctypes.windll.winmm.mciSendStringW

    def play(path):
        """Plays a sound without waiting for it to finish. Uses Windows' media player engine
        (the same kind the jumpscare bot uses) - the basic winsound player fails on this PC."""
        if not path:
            return
        alias = {sound: "scare", heartbeat: "heart", creeper_sound: "creeper"}.get(path, "ring")
        mci(f"close {alias}", None, 0, None)  # a new one cuts off the last one
        if mci(f'open "{path}" type mpegvideo alias {alias}', None, 0, None) == 0:
            mci(f"play {alias}", None, 0, None)
            return
        try:
            import winsound
            winsound.PlaySound(path, winsound.SND_FILENAME | winsound.SND_ASYNC)
        except Exception:
            log(f"WARNING: couldn't play {os.path.basename(path)}")

    def start_screen(name, info=None):
        who = (info or {}).get("who", "")
        if name == "fakeban":
            ban.itemconfig(ban_by, text=f"Banned by: {who}" if who else "")
        elif name == "bsod":
            bsod_code.config(text=f"Stop code: {_stop_code(who)}")
        if name == "jumpscare":
            play(sound)
        elif name == "lowhp":
            play(heartbeat)
            state["heart_at"] = time.time()
        elif name == "creeper":
            play(creeper_sound)
            draw_crater(who)
            face.itemconfig(blast, state="hidden")
            face.itemconfig(fuse_flash, state="hidden")
            state["creeper_stage"] = "fuse"
            show(hwnds["creeper_face"])
            return  # the hole only appears when it blows
        show(hwnds[name])
        for extra in EXTRA_WINDOWS.get(name, ()):
            show(hwnds[extra])

    def stop_screen(name):
        hide(hwnds[name])
        for extra in EXTRA_WINDOWS.get(name, ()):
            hide(hwnds[extra])
        if name == "lowhp":
            mci("close heart", None, 0, None)

    def update_creeper(elapsed):
        if elapsed < CREEPER_FUSE:
            face.itemconfig(fuse_flash, state="normal" if elapsed > CREEPER_FUSE * .45 and int(elapsed * 8) % 2 else "hidden")
        elif elapsed < CREEPER_FUSE + CREEPER_BLAST:
            if state["creeper_stage"] == "fuse":
                state["creeper_stage"] = "blast"
                face.itemconfig(blast, state="normal")
        elif state["creeper_stage"] != "hole":
            state["creeper_stage"] = "hole"
            hide(hwnds["creeper_face"])
            show(hwnds["creeper"])

    def update_lowhp(elapsed):
        pulse = lowhp_pulse(elapsed)
        for n in ("lowhp", "lowhp2", "lowhp3"):
            wins[n].attributes("-alpha", .08 + .2 * pulse)
        if heartbeat and time.time() - state["heart_at"] >= LOWHP_SOUND_LENGTH:
            state["heart_at"] = time.time()
            play(heartbeat)

    def poll():
        try:
            while True:
                h, d = popups.get_nowait()
                head.config(text=h)
                detail.config(text=d)
                win.update_idletasks()
                x = (sw - win.winfo_reqwidth()) // 2
                win.geometry(f"+{x}+40")
                show(banner)
                state["hide_at"] = time.time() + POPUP_SECONDS
        except queue.Empty:
            pass
        if state["hide_at"] and time.time() >= state["hide_at"]:
            hide(banner)
            state["hide_at"] = 0.0
        try:
            with lock:
                now = time.time()
                want = {n: (data.get(n), active[n] - now) for n in SCREEN & set(active)}
                flash_total = totals.get("flashbang", 1)
                spent = {n: totals[n] - (active[n] - now) for n in ("blink", "lowhp", "creeper") if n in active}
            for n in list(screens):
                if n not in want:
                    stop_screen(n)
                    del screens[n]
            new = False
            for n, (started, left) in want.items():
                if n == "fog":
                    wins[n].attributes("-alpha", min(0.85, max(0.0, left / 2 * 0.85)))
                elif n == "flashbang":
                    wins[n].attributes("-alpha", flash_alpha(left, flash_total))
                elif n == "blink":
                    set_lids(blink_amount(spent[n]))
                elif n == "lowhp":
                    update_lowhp(spent[n])
                if n not in screens or screens[n] is not started:  # new, or restarted
                    start_screen(n, started)
                    screens[n] = started
                    new = True
                if n == "creeper":
                    update_creeper(spent[n])
            if new and state["hide_at"]:
                show(banner)  # keep the banner above the effects
        except Exception:
            traceback.print_exc()
        root.after(30 if screens.keys() & {"flashbang", "blink", "creeper"} else 50, poll)

    poll()
    root.mainloop()


def main():
    if os.name != "nt":
        raise SystemExit("This script only works on Windows.")

    threading.Thread(target=_log_writer, daemon=True).start()
    try:  # turn off QuickEdit: clicking inside the console window can otherwise freeze output
        k32 = ctypes.windll.kernel32
        h = k32.GetStdHandle(-10)
        mode = wt.DWORD()
        if k32.GetConsoleMode(h, ctypes.byref(mode)):
            k32.SetConsoleMode(h, (mode.value & ~0x0040) | 0x0080)
    except Exception:
        pass

    # Refuse to start if another copy is already running (two copies cancel each other's
    # key remaps, and the old copy would silently keep receiving the webhooks).
    try:
        server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    except OSError:
        print(f"\nERROR: another copy of Fortnite Chaos is already running (port {PORT} is taken).")
        print("Close the other window, or run:  taskkill /f /im python.exe   then start this again.")
        input("\nPress Enter to close...")
        raise SystemExit(ALREADY_RUNNING)

    try:  # asks first, and says nothing if there's no update or no internet
        import updater
        print(f"Fortnite Chaos {updater.local_version()}")
        if updater.check_and_prompt():
            server.server_close()
            if "--child" in sys.argv:
                raise SystemExit(RESTART_CODE)  # the restarter opens the new version in this window
            updater.restart(os.path.abspath(__file__))
            return
    except Exception as e:
        print(f"Update check skipped: {e}")

    try:
        flash["ring"] = make_ring()
    except Exception:
        log("WARNING: couldn't make the flashbang sound")
    try:
        flash["creeper"] = make_creeper_sound()
    except Exception:
        flash["creeper"] = None
        log("WARNING: couldn't make the creeper sound")
    _load_gift_files()

    ready, result = threading.Event(), {}
    threading.Thread(target=hook_thread, args=(ready, result), daemon=True).start()
    ready.wait(5)
    if not result.get("hook"):
        raise SystemExit("Could not install keyboard hook.")

    threading.Thread(target=watcher, daemon=True).start()
    threading.Thread(target=focus_watcher, daemon=True).start()
    threading.Thread(target=memory_watcher, daemon=True).start()
    threading.Thread(target=discord_bot, daemon=True).start()
    threading.Thread(target=bettertok_events, daemon=True).start()
    threading.Thread(target=vote_loop, daemon=True).start()
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        flash_server = ThreadingHTTPServer(("127.0.0.1", FLASHBANG_PORT), FlashbangHandler)
        threading.Thread(target=flash_server.serve_forever, daemon=True).start()
    except OSError:
        print(f"WARNING: port {FLASHBANG_PORT} is taken - close flashbang.py so its links come here.")
    else:
        print(f"  flashbang browser source (same as flashbang.py): http://localhost:{FLASHBANG_PORT}/")
    print(f"Fortnite Chaos ready on http://127.0.0.1:{PORT}/")
    print("  effects: " + ", ".join(ROUTES))
    print(f"  viewer overlay (LIVE Studio Link source): http://127.0.0.1:{PORT}/overlay.html")
    print(f"  test panel (open in a browser): http://127.0.0.1:{PORT}/panel.html")
    if not _find_file("jumpscare.png"):
        print("  note: no jumpscare.png found, /jumpscare will show BOO! instead")
    wav = _find_file("jumpscare.wav")
    print(f"  jumpscare sound: {wav}" if wav else "  note: no jumpscare.wav found, /jumpscare will be silent")
    print(f"  heartbeat sound: {_find_file('heartbeat.mp3') or 'not found, /lowhp will be silent'}")
    print(f"  gift pictures found: {len(_gift_files)}")
    print("Panic key: F8 restores your controls (and mouse) instantly.")
    if "--restarted" in sys.argv:
        announce("Fortnite Chaos restarted", "It crashed and came straight back")
        print("NOTE: restarted after a crash - the error is above.")

    try:
        run_popups()
    finally:
        clear("closing")


def supervise():
    """Runs Fortnite Chaos and starts it again if it crashes. Closing the window still closes everything."""
    if os.name != "nt" or "--child" in sys.argv:
        return main()
    crashes, restarted = [], False
    while True:
        try:
            code = subprocess.call([sys.executable, os.path.abspath(__file__), "--child"] +
                                   (["--restarted"] if restarted else []), cwd=HERE)
        except KeyboardInterrupt:
            return
        if code in (0, ALREADY_RUNNING):
            return
        if code == RESTART_CODE:  # updated: open the new version
            restarted = False
            continue
        now = time.time()
        crashes = [t for t in crashes if now - t < 120] + [now]
        if len(crashes) > 5:
            print("\nFortnite Chaos crashed 5 times in 2 minutes, so it won't restart again. The error is above.")
            input("Press Enter to close...")
            return
        print(f"\nFortnite Chaos stopped unexpectedly (code {code}). Restarting in 2 seconds...")
        time.sleep(2)
        restarted = True


if __name__ == "__main__":
    supervise()

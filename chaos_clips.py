"""
Chaos Clips - cuts the best moments of your last stream into vertical clips, ready to edit.

Reads the gift log Fortnite Chaos writes (Stream Reports\\events-<date>.csv), finds your recording of the
stream, and saves one clip per moment to the clips folder in config.json. It only reads your recording: it
never changes or deletes it.

Run:  py -3 chaos_clips.py                  (most recent stream, best 10 moments)
      py -3 chaos_clips.py 2026-11-05       (the stream that started on that day)
      py -3 chaos_clips.py --top 20         (more clips)
      py -3 chaos_clips.py --dry-run        (just list the moments, cut nothing)
      py -3 chaos_clips.py --shift 2.5      (clips start too early? cut 2.5s later. Too late? use -2.5)

You need to have recorded the stream (the record button in LIVE Studio).
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timedelta

import stream_config
import stream_report

# ---------------- settings ----------------
BEFORE = 8        # seconds of clip before the gift lands, for the build-up
AFTER = 3         # seconds of clip after the effect ends
MAX_CLIP = 60     # a clip never runs longer than this
TOP = 10          # how many clips to make
# How good a moment is. A moment's score is its best effect, plus 1 for every extra gift in it.
WEIGHTS = {"jumpscare": 5, "flashbang": 4, "chaos": 4, "emote": 3, "spin": 3, "lookdown": 3, "lookup": 3}
DEFAULT_WEIGHT = 2

HOME = os.path.expanduser("~")
OUT_DIR = stream_config.folder("clips_folder", "Clips")
SEARCH = [os.path.join(HOME, "Videos")] + stream_config.folders("recordings_folders")  # top level only
VIDEO = (".mp4", ".mkv", ".mov", ".flv")
LIVE_STUDIO_SETTINGS = os.path.join(os.environ.get("APPDATA", ""), "TikTok LIVE Studio", "TTStore", "services.json")
# ------------------------------------------


def find_tool(name):
    """ffmpeg/ffprobe: on the PATH, or where winget put them (a window opened before the install can't see the PATH)."""
    path = shutil.which(name)
    if path:
        return path
    path = os.path.join(os.environ.get("LOCALAPPDATA", ""), "Microsoft", "WinGet", "Links", name + ".exe")
    return path if os.path.exists(path) else None


def probe(ffprobe, path):
    """(duration seconds, width, height) of a video, or None if it can't be read (e.g. still being written)."""
    r = subprocess.run([ffprobe, "-v", "error", "-select_streams", "v:0", "-show_entries",
                        "stream=width,height:format=duration", "-of", "json", path],
                       capture_output=True, text=True, encoding="utf-8", errors="ignore")
    try:
        info = json.loads(r.stdout)
        stream = info["streams"][0]
        return float(info["format"]["duration"]), int(stream["width"]), int(stream["height"])
    except (ValueError, KeyError, IndexError):
        return None


def started_at(path, duration):
    """When a recording started: from its name if that has the time in it, else from when it finished saving."""
    name = os.path.basename(path)
    m = re.search(r"(?<!\d)(\d{12})(?!\d)", name)  # LIVE Studio: FORTNITE+CHILL_260426150431.mp4
    if m:
        try:
            return datetime.strptime(m.group(1), "%y%m%d%H%M%S")
        except ValueError:
            pass
    m = re.search(r"(\d{4}-\d\d-\d\d)[ _](\d\d)-(\d\d)-(\d\d)", name)  # OBS: 2026-10-15 13-50-43.mp4
    if m:
        try:
            return datetime.strptime(" ".join(m.groups()), "%Y-%m-%d %H %M %S")
        except ValueError:
            pass
    return datetime.fromtimestamp(os.path.getmtime(path)) - timedelta(seconds=duration)


def search_folders():
    folders = list(SEARCH)
    try:  # plus wherever LIVE Studio is set to record to
        with open(LIVE_STUDIO_SETTINGS, encoding="utf-8", errors="ignore") as f:
            m = re.search(r'"recordFolder":\s*("(?:[^"\\]|\\.)*")', f.read())
        if m:
            folders.append(json.loads(m.group(1)))
    except (OSError, ValueError):
        pass
    seen, out = set(), []
    for d in folders:
        key = os.path.normcase(os.path.abspath(d))
        if key not in seen and os.path.isdir(d):
            seen.add(key)
            out.append(d)
    return out


def find_recordings(ffprobe, t0, t1):
    """Every video that overlaps t0-t1: [{path, start, end, w, h, size}]. Cheap checks first, probing is slow."""
    found = []
    for folder in search_folders():
        for name in os.listdir(folder):
            path = os.path.join(folder, name)
            if not name.lower().endswith(VIDEO) or not os.path.isfile(path):
                continue
            if datetime.fromtimestamp(os.path.getmtime(path)) < t0:  # finished saving before the stream began
                continue
            info = probe(ffprobe, path)
            if not info:
                continue
            duration, w, h = info
            start = started_at(path, duration)
            end = start + timedelta(seconds=duration)
            if start < t1 and end > t0:
                found.append({"path": path, "start": start, "end": end, "w": w, "h": h, "size": os.path.getsize(path)})
    return found


def effect_weight(effect):
    return WEIGHTS.get(effect.split(":")[0], DEFAULT_WEIGHT)


def build_moments(events):
    """Gifts close enough to overlap become one moment. Returns [{start, end, events, score}] in time order."""
    moments = []
    for e in sorted(events, key=lambda e: e["t"]):
        start = e["t"] - timedelta(seconds=BEFORE)
        end = e["t"] + timedelta(seconds=e["seconds"] + AFTER)
        if moments and start <= moments[-1]["end"]:
            moments[-1]["end"] = max(moments[-1]["end"], end)
            moments[-1]["events"].append(e)
        else:
            moments.append({"start": start, "end": end, "events": [e]})
    for m in moments:
        m["end"] = min(m["end"], m["start"] + timedelta(seconds=MAX_CLIP))
        m["events"] = [e for e in m["events"] if e["t"] < m["end"]]  # ones past the cut-off aren't in the clip
        m["score"] = max(effect_weight(e["effect"]) for e in m["events"]) + len(m["events"]) - 1
    return moments


def pick_top(moments, top):
    """The best moments (earliest wins a tie), back in time order."""
    best = sorted(moments, key=lambda m: (-m["score"], m["start"]))[:top]
    return sorted(best, key=lambda m: m["start"])


def pick_recording(recordings, m):
    """The recording for this moment: one that has all of it first, then vertical, then the biggest."""
    def has_part(r):
        return r["start"] < m["end"] and r["end"] > m["start"]

    def rank(r):
        return (r["start"] <= m["start"] and r["end"] >= m["end"], r["h"] > r["w"], r["size"])

    options = [r for r in recordings if has_part(r)]
    return max(options, key=rank) if options else None


def clean_name(text, limit=40):
    text = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", text or "").strip(" .")
    return text[:limit].strip(" .")


def clip_name(m):
    best = max(m["events"], key=lambda e: effect_weight(e["effect"]))
    effect = best["effect"].replace("chaos:", "chaos ").replace("+", " ")
    parts = [f"{m['start']:%Y-%m-%d %H%M}", clean_name(best["who"]) or "Someone"]
    if best["gift"]:
        parts.append(clean_name(best["gift"]))
    parts.append(effect)
    return " - ".join(p for p in parts if p) + ".mp4"


def describe(m):
    gifts = ", ".join(f"{e['who'] or 'Someone'}: {e['effect']}" for e in m["events"][:4])
    more = f" (+{len(m['events']) - 4} more)" if len(m["events"]) > 4 else ""
    return f"{m['start']:%I:%M:%S %p}  {(m['end'] - m['start']).total_seconds():>3.0f}s  score {m['score']:>2}  {gifts}{more}"


def cut(ffmpeg, rec, m, out, shift=0.0):
    """Saves one clip. Landscape recordings get the middle cropped out to 9:16. Returns True if it worked."""
    start = max(m["start"], rec["start"])
    end = min(m["end"], rec["end"])
    offset = max(0.0, (start - rec["start"]).total_seconds() + shift)
    length = (end - start).total_seconds()
    vf = ["-vf", "crop=trunc(ih*9/16/2)*2:ih,scale=1080:1920"] if rec["w"] > rec["h"] else []
    tmp = out + ".part.mp4"  # so a clip that fails halfway never looks finished
    for encoder in (["-c:v", "h264_nvenc", "-preset", "p5", "-cq", "21"],
                    ["-c:v", "libx264", "-preset", "veryfast", "-crf", "20"]):
        r = subprocess.run([ffmpeg, "-y", "-v", "error", "-ss", f"{offset:.3f}", "-i", rec["path"], "-t", f"{length:.3f}"]
                           + vf + encoder + ["-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", tmp],
                           capture_output=True, text=True, encoding="utf-8", errors="ignore")
        if r.returncode == 0:
            os.replace(tmp, out)
            return True
    if os.path.exists(tmp):
        os.remove(tmp)
    print("    ffmpeg:", (r.stderr or "").strip()[-300:])
    return False


def make_clips(start, end, top=TOP, dry_run=False, shift=0.0):
    """Returns how many clips it saved, or None if it stopped early."""
    print(f"Stream: {start:%A %d %B %Y}, {start:%I:%M %p} to {end:%I:%M %p}")
    events = stream_report.read_events(start, end)
    if not events:
        print("No gifts logged for this stream, so there's nothing to clip (the gift log started on 5 Nov 2026).")
        return None
    moments = build_moments(events)
    chosen = pick_top(moments, top)
    print(f"{len(events)} gifts, {len(moments)} moments, best {len(chosen)}:")
    for m in chosen:
        print("  " + describe(m))
    if dry_run:
        return 0
    ffmpeg, ffprobe = find_tool("ffmpeg"), find_tool("ffprobe")
    if not ffmpeg or not ffprobe:
        print("ffmpeg isn't installed. Run:  winget install -e --id Gyan.FFmpeg")
        return None
    recordings = find_recordings(ffprobe, start, end)
    if not recordings:
        print("\nNo recording of this stream found - hit record in LIVE Studio next time. Looked in:")
        for d in search_folders():
            print("  " + d)
        return None
    print("\nRecording(s):")
    for r in recordings:
        print(f"  {r['path']}  ({r['w']}x{r['h']}, {r['size'] / 1024 ** 3:.1f} GB)")
    os.makedirs(OUT_DIR, exist_ok=True)
    saved = 0
    for m in chosen:
        rec = pick_recording(recordings, m)
        name = clip_name(m)
        out = os.path.join(OUT_DIR, name)
        if not rec:
            print(f"  not recorded: {name}")
        elif os.path.exists(out):
            print(f"  already there: {name}")
        elif cut(ffmpeg, rec, m, out, shift):
            saved += 1
            print(f"  saved: {name}")
        else:
            print(f"  FAILED: {name}")
    print(f"\n{saved} clip(s) saved to {OUT_DIR}")
    return saved


def main():
    sys.stdout.reconfigure(errors="replace")  # gifter names with emoji must never crash the print
    ap = argparse.ArgumentParser(description="Cuts the best moments of a stream into vertical clips.")
    ap.add_argument("day", nargs="?", help="the day the stream started, like 2026-11-05 (default: the latest stream)")
    ap.add_argument("--top", type=int, default=TOP, help="how many clips to make")
    ap.add_argument("--dry-run", action="store_true", help="list the moments, cut nothing")
    ap.add_argument("--shift", type=float, default=0.0, help="seconds to move every cut later (minus for earlier)")
    args = ap.parse_args()
    streams = stream_report.find_streams()
    if args.day:
        streams = [s for s in streams if s[0].strftime("%Y-%m-%d") == args.day]
    if not streams:
        sys.exit(f"No stream started on {args.day}." if args.day else "No streams found in LIVE Studio's logs.")
    start, end = streams[-1]
    make_clips(start, end, args.top, args.dry_run, args.shift)


if __name__ == "__main__":
    main()

"""
Checks GitHub for a newer release when Fortnite Chaos opens, and asks before installing it.

Your config.json, Discord token, logs and anything else not in the release are left alone. Files it
replaces are saved first in "Old versions\\before-update-<version>". If there's no internet or GitHub can't
be reached, it says nothing and Fortnite Chaos opens as normal.

It checks DEFAULT_REPO, which is public, so no account is needed. To use a different repo, set github_repo in
config.json. A private one also needs github_token there, or the GITHUB_TOKEN environment variable, or the
GitHub CLI signed in. Copies that are git checkouts (the ones you develop in) are never updated.

Check by hand:  py -3 updater.py
"""
import ctypes
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
import zipfile
from urllib.parse import urlparse

import stream_config

HERE = stream_config.HERE
API = "https://api.github.com"
DEFAULT_REPO = "Brownie7227/stream-tools-downloads"
TIMEOUT = 4            # seconds to wait for the version check, so a slow connection can't hold up the stream
DOWNLOAD_TIMEOUT = 60
USER_AGENT = "stream-tools-updater"
TOKEN_ERROR_HINT = "Try again later, or download the latest version from GitHub."
# Never replaced, even if one turns up in a release
PROTECTED = {"config.json", "discord_token.txt", "jumpscare-state.json"}
TRUSTED_DOWNLOAD_HOSTS = ("github.com", "githubusercontent.com")


def local_version():
    try:
        with open(os.path.join(HERE, "VERSION"), encoding="utf-8") as f:
            return f.read().strip()
    except OSError:
        return "0.0.0"


def parse_version(text):
    """"v1.2.3" -> (1, 2, 3), or None if it isn't a version number."""
    m = re.fullmatch(r"v?(\d+)\.(\d+)(?:\.(\d+))?", (text or "").strip())
    return tuple(int(n or 0) for n in m.groups()) if m else None


def is_newer(latest, current):
    a, b = parse_version(latest), parse_version(current)
    return bool(a and b and a > b)


def _gh_token():
    try:
        r = subprocess.run(["gh", "auth", "token"], capture_output=True, text=True, timeout=TIMEOUT,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except (OSError, subprocess.SubprocessError):
        return None
    return r.stdout.strip() if r.returncode == 0 and r.stdout.strip() else None


def get_token():
    return stream_config.get("github_token") or os.environ.get("GITHUB_TOKEN") or _gh_token()


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def _trusted_host(url):
    parts = urlparse(url)
    host = (parts.hostname or "").lower()
    return parts.scheme == "https" and any(host == h or host.endswith("." + h) for h in TRUSTED_DOWNLOAD_HOSTS)


def _fetch(url, token, timeout, accept="application/vnd.github+json"):
    """GET a GitHub address. Redirects are followed without the sign-in, which never leaves api.github.com."""
    headers = {"User-Agent": USER_AGENT, "Accept": accept, "X-GitHub-Api-Version": "2022-11-28"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    opener = urllib.request.build_opener(_NoRedirect)
    try:
        with opener.open(urllib.request.Request(url, headers=headers), timeout=timeout) as r:
            return r.read()
    except urllib.error.HTTPError as e:
        if e.code == 401 and token:  # an old or wrong sign-in shouldn't block a public repo
            return _fetch(url, None, timeout, accept)
        if e.code not in (301, 302, 303, 307, 308):
            raise
        location = e.headers.get("Location", "")
    if not _trusted_host(location):
        raise ValueError(f"unexpected download address: {urlparse(location).hostname}")
    with urllib.request.urlopen(urllib.request.Request(location, headers={"User-Agent": USER_AGENT}),
                                timeout=timeout) as r:
        return r.read()


def latest_release(repo, token):
    return json.loads(_fetch(f"{API}/repos/{repo}/releases/latest", token, TIMEOUT).decode("utf-8"))


def _safe_members(zf):
    """(zip name, path inside the release) for each file. GitHub wraps everything in one top folder."""
    found = []
    for info in zf.infolist():
        if info.is_dir():
            continue
        parts = info.filename.replace("\\", "/").split("/")
        if len(parts) < 2 or any(p in ("", ".", "..") or ":" in p for p in parts):
            raise ValueError(f"unsafe path in the download: {info.filename}")
        found.append((info.filename, os.path.join(*parts[1:])))
    return found


def apply_zip(data, dest, version):
    """Install a release zip over dest, saving what it replaces. Returns how many files it installed."""
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        members = [(z, rel) for z, rel in _safe_members(zf) if os.path.basename(rel).lower() not in PROTECTED]
        if not any(rel == "fortnite_chaos.py" for _, rel in members):
            raise ValueError("the download doesn't contain fortnite_chaos.py")
        with tempfile.TemporaryDirectory() as staging:  # unpack everything first, so a bad zip changes nothing
            for zip_name, rel in members:
                path = os.path.join(staging, rel)
                os.makedirs(os.path.dirname(path), exist_ok=True)
                with zf.open(zip_name) as src, open(path, "wb") as out:
                    shutil.copyfileobj(src, out)
            backup = os.path.join(dest, "Old versions", f"before-update-{version}")
            for _, rel in members:
                target = os.path.join(dest, rel)
                if os.path.isfile(target):
                    saved = os.path.join(backup, rel)
                    os.makedirs(os.path.dirname(saved), exist_ok=True)
                    shutil.copy2(target, saved)
            for _, rel in members:
                target = os.path.join(dest, rel)
                os.makedirs(os.path.dirname(target), exist_ok=True)
                shutil.copy2(os.path.join(staging, rel), target + ".new")
                os.replace(target + ".new", target)
    return len(members)


def _box(text, flags):
    """MB_TOPMOST | MB_SETFOREGROUND, so it can't end up hidden behind LIVE Studio."""
    return ctypes.windll.user32.MessageBoxW(0, text, "Fortnite Chaos update", flags | 0x40000 | 0x10000)


def _ask(current, latest, notes):
    text = f"A new version is available.\n\nYours: {current}\nLatest: {latest}"
    if notes:
        text += f"\n\nWhat's new:\n{notes[:600]}"
    return _box(text + "\n\nUpdate now?", 0x4 | 0x20) == 6  # Yes/No with a question mark; 6 = Yes


def check_and_prompt(ask=_ask, tell=lambda text: _box(text, 0x40), dest=HERE):
    """True if an update was installed and the program should restart. Never raises."""
    try:
        if os.path.exists(os.path.join(dest, ".git")):
            return False
        repo = stream_config.get("github_repo", DEFAULT_REPO)
        if not repo:
            return False
        token = get_token()
        current = local_version()
        try:
            release = latest_release(repo, token)
        except (OSError, ValueError):
            return False  # offline, no access or no release yet: open as normal
        latest = release.get("tag_name", "")
        if not is_newer(latest, current) or not ask(current, latest, (release.get("body") or "").strip()):
            return False
    except Exception as e:
        print(f"Update check skipped: {e}")
        return False
    try:
        count = apply_zip(_fetch(release["zipball_url"], token, DOWNLOAD_TIMEOUT), dest, current)
    except Exception as e:
        tell(f"The update didn't install, so you're still on {current}.\n\n{e}\n\n{TOKEN_ERROR_HINT}")
        return False
    print(f"Updated from {current} to {latest} ({count} files).")
    return True


def restart(script):
    """Open the updated program in a new window. The caller exits straight after."""
    subprocess.Popen([sys.executable, script], cwd=HERE, creationflags=getattr(subprocess, "CREATE_NEW_CONSOLE", 0))


def main():
    print(f"This copy: {local_version()}")
    repo = stream_config.get("github_repo", DEFAULT_REPO)
    if os.path.exists(os.path.join(HERE, ".git")):
        print("This is a git checkout, so it won't update itself. Use git pull.")
    try:
        release = latest_release(repo, get_token())
    except urllib.error.HTTPError as e:
        print(f"GitHub said {e.code}. A private repo answers 404 when you aren't signed in or don't have access.")
        return
    except (OSError, ValueError) as e:
        print(f"Couldn't reach GitHub: {e}")
        return
    print(f"Latest on GitHub: {release.get('tag_name')}")
    if check_and_prompt():
        print("Done. Reopen Fortnite Chaos to use it.")


if __name__ == "__main__":
    main()

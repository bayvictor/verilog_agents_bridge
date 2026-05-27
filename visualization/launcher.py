"""Browser detection and launch with user-profile support (Chrome / Firefox)."""

import os
import subprocess
import sys
import webbrowser
from pathlib import Path
from typing import Optional


# ── Chrome / Chromium discovery ──────────────────────────────────────────────

_CHROME_BINS_LINUX = [
    'google-chrome', 'google-chrome-stable',
    'chromium-browser', 'chromium',
    '/usr/bin/google-chrome', '/usr/bin/google-chrome-stable',
    '/usr/bin/chromium-browser', '/usr/bin/chromium',
    '/opt/google/chrome/chrome',
    '/snap/bin/chromium',
]
_CHROME_BINS_MAC = [
    '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    '/Applications/Chromium.app/Contents/MacOS/Chromium',
]
_CHROME_BINS_WIN = [
    r'C:\Program Files\Google\Chrome\Application\chrome.exe',
    r'C:\Program Files (x86)\Google\Chrome\Application\chrome.exe',
    r'C:\Program Files\Chromium\Application\chrome.exe',
]

_FIREFOX_BINS_LINUX = [
    'firefox', 'firefox-esr',
    '/usr/bin/firefox', '/usr/bin/firefox-esr',
    '/snap/bin/firefox',
]
_FIREFOX_BINS_MAC = [
    '/Applications/Firefox.app/Contents/MacOS/firefox',
]
_FIREFOX_BINS_WIN = [
    r'C:\Program Files\Mozilla Firefox\firefox.exe',
    r'C:\Program Files (x86)\Mozilla Firefox\firefox.exe',
]


def _which(name: str) -> Optional[str]:
    """Return full path to binary if found via PATH, else None."""
    try:
        r = subprocess.run(['which', name], capture_output=True, text=True, timeout=3)
        path = r.stdout.strip()
        return path if path else None
    except Exception:
        return None


def _find_binary(candidates: list) -> Optional[str]:
    for c in candidates:
        if os.path.isfile(c) and os.access(c, os.X_OK):
            return c
        found = _which(c)
        if found:
            return found
    return None


def find_chrome() -> Optional[str]:
    if sys.platform == 'linux':
        return _find_binary(_CHROME_BINS_LINUX)
    if sys.platform == 'darwin':
        return _find_binary(_CHROME_BINS_MAC + _CHROME_BINS_LINUX)
    if sys.platform == 'win32':
        return _find_binary(_CHROME_BINS_WIN)
    return None


def find_firefox() -> Optional[str]:
    if sys.platform == 'linux':
        return _find_binary(_FIREFOX_BINS_LINUX)
    if sys.platform == 'darwin':
        return _find_binary(_FIREFOX_BINS_MAC + _FIREFOX_BINS_LINUX)
    if sys.platform == 'win32':
        return _find_binary(_FIREFOX_BINS_WIN)
    return None


# ── Profile detection ────────────────────────────────────────────────────────

def _chrome_user_data_dir() -> Optional[str]:
    """Return the Chrome/Chromium user-data directory if it exists."""
    if sys.platform == 'linux':
        for sub in ('google-chrome', 'chromium', 'chromium-browser'):
            p = Path.home() / '.config' / sub
            if p.is_dir():
                return str(p)
    elif sys.platform == 'darwin':
        p = Path.home() / 'Library' / 'Application Support' / 'Google' / 'Chrome'
        if p.is_dir():
            return str(p)
    elif sys.platform == 'win32':
        base = os.environ.get('LOCALAPPDATA', '')
        p = Path(base) / 'Google' / 'Chrome' / 'User Data'
        if p.is_dir():
            return str(p)
    return None


def _firefox_profile_dir() -> Optional[str]:
    """Return the path to the most-recently-used Firefox profile directory."""
    if sys.platform == 'linux':
        base = Path.home() / '.mozilla' / 'firefox'
    elif sys.platform == 'darwin':
        base = Path.home() / 'Library' / 'Application Support' / 'Firefox' / 'Profiles'
    elif sys.platform == 'win32':
        appdata = os.environ.get('APPDATA', '')
        base = Path(appdata) / 'Mozilla' / 'Firefox' / 'Profiles'
    else:
        return None

    if not base.is_dir():
        return None

    # Prefer default-release, then any .default profile
    for pattern in ('*.default-release', '*.default', '*'):
        hits = sorted(base.glob(pattern))
        if hits:
            return str(hits[0])
    return None


# ── Launch ───────────────────────────────────────────────────────────────────

def _launch(cmd: list) -> bool:
    """Fire-and-forget process launch; return True on success."""
    try:
        subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            close_fds=True,
        )
        return True
    except Exception:
        return False


def open_in_browser(
    html_path: str,
    browser: str = 'auto',
    use_profile: bool = True,
) -> bool:
    """
    Open *html_path* in a browser.

    browser  : 'auto' (try chrome then firefox), 'chrome', or 'firefox'.
    use_profile : pass the user's existing profile directory so bookmarks,
                  zoom settings, etc. are preserved.
    Returns True if a browser process was successfully started.
    """
    file_url = f'file://{os.path.abspath(html_path)}'

    def try_chrome() -> bool:
        exe = find_chrome()
        if not exe:
            return False
        cmd = [exe]
        if use_profile:
            udd = _chrome_user_data_dir()
            if udd:
                cmd += [f'--user-data-dir={udd}']
        cmd += ['--new-window', file_url]
        return _launch(cmd)

    def try_firefox() -> bool:
        exe = find_firefox()
        if not exe:
            return False
        cmd = [exe]
        if use_profile:
            pdir = _firefox_profile_dir()
            if pdir:
                cmd += ['-profile', pdir]
        cmd += [file_url]
        return _launch(cmd)

    if browser == 'chrome':
        return try_chrome()
    if browser == 'firefox':
        return try_firefox()

    # auto: chrome first, then firefox, then Python fallback
    if try_chrome():
        return True
    if try_firefox():
        return True

    try:
        webbrowser.open(file_url)
        return True
    except Exception:
        return False


def browser_info() -> dict:
    """Return a dict describing what browsers are available."""
    return {
        'chrome': find_chrome(),
        'firefox': find_firefox(),
        'chrome_profile': _chrome_user_data_dir(),
        'firefox_profile': _firefox_profile_dir(),
    }

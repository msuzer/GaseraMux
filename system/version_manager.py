import os, re, json, shlex, subprocess, time
from pathlib import Path
from .log_utils import debug, info, warn, error

APP_DIR = Path("/opt/GaseraMux")
CONFIG_DIR = APP_DIR / "config"
INSTALL_DIR = APP_DIR / "install"
LAST_PATH = APP_DIR / "last_version.txt"
VERSION_INFO = APP_DIR / "version_info.sh"
API_SECRET_PATH = CONFIG_DIR / "api_secret"

SERVICE_NAME = "gasera.service"  # kept consistent with install scripts

SHA_RE = re.compile(r"^[0-9a-f]{7,40}$")

def _run(cmd, **kw):
    """Run a shell-safe command and capture output; raise on failure."""
    if isinstance(cmd, str):
        cmd = shlex.split(cmd)
    return subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=kw.pop("timeout", 60), **kw).stdout.strip()

def read_version_info():
    info = {}
    if VERSION_INFO.exists():
        for line in VERSION_INFO.read_text().splitlines():
            if line.startswith("BUILD_"):
                k, v = line.split("=", 1)
                info[k] = v.strip().strip('"')
    return info

def current_full_sha():
    try:
        return _run(["git", "-C", str(APP_DIR), "rev-parse", "HEAD"])
    except Exception:
        vi = read_version_info()
        return vi.get("BUILD_HASH", "unknown")

def _regen_version_info():
    gen = INSTALL_DIR / "gen_version.sh"
    if gen.exists():
        _run([str(gen)])
    else:
        # minimal fallback if generator is missing
        now = time.strftime("%Y-%m-%d")
        VERSION_INFO.write_text(
            f'BUILD_HASH="{current_full_sha()}"\n'
            f'BUILD_SHORT="{_run(["git","-C",str(APP_DIR),"rev-parse","--short","HEAD"]) if (APP_DIR/".git").exists() else "manual"}"\n'
            f'BUILD_BRANCH="{_run(["git","-C",str(APP_DIR),"rev-parse","--abbrev-ref","HEAD"]) if (APP_DIR/".git").exists() else "unknown"}"\n'
            f'BUILD_DATE="{now}"\n'
            f'BUILD_DESCRIBE="manual"\n'
            f'BUILD_MESSAGE="manual write"\n'
        )

def _normalize_perms_and_prefs():
    # mirror relevant parts of update.sh without resetting git
    # - make *.sh executable, others 644; dirs 755; ensure prefs file is 660 & group www-data
    _run(["bash", "-lc", f'find {APP_DIR} -type f -name "*.sh" -exec chmod 755 {{}} \\;'])
    _run(["bash", "-lc", f'find {APP_DIR} -type f ! -name "*.sh" -exec chmod 644 {{}} \\;'])
    _run(["bash", "-lc", f'find {APP_DIR} -type d -exec chmod 755 {{}} \\;'])
    prefs = CONFIG_DIR / "user_prefs.json"
    if prefs.exists():
        try:
            _run(["chgrp", "www-data", str(prefs)])
            _run(["chmod", "660", str(prefs)])
        except Exception:
            pass

def _restart_service():
    """Restart the service but don't treat non-zero exit as fatal if service ends up active."""
    import subprocess
    proc = subprocess.run(["systemctl", "restart", SERVICE_NAME],
                          capture_output=True, text=True)
    # Check if service is active now
    state = subprocess.run(["systemctl", "is-active", SERVICE_NAME],
                           capture_output=True, text=True)
    if state.stdout.strip() != "active":
        msg = proc.stderr.strip() or "Service did not reach active state"
        error(f"Service restart problem: {msg}")
        raise RuntimeError(msg)
    info("Service restarted successfully")


def require_admin(request):
    """Access control: allow local or header token."""
    if request.remote_addr == "127.0.0.1" or request.remote_addr == "::1":
        return True
    token_hdr = request.headers.get("X-Admin-Token", "")
    if API_SECRET_PATH.exists() and token_hdr:
        secret = API_SECRET_PATH.read_text().strip()
        return secret and token_hdr == secret
    return False

# version_manager.py
def _is_same_commit(target: str, current_full: str) -> bool:
    # allow 7..40 hex prefix match
    return current_full.startswith(target) if 7 <= len(target) <= 40 else False

def checkout_commit(sha: str):
    if not SHA_RE.match(sha):
        raise ValueError("Invalid SHA")
    # Save current for rollback
    current = current_full_sha()
    # Guard against no-op
    if _is_same_commit(sha, current):
        debug(f"noop checkout: already on {current[:7]}")
        # DO NOT touch LAST_PATH; DO NOT restart; DO NOT regen info
        return {"previous": current, "current": current, "noop": True}

    # Save current for rollback only when it's actually changing
    LAST_PATH.write_text(current + "\n")

    debug(f"checkout requested sha={sha} current={current}")

    # Fetch and checkout detached to avoid moving branches
    _run(["git", "-C", str(APP_DIR), "fetch", "--all", "--prune"])

    # _run(["git", "-C", str(APP_DIR), "checkout", "--detach", sha])

    import subprocess
    proc = subprocess.run(
        ["git", "-C", str(APP_DIR), "checkout", "--detach", sha, "-f"],
        capture_output=True, text=True
    )
    if proc.returncode != 0:
        msg = proc.stderr.strip() or proc.stdout.strip() or "git checkout failed"
        error(f"git checkout returned {proc.returncode}: {msg}")
        raise RuntimeError(msg)
    else:
        debug(f"git checkout OK: {proc.stdout.strip()}")

    # DO NOT call update.sh here: it hard-resets to origin/main (would undo checkout). :contentReference[oaicite:1]{index=1}
    _normalize_perms_and_prefs()
    _regen_version_info()
    _restart_service()

    new_sha = current_full_sha()
    info(f"checkout completed sha={sha} now={new_sha}")
    return {"previous": current, "current": new_sha}

def rollback_previous():
    if not LAST_PATH.exists():
        raise RuntimeError("No previous version recorded")
    prev = LAST_PATH.read_text().strip()
    if not SHA_RE.match(prev):
        raise RuntimeError("Invalid previous SHA recorded")

    info(f"rollback requested to {prev}")

    _run(["git", "-C", str(APP_DIR), "fetch", "--all", "--prune"])
    _run(["git", "-C", str(APP_DIR), "checkout", "--detach", prev])

    _normalize_perms_and_prefs()
    _regen_version_info()
    _restart_service()

    now = current_full_sha()
    info(f"rollback completed now={now}")
    return {"current": now}

from pathlib import Path
import json, requests, time, subprocess

REPO = "msuzer/GaseraMux"
BRANCH = "main"
CACHE_DIR = Path("/opt/GaseraMux/cache")
CACHE_DIR.mkdir(exist_ok=True)
CACHE_FILE = CACHE_DIR / f"github_commits_{BRANCH}.json"
CACHE_TTL = 3600  # 1 hour
API_URL = f"https://api.github.com/repos/{REPO}/commits?sha={BRANCH}&per_page=40"

TAG_API_URL = f"https://api.github.com/repos/{REPO}/tags?per_page=100"

def _fetch_tags(headers):
    """Return a list of tags (name → sha) from GitHub."""
    try:
        r = requests.get(TAG_API_URL, headers=headers, timeout=6)
        r.raise_for_status()
        tags = r.json()
        return [
            {"name": t["name"], "sha": t["commit"]["sha"]}
            for t in tags
            if t.get("name")
        ]
    except Exception as e:
        return []

def _is_ancestor(older: str, newer: str) -> bool:
    try:
        subprocess.run(
            ["git", "-C", str(CACHE_DIR.parent),
             "merge-base", "--is-ancestor", older, newer],
            check=True, capture_output=True)
        return True
    except subprocess.CalledProcessError:
        return False

def get_github_commits(force=False, stable_only=False):
    """
    Fetch recent commits from GitHub, optionally listing only commits
    *after* a given base SHA (exclusive). If base_sha=None, return all.
    """
    now = time.time()

    # ---------- Cached?
    if not force and CACHE_FILE.exists():
        age = now - CACHE_FILE.stat().st_mtime
        if age < CACHE_TTL:
            try:
                data = json.loads(CACHE_FILE.read_text())
                data["cached"] = True
                return data
            except Exception:
                pass

    # ---------- GitHub API call
    headers = {}
    token_path = Path("/opt/GaseraMux/config/github_token")
    if token_path.exists():
        token = token_path.read_text().strip()
        if token:
            headers["Authorization"] = f"token {token}"

    try:
        r = requests.get(API_URL, headers=headers, timeout=6)
        r.raise_for_status()
        commits = r.json()

        # fetch tags once
        tags = _fetch_tags(headers)
        stable_shas = {
            t["sha"] for t in tags if t["name"].lower().startswith("stable")
        }

        simplified = []
        for c in commits:
            sha = c["sha"]
            is_stable = sha in stable_shas
            if stable_only and not is_stable:
                continue
            simplified.append({
                "sha": sha[:7],
                "full_sha": sha,
                "date": c["commit"]["committer"]["date"][:10],
                "author": c["commit"]["committer"]["name"],
                "message": c["commit"]["message"].split("\n", 1)[0],
                "stable": is_stable,
            })

        payload = {"branch": BRANCH, "cached": False, "commits": simplified}
        CACHE_FILE.write_text(json.dumps(payload, indent=2))
        return payload

    except Exception as e:
        # fallback to cache on any failure
        if CACHE_FILE.exists():
            data = json.loads(CACHE_FILE.read_text())
            data["cached"] = True
            data["warning"] = str(e)
            return data
        return {"branch": BRANCH, "cached": True, "commits": [], "error": str(e)}

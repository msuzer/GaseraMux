import os
import shutil
import glob
import time

def get_free_space(path):
    try:
        total, used, free = shutil.disk_usage(path)
        return free
    except Exception:
        return None

def get_total_space(path):
    try:
        total, used, free = shutil.disk_usage(path)
        return total
    except Exception:
        return None

def usb_block_device_exists():
    """
    Return True if a block device for USB is present.
    Supports /dev/sda1, /dev/sdb1, /dev/sdX1...
    """
    return len(glob.glob("/dev/sd[a-z]1")) > 0

def usb_mounted():
    """
    Returns True if USB storage is both:
    - physically present as /dev/sdX1
    - mounted at /media/usb0
    """
    # Check physical presence first (avoids systemd automount hang)
    dev_present = usb_block_device_exists()
    if not dev_present:
        return False

    # Then check if mountpoint is active
    usb_path = "/media/usb0"
    return os.path.ismount(usb_path)

_last_usb_state = None
_latest_usb_mounted = False

def check_usb_change():
    """
    Return (usb_mounted, usb_event), where:
      usb_mounted = current on/off state
      usb_event = "USB_MOUNT", "USB_UNMOUNT", or None
    """
    global _last_usb_state, _latest_usb_mounted

    current_usb = usb_mounted()

    # First-time initialization
    if _last_usb_state is None:
        _last_usb_state = current_usb
        _latest_usb_mounted = current_usb
        return current_usb, None

    # Detect change
    if current_usb != _last_usb_state:
        _latest_usb_mounted = current_usb
        _last_usb_state = current_usb
        event = "USB_MOUNT" if current_usb else "USB_UNMOUNT"
        return current_usb, event

    # No change
    return current_usb, None

def get_log_directory():
    if usb_mounted():
        usb_logs = "/media/usb0/logs"
        os.makedirs(usb_logs, exist_ok=True)
        return usb_logs

    internal_logs = "/data/logs"
    os.makedirs(internal_logs, exist_ok=True)
    return internal_logs

def get_log_entries():
    """
    Returns a sorted list of all log entries in the active log directory.
    Each entry is {name, size, mtime}.
    Sorted: newest → oldest.
    """
    logdir = get_log_directory()
    if not os.path.exists(logdir):
        return []

    entries = []
    for fname in os.listdir(logdir):
        full = os.path.join(logdir, fname)
        if not os.path.isfile(full):
            continue
        # Only include CSV logs
        if not fname.lower().endswith(".csv"):
            continue

        try:
            st = os.stat(full)
            entries.append({
                "name": fname,
                "size": st.st_size,
                "mtime": int(st.st_mtime),
                "modified_readable": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(st.st_mtime))
            })
        except Exception:
            continue

    # Newest → oldest
    entries.sort(key=lambda x: x["mtime"], reverse=True)
    return entries


def list_log_files(page=1, page_size=50):
    """
    Paginated logs listing.
    Returns dict: {"total": int, "files": [...], "page": int, "page_size": int}
    """
    # Sanitize inputs
    try:
        page = int(page)
    except Exception:
        page = 1
    try:
        page_size = int(page_size)
    except Exception:
        page_size = 50

    if page < 1:
        page = 1
    if page_size <= 0:
        page_size = 50

    entries = get_log_entries()
    total = len(entries)

    start = (page - 1) * page_size
    end = start + page_size
    if start >= total:
        start = max(0, (max(1, (total + page_size - 1) // page_size) - 1) * page_size)
        end = start + page_size

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "files": entries[start:end]
    }


def safe_join_in_logdir(filename):
    """
    Prevents path traversal. Returns the safe absolute path for a log file.
    Raises FileNotFoundError if file does not exist.
    """
    log_dir = get_log_directory()
    safe_name = os.path.basename(filename)
    full = os.path.join(log_dir, safe_name)

    if not os.path.isfile(full):
        raise FileNotFoundError(f"{safe_name} not found")

    return full

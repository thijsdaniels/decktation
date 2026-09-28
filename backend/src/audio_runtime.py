"""Connect Decky's backend process to the active desktop audio session."""

import os


def _log(logger, level, message):
    if logger:
        getattr(logger, level)(message)
    else:
        print(message)


def _candidate_uids(decky_user_home=None):
    """Return likely desktop-session UIDs, preferring Decky's configured user."""
    candidates = []
    if decky_user_home and os.path.exists(decky_user_home):
        candidates.append(str(os.stat(decky_user_home).st_uid))
    if os.environ.get("SUDO_UID"):
        candidates.append(os.environ["SUDO_UID"])

    # A normal Deck installation has one logged-in desktop user.  Keep this as
    # a fallback for older Decky versions that do not expose DECKY_USER_HOME.
    try:
        candidates.extend(
            entry for entry in sorted(os.listdir("/run/user"))
            if entry.isdigit() and entry != "0"
        )
    except OSError:
        pass

    seen = set()
    return [uid for uid in candidates if not (uid in seen or seen.add(uid))]


def setup_audio_environment(decky_user_home=None, logger=None):
    """Select a live non-root PipeWire runtime directory, if one is available."""
    current = os.environ.get("XDG_RUNTIME_DIR")
    if current and current != "/run/user/0" and os.path.exists(
        os.path.join(current, "pipewire-0")
    ):
        return current

    for uid in _candidate_uids(decky_user_home):
        runtime_dir = f"/run/user/{uid}"
        socket = os.path.join(runtime_dir, "pipewire-0")
        try:
            if not os.path.exists(socket) or str(os.stat(socket).st_uid) != uid:
                continue
        except OSError:
            continue

        os.environ["XDG_RUNTIME_DIR"] = runtime_dir
        os.environ["PIPEWIRE_RUNTIME_DIR"] = runtime_dir
        os.environ["PULSE_SERVER"] = f"unix:{runtime_dir}/pulse/native"
        _log(logger, "info", f"Configured desktop audio runtime: {runtime_dir}")
        return runtime_dir

    _log(logger, "warning", "No desktop PipeWire runtime directory was found")
    return None


def ensure_audio_environment(sounddevice, decky_user_home=None, logger=None):
    """Reconnect sounddevice after selecting the desktop PipeWire session."""
    previous = os.environ.get("XDG_RUNTIME_DIR")
    runtime_dir = setup_audio_environment(decky_user_home, logger)
    if runtime_dir and runtime_dir != previous:
        try:
            sounddevice._terminate()
            sounddevice._initialize()
            _log(logger, "info", f"Reconnected sounddevice to PipeWire ({runtime_dir})")
        except Exception as error:
            _log(logger, "warning", f"Could not reinitialize sounddevice: {error}")
    return runtime_dir

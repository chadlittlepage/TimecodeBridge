"""
Run from Resolve Py3 console:
  exec(open("/Users/chadlittlepage/Documents/APPs/TimecodeBridge/resolve_console_script.py").read())

Writes timecode state to a file every 100ms. The server watches this file.
No sockets, no threads that can crash.
"""

import json
import time
import sys
import os

_G = sys.modules.setdefault("_tcb_globals", type(sys)("_tcb_globals"))
_G.resolve_ref = resolve  # noqa: F821
_G.threading_ref = threading  # noqa: F821
_G.running = True
_G.STATE_FILE = "/tmp/tcb_resolve_state.json"


def _tcb_poll():
    last_tc = None
    last_tl = None
    while _G.running:
        try:
            r = _G.resolve_ref
            pm = r.GetProjectManager()
            proj = pm.GetCurrentProject()
            if not proj:
                time.sleep(0.1)
                continue
            tl = proj.GetCurrentTimeline()
            if not tl:
                time.sleep(0.1)
                continue

            tc = tl.GetCurrentTimecode()
            tl_name = tl.GetName()
            changed = (tc != last_tc) or (tl_name != last_tl)

            if changed:
                last_tc = tc
                fps_str = tl.GetSetting("timelineFrameRate")

                state = {
                    "tc": tc,
                    "project": proj.GetName(),
                    "timeline": tl_name,
                    "fps": float(fps_str) if fps_str else 24.0,
                    "startTC": tl.GetStartTimecode(),
                    "ts": time.time(),
                    "tl_changed": tl_name != last_tl,
                }
                last_tl = tl_name

                # Atomic write: write to temp file then rename
                tmp = _G.STATE_FILE + ".tmp"
                with open(tmp, "w") as f:
                    json.dump(state, f)
                os.replace(tmp, _G.STATE_FILE)

        except Exception as e:
            try:
                with open(_G.STATE_FILE + ".err", "w") as f:
                    f.write(str(e))
            except Exception:
                pass
        time.sleep(0.033)


# Stop previous poll thread if re-running
_G.running = False
time.sleep(0.2)
_G.running = True

# Write initial state immediately on main thread (avoids slow first scrub)
try:
    r = _G.resolve_ref
    pm = r.GetProjectManager()
    proj = pm.GetCurrentProject()
    if proj:
        tl = proj.GetCurrentTimeline()
        if tl:
            fps_str = tl.GetSetting("timelineFrameRate")
            state = {
                "tc": tl.GetCurrentTimecode(),
                "project": proj.GetName(),
                "timeline": tl.GetName(),
                "fps": float(fps_str) if fps_str else 24.0,
                "startTC": tl.GetStartTimecode(),
                "ts": time.time(),
                "tl_changed": True,
            }
            tmp = _G.STATE_FILE + ".tmp"
            with open(tmp, "w") as f:
                json.dump(state, f)
            os.replace(tmp, _G.STATE_FILE)
except Exception:
    pass

_G.threading_ref.Thread(target=_tcb_poll, daemon=True).start()
print(f"[TCB] Writing state to {_G.STATE_FILE}")

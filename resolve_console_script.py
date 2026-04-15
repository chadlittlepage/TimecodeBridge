"""
Run from Resolve Py3 console:
  exec(open("/Users/chadlittlepage/Documents/APPs/TimecodeBridge/resolve_console_script.py").read())
"""

import json
import socket
import time

# Capture console globals so daemon threads can access them.
_resolve = resolve  # noqa: F821
_threading = threading  # noqa: F821

PORT = 9877
POLL_INTERVAL = 0.1

_tcb_clients = []
_tcb_lock = _threading.Lock()


def _tcb_get_state():
    pm = _resolve.GetProjectManager()
    proj = pm.GetCurrentProject()
    if not proj:
        return None
    tl = proj.GetCurrentTimeline()
    if not tl:
        return None
    fps_str = tl.GetSetting("timelineFrameRate")
    return {
        "tc": tl.GetCurrentTimecode(),
        "project": proj.GetName(),
        "timeline": tl.GetName(),
        "fps": float(fps_str) if fps_str else 24.0,
        "startTC": tl.GetStartTimecode(),
        "_timeline_obj": tl,
    }


def _tcb_get_markers(tl):
    """Extract markers from a timeline object."""
    try:
        raw = tl.GetMarkers()
        if not raw:
            return []
        markers = []
        for frame_offset, info in raw.items():
            markers.append({
                "frame": frame_offset,
                "color": info.get("color", ""),
                "name": info.get("name", ""),
                "note": info.get("note", ""),
                "duration": info.get("duration", 1),
                "customData": info.get("customData", ""),
            })
        return markers
    except Exception:
        return []


def _tcb_accept(srv_sock):
    while True:
        try:
            conn, addr = srv_sock.accept()
            conn.settimeout(1.0)
            with _tcb_lock:
                _tcb_clients.append(conn)
            print(f"[TCB] Client connected: {addr}")
        except Exception:
            break


def _tcb_send(data):
    """Send data to all connected clients, removing dead ones."""
    with _tcb_lock:
        dead = []
        for c in _tcb_clients:
            try:
                c.sendall(data)
            except Exception:
                dead.append(c)
        for c in dead:
            _tcb_clients.remove(c)
            try:
                c.close()
            except Exception:
                pass


def _tcb_poll():
    last_tc = None
    last_tl = None
    last_markers_hash = None

    while True:
        try:
            st = _tcb_get_state()
            if st:
                tl_obj = st.pop("_timeline_obj")
                msgs = []

                # Timeline change: send info + markers
                if st["timeline"] != last_tl:
                    last_tl = st["timeline"]
                    msgs.append(json.dumps({
                        "type": "timeline_info",
                        "project": st["project"],
                        "timeline": st["timeline"],
                        "fps": st["fps"],
                        "startTC": st["startTC"],
                    }) + "\n")

                    # Send markers
                    markers = _tcb_get_markers(tl_obj)
                    markers_hash = str(markers)
                    if markers_hash != last_markers_hash:
                        last_markers_hash = markers_hash
                        msgs.append(json.dumps({
                            "type": "markers",
                            "markers": markers,
                        }) + "\n")

                # Timecode change
                if st["tc"] != last_tc:
                    last_tc = st["tc"]
                    msgs.append(json.dumps({
                        "type": "timecode",
                        "tc": st["tc"],
                        "ts": time.time(),
                    }) + "\n")

                if msgs:
                    _tcb_send("".join(msgs).encode())

        except Exception as e:
            print(f"[TCB] Poll error: {e}")
        time.sleep(POLL_INTERVAL)


# Close previous server if re-running
try:
    _tcb_srv.close()  # noqa: F821
except Exception:
    pass

# Start TCP server
_tcb_srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
_tcb_srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
_tcb_srv.bind(("0.0.0.0", PORT))
_tcb_srv.listen(5)

_threading.Thread(target=_tcb_accept, args=(_tcb_srv,), daemon=True).start()
_threading.Thread(target=_tcb_poll, daemon=True).start()

print(f"[TCB] TCP server running on port {PORT}")

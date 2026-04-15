/**
 * TimecodeBridge JS Client Library
 *
 * Zero-dependency WebSocket client for consuming timecode from a TimecodeBridge server.
 * Works as an ES module or a plain <script> tag.
 *
 * Usage:
 *   const bridge = new TimecodeBridge("ws://192.168.1.100:9876");
 *   bridge.on("timecode", (data) => console.log(data.tc));   // "01:02:03:04"
 *   bridge.on("timeline", (info) => console.log(info));       // {project, timeline, fps, startTC}
 *   bridge.on("markers", (markers) => console.log(markers));  // [{frame, color, name, ...}]
 *   bridge.on("connect", () => {});
 *   bridge.on("disconnect", () => {});
 *   bridge.close();
 *
 * Properties:
 *   bridge.timecode   // current timecode string or null
 *   bridge.timeline   // current timeline info object or null
 *   bridge.markers    // current markers array or []
 *   bridge.connected  // boolean
 */

class TimecodeBridge {
  constructor(url, { reconnectMs = 2000 } = {}) {
    this._url = url;
    this._reconnectMs = reconnectMs;
    this._ws = null;
    this._listeners = {};
    this._reconnectTimer = null;
    this._closed = false;

    // State
    this.timecode = null;
    this.source = null;
    this.timeline = null;
    this.markers = [];

    this._connect();
  }

  /** Register an event listener. Events: timecode, timeline, markers, connect, disconnect, hello */
  on(event, fn) {
    (this._listeners[event] = this._listeners[event] || []).push(fn);
    return this;
  }

  /** Remove an event listener. */
  off(event, fn) {
    const arr = this._listeners[event];
    if (arr) this._listeners[event] = arr.filter(f => f !== fn);
    return this;
  }

  /** Permanently close the connection. */
  close() {
    this._closed = true;
    clearTimeout(this._reconnectTimer);
    if (this._ws) this._ws.close();
  }

  get connected() {
    return this._ws && this._ws.readyState === WebSocket.OPEN;
  }

  // ---- Internal ----

  _emit(event, ...args) {
    for (const fn of this._listeners[event] || []) {
      try { fn(...args); } catch (e) { console.error(`[TimecodeBridge] ${event} handler error:`, e); }
    }
  }

  _connect() {
    if (this._closed) return;

    try { this._ws = new WebSocket(this._url); }
    catch { this._scheduleReconnect(); return; }

    this._ws.onopen = () => this._emit("connect");

    this._ws.onclose = () => {
      this._emit("disconnect");
      this._scheduleReconnect();
    };

    this._ws.onerror = () => {};

    this._ws.onmessage = (event) => {
      let data;
      try { data = JSON.parse(event.data); } catch { return; }

      switch (data.type) {
        case "timecode":
          this.timecode = data.tc;
          this.source = data.source || "api";
          this._emit("timecode", data);
          break;
        case "timeline_info":
          this.timeline = data;
          this._emit("timeline", data);
          break;
        case "markers":
          this.markers = data.markers || [];
          this._emit("markers", this.markers);
          break;
        case "hello":
          this._emit("hello", data);
          break;
      }
    };
  }

  _scheduleReconnect() {
    if (this._closed) return;
    clearTimeout(this._reconnectTimer);
    this._reconnectTimer = setTimeout(() => this._connect(), this._reconnectMs);
  }
}

// Export for ES modules and script tags
if (typeof module !== "undefined" && module.exports) module.exports = TimecodeBridge;
if (typeof window !== "undefined") window.TimecodeBridge = TimecodeBridge;

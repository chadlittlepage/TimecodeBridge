/**
 * LTC Audio Decoder — captures audio from a virtual device (BlackHole/SonoBus)
 * and decodes SMPTE LTC timecode using LTC.wasm (libltc compiled to WebAssembly).
 *
 * Usage:
 *   const decoder = new LTCDecoder();
 *   decoder.onTimecode = (tc) => console.log(tc);  // "01:02:03:04"
 *   decoder.onStateChange = (active) => console.log(active ? 'receiving' : 'idle');
 *   await decoder.start();          // prompts for mic permission, selects device
 *   await decoder.start(deviceId);  // skip device picker
 *   decoder.stop();
 */

const WASM_DIR = "browser/wasm/";
const STALE_MS = 500; // LTC considered stale after this many ms without a frame

class LTCDecoder {
  constructor() {
    this.onTimecode = null;   // (tc: string) => void
    this.onStateChange = null; // (receiving: boolean) => void

    this._audioCtx = null;
    this._stream = null;
    this._processor = null;
    this._wasmModule = null;
    this._decoder = null;
    this._bufferPtr = null;
    this._active = false;
    this._receiving = false;
    this._lastFrameTime = 0;
    this._staleTimer = null;
    this._lastTC = null;
  }

  get active() { return this._active; }
  get receiving() { return this._receiving; }
  get timecode() { return this._lastTC; }

  /** List audio input devices that look like virtual audio (BlackHole, SonoBus, etc). */
  static async listDevices() {
    // Need a temporary stream to get labeled device list
    let tempStream;
    try {
      tempStream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch {
      return [];
    }
    const devices = await navigator.mediaDevices.enumerateDevices();
    tempStream.getTracks().forEach(t => t.stop());
    return devices.filter(d => d.kind === "audioinput");
  }

  /** Start capturing and decoding LTC audio. */
  async start(deviceId) {
    if (this._active) this.stop();

    // Load WASM module
    await this._loadWasm();

    // Get audio stream
    const constraints = { audio: deviceId
      ? { deviceId: { exact: deviceId }, echoCancellation: false, noiseSuppression: false, autoGainControl: false }
      : { echoCancellation: false, noiseSuppression: false, autoGainControl: false }
    };
    console.log("[LTC] getUserMedia constraints:", JSON.stringify(constraints));
    this._stream = await navigator.mediaDevices.getUserMedia(constraints);
    const tracks = this._stream.getAudioTracks();
    for (const t of tracks) {
      const settings = t.getSettings();
      console.log("[LTC] Track label:", t.label);
      console.log("[LTC] Track settings:", JSON.stringify(settings));
      console.log("[LTC] Actual deviceId:", settings.deviceId);
    }

    // Audio pipeline
    this._audioCtx = new AudioContext();
    console.log("[LTC] AudioContext sample rate:", this._audioCtx.sampleRate);
    const source = this._audioCtx.createMediaStreamSource(this._stream);

    // ScriptProcessorNode: 1024 samples, mono input, no output
    this._processor = this._audioCtx.createScriptProcessor(1024, 1, 1);

    // Create decoder at the capture sample rate
    this._decoder = this._wasmModule._ltc_dec_create(this._audioCtx.sampleRate);
    console.log("[LTC] Decoder created:", this._decoder);

    // Pre-allocate WASM heap buffer for 1024 float32 samples
    this._bufferPtr = this._wasmModule._malloc(1024 * 4);
    console.log("[LTC] Buffer allocated at:", this._bufferPtr);

    // Wire up audio processing
    this._audioCallCount = 0;
    this._processor.onaudioprocess = (e) => this._onAudio(e);
    source.connect(this._processor);
    this._processor.connect(this._audioCtx.destination);

    this._active = true;
    this._startStaleCheck();
    console.log("[LTC] Started, listening for LTC audio...");
  }

  /** Stop capturing. */
  stop() {
    this._stopStaleCheck();

    if (this._processor) {
      this._processor.onaudioprocess = null;
      this._processor.disconnect();
      this._processor = null;
    }
    if (this._audioCtx) {
      this._audioCtx.close();
      this._audioCtx = null;
    }
    if (this._stream) {
      this._stream.getTracks().forEach(t => t.stop());
      this._stream = null;
    }
    if (this._decoder && this._wasmModule) {
      this._wasmModule._ltc_dec_free(this._decoder);
      this._decoder = null;
    }
    if (this._bufferPtr && this._wasmModule) {
      this._wasmModule._free(this._bufferPtr);
      this._bufferPtr = null;
    }

    this._active = false;
    this._setReceiving(false);
  }

  // ---- Internal ----

  async _loadWasm() {
    if (this._wasmModule) return;

    const self = this;
    return new Promise((resolve, reject) => {
      // The ltcdec.js script sets up a global `Module` object.
      // We need to configure it before loading.
      window.Module = {
        locateFile: (path) => {
          console.log("[LTC] locateFile:", path);
          return WASM_DIR + path;
        },
        print: (line) => self._onWasmPrint(line),
        printErr: (line) => console.warn("[LTC.wasm]", line),
        onRuntimeInitialized: () => {
          console.log("[LTC] WASM runtime initialized");
          console.log("[LTC] Available functions:", {
            create: typeof Module._ltc_dec_create,
            write: typeof Module._ltc_dec_write,
            free: typeof Module._ltc_dec_free,
            malloc: typeof Module._malloc,
          });
          self._wasmModule = window.Module;
          resolve();
        },
      };

      const script = document.createElement("script");
      script.src = WASM_DIR + "ltcdec.js";
      script.onerror = () => {
        console.error("[LTC] Failed to load ltcdec.js from", WASM_DIR);
        reject(new Error("Failed to load ltcdec.js"));
      };
      document.head.appendChild(script);
    });
  }

  _onWasmPrint(line) {
    // Output format from ltcdec.c:
    // "YYYY-MM-DD ; HH:MM:SS:FF ; off_start ; off_end ; start_sec ; end_sec ; reverse"
    const parts = line.split(" ; ");
    if (parts.length < 3) return;

    const tc = parts[1].trim(); // "HH:MM:SS:FF" or "HH:MM:SS.FF" (drop-frame)
    if (!tc || tc.length < 11) return;

    // Normalize separator: ltcdec uses '.' for drop-frame, ':' for non-drop
    // Keep as-is — the consumer can check for '.' vs ':'

    this._lastTC = tc;
    this._lastFrameTime = Date.now();
    this._setReceiving(true);

    if (this.onTimecode) {
      this.onTimecode(tc);
    }
  }

  _onAudio(event) {
    if (!this._decoder || !this._wasmModule) return;

    const input = event.inputBuffer.getChannelData(0);
    const M = this._wasmModule;

    // Log first few callbacks to verify audio is flowing
    this._audioCallCount = (this._audioCallCount || 0) + 1;
    if (this._audioCallCount <= 5 || this._audioCallCount % 500 === 0) {
      const maxVal = Math.max(...Array.from(input).map(Math.abs));
      console.log(`[LTC] Audio callback #${this._audioCallCount}, max amplitude: ${maxVal.toFixed(6)}, samples: ${input.length}`);
    }

    // Copy Float32 samples to WASM heap
    const heap = new Float32Array(M.HEAPU8.buffer, this._bufferPtr, 1024);
    heap.set(input);

    // Decode — any results come via Module.print → _onWasmPrint
    M._ltc_dec_write(this._decoder, this._bufferPtr, input.length);
  }

  _startStaleCheck() {
    this._staleTimer = setInterval(() => {
      if (this._receiving && Date.now() - this._lastFrameTime > STALE_MS) {
        this._setReceiving(false);
      }
    }, 200);
  }

  _stopStaleCheck() {
    if (this._staleTimer) {
      clearInterval(this._staleTimer);
      this._staleTimer = null;
    }
  }

  _setReceiving(val) {
    if (this._receiving !== val) {
      this._receiving = val;
      if (this.onStateChange) this.onStateChange(val);
    }
  }
}

// Export for both module and script tag usage
if (typeof window !== "undefined") window.LTCDecoder = LTCDecoder;

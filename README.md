# WebSocket Binary Audio Receiver

A minimal WebSocket server that receives binary audio frames and plays them through the local audio device using PyAudio.

- Protocol: client sends raw PCM16 (16‑bit signed), mono, 16 kHz frames as binary WebSocket messages
- Server: Python `websockets` + `pyaudio`
- Default address: `ws://0.0.0.0:8080`

## Features
- Plays incoming binary audio in real‑time
- Ignores text messages with a warning
- Handles disconnects and common playback errors gracefully

## Requirements
- Python 3.9+
- PortAudio (for PyAudio)
- pip packages (see `requirements.txt`):
  - websockets
  - pyaudio

### Notes on PyAudio (PortAudio)
- Windows: `pip install pyaudio` usually works, but if it fails, try prebuilt wheels (e.g., `pip install pipwin && pipwin install pyaudio`).
- macOS: `brew install portaudio` then `pip install pyaudio`.
- Linux: install dev headers (e.g., Debian/Ubuntu: `sudo apt-get install portaudio19-dev`), then `pip install pyaudio`.

## Installation
1. Clone this repository
2. Create and activate a virtual environment (recommended)
3. Install dependencies

Example (Windows PowerShell):

```
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Run the server
```
python server.py
```
You should see logs like:
```
[....] INFO: Starting WebSocket audio server on ws://0.0.0.0:8080
[....] INFO: Server is ready to receive binary audio frames
```

## Audio format expected by the server
- Encoding: PCM 16-bit signed little-endian ("Int16")
- Channels: 1 (mono)
- Sample rate: 16000 Hz
- Suggested frame size: multiples of 1024 samples (as configured for playback buffer), but any chunking works

Send your audio as the raw PCM bytes directly (no WAV headers, no compression) in binary WebSocket messages.

## Simple client examples

### Python (websockets)
```python
import asyncio, websockets, math, struct

URI = "ws://localhost:8080"

async def send_tone():
    async with websockets.connect(URI, max_size=None) as ws:
        sr = 16000
        duration_sec = 2
        freq = 440.0
        amp = 0.2  # 20% of full scale
        # Build 16-bit PCM mono bytes for a 440 Hz sine tone
        frames = bytearray()
        for n in range(int(sr * duration_sec)):
            s = math.sin(2 * math.pi * freq * n / sr)
            val = int(max(-1.0, min(1.0, s * amp)) * 32767)
            frames += struct.pack('<h', val)
        # Send in chunks
        chunk = 1024 * 2  # bytes (~512 samples)
        for i in range(0, len(frames), chunk):
            await ws.send(frames[i:i+chunk])
        await asyncio.sleep(0.1)

asyncio.run(send_tone())
```

### JavaScript (browser)
This snippet resamples microphone audio to 16 kHz mono PCM16 and streams via WebSocket. The resampling approach is simplified; in production use a robust resampler.
```html
<script>
(async () => {
  const ws = new WebSocket('ws://localhost:8080');
  ws.binaryType = 'arraybuffer';

  const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
  const audioCtx = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: 48000 });
  const source = audioCtx.createMediaStreamSource(stream);

  const processor = audioCtx.createScriptProcessor(4096, 1, 1);
  source.connect(processor);
  processor.connect(audioCtx.destination);

  function floatTo16BitPCM(float32Array) {
    const out = new Int16Array(float32Array.length);
    for (let i = 0; i < float32Array.length; i++) {
      let s = Math.max(-1, Math.min(1, float32Array[i]));
      out[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
    }
    return out;
  }

  function downsampleBuffer(buffer, inRate, outRate) {
    if (outRate === inRate) return buffer;
    const ratio = inRate / outRate;
    const newLen = Math.round(buffer.length / ratio);
    const result = new Float32Array(newLen);
    let offsetResult = 0;
    let offsetBuffer = 0;
    while (offsetResult < newLen) {
      const nextOffsetBuffer = Math.round((offsetResult + 1) * ratio);
      let accum = 0, count = 0;
      for (let i = offsetBuffer; i < nextOffsetBuffer && i < buffer.length; i++) {
        accum += buffer[i];
        count++;
      }
      result[offsetResult] = accum / count;
      offsetResult++;
      offsetBuffer = nextOffsetBuffer;
    }
    return result;
  }

  processor.onaudioprocess = (e) => {
    if (ws.readyState !== WebSocket.OPEN) return;
    const input = e.inputBuffer.getChannelData(0);
    const down = downsampleBuffer(input, audioCtx.sampleRate, 16000);
    const pcm16 = floatTo16BitPCM(down);
    ws.send(pcm16.buffer);
  };
})();
</script>
```

## Troubleshooting
- No sound: ensure your default output device is available and not exclusively locked by another app.
- Distorted or too fast/slow audio: verify you are sending PCM16, mono, 16 kHz.
- PyAudio install errors: see the platform notes above.

## License
MIT

## Acknowledgements
Based on a minimal server using `websockets` and `pyaudio`. Original repository: https://github.com/arthurabreu/wss_binary_audio_receiver

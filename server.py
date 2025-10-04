import asyncio
import logging
from typing import Optional, Protocol, AsyncIterator, Union

from websockets import serve
from websockets.exceptions import (
    ConnectionClosedError,
    ConnectionClosedOK,
    WebSocketException,
)

import pyaudio

# Minimal protocol for what we need from a websocket connection
class _WSLike(Protocol):
    def __aiter__(self) -> AsyncIterator[Union[bytes, str]]: ...
    @property
    def remote_address(self) -> object: ...

# Global audio resources initialized in main()
_PYAUDIO: Optional[pyaudio.PyAudio] = None
_STREAM: Optional[pyaudio.Stream] = None

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s: %(message)s")


def _close_audio() -> None:
    global _PYAUDIO, _STREAM
    if _STREAM is not None:
        try:
            if _STREAM.is_active():
                _STREAM.stop_stream()
        except (OSError, RuntimeError):
            pass
        try:
            _STREAM.close()
        except (OSError, RuntimeError):
            pass
        _STREAM = None
    if _PYAUDIO is not None:
        try:
            _PYAUDIO.terminate()
        except (OSError, RuntimeError):
            pass
        _PYAUDIO = None


async def handler(ws: _WSLike) -> None:
    """Handle a single client connection.

    Expects binary audio frames (bytes). Text messages are ignored with a warning.
    """
    peer = getattr(ws, "remote_address", None)
    logging.info(f"Client connected: {peer}")
    try:
        async for msg in ws:
            if isinstance(msg, (bytes, bytearray)):
                if _STREAM is not None:
                    try:
                        _STREAM.write(bytes(msg))  # ensure bytes type
                    except OSError as exc:
                        logging.error(f"Audio playback error: {exc}")
                else:
                    logging.warning("Received audio data but audio output stream isn't initialized")
            else:
                logging.warning(f"Ignoring non-binary message of type {type(msg).__name__}")
    except (ConnectionClosedOK, ConnectionClosedError) as exc:
        logging.info(f"Connection closed: {peer} ({exc})")
    except (WebSocketException, OSError) as exc:
        logging.error(f"WebSocket error in connection {peer}: {exc}")
    finally:
        logging.info(f"Client disconnected: {peer}")


async def main() -> None:
    global _PYAUDIO, _STREAM

    # Initialize audio output
    _PYAUDIO = pyaudio.PyAudio()
    _STREAM = _PYAUDIO.open(
        format=pyaudio.paInt16,  # 16-bit PCM
        channels=1,              # mono
        rate=16000,              # 16 kHz sample rate
        output=True,
        frames_per_buffer=1024,
    )

    # Start WebSocket server
    host = "0.0.0.0"
    port = 8080
    logging.info(f"Starting WebSocket audio server on ws://{host}:{port}")

    # max_size=None allows large binary frames without automatic closing
    async with serve(handler, host, port, max_size=None):
        logging.info("Server is ready to receive binary audio frames")
        try:
            await asyncio.Future()  # run forever
        finally:
            logging.info("Server shutting down...")
            _close_audio()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Interrupted by user")
        _close_audio()
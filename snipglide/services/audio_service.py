import os
import time
import uuid
import threading
import numpy as np
from pathlib import Path
from typing import Optional, Callable

try:
    import sounddevice as sd
    import soundfile as sf
    AUDIO_AVAILABLE = True
except Exception:
    AUDIO_AVAILABLE = False

from snipglide.utils.logger import logger

VOICE_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "voice_notes"
VOICE_DIR.mkdir(parents=True, exist_ok=True)

class AudioRecorder:
    def __init__(self, sample_rate: int = 24000):
        self.sample_rate = sample_rate
        self.is_recording = False
        self._frames = []
        self._stream = None
        self._lock = threading.Lock()
        self.start_time = 0.0

    def start(self):
        if not AUDIO_AVAILABLE:
            logger.warning("Audio library sounddevice/soundfile not available.")
            return False

        with self._lock:
            self._frames = []
            self.is_recording = True
            self.start_time = time.time()

            def callback(indata, frames, time_info, status):
                if self.is_recording:
                    self._frames.append(indata.copy())

            try:
                self._stream = sd.InputStream(
                    samplerate=self.sample_rate,
                    channels=1,
                    dtype="float32",
                    callback=callback
                )
                self._stream.start()
                logger.info("Real audio microphone recording started.")
                return True
            except Exception as e:
                logger.error(f"Failed to open microphone audio stream: {e}")
                self.is_recording = False
                return False

    def stop(self) -> Optional[dict]:
        with self._lock:
            if not self.is_recording:
                return None
            self.is_recording = False

            if self._stream:
                try:
                    self._stream.stop()
                    self._stream.close()
                except Exception:
                    pass
                self._stream = None

            if not self._frames:
                logger.warning("No audio frames recorded.")
                return None

            audio_data = np.concatenate(self._frames, axis=0)
            duration = float(len(audio_data)) / float(self.sample_rate)

            # Generate unique wav file
            file_id = f"voice_{uuid.uuid4().hex[:10]}.wav"
            file_path = VOICE_DIR / file_id

            try:
                sf.write(str(file_path), audio_data, self.sample_rate)
                logger.info(f"Voice note saved to: {file_path} (duration: {duration:.2f}s)")
                return {
                    "file_path": str(file_path),
                    "file_name": file_id,
                    "duration": duration,
                }
            except Exception as e:
                logger.error(f"Failed to write audio file: {e}")
                return None

class AudioPlayer:
    def __init__(self):
        self.is_playing = False
        self._current_stream = None
        self._stop_event = threading.Event()

    def play(self, file_path: str, progress_callback: Optional[Callable[[float, float], None]] = None, finished_callback: Optional[Callable[[], None]] = None):
        if not os.path.exists(file_path):
            logger.error(f"Audio file does not exist: {file_path}")
            if finished_callback:
                finished_callback()
            return

        self.stop()
        self._stop_event.clear()
        self.is_playing = True

        def _play_worker():
            try:
                data, fs = sf.read(file_path, dtype="float32")
                total_duration = float(len(data)) / float(fs)
                start_t = time.time()

                # Start playback stream
                sd.play(data, fs)

                while sd.get_stream().active and not self._stop_event.is_set():
                    elapsed = time.time() - start_t
                    if elapsed >= total_duration:
                        break
                    if progress_callback:
                        progress_callback(elapsed, total_duration)
                    time.sleep(0.05)

                sd.stop()
            except Exception as e:
                logger.error(f"Audio playback error: {e}")
            finally:
                self.is_playing = False
                if finished_callback:
                    finished_callback()

        t = threading.Thread(target=_play_worker, daemon=True)
        t.start()

    def stop(self):
        self._stop_event.set()
        self.is_playing = False
        try:
            sd.stop()
        except Exception:
            pass

# Global instances
global_recorder = AudioRecorder()
global_player = AudioPlayer()

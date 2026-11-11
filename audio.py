"""
audio.py - microphone input, utterance splitting and speech output for Hey Cook.

Flow:
    mic (sounddevice's background thread)
      -> queue of 30ms frames
      -> UtteranceSplitter (speech vs silence, energy-based)
      -> one numpy array per utterance  ->  (Whisper, in transcriber.py)

    speak(text) mutes the mic, talks via macOS `say`, then unmutes,
    so Hey Cook never hears (and answers) itself.
"""
from __future__ import annotations  # lets `float | None` hints work on Python 3.9

import collections
import queue
import subprocess
import threading
import time

import numpy as np
import sounddevice as sd

# ---- Tunable constants -----------------------------------------------------
SAMPLE_RATE = 16_000                               # Whisper expects 16 kHz mono
FRAME_MS = 30                                      # size of each chunk the mic hands us
FRAME_SAMPLES = SAMPLE_RATE * FRAME_MS // 1000     # = 480 samples per frame

PRE_ROLL_MS = 300       # audio kept from *before* speech started, so "hey" isn't clipped
END_SILENCE_MS = 800    # this much continuous silence = the utterance is over
MIN_SPEECH_MS = 250     # less loud audio than this = a cough / pan clatter, ignore it
MAX_UTTERANCE_S = 15    # hard cap so a running tap or extractor fan can't record forever


def rms(frame: np.ndarray) -> float:
    """Root-mean-square loudness of a frame. Silence ~0.001-0.005, speech ~0.02+."""
    return float(np.sqrt(np.mean(frame ** 2)))


class Microphone:
    """Producer side of producer/consumer: the audio thread only ever enqueues frames."""

    def __init__(self):
        self._frames: "queue.Queue[np.ndarray]" = queue.Queue()
        self._muted = threading.Event()  # thread-safe on/off flag
        self._stream = sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=1,
            dtype="float32",
            blocksize=FRAME_SAMPLES,
            callback=self._on_audio,
        )

    def _on_audio(self, indata, frames, time_info, status):
        # Runs on sounddevice's audio thread, ~33 times a second.
        # Rule: do almost nothing here. Anything slow = dropped audio.
        if status:
            print(f"[mic] {status}")
        if not self._muted.is_set():
            # .copy() matters: sounddevice reuses `indata`'s memory for the next chunk.
            self._frames.put(indata[:, 0].copy())

    def start(self):
        self._stream.start()

    def stop(self):
        self._stream.stop()
        self._stream.close()

    def read_frame(self, timeout=None) -> np.ndarray:
        """Consumer side: blocks until the next 30ms frame arrives."""
        return self._frames.get(timeout=timeout)

    def mute(self):
        self._muted.set()

    def unmute(self):
        # Throw away anything that slipped in around the switch, then listen again.
        while True:
            try:
                self._frames.get_nowait()
            except queue.Empty:
                break
        self._muted.clear()


class UtteranceSplitter:
    """Turns an endless stream of frames into discrete utterances."""

    def __init__(self, mic: Microphone, threshold: float | None = None):
        self.mic = mic
        self.threshold = threshold

    def calibrate(self, seconds: float = 1.5):
        """Measure the room's background noise, then set 'loud' to be well above it."""
        print("[audio] Calibrating - stay quiet for a moment...")
        n = int(seconds * 1000 / FRAME_MS)
        levels = [rms(self.mic.read_frame()) for _ in range(n)]
        noise = float(np.percentile(levels, 90))
        self.threshold = max(noise * 3.0, 0.01)
        print(f"[audio] noise={noise:.4f}  threshold={self.threshold:.4f}")

    def next_utterance(self) -> np.ndarray:
        """Block until someone says something; return it as one 1-D float32 array."""
        if self.threshold is None:
            self.calibrate()

        pre_roll = collections.deque(maxlen=PRE_ROLL_MS // FRAME_MS)
        speech: list[np.ndarray] = []
        silent_ms = 0
        speech_ms = 0

        while True:
            frame = self.mic.read_frame()
            loud = rms(frame) > self.threshold

            if not speech:
                # Waiting for speech: keep a short rolling buffer of recent audio.
                pre_roll.append(frame)
                if loud:
                    speech = list(pre_roll)   # include the lead-in so the first syllable survives
                    speech_ms = FRAME_MS
                    silent_ms = 0
                continue

            # Currently recording an utterance.
            speech.append(frame)
            if loud:
                speech_ms += FRAME_MS
                silent_ms = 0
            else:
                silent_ms += FRAME_MS

            too_long = len(speech) * FRAME_MS >= MAX_UTTERANCE_S * 1000
            if silent_ms >= END_SILENCE_MS or too_long:
                if speech_ms >= MIN_SPEECH_MS:
                    return np.concatenate(speech)
                # Too short to be words - reset and keep waiting.
                speech, silent_ms, speech_ms = [], 0, 0
                pre_roll.clear()


def speak(text: str, mic: Microphone, voice: str = "Daniel"):
    """Say `text` out loud with the mic muted, so we don't transcribe ourselves."""
    mic.mute()
    try:
        result = subprocess.run(["say", "-v", voice, text], capture_output=True)
        if result.returncode != 0:              # voice not installed -> system default
            subprocess.run(["say", text])
    finally:
        time.sleep(0.2)                          # let the room echo die away
        mic.unmute()


# ---- Quick manual test: `python audio.py` -----------------------------------
if __name__ == "__main__":
    mic = Microphone()
    mic.start()
    splitter = UtteranceSplitter(mic)
    splitter.calibrate()
    print("Talk. Each time you stop, I'll report how long you spoke. Ctrl+C to quit.")
    try:
        while True:
            audio = splitter.next_utterance()
            seconds = len(audio) / SAMPLE_RATE
            print(f"Got an utterance: {seconds:.2f}s")
            speak(f"That was {seconds:.1f} seconds", mic)
    except KeyboardInterrupt:
        mic.stop()

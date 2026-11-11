from __future__ import annotations

import re

from faster_whisper import WhisperModel

WAKE_FIRST = {"hey", "hay", "hi", "a"}
WAKE_SECOND = {"cook", "cooke", "kook", "cooks"}
WAKE_SEARCH_WORDS = 3

model = WhisperModel("base.en", device="cpu", compute_type="int8")


def transcribe(audio) -> str:
    segments, _ = model.transcribe(audio, language="en", vad_filter=True, beam_size=1)
    return " ".join(segment.text.strip() for segment in segments).strip()


def normalise(text: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", text.lower())


def split_wake(text: str) -> str | None:
    words = normalise(text).split()
    for i in range(min(WAKE_SEARCH_WORDS, len(words) - 1)):
        if words[i] in WAKE_FIRST and words[i + 1] in WAKE_SECOND:
            return " ".join(words[i + 2:])
    return None


if __name__ == "__main__":
    from audio import Microphone, UtteranceSplitter

    mic = Microphone()
    mic.start()
    splitter = UtteranceSplitter(mic)
    splitter.calibrate()
    print("Say the wake phrase + a question. Ctrl+C to stop.")
    try:
        while True:
            text = transcribe(splitter.next_utterance())
            print(f"RAW: {text!r}   ->   WAKE: {split_wake(text)!r}")
    except KeyboardInterrupt:
        mic.stop()

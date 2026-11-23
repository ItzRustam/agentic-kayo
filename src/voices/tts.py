"""Text-To-Speech conversion using gTTS and PyGame"""

from gtts import gTTS
import pygame
import tempfile
import os

pygame.mixer.init()


def tts(text: str, slow: bool = False):
    """Convert text to speech and play it."""

    if not text.strip():
        return

    tts = gTTS(text=text, lang="en", slow=slow, tld="us")

    # Temporary audio file
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
        audio_path = f.name

    try:
        tts.save(audio_path)

        pygame.mixer.music.load(audio_path)
        pygame.mixer.music.play()

        # Wait until playback finishes
        while pygame.mixer.music.get_busy():
            pygame.time.Clock().tick(10)

    finally:
        pygame.mixer.music.stop()
        pygame.mixer.music.unload()
        os.remove(audio_path)


tts("Hey, I'm Kayo and It's pretty cool!")
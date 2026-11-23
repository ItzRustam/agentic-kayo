import asyncio
import tempfile
import os

import edge_tts
import pygame


VOICE = "en-US-GuyNeural"
RATE = "+30%"
PITCH = "-20Hz"

pygame.mixer.init()


async def generate_audio(text: str, output_path: str):
    communicate = edge_tts.Communicate(
        text=text,
        voice=VOICE,
        rate=RATE,
        pitch=PITCH,
    )
    await communicate.save(output_path)


def speak(text: str):
    if not text.strip():
        return

    with tempfile.NamedTemporaryFile(
        suffix=".mp3",
        delete=False,
    ) as file:
        audio_path = file.name

    try:
        asyncio.run(generate_audio(text, audio_path))

        pygame.mixer.music.load(audio_path)
        pygame.mixer.music.play()

        clock = pygame.time.Clock()
        while pygame.mixer.music.get_busy():
            clock.tick(20)

    finally:
        pygame.mixer.music.stop()
        pygame.mixer.music.unload()

        if os.path.exists(audio_path):
            os.remove(audio_path)


speak("Hello. I am Kayo. How can I help you today?")
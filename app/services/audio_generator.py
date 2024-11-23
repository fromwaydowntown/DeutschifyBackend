# app/services/audio_generator.py
from io import BytesIO

import requests
import random
from app.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)

class AudioGenerator:
    def __init__(self):
        self.api_key = settings.OPENAI_API_KEY
        self.base_url = "https://api.openai.com/v1/audio/speech"
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        self.female_voices = ['echo', 'fable', 'nova', 'shimmer']
        self.male_voices = ['alloy', 'onyx']

    def get_random_voice(self):
        return random.choice(self.female_voices + self.male_voices)

    def generate_audio(self, text: str, voice: str):
        """
        Generates audio content from the provided text using the specified voice.
        Returns the audio content as a BytesIO object.
        """
        logger.info(f"Generating audio with voice: {voice}")

        data = {
            "model": "tts-1",
            "input": text,
            "voice": voice
        }

        try:
            logger.info("Sending request to TTS API for audio.")
            response = requests.post(self.base_url, headers=self.headers, json=data)
            response.raise_for_status()
            audio_content = response.content
            logger.info("Audio content received from TTS API.")
            return BytesIO(audio_content)
        except requests.exceptions.RequestException as e:
            logger.error(f"Error generating audio: {e}")
            if e.response is not None:
                logger.error(f"Response Content: {e.response.text}")
            return None
        except Exception as e:
            logger.error(f"An unexpected error occurred: {e}")
            return None
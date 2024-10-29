# app/services/audio_generator.py
import requests
import tempfile
import shutil
import os
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

    def generate_unique_suffix(self) -> int:
        return random.randint(1000, 9999)

    def generate_audio(self, text: str, voice: str) -> str:
        """
        Generates audio content from the provided text using the specified voice.
        Returns the path to the temporary audio file.
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

            # Write to a temporary file
            with tempfile.NamedTemporaryFile(delete=False, suffix='.mp3') as temp_audio:
                temp_audio.write(audio_content)
                temp_audio_path = temp_audio.name
            logger.info("Audio file generated and saved.")
            return temp_audio_path
        except requests.exceptions.RequestException as e:
            logger.error(f"Error generating audio: {e}")
            if e.response is not None:
                logger.error(f"Response Content: {e.response.text}")
            return None
        except Exception as e:
            logger.error(f"An unexpected error occurred: {e}")
            return None

    def save_audio(self, temp_audio_path: str, final_path: str):
        """
        Moves the temporary audio file to the final destination.
        """
        try:
            shutil.move(temp_audio_path, final_path)
            logger.info(f"Audio file moved to {final_path}")
        except Exception as e:
            logger.error(f"Failed to move audio file: {e}")
            raise

    def cleanup_temp_audio(self, temp_audio_path: str):
        """
        Removes the temporary audio file.
        """
        try:
            if os.path.exists(temp_audio_path):
                os.remove(temp_audio_path)
                logger.info(f"Temporary audio file {temp_audio_path} removed.")
        except Exception as e:
            logger.error(f"Failed to remove temporary audio file: {e}")
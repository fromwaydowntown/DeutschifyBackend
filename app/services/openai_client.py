# app/services/openai_client.py
import requests
import json
from app.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)

class OpenAIClient:
    def __init__(self):
        self.api_key = settings.OPENAI_API_KEY
        self.base_url = "https://api.openai.com/v1/chat/completions"
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }

    def adapt_text_with_prompt(self, prompt):
        """
        Uses OpenAI to process the text with a custom prompt.
        """
        data = {
            "model": "gpt-4o-mini",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 1000,
            "temperature": 0.7
        }

        try:
            logger.info("Sending request to OpenAI API with custom prompt.")
            response = requests.post(self.base_url, headers=self.headers, json=data)
            response.raise_for_status()
            result = response.json()
            adapted_text = result['choices'][0]['message']['content'].strip()
            logger.info("Text processed successfully.")
            return adapted_text
        except requests.exceptions.RequestException as e:
            logger.error(f"Error processing text with custom prompt: {e}")
            return None
        except KeyError as e:
            logger.error(f"Unexpected response format from OpenAI API: {e}")
            return None

    def adapt_text_to_level(self, text, level):
        """
        Uses OpenAI to adapt the text to the user's German level (A1, A2, B1, etc.).
        """
        if not text.strip():
            logger.warning("Empty text provided for adaptation.")
            return ''

        prompt = (
            f"Bitte passe den folgenden Text an das deutsche Niveau {level} an. "
            "Antworte nur mit dem angepassten Text, ohne zusätzliche Erläuterungen oder Kommentare.\n\n"
            f"{text}"
        )

        data = {
            "model": "gpt-4o-mini",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.7
        }

        try:
            logger.info(f"Sending request to OpenAI API to adapt text to level {level}.")
            response = requests.post(self.base_url, headers=self.headers, json=data)
            response.raise_for_status()
            result = response.json()
            adapted_text = result['choices'][0]['message']['content']
            logger.info("Text adapted successfully.")
            return adapted_text.strip()
        except requests.exceptions.RequestException as e:
            logger.error(f"Error adapting text to level {level}: {e}")
            return None

    def extract_articles(self, prompt):
        """
        Uses the OpenAI API to extract articles from the given prompt.
        """
        data = {
            "model": "gpt-4o-mini",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 2000,
            "temperature": 0.5
        }

        try:
            logger.info("Sending request to OpenAI API to extract articles.")
            response = requests.post(self.base_url, headers=self.headers, json=data)
            response.raise_for_status()
            result = response.json()
            extracted_text = result['choices'][0]['message']['content'].strip()
            logger.info("Articles extracted successfully.")
            return extracted_text
        except requests.exceptions.RequestException as e:
            logger.error(f"OpenAI API error during article extraction: {e}")
            return ''

    def extract_article_details(self, prompt):
        """
        Uses the OpenAI API to extract article details from the given prompt.
        """
        data = {
            "model": "gpt-4o-mini",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 1000,
            "temperature": 0.5
        }

        try:
            logger.info("Sending request to OpenAI API to extract article details.")
            response = requests.post(self.base_url, headers=self.headers, json=data)
            response.raise_for_status()
            result = response.json()
            extracted_details = result['choices'][0]['message']['content'].strip()
            logger.info("Article details extracted successfully.")
            return extracted_details
        except requests.exceptions.RequestException as e:
            logger.error(f"OpenAI API error during article details extraction: {e}")
            return ''

    def get_token_count(self, text):
        """
        Estimates the token count of the given text.
        """
        # Simple approximation: 1 token ~ 4 characters
        token_count = int(len(text) / 4)
        return token_count

    def get_char_limit_for_tokens(self, token_limit):
        """
        Returns character limit for the given token limit.
        """
        return token_limit * 4

    def generate_questions(self, text: str) -> str:
        """
        Generates comprehension questions based on the provided text.
        """
        prompt = f"Lies den folgenden Text und erstelle drei Verständnisfragen dazu:\n\n{text}\n\nFragen:"
        data = {
            "model": "gpt-4o-mini",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.7
        }

        try:
            logger.info("Sending request to OpenAI API for questions.")
            response = requests.post(self.base_url, headers=self.headers, json=data)
            response.raise_for_status()
            result = response.json()
            questions = result['choices'][0]['message']['content'].strip()
            logger.info("Questions received from OpenAI API.")
            return questions
        except requests.exceptions.RequestException as e:
            logger.error(f"Error generating questions: {e}")
            return None

    def generate_vocabulary(self, text: str) -> str:
        """
        Extracts key vocabulary from the text with English translations.
        """
        prompt = (
            f"Extrahiere die wichtigsten Vokabeln aus dem folgenden Text und gib eine Liste mit Übersetzungen ins Englische:\n\n{text}\n\n"
            "Vokabelliste (verwende immer den bestimmten Artikel):"
        )
        data = {
            "model": "gpt-4o-mini",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.7
        }

        try:
            logger.info("Sending request to OpenAI API for vocabulary.")
            response = requests.post(self.base_url, headers=self.headers, json=data)
            response.raise_for_status()
            result = response.json()
            vocabulary = result['choices'][0]['message']['content'].strip()
            logger.info("Vocabulary received from OpenAI API.")
            return vocabulary
        except requests.exceptions.RequestException as e:
            logger.error(f"Error generating vocabulary: {e}")
            return None

    def generate_feedback(self, text: str, questions: str, user_answers: list) -> str:
        """
        Generates feedback for the user's answers based on the original text and questions.
        """
        prompt = (
            f"Hier ist ein Text:\n\n{text}\n\n"
            f"Hier sind die Fragen:\n{questions}\n\n"
            f"Hier sind die Antworten des Lerners:\n" + "\n".join(user_answers) +
            "\n\nBitte überprüfe die Antworten und gib Feedback auf Deutsch:"
        )
        data = {
            "model": "gpt-4o-mini",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.7
        }

        try:
            logger.info("Sending request to OpenAI API for feedback.")
            response = requests.post(self.base_url, headers=self.headers, json=data)
            response.raise_for_status()
            result = response.json()
            feedback = result['choices'][0]['message']['content'].strip()
            logger.info("Feedback received from OpenAI API.")
            return feedback
        except requests.exceptions.RequestException as e:
            logger.error(f"Error generating feedback: {e}")
            return None

    def shorten_title(self, title: str, max_length: int = 30) -> str:
        """
        Generates a concise summary title suitable for button display.
        """
        if len(title) <= max_length:
            return title  # Title is already short enough

        prompt = (
            f"Verkürze den folgenden Titel auf maximal {max_length} Zeichen, sodass er die Hauptidee enthält und für eine Liste geeignet ist:\n\n"
            f"Titel: {title}\n\n"
            "Kurzer Titel:"
        )

        data = {
            "model": "gpt-4o-mini",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.5,
            "max_tokens": 20
        }

        try:
            logger.info(f"Generating short title for: {title}")
            response = requests.post(self.base_url, headers=self.headers, json=data)
            response.raise_for_status()
            result = response.json()
            short_title = result['choices'][0]['message']['content'].strip()
            logger.info(f"Short title generated: {short_title}")
            return short_title
        except requests.exceptions.RequestException as e:
            logger.error(f"Error generating short title: {e}")
            # Fallback to truncating the title
            return title[:max_length] + "..."

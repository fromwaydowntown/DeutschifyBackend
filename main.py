import logging
import os
import random
import json
import urllib.request
import urllib.error
import datetime
import tempfile
import subprocess
from io import BytesIO

from telegram import (
    Update,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    Bot
)
from telegram.ext import (
    Updater,
    CommandHandler,
    MessageHandler,
    Filters,
    CallbackContext,
    ConversationHandler,
    CallbackQueryHandler,
    JobQueue
)

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
logger = logging.getLogger(__name__)

# Define conversation states
LEVEL, TOPIC, STORY_SENT, ANSWERING_QUESTIONS, CHECKING_VOCABULARY, CHECKING_ANSWERS = range(6)

# Fetch tokens securely from environment variables
openai_api_key = os.environ.get('OPENAI_API_KEY')
telegram_bot_token = os.environ.get('TELEGRAM_BOT_TOKEN')

# List of topics related to living in Germany as an expat learning German
expat_topics = [
    "Einkaufen im deutschen Supermarkt",
    "Öffentliche Verkehrsmittel nutzen",
    "Wohnungssuche in Deutschland",
    "Deutsche Bürokratie verstehen",
    "Freizeitaktivitäten in deiner Stadt",
    "Arbeiten in einem deutschen Unternehmen",
    "Deutschsprachige Freunde finden",
    "Kulturelle Unterschiede erleben",
    "Deutsche Feste und Traditionen",
    "Besuch beim Arzt in Deutschland",
    # Add more topics as needed
]

# Define voice lists based on gender
male_voices = ['alloy', 'onyx']     # Replace with actual male voice names from your TTS service
female_voices = ['echo', 'fable', 'nova', 'shimmer']  # Replace with actual female voice names from your TTS service

# Path to the static image to be used in the video note (if applicable)
image_url = "https://www.stuttgarter-nachrichten.de/media.media.2181c3bc-5761-482c-9a2a-fa15a51b9dbb.original1024.jpg"

def start(update: Update, context: CallbackContext) -> int:
    logger.info("User started the bot.")
    keyboard = [
        [InlineKeyboardButton("📝 Start", callback_data='start')],
        [InlineKeyboardButton("📖 Tägliche Geschichte abonnieren", callback_data='subscribe_daily')],
        [InlineKeyboardButton("📚 Vokabeln überprüfen", callback_data='review_vocabulary')],
        [InlineKeyboardButton("🔄 Reset", callback_data='reset')],
        [InlineKeyboardButton("🌐 Level ändern", callback_data='change_level')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text(
        "👋 Willkommen zum Deutsch Lern Bot! Bitte wähle eine Option:", reply_markup=reply_markup
    )
    return LEVEL

def button_handler(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    data = query.data
    logger.info(f"Button clicked: {data}")
    query.answer()

    if data == 'start':
        return ask_level(query, context)
    elif data == 'change_level':
        return ask_level(query, context)
    elif data == 'reset':
        context.user_data.clear()
        logger.info("User reset the bot.")
        query.edit_message_text("🔄 Bot wurde zurückgesetzt. Bitte starte erneut.")
        return start(update, context)  # Return to start
    elif data == 'subscribe_daily':
        user_id = update.effective_user.id
        context.bot_data.setdefault('subscribers', set()).add(user_id)
        logger.info(f"User {user_id} subscribed to daily stories.")
        query.edit_message_text("✅ Du hast dich erfolgreich für tägliche Geschichten angemeldet!")

        # Provide options again
        keyboard = [
            [InlineKeyboardButton("📝 Start", callback_data='start')],
            [InlineKeyboardButton("📖 Tägliche Geschichte abbestellen", callback_data='unsubscribe_daily')],
            [InlineKeyboardButton("📚 Vokabeln überprüfen", callback_data='review_vocabulary')],
            [InlineKeyboardButton("🔄 Reset", callback_data='reset')],
            [InlineKeyboardButton("🌐 Level ändern", callback_data='change_level')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        query.message.reply_text("Was möchtest du als Nächstes tun?", reply_markup=reply_markup)
        return LEVEL
    elif data == 'unsubscribe_daily':
        user_id = update.effective_user.id
        context.bot_data.setdefault('subscribers', set()).discard(user_id)
        logger.info(f"User {user_id} unsubscribed from daily stories.")
        query.edit_message_text("❌ Du hast dich von täglichen Geschichten abgemeldet.")

        # Provide options again
        keyboard = [
            [InlineKeyboardButton("📝 Start", callback_data='start')],
            [InlineKeyboardButton("📖 Tägliche Geschichte abonnieren", callback_data='subscribe_daily')],
            [InlineKeyboardButton("📚 Vokabeln überprüfen", callback_data='review_vocabulary')],
            [InlineKeyboardButton("🔄 Reset", callback_data='reset')],
            [InlineKeyboardButton("🌐 Level ändern", callback_data='change_level')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        query.message.reply_text("Was möchtest du als Nächstes tun?", reply_markup=reply_markup)
        return LEVEL
    elif data in ['A1', 'A2', 'B1']:
        context.user_data['level'] = data
        # Store user's level in bot_data for daily stories
        user_id = update.effective_user.id
        context.bot_data.setdefault('user_levels', {})[user_id] = data
        logger.info(f"User selected level: {data}")
        return ask_topic(query, context)
    elif data == 'get_questions':
        return send_questions(query, context)
    elif data == 'show_text':
        return send_text(query, context)
    elif data == 'change_topic':
        return ask_topic(query, context)
    elif data == 'check_vocabulary':
        return send_vocabulary(query, context)
    elif data == 'review_vocabulary':
        return review_vocabulary(query, context)
    elif data == 'check_answers':
        return check_answers(query, context)
    else:
        query.edit_message_text("Unbekannte Option.")

        # Provide options again
        keyboard = [
            [InlineKeyboardButton("📝 Start", callback_data='start')],
            [InlineKeyboardButton("📖 Tägliche Geschichte abonnieren", callback_data='subscribe_daily')],
            [InlineKeyboardButton("📚 Vokabeln überprüfen", callback_data='review_vocabulary')],
            [InlineKeyboardButton("🔄 Reset", callback_data='reset')],
            [InlineKeyboardButton("🌐 Level ändern", callback_data='change_level')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        query.message.reply_text("Bitte wähle eine Option:", reply_markup=reply_markup)
        return LEVEL

def ask_level(entry_point, context) -> int:
    logger.info("Asking user for language level.")
    keyboard = [
        [InlineKeyboardButton("A1", callback_data='A1'), InlineKeyboardButton("A2", callback_data='A2')],
        [InlineKeyboardButton("B1", callback_data='B1')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    if isinstance(entry_point, Update):
        entry_point.message.reply_text("Bitte wähle dein Deutschniveau:", reply_markup=reply_markup)
    else:
        entry_point.edit_message_text("Bitte wähle dein Deutschniveau:", reply_markup=reply_markup)
    return LEVEL

def ask_topic(entry_point, context) -> int:
    logger.info("Asking user for topic.")
    if isinstance(entry_point, Update):
        entry_point.message.reply_text("📝 Gib bitte das Thema ein, über das du eine Geschichte möchtest:")
    else:
        entry_point.edit_message_text("📝 Gib bitte das Thema ein, über das du eine Geschichte möchtest:")
    return TOPIC

def receive_topic(update: Update, context: CallbackContext) -> int:
    topic = update.message.text
    user_level = context.user_data.get('level')

    if not user_level:
        update.message.reply_text("Bitte wähle zuerst dein Deutschniveau.")
        return LEVEL

    logger.info(f"User provided topic: {topic}")
    update.message.reply_text("✨ Geschichte wird erstellt, bitte warten... ⏳")
    return generate_and_send_story(update, context, topic, user_level)

def generate_and_send_story(update: Update, context: CallbackContext, topic: str, user_level: str) -> int:
    # Step 1: Generate the story based on the topic and user level
    story = generate_story(topic, user_level)

    if not story:
        logger.error("Failed to generate story.")
        update.message.reply_text('Entschuldigung, es gab einen Fehler bei der Geschichte-Generierung.')
        return LEVEL

    context.user_data['story'] = story
    update.message.reply_text("🎧 Die Geschichte wird jetzt generiert...")
    logger.info("Story generated successfully.")

    # Step 2: Generate the audio from the story
    # Voice selection based on the video
    video_options = ['scholz.mov', 'merkel.mov']
    selected_video = random.choice(video_options)
    logger.info(f"Selected video: {selected_video}")

    # Define voice lists
    if selected_video == 'scholz.mov':
        voice_type = 'male'
        available_voices = male_voices
    elif selected_video == 'merkel.mov':
        voice_type = 'female'
        available_voices = female_voices
    else:
        voice_type = 'neutral'
        available_voices = male_voices + female_voices  # Default to all voices

    # Select a voice based on the video
    selected_voice = random.choice(available_voices)
    logger.info(f"Selected voice ({voice_type}): {selected_voice}")

    # Generate audio with the selected voice
    audio_file = generate_audio(story, selected_voice)
    if not audio_file:
        logger.error("Failed to generate audio.")
        update.message.reply_text('Entschuldigung, es gab einen Fehler bei der Audio-Generierung.')
        return LEVEL

    # Ensure the selected video exists
    if not os.path.exists(selected_video):
        logger.error(f"Video file {selected_video} does not exist.")
        update.message.reply_text("Entschuldigung, das ausgewählte Basisvideo ist nicht verfügbar.")
        os.remove(audio_file)  # Clean up audio file
        return LEVEL

    # Step 3: Create a temporary file for the output video
    with tempfile.NamedTemporaryFile(delete=False, suffix='.mp4') as temp_video:
        output_video_path = temp_video.name

    try:
        # Step 4: Define the FFmpeg command to loop the video and combine with audio
        ffmpeg_command = [
            'ffmpeg',
            '-y',  # Overwrite output files without asking
            '-stream_loop', '-1',  # Loop the video indefinitely
            '-i', selected_video,  # Input video file
            '-i', audio_file,  # Input audio file
            '-c:v', 'libx264',  # Video codec
            '-c:a', 'aac',  # Audio codec
            '-b:a', '128k',  # Audio bitrate
            '-ar', '44100',  # Audio sample rate
            '-ac', '1',  # Set audio channels to mono
            '-shortest',  # Stop encoding when the shortest input ends (audio)
            '-vf', 'scale=240:240,setsar=1:1',  # Scale video to 240x240 and set SAR
            '-map', '0:v:0',  # Map the first video stream
            '-map', '1:a:0',  # Map the first audio stream
            '-f', 'mp4',  # Output format
            output_video_path  # Output file path
        ]

        logger.info(f"Running FFmpeg command: {' '.join(ffmpeg_command)}")

        # Step 5: Execute the FFmpeg command
        process = subprocess.Popen(
            ffmpeg_command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        stdout_data, stderr_data = process.communicate()

        # Optional: Log FFmpeg's stdout and stderr for debugging
        logger.debug(f"FFmpeg stdout: {stdout_data.decode()}")
        logger.debug(f"FFmpeg stderr: {stderr_data.decode()}")

        # Check for FFmpeg errors
        if process.returncode != 0:
            logger.error(f"FFmpeg failed: {stderr_data.decode()}")
            update.message.reply_text("Entschuldigung, es gab einen Fehler bei der Video-Generierung.")
            os.remove(audio_file)  # Clean up audio file
            os.remove(output_video_path)  # Clean up video file
            return LEVEL

        # Step 6: Verify the output video has an audio stream
        probe_output = subprocess.run(
            [
                'ffprobe',
                '-v', 'error',
                '-show_entries', 'stream=codec_type',
                '-of', 'default=noprint_wrappers=1:nokey=1',
                output_video_path
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        streams = probe_output.stdout.decode().strip().split('\n')
        if 'audio' not in streams:
            logger.error("FFmpeg did not embed audio into the video.")
            update.message.reply_text("Entschuldigung, es gab einen Fehler beim Einbetten der Audio in das Video.")
            os.remove(audio_file)  # Clean up audio file
            os.remove(output_video_path)  # Clean up video file
            return LEVEL

        video_size = os.path.getsize(output_video_path)
        logger.info(f"Video created successfully with size {video_size} bytes.")

    except subprocess.CalledProcessError as e:
        logger.error(f"FFmpeg failed: {e}")
        update.message.reply_text("Entschuldigung, es gab einen Fehler bei der Video-Generierung.")
        os.remove(audio_file)  # Clean up audio file
        os.remove(output_video_path)  # Clean up video file
        return LEVEL
    except Exception as e:
        logger.error(f"An unexpected error occurred during video processing: {e}")
        update.message.reply_text("Entschuldigung, es gab einen unerwarteten Fehler bei der Video-Generierung.")
        os.remove(audio_file)  # Clean up audio file
        os.remove(output_video_path)  # Clean up video file
        return LEVEL

    # Step 7: Send the video as a regular video message
    try:
        with open(output_video_path, 'rb') as video_file:
            update.message.reply_video(
                video=video_file,
                caption="🎥 Hier ist deine Geschichte!",
                supports_streaming=True
            )
        logger.info("Video sent to user.")
    except Exception as e:
        logger.error(f"Failed to send video: {e}")
        update.message.reply_text("Entschuldigung, es gab einen Fehler beim Senden des Videos.")
        return LEVEL
    finally:
        os.remove(output_video_path)  # Clean up video file

    # Step 8: Send the options keyboard
    keyboard = [
        [InlineKeyboardButton("❓ Fragen erhalten", callback_data='get_questions')],
        [InlineKeyboardButton("📄 Text anzeigen", callback_data='show_text')],
        [InlineKeyboardButton("📚 Vokabeln anzeigen", callback_data='check_vocabulary')],
        [InlineKeyboardButton("🔄 Thema wechseln", callback_data='change_topic')],
        [InlineKeyboardButton("🌐 Level ändern", callback_data='change_level')],
        [InlineKeyboardButton("🔄 Reset", callback_data='reset')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text("Was möchtest du als Nächstes tun?", reply_markup=reply_markup)
    return STORY_SENT

def generate_audio(text: str, voice: str) -> str:
    logger.info(f"Generating audio with voice: {voice}")

    url = "https://api.openai.com/v1/audio/speech"  # Replace with your actual TTS API endpoint
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {openai_api_key}"
    }
    data = {
        "model": "tts-1",  # Replace with your actual TTS model if different
        "input": text,
        "voice": voice
    }

    try:
        logger.info("Sending request to TTS API for audio.")
        request = urllib.request.Request(
            url, data=json.dumps(data).encode('utf-8'), headers=headers
        )
        response = urllib.request.urlopen(request)
        audio_content = response.read()

        # Write to a temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix='.ogg') as temp_audio:
            temp_audio.write(audio_content)
            temp_audio_path = temp_audio.name
        logger.info("Audio file generated and saved.")
        return temp_audio_path
    except urllib.error.HTTPError as e:
        error_response = e.read().decode()
        error_message = json.loads(error_response).get('error', {}).get('message', 'Unknown error')
        logger.error(f"Error generating audio: {e.code} - {error_message}")
        return None
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        return None

def send_questions(query, context) -> int:
    story = context.user_data.get('story')
    if not story:
        query.edit_message_text("Es gibt keine Geschichte, um Fragen zu generieren.")
        return STORY_SENT

    logger.info("Generating questions based on the story.")
    query.edit_message_text("✨ Fragen werden generiert, bitte warten... ⏳")
    questions = generate_questions(story)
    if questions:
        context.user_data['questions'] = questions
        context.user_data['user_answers'] = []  # Reset any previous answers
        query.message.reply_text("Hier sind einige Fragen zur Geschichte: ❓\n" + questions)
        query.message.reply_text("Bitte sende deine Antworten einzeln. 💬")
        # Provide options to the user
        keyboard = [
            [InlineKeyboardButton("✅ Antworten überprüfen", callback_data='check_answers')],
            [InlineKeyboardButton("📄 Text anzeigen", callback_data='show_text')],
            [InlineKeyboardButton("📚 Vokabeln anzeigen", callback_data='check_vocabulary')],
            [InlineKeyboardButton("🔄 Thema wechseln", callback_data='change_topic')],
            [InlineKeyboardButton("🔄 Reset", callback_data='reset')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        query.message.reply_text("Du kannst jederzeit Optionen wählen:", reply_markup=reply_markup)
        return ANSWERING_QUESTIONS
    else:
        logger.error("Failed to generate questions.")
        query.message.reply_text("Entschuldigung, es gab einen Fehler beim Generieren der Fragen.")

        # Provide options again
        keyboard = [
            [InlineKeyboardButton("📝 Start", callback_data='start')],
            [InlineKeyboardButton("📖 Tägliche Geschichte abonnieren", callback_data='subscribe_daily')],
            [InlineKeyboardButton("📚 Vokabeln überprüfen", callback_data='review_vocabulary')],
            [InlineKeyboardButton("🔄 Reset", callback_data='reset')],
            [InlineKeyboardButton("🌐 Level ändern", callback_data='change_level')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        query.message.reply_text("Bitte wähle eine Option:", reply_markup=reply_markup)
        return LEVEL

def send_text(query, context) -> int:
    story = context.user_data.get('story')
    if not story:
        query.edit_message_text("Es gibt keinen Text zum Anzeigen.")
        return STORY_SENT
    logger.info("Sending story text to user.")
    query.message.reply_text("Hier ist der Text der Geschichte: 📄\n" + story)
    # Provide options again
    keyboard = [
        [InlineKeyboardButton("❓ Fragen erhalten", callback_data='get_questions')],
        [InlineKeyboardButton("📚 Vokabeln anzeigen", callback_data='check_vocabulary')],
        [InlineKeyboardButton("🔄 Thema wechseln", callback_data='change_topic')],
        [InlineKeyboardButton("🌐 Level ändern", callback_data='change_level')],
        [InlineKeyboardButton("🔄 Reset", callback_data='reset')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    query.message.reply_text("Was möchtest du als Nächstes tun?", reply_markup=reply_markup)
    return STORY_SENT

def send_vocabulary(query, context) -> int:
    story = context.user_data.get('story')
    if not story:
        query.edit_message_text("Es gibt keinen Text, um Vokabeln zu extrahieren.")
        return STORY_SENT

    logger.info("Extracting vocabulary from the story.")
    query.edit_message_text("🔍 Vokabeln werden extrahiert, bitte warten... ⏳")
    vocabulary = generate_vocabulary(story)
    if vocabulary:
        query.message.reply_text("Hier sind einige Vokabeln aus der Geschichte: 📚\n" + vocabulary)

        # Store vocabulary for tracking
        user_id = query.from_user.id
        user_vocab = context.bot_data.setdefault('user_vocab', {})
        user_vocab.setdefault(user_id, []).extend(vocabulary.split('\n'))
        logger.info(f"Vocabulary stored for user {user_id}.")

    else:
        logger.error("Failed to generate vocabulary.")
        query.message.reply_text("Entschuldigung, es gab einen Fehler beim Extrahieren der Vokabeln.")
    # Provide options again
    keyboard = [
        [InlineKeyboardButton("❓ Fragen erhalten", callback_data='get_questions')],
        [InlineKeyboardButton("📄 Text anzeigen", callback_data='show_text')],
        [InlineKeyboardButton("🔄 Thema wechseln", callback_data='change_topic')],
        [InlineKeyboardButton("🔄 Reset", callback_data='reset')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    query.message.reply_text("Was möchtest du als Nächstes tun?", reply_markup=reply_markup)
    return STORY_SENT

def review_vocabulary(query, context) -> int:
    user_id = query.from_user.id
    user_vocab = context.bot_data.get('user_vocab', {}).get(user_id, [])
    if user_vocab:
        unique_vocab = list(set(user_vocab))
        vocab_text = "\n".join(unique_vocab)
        query.message.reply_text("Hier ist deine gesammelte Vokabelliste: 📚\n" + vocab_text)
    else:
        query.message.reply_text("Du hast noch keine Vokabeln gesammelt.")
    # Provide options again
    keyboard = [
        [InlineKeyboardButton("📝 Start", callback_data='start')],
        [InlineKeyboardButton("📖 Tägliche Geschichte abbestellen", callback_data='unsubscribe_daily')],
        [InlineKeyboardButton("🔄 Reset", callback_data='reset')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    query.message.reply_text("Was möchtest du als Nächstes tun?", reply_markup=reply_markup)
    return LEVEL

def receive_answer(update: Update, context: CallbackContext) -> int:
    user_answer = update.message.text
    context.user_data.setdefault('user_answers', []).append(user_answer)
    logger.info(f"User provided answer: {user_answer}")
    update.message.reply_text("Antwort erhalten. 😊")
    # Provide options to check answers or continue
    keyboard = [
        [InlineKeyboardButton("✅ Antworten überprüfen", callback_data='check_answers')],
        [InlineKeyboardButton("📄 Text anzeigen", callback_data='show_text')],
        [InlineKeyboardButton("🔄 Thema wechseln", callback_data='change_topic')],
        [InlineKeyboardButton("🔄 Reset", callback_data='reset')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text("Du kannst weitere Antworten senden oder Optionen wählen:", reply_markup=reply_markup)
    return ANSWERING_QUESTIONS

def check_answers(query, context) -> int:
    story = context.user_data.get('story')
    questions = context.user_data.get('questions')
    user_answers = context.user_data.get('user_answers', [])

    if not story or not questions or not user_answers:
        query.edit_message_text("Es gibt keine Antworten zum Überprüfen.")
        return STORY_SENT

    logger.info("Checking user's answers.")
    query.edit_message_text("🔎 Antworten werden überprüft, bitte warten... ⏳")
    feedback = generate_feedback(story, questions, user_answers)
    if feedback:
        query.message.reply_text("Hier ist das Feedback zu deinen Antworten: ✅\n" + feedback)
    else:
        logger.error("Failed to generate feedback.")
        query.message.reply_text("Entschuldigung, es gab einen Fehler beim Überprüfen der Antworten.")
    # Provide options again
    keyboard = [
        [InlineKeyboardButton("❓ Fragen erhalten", callback_data='get_questions')],
        [InlineKeyboardButton("📄 Text anzeigen", callback_data='show_text')],
        [InlineKeyboardButton("📚 Vokabeln anzeigen", callback_data='check_vocabulary')],
        [InlineKeyboardButton("🔄 Thema wechseln", callback_data='change_topic')],
        [InlineKeyboardButton("🌐 Level ändern", callback_data='change_level')],
        [InlineKeyboardButton("🔄 Reset", callback_data='reset')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    query.message.reply_text("Was möchtest du als Nächstes tun?", reply_markup=reply_markup)
    return STORY_SENT

def generate_feedback(story: str, questions: str, user_answers: list) -> str:
    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {openai_api_key}"
    }
    prompt = (
        f"Hier ist eine Geschichte:\n\n{story}\n\n"
        f"Hier sind die Fragen:\n{questions}\n\n"
        f"Hier sind die Antworten des Lerners:\n" + "\n".join(user_answers) +
        "\n\nBitte überprüfe die Antworten und gib Feedback auf Deutsch:"
    )
    data = {
        "model": "gpt-4o-mini",
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.7
    }

    try:
        logger.info("Sending request to OpenAI API for feedback.")
        request = urllib.request.Request(
            url, data=json.dumps(data).encode('utf-8'), headers=headers
        )
        response = urllib.request.urlopen(request)
        response_data = json.loads(response.read())
        feedback = response_data['choices'][0]['message']['content'].strip()
        logger.info("Feedback received from OpenAI API.")
        return feedback
    except urllib.error.HTTPError as e:
        error_response = e.read().decode()
        error_message = json.loads(error_response).get('error', {}).get('message', 'Unknown error')
        logger.error(f"Error generating feedback: {e.code} - {error_message}")
        return None
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        return None

def generate_vocabulary(story: str) -> str:
    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {openai_api_key}"
    }
    prompt = (
        f"Extrahiere die wichtigsten Vokabeln aus dem folgenden Text und gib eine Liste mit Übersetzungen ins Englische:\n\n{story}\n\n"
        "Vokabelliste (immer nutzen DER DIE DAS):"
    )
    data = {
        "model": "gpt-4o-mini",
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.7
    }

    try:
        logger.info("Sending request to OpenAI API for vocabulary.")
        request = urllib.request.Request(
            url, data=json.dumps(data).encode('utf-8'), headers=headers
        )
        response = urllib.request.urlopen(request)
        response_data = json.loads(response.read())
        vocabulary = response_data['choices'][0]['message']['content'].strip()
        logger.info("Vocabulary received from OpenAI API.")
        return vocabulary
    except urllib.error.HTTPError as e:
        error_response = e.read().decode()
        error_message = json.loads(error_response).get('error', {}).get('message', 'Unknown error')
        logger.error(f"Error generating vocabulary: {e.code} - {error_message}")
        return None
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        return None

def generate_questions(story: str) -> str:
    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {openai_api_key}"
    }
    prompt = f"Lies den folgenden Text und erstelle drei Verständnisfragen dazu:\n\n{story}\n\nFragen:"
    data = {
        "model": "gpt-4o-mini",
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.7
    }

    try:
        logger.info("Sending request to OpenAI API for questions.")
        request = urllib.request.Request(
            url, data=json.dumps(data).encode('utf-8'), headers=headers
        )
        response = urllib.request.urlopen(request)
        response_data = json.loads(response.read())
        questions = response_data['choices'][0]['message']['content'].strip()
        logger.info("Questions received from OpenAI API.")
        return questions
    except urllib.error.HTTPError as e:
        error_response = e.read().decode()
        error_message = json.loads(error_response).get('error', {}).get('message', 'Unknown error')
        logger.error(f"Error generating questions: {e.code} - {error_message}")
        return None
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        return None

def generate_story(topic: str, level: str) -> str:
    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {openai_api_key}"
    }
    prompt = (
        f"Erstelle eine interessante Geschichte auf Deutsch über '{topic}', "
        f"die für Deutschlerner auf Niveau {level} geeignet ist. "
        f"Die Geschichte sollte MAXIMUM 60 sekunden beim Vorlesen dauern und so gestaltet sein, dass man anschließend einfache Fragen dazu stellen kann. "
        f"Verwende nützliches Vokabular, das für eine nachfolgende Übung hilfreich ist, und baue dabei alltägliche Themen ein, die das Sprachverständnis fördern."
    )
    data = {
        "model": "gpt-4o-mini",
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.7
    }

    try:
        logger.info("Sending request to OpenAI API for story.")
        request = urllib.request.Request(url, data=json.dumps(data).encode('utf-8'), headers=headers)
        response = urllib.request.urlopen(request)
        response_data = json.loads(response.read())
        story = response_data['choices'][0]['message']['content'].strip()
        logger.info("Story received from OpenAI API.")
        return story
    except urllib.error.HTTPError as e:
        error_response = e.read().decode()
        error_message = json.loads(error_response).get('error', {}).get('message', 'Unknown error')
        logger.error(f"Error generating story: {e.code} - {error_message}")
        return None
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        return None

def generate_audio(text: str, voice: str) -> str:
    logger.info(f"Generating audio with voice: {voice}")

    url = "https://api.openai.com/v1/audio/speech"  # Replace with your actual TTS API endpoint
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {openai_api_key}"
    }
    data = {
        "model": "tts-1",  # Replace with your actual TTS model if different
        "input": text,
        "voice": voice
    }

    try:
        logger.info("Sending request to TTS API for audio.")
        request = urllib.request.Request(
            url, data=json.dumps(data).encode('utf-8'), headers=headers
        )
        response = urllib.request.urlopen(request)
        audio_content = response.read()

        # Write to a temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix='.ogg') as temp_audio:
            temp_audio.write(audio_content)
            temp_audio_path = temp_audio.name
        logger.info("Audio file generated and saved.")
        return temp_audio_path
    except urllib.error.HTTPError as e:
        error_response = e.read().decode()
        error_message = json.loads(error_response).get('error', {}).get('message', 'Unknown error')
        logger.error(f"Error generating audio: {e.code} - {error_message}")
        return None
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        return None

def cancel(update: Update, context: CallbackContext) -> int:
    logger.info("User cancelled the conversation.")
    update.message.reply_text('Auf Wiedersehen! 👋')
    return ConversationHandler.END

def level_received(update: Update, context: CallbackContext) -> int:
    user_level = update.message.text.upper()
    if user_level not in ['A1', 'A2', 'B1']:
        update.message.reply_text(
            "Bitte gib ein gültiges Niveau ein (A1, A2, B1):"
        )
        return LEVEL
    context.user_data['level'] = user_level
    # Store user's level in bot_data for daily stories
    user_id = update.effective_user.id
    context.bot_data.setdefault('user_levels', {})[user_id] = user_level
    logger.info(f"User provided level: {user_level}")
    return ask_topic(update, context)

def send_daily_story(context: CallbackContext):
    job = context.job
    subscribers = context.bot_data.get('subscribers', set())
    logger.info(f"Sending daily story to subscribers: {subscribers}")

    for user_id in subscribers:
        try:
            user_level = context.bot_data.get('user_levels', {}).get(user_id, 'A1')  # Default to 'A1'
            topic = random.choice(expat_topics)
            bot = context.bot

            # Send a message to the user
            chat_id = user_id
            bot.send_message(chat_id, "Guten Morgen! Hier ist deine tägliche Geschichte. 📖")

            # Generate and send the story
            # Create a dummy Update and CallbackContext for the function
            # Note: This is a workaround since we don't have an actual Update object
            update = Update(update_id=0, message=bot.send_message(chat_id, ""))
            update.effective_user = bot.get_chat(chat_id)
            new_context = CallbackContext.from_update(update, bot)
            new_context.user_data = {}
            new_context.bot_data = context.bot_data

            # Generate and send the story
            generate_and_send_story(update, new_context, topic, user_level)
        except Exception as e:
            logger.error(f"Failed to send daily story to user {user_id}: {e}")

def main():
    # Fetch tokens securely from environment variables
    telegram_bot_token = os.environ.get('TELEGRAM_BOT_TOKEN')
    openai_api_key_env = os.environ.get('OPENAI_API_KEY')  # Avoid overwriting the global variable

    # Check if tokens are available
    if not telegram_bot_token or not openai_api_key_env:
        logger.error("Bot token or OpenAI API key not set in environment variables.")
        return

    global openai_api_key
    openai_api_key = openai_api_key_env  # Assign to the global variable used in functions

    # Initialize the updater and dispatcher
    updater = Updater(telegram_bot_token, use_context=True)
    dispatcher = updater.dispatcher

    # Set up your ConversationHandler and other handlers
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            LEVEL: [
                CallbackQueryHandler(button_handler),
                MessageHandler(Filters.text & ~Filters.command, level_received)
            ],
            TOPIC: [
                MessageHandler(Filters.text & ~Filters.command, receive_topic),
                CallbackQueryHandler(button_handler)
            ],
            STORY_SENT: [
                CallbackQueryHandler(button_handler),
                MessageHandler(Filters.text & ~Filters.command, receive_answer)
            ],
            ANSWERING_QUESTIONS: [
                MessageHandler(Filters.text & ~Filters.command, receive_answer),
                CallbackQueryHandler(button_handler)
            ],
            # Add any additional states if necessary
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )

    dispatcher.add_handler(conv_handler)

    # Use long polling
    logger.info("Starting bot using long polling.")

    # Set up daily job for sending stories
    job_queue = updater.job_queue

    # Schedule the daily story at 11:00 AM
    target_time = datetime.time(hour=11, minute=0)
    job_queue.run_daily(send_daily_story, time=target_time, context=dispatcher)

    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
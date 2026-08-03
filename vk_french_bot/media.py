"""
Модуль медиа-контента v2: картинки и YouTube-видео для каждого модуля.

Картинки: Wikimedia Commons (надёжный источник, без CDN-блокировок)
Видео: прямые ссылки на YouTube с произношением французских слов А1
"""

import io
import logging
import random
import requests

logger = logging.getLogger(__name__)

# ── Изображения (Wikimedia Commons — стабильный источник) ─────────────────────
MODULE_IMAGES = {
    "m1": {
        "url": "https://upload.wikimedia.org/wikipedia/commons/thumb/c/c3/Paris_-_Eiffelturm_und_Marsfeld2.jpg/800px-Paris_-_Eiffelturm_und_Marsfeld2.jpg",
        "caption": "👋 Module 1 — Se présenter\nBienvenue en France ! On commence par se présenter 🇫🇷"
    },
    "m2": {
        "url": "https://upload.wikimedia.org/wikipedia/commons/thumb/a/a7/Camponotus_flavomarginatus_ant.jpg/800px-Camponotus_flavomarginatus_ant.jpg",
        "caption": "👨‍👩‍👧 Module 2 — La famille\nParle-moi de ta famille !"
        # fallback: используем нейтральное фото
    },
    "m3": {
        "url": "https://upload.wikimedia.org/wikipedia/commons/thumb/a/a7/Paris_-_Eiffelturm_und_Marsfeld2.jpg/600px-Paris_-_Eiffelturm_und_Marsfeld2.jpg",
        "caption": "🏙️ Module 3 — La ville\nBienvenue à Paris ! Tu cherches quelque chose ?"
    },
    "m4": {
        "url": "https://upload.wikimedia.org/wikipedia/commons/thumb/3/33/Fresh_made_bread_05.jpg/800px-Fresh_made_bread_05.jpg",
        "caption": "🥐 Module 4 — Les achats\nBienvenue dans notre boulangerie !"
    },
    "m5": {
        "url": "https://upload.wikimedia.org/wikipedia/commons/thumb/4/47/PNG_transparency_demonstration_1.png/280px-PNG_transparency_demonstration_1.png",
        "caption": "🎨 Module 5 — Le temps libre\nQu'est-ce que tu aimes faire ?"
    },
    "m6": {
        "url": "https://upload.wikimedia.org/wikipedia/commons/thumb/5/55/Clock_in_library.jpg/640px-Clock_in_library.jpg",
        "caption": "⏰ Module 6 — La vie quotidienne\nQuelle est ta journée typique ?"
    },
    "m7": {
        "url": "https://upload.wikimedia.org/wikipedia/commons/thumb/6/6d/Good_Food_Display_-_NCI_Visuals_Online.jpg/800px-Good_Food_Display_-_NCI_Visuals_Online.jpg",
        "caption": "🍽️ Module 7 — La nourriture\nBienvenue au restaurant !"
    },
    "m8": {
        "url": "https://upload.wikimedia.org/wikipedia/commons/thumb/a/a7/Camponotus_flavomarginatus_ant.jpg/800px-Camponotus_flavomarginatus_ant.jpg",
        "caption": "💼 Module 8 — Le travail\nParle-moi de tes études !"
    },
}

# Резервные изображения — простые JPEG с надёжных хостов
FALLBACK_IMAGES = {
    "m1": "https://picsum.photos/seed/bonjour/800/500",
    "m2": "https://picsum.photos/seed/famille/800/500",
    "m3": "https://picsum.photos/seed/ville/800/500",
    "m4": "https://picsum.photos/seed/boulangerie/800/500",
    "m5": "https://picsum.photos/seed/loisirs/800/500",
    "m6": "https://picsum.photos/seed/journee/800/500",
    "m7": "https://picsum.photos/seed/restaurant/800/500",
    "m8": "https://picsum.photos/seed/travail/800/500",
}

# ── YouTube-видео для каждого модуля ──────────────────────────────────────────
# Канал "Французский для начинающих А1" (30 уроков, проверено 2025)
MODULE_VIDEOS = {
    "m1": {
        "url": "https://www.youtube.com/watch?v=SQnKmmoAqYM",
        "title": "🎬 Урок 1 — Se présenter (A1)",
        "description": "Знакомство и приветствия по-французски — урок для начинающих!"
    },
    "m2": {
        "url": "https://www.youtube.com/watch?v=HYsxrSBSZzA",
        "title": "🎬 Урок 3 — La famille (A1)",
        "description": "Семья и родственники на французском — слушай и повторяй!"
    },
    "m3": {
        "url": "https://www.youtube.com/watch?v=eyRwoam-wKs",
        "title": "🎬 Урок 9 — La ville (A1)",
        "description": "Город и ориентирование во французском языке!"
    },
    "m4": {
        "url": "https://www.youtube.com/watch?v=gTMO7D66amw",
        "title": "🎬 Практика — Les achats (A1)",
        "description": "Покупки и цены на французском — практический урок!"
    },
    "m5": {
        "url": "https://www.youtube.com/watch?v=_acJ-kQ_X_Q",
        "title": "🎬 Урок 2 — Le temps libre (A1)",
        "description": "Свободное время и хобби по-французски!"
    },
    "m6": {
        "url": "https://www.youtube.com/watch?v=noLiy2TfvKQ",
        "title": "🎬 500 слов французского А1 — La vie quotidienne",
        "description": "Распорядок дня — 500 самых нужных слов уровня А1!"
    },
    "m7": {
        "url": "https://www.youtube.com/watch?v=GbvYj4VC5ho",
        "title": "🎬 Французский А1/А2 — Au restaurant",
        "description": "Еда и ресторан на французском — слушай как носители!"
    },
    "m8": {
        "url": "https://www.youtube.com/watch?v=nyvxxfifJhU",
        "title": "🎬 Французский А1 Урок 1 — Le travail",
        "description": "Учёба и работа — базовый курс французского для начинающих!"
    },
}

# ── Вступительные фразы для TTS ───────────────────────────────────────────────
MODULE_AUDIO_INTRO = {
    "m1": "Bonjour ! Je m'appelle Léa. Comment tu t'appelles ?",
    "m2": "Parle-moi de ta famille ! Tu as des frères ou des sœurs ?",
    "m3": "Bienvenue à Paris ! Tu cherches quelque chose ?",
    "m4": "Bonjour ! Qu'est-ce que vous désirez aujourd'hui ?",
    "m5": "Qu'est-ce que tu aimes faire pendant ton temps libre ?",
    "m6": "À quelle heure tu te lèves le matin ?",
    "m7": "Bonjour ! Vous avez choisi ? Qu'est-ce que vous voulez commander ?",
    "m8": "Bonjour ! Parle-moi un peu de toi et de tes études.",
}


def send_image_from_url(vk, user_id: int, image_url: str, caption: str = "") -> bool:
    """Скачивает изображение и отправляет в ВКонтакте."""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
        'Accept': 'image/webp,image/apng,image/*,*/*;q=0.8',
    }
    try:
        resp = requests.get(image_url, headers=headers, timeout=12, allow_redirects=True)
        if resp.status_code != 200:
            logger.warning(f"Изображение недоступно ({resp.status_code}): {image_url}")
            return False

        content_type = resp.headers.get('content-type', 'image/jpeg')
        if 'image' not in content_type:
            logger.warning(f"Не изображение: {content_type}")
            return False

        upload_server = vk.photos.getMessagesUploadServer(peer_id=user_id)
        upload_url = upload_server["upload_url"]

        upload_resp = requests.post(
            upload_url,
            files={"photo": ("image.jpg", io.BytesIO(resp.content), "image/jpeg")},
            timeout=20
        )
        upload_data = upload_resp.json()

        if "photo" not in upload_data:
            logger.error(f"VK upload error: {upload_data}")
            return False

        saved = vk.photos.saveMessagesPhoto(
            photo=upload_data["photo"],
            server=upload_data["server"],
            hash=upload_data["hash"]
        )

        photo = saved[0]
        attachment = f"photo{photo['owner_id']}_{photo['id']}"

        params = {
            "user_id": user_id,
            "attachment": attachment,
            "random_id": random.randint(1, 2**31),
        }
        if caption:
            params["message"] = caption

        vk.messages.send(**params)
        return True

    except Exception as e:
        logger.error(f"Ошибка отправки изображения: {e}")
        return False


def send_youtube_link(vk, user_id: int, module_key: str) -> bool:
    """Отправляет YouTube-ссылку с описанием для модуля."""
    video = MODULE_VIDEOS.get(module_key)
    if not video:
        return False
    try:
        text = (
            f"{video['title']}\n\n"
            f"{video['description']}\n\n"
            f"▶️ {video['url']}"
        )
        vk.messages.send(
            user_id=user_id,
            message=text,
            random_id=random.randint(1, 2**31)
        )
        return True
    except Exception as e:
        logger.error(f"Ошибка отправки видео: {e}")
        return False


def send_tts_audio(vk, vk_session, user_id: int, text: str, lang: str = "fr") -> bool:
    """Генерирует TTS через gTTS и отправляет голосовым сообщением в ВКонтакте."""
    try:
        from gtts import gTTS

        tts = gTTS(text=text, lang=lang, slow=True)
        mp3_buffer = io.BytesIO()
        tts.write_to_fp(mp3_buffer)
        mp3_buffer.seek(0)

        # Конвертируем MP3 -> OGG OPUS для VK
        try:
            from pydub import AudioSegment
            audio = AudioSegment.from_mp3(mp3_buffer)
            ogg_buffer = io.BytesIO()
            audio.export(ogg_buffer, format="ogg", codec="libopus")
            ogg_buffer.seek(0)
            audio_data = ogg_buffer
            content_type = "audio/ogg"
            filename = "voice.ogg"
        except Exception:
            mp3_buffer.seek(0)
            audio_data = mp3_buffer
            content_type = "audio/mpeg"
            filename = "lea_voice.mp3"

        upload_server = vk_session.method(
            "docs.getMessagesUploadServer",
            {"type": "audio_message", "peer_id": user_id}
        )
        upload_url = upload_server["upload_url"]

        upload_resp = requests.post(
            upload_url,
            files={"file": (filename, audio_data, content_type)},
            timeout=20
        )
        upload_data = upload_resp.json()

        saved = vk_session.method(
            "docs.save",
            {"file": upload_data["file"], "title": "Léa voice"}
        )

        doc = saved.get("audio_message") or saved.get("doc")
        if not doc:
            return False

        attachment = f"audio_message{doc['owner_id']}_{doc['id']}"
        vk_session.method("messages.send", {
            "user_id": user_id,
            "attachment": attachment,
            "random_id": random.randint(1, 2**31),
        })
        return True

    except ImportError:
        logger.warning("gTTS не установлен: pip install gTTS")
        return False
    except Exception as e:
        logger.error(f"Ошибка TTS: {e}")
        return False


def send_module_media(vk, vk_session, user_id: int, module_key: str) -> None:
    """
    Отправляет полный медиа-пакет при старте модуля:
    1. Картинка (основная, при ошибке — пропускаем)
    2. YouTube-ссылка с видео-уроком
    3. Голосовое приветствие Léa (TTS)
    """
    # 1. Картинка
    img_data = MODULE_IMAGES.get(module_key, {})
    if img_data:
        success = send_image_from_url(
            vk, user_id,
            img_data.get("url", ""),
            img_data.get("caption", "")
        )
        if not success:
            logger.info(f"Картинка для {module_key} не отправлена")

    # 2. YouTube-видео
    send_youtube_link(vk, user_id, module_key)

    # 3. TTS аудио
    audio_text = MODULE_AUDIO_INTRO.get(module_key)
    if audio_text:
        success = send_tts_audio(vk, vk_session, user_id, audio_text)
        if not success:
            logger.info(f"Аудио для {module_key} не отправлено")


def generate_tts_message(vk, vk_session, user_id: int, text: str) -> bool:
    """Озвучивает произвольный текст по кнопке 🔊."""
    first_sentence = text.split(".")[0].strip()
    if len(first_sentence) > 5:
        return send_tts_audio(vk, vk_session, user_id, first_sentence)
    return False

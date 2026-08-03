"""
Образовательный чат-бот Léa v3 — французский язык А1
ВКонтакте + GigaChat API + персистентные сессии + LLM-детекция ошибок

Установка:
    pip install vk-api gigachat gTTS pydub requests python-dotenv

Запуск:
    python3 vk_bot.py

Конфигурация: создайте файл .env
    VK_TOKEN=ваш_токен_вк
    GIGACHAT_CREDENTIALS=ваш_ключ_сбера
"""

import json
import logging
import random
import time
import threading
from gigachat import GigaChat
from gigachat.models import Chat, Messages, MessagesRole
import vk_api
from vk_api.longpoll import VkLongPoll, VkEventType
from vk_api.keyboard import VkKeyboard, VkKeyboardColor

from database import Database, detect_errors_llm
from config import GIGACHAT_CREDENTIALS, VK_TOKEN, MODULES, build_system_prompt
from media import send_module_media, generate_tts_message

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ID администратора — замените на ваш VK ID для получения отчётов
ADMIN_VK_ID = 822644331  # например: 123456789

giga = GigaChat(
    credentials=GIGACHAT_CREDENTIALS,
    scope="GIGACHAT_API_PERS",
    model="GigaChat-2",
    verify_ssl_certs=False
)
db = Database("french_bot.db")


def ask_gigachat(messages: list) -> str:
    role_map = {
        "system":    MessagesRole.SYSTEM,
        "user":      MessagesRole.USER,
        "assistant": MessagesRole.ASSISTANT
    }
    giga_messages = [
        Messages(role=role_map.get(m["role"], MessagesRole.USER), content=m["content"])
        for m in messages
    ]
    return giga.chat(Chat(messages=giga_messages)).choices[0].message.content.strip()


def send_msg(vk, user_id: int, text: str, keyboard=None):
    params = {
        "user_id":   user_id,
        "message":   text[:4096],
        "random_id": random.randint(1, 2**31)
    }
    if keyboard:
        params["keyboard"] = keyboard.get_keyboard()
    for attempt in range(2):
        try:
            vk.messages.send(**params)
            return
        except Exception as e:
            logger.error("Ошибка отправки (попытка %d): %s", attempt + 1, e)
            time.sleep(1)


# ── Клавиатуры ────────────────────────────────────────────────────────────────

def kb_main():
    k = VkKeyboard(one_time=False)
    k.add_button("📚 Выбрать модуль", color=VkKeyboardColor.PRIMARY)
    k.add_button("📊 Мой прогресс",   color=VkKeyboardColor.SECONDARY)
    k.add_line()
    k.add_button("ℹ️ Справка",         color=VkKeyboardColor.SECONDARY)
    return k


def kb_modules():
    k = VkKeyboard(one_time=True)
    items = list(MODULES.items())
    for i, (key, m) in enumerate(items):
        k.add_button(
            f"{m['emoji']} {m['title_ru']}",
            color=VkKeyboardColor.PRIMARY,
            payload={"cmd": "module", "key": key}
        )
        if i % 2 == 1 and i < len(items) - 1:
            k.add_line()
    k.add_line()
    k.add_button("🏠 Меню", color=VkKeyboardColor.SECONDARY, payload={"cmd": "main_menu"})
    return k


def kb_mode(module_key):
    k = VkKeyboard(one_time=True)
    k.add_button("🎭 Управляемый диалог", color=VkKeyboardColor.PRIMARY,
                 payload={"cmd": "start", "module": module_key, "mode": "guided"})
    k.add_line()
    k.add_button("💬 Свободная беседа", color=VkKeyboardColor.POSITIVE,
                 payload={"cmd": "start", "module": module_key, "mode": "free"})
    k.add_line()
    k.add_button("🔍 Диагностика", color=VkKeyboardColor.SECONDARY,
                 payload={"cmd": "start", "module": module_key, "mode": "diagnostic"})
    k.add_line()
    k.add_button("◀️ Назад", color=VkKeyboardColor.NEGATIVE, payload={"cmd": "show_modules"})
    return k


def kb_session():
    k = VkKeyboard(one_time=False)
    k.add_button("🔊 Послушать",  color=VkKeyboardColor.SECONDARY, payload={"cmd": "tts_last"})
    k.add_button("🛑 Завершить", color=VkKeyboardColor.NEGATIVE,   payload={"cmd": "end_session"})
    k.add_line()
    k.add_button("📋 Меню",      color=VkKeyboardColor.SECONDARY,  payload={"cmd": "main_menu"})
    return k


# ── Обработчики событий ───────────────────────────────────────────────────────

def on_start(vk, user_id: int, name: str):
    db.create_user(user_id, name)
    db.reset_session(user_id)
    text = (
        f"👋 Bonjour, {name}!\n\n"
        "Я — Léa, твой репетитор французского языка 🇫🇷\n\n"
        "🎯 Курс: французский язык А1 (для начинающих)\n\n"
        "📚 8 модулей:\n"
    )
    for m in MODULES.values():
        text += f"  {m['emoji']} {m['title_ru']} ({m['title_fr']})\n"
    text += "\nВыбери действие:"
    send_msg(vk, user_id, text, kb_main())


def on_show_modules(vk, user_id: int):
    send_msg(vk, user_id, "📚 Выбери модуль:", kb_modules())


def on_select_module(vk, user_id: int, key: str):
    m = MODULES[key]
    text = (
        f"{m['emoji']} {m['title_ru']} ({m['title_fr']})\n\n"
        f"🎯 Цель: {m['goal']}\n\n"
        f"📝 Структуры:\n" + "\n".join(f"  • {s}" for s in m['structures']) +
        f"\n\n💬 Лексика: {', '.join(m['vocabulary'][:5])}...\n\nВыбери режим:"
    )
    send_msg(vk, user_id, text, kb_mode(key))


def on_start_session(vk, vk_session, user_id: int, module_key: str, mode: str):
    m = MODULES[module_key]
    mode_names = {
        "guided":     "🎭 Управляемый диалог",
        "free":       "💬 Свободная беседа",
        "diagnostic": "🔍 Диагностика"
    }

    profile = db.get_user_profile(user_id)
    system_prompt = build_system_prompt(profile, module_key, mode)
    history = [{"role": "system", "content": system_prompt}]

    session = {
        "state":        "in_session",
        "module":       module_key,
        "mode":         mode,
        "msg_count":    0,
        "history":      history,
        "last_bot_msg": ""
    }
    db.save_session(user_id, session)

    send_msg(vk, user_id,
             f"✅ Сессия началась!\n\nМодуль: {m['emoji']} {m['title_ru']}\n"
             f"Режим: {mode_names[mode]}\n\n───────────────")

    # Медиа-пакет отправляем в фоновом потоке
    threading.Thread(
        target=send_module_media,
        args=(vk, vk_session, user_id, module_key),
        daemon=True
    ).start()

    try:
        bot_msg = ask_gigachat(history + [{"role": "user", "content": "Commence la session."}])
        session["history"].append({"role": "assistant", "content": bot_msg})
        session["last_bot_msg"] = bot_msg
        db.save_session(user_id, session)
        send_msg(vk, user_id, f"🤖 Léa: {bot_msg}", kb_session())
    except Exception as e:
        logger.error("GigaChat error on session start: %s", e)
        send_msg(vk, user_id, "⚠️ Ошибка подключения к ИИ. Проверьте GIGACHAT_CREDENTIALS.", kb_main())
        db.reset_session(user_id)


def on_message(vk, vk_session, user_id: int, text: str):
    session = db.get_session(user_id)
    session["msg_count"] += 1

    # LLM-диагностика ошибок (асинхронно не блокирует ответ)
    try:
        errors = detect_errors_llm(giga, text)
        if errors:
            db.update_errors(user_id, errors)
    except Exception as e:
        logger.warning("Ошибка детекции: %s", e)

    session["history"].append({"role": "user", "content": text})

    try:
        bot_msg = ask_gigachat(session["history"])
        session["history"].append({"role": "assistant", "content": bot_msg})
        session["last_bot_msg"] = bot_msg
        db.save_session(user_id, session)
        db.save_interaction(user_id, session["module"], session["mode"], text, bot_msg)
        send_msg(vk, user_id, f"🤖 Léa: {bot_msg}", kb_session())

        if session["msg_count"] >= 15:
            on_end_session(vk, user_id)
    except Exception as e:
        logger.error("GigaChat error on message: %s", e)
        db.save_session(user_id, session)
        send_msg(vk, user_id, "⚠️ Ошибка ИИ. Попробуй ещё раз.", kb_session())


def on_tts_last(vk, vk_session, user_id: int):
    session = db.get_session(user_id)
    last_msg = session.get("last_bot_msg", "")
    if not last_msg:
        send_msg(vk, user_id, "Нет сообщения для озвучивания.", kb_session())
        return
    send_msg(vk, user_id, "🔊 Генерирую аудио...")

    def send_audio():
        success = generate_tts_message(vk, vk_session, user_id, last_msg)
        if not success:
            send_msg(vk, user_id,
                     "⚠️ TTS недоступен.\nУстанови: pip install gTTS pydub\nИ ffmpeg: sudo apt install ffmpeg",
                     kb_session())

    threading.Thread(target=send_audio, daemon=True).start()


def on_end_session(vk, user_id: int):
    session = db.get_session(user_id)
    if session.get("state") != "in_session":
        send_msg(vk, user_id, "Нет активной сессии.", kb_main())
        return

    module_key = session.get("module", "m1")
    m = MODULES[module_key]
    db.complete_module_session(user_id, module_key)
    profile = db.get_user_profile(user_id)

    tips = {
        "élision_je":       "Элизия: j'habite, j'aime (не «je habite»)",
        "conjugaison_être": "Être: je suis, tu es, il est",
        "article_genre":    "Артикль: l'école, l'université (не «le école»)",
        "conjugaison_aller":"Aller: je vais (не «je va»)",
        "accord_adjectif":  "Согласование прилаг.: une femme grande",
        "conjugaison_avoir":"Avoir: j'ai, tu as (не «j'as»)",
        "négation":         "Отрицание: je ne parle pas (не «je parle pas»)",
    }

    summary = (
        f"✅ Сессия завершена!\n\n📚 {m['emoji']} {m['title_ru']}\n"
        f"💬 Реплик: {session.get('msg_count', 0)}\n"
        f"🏆 Всего сессий: {profile.get('total_sessions', 0)}\n"
    )
    errors = profile.get("errors", {})
    if errors:
        top = sorted(errors.items(), key=lambda x: x[1], reverse=True)[:2]
        summary += "\n📝 Обрати внимание:\n"
        for err, cnt in top:
            summary += f"  • {tips.get(err, err)} ({cnt}×)\n"
    summary += "\nBravo! Продолжай в том же духе! 💪"

    db.reset_session(user_id)
    send_msg(vk, user_id, summary, kb_main())


def on_progress(vk, user_id: int):
    profile = db.get_user_profile(user_id)
    completed = profile.get("completed_modules", [])
    text = f"📊 Прогресс\n\n🏆 Сессий: {profile.get('total_sessions', 0)}\n\n📚 Модули:\n"
    for key, m in MODULES.items():
        text += f"  {'✅' if key in completed else '⬜'} {m['emoji']} {m['title_ru']}\n"
    errors = profile.get("errors", {})
    if errors:
        tips = {
            "élision_je": "элизия (j'aime)",
            "conjugaison_être": "être (je suis)",
            "article_genre": "артикль (l'école)",
            "conjugaison_aller": "aller (je vais)",
            "accord_adjectif": "согласование прил.",
            "conjugaison_avoir": "avoir (j'ai)",
            "négation": "отрицание (ne…pas)",
        }
        text += "\n📝 Частые ошибки:\n"
        for err, cnt in sorted(errors.items(), key=lambda x: x[1], reverse=True)[:3]:
            text += f"  • {tips.get(err, err)}: {cnt}×\n"
    send_msg(vk, user_id, text, kb_main())


def on_help(vk, user_id: int):
    send_msg(vk, user_id,
             "ℹ️ Как работать с ботом\n\n"
             "1️⃣ Выбери модуль — тему занятия\n"
             "2️⃣ При старте модуля получишь:\n"
             "   🖼️ Картинку по теме\n"
             "   🎬 YouTube-видео с произношением\n"
             "   🔊 Голосовое приветствие Léa\n"
             "3️⃣ Выбери режим:\n"
             "   🎭 Управляемый — Léa задаёт ситуацию\n"
             "   💬 Свободный — говори о чём хочешь\n"
             "   🔍 Диагностика — проверь себя\n"
             "4️⃣ Общайся с Léa по-французски!\n"
             "5️⃣ Кнопка 🔊 — послушать ответ Léa\n\n"
             "Léa объясняет на русском если нужно 😊",
             kb_main())


def on_admin_report(vk, user_id: int):
    """Отчёт для преподавателя — доступен только ADMIN_VK_ID."""
    if ADMIN_VK_ID and user_id != ADMIN_VK_ID:
        send_msg(vk, user_id, "⛔ Команда доступна только администратору.", kb_main())
        return

    report = db.get_all_users_report()
    group_errors = db.get_group_top_errors()

    text = f"📋 Отчёт по группе ({len(report)} студентов)\n\n"
    for r in report[:10]:  # первые 10
        mods = ", ".join(r["modules"]) if r["modules"] else "—"
        top_err = ", ".join(f"{e}({c}×)" for e, c in r["top_errors"]) or "—"
        text += (
            f"👤 {r['name']} (id{r['user_id']})\n"
            f"   Сессий: {r['sessions']} | Реплик: {r['messages']}\n"
            f"   Модули: {mods}\n"
            f"   Ошибки: {top_err}\n\n"
        )

    if group_errors:
        text += "📊 Топ ошибок по группе:\n"
        for err, cnt in list(group_errors.items())[:5]:
            text += f"  • {err}: {cnt}×\n"

    send_msg(vk, user_id, text[:4096])


# ── Маршрутизация входящих сообщений ─────────────────────────────────────────

def route(vk, vk_session, event):
    user_id = event.user_id
    text = (event.text or "").strip()

    try:
        info = vk.users.get(user_ids=user_id)[0]
        name = info.get("first_name", "студент")
    except Exception:
        name = "студент"

    # Восстанавливаем состояние из БД (персистентность)
    session = db.get_session(user_id)
    state = session.get("state", "menu")

    raw = getattr(event, "payload", None)
    payload = None
    if raw:
        try:
            payload = json.loads(raw)
        except Exception:
            payload = None

    if payload:
        cmd = payload.get("cmd", "")
        if cmd == "main_menu":
            db.reset_session(user_id)
            send_msg(vk, user_id, "🏠 Главное меню:", kb_main())
        elif cmd == "show_modules":
            on_show_modules(vk, user_id)
        elif cmd == "module":
            on_select_module(vk, user_id, payload["key"])
        elif cmd == "start":
            on_start_session(vk, vk_session, user_id, payload["module"], payload["mode"])
        elif cmd == "end_session":
            on_end_session(vk, user_id)
        elif cmd == "tts_last":
            on_tts_last(vk, vk_session, user_id)
        return

    lower = text.lower()
    if lower in ["начать", "старт", "/start", "start", "привет", "bonjour"]:
        on_start(vk, user_id, name)
    elif lower in ["меню", "/menu", "menu"]:
        db.reset_session(user_id)
        send_msg(vk, user_id, "🏠 Главное меню:", kb_main())
    elif lower in ["📚 выбрать модуль"]:
        on_show_modules(vk, user_id)
    elif lower in ["📊 мой прогресс"]:
        on_progress(vk, user_id)
    elif lower in ["ℹ️ справка"]:
        on_help(vk, user_id)
    elif lower in ["🛑 завершить"]:
        on_end_session(vk, user_id)
    elif lower in ["/report", "отчёт", "отчет"]:
        on_admin_report(vk, user_id)
    elif state == "in_session" and text:
        on_message(vk, vk_session, user_id, text)
    elif text:
        send_msg(vk, user_id, "Напиши «начать» или выбери действие:", kb_main())


def main():
    db.init()
    vk_session = vk_api.VkApi(token=VK_TOKEN)
    vk = vk_session.get_api()
    longpoll = VkLongPoll(vk_session)
    logger.info("Léa v3 запущена! (персистентные сессии + LLM-детекция ошибок + аналитика)")
    for event in longpoll.listen():
        if event.type == VkEventType.MESSAGE_NEW and event.to_me:
            threading.Thread(
                target=route,
                args=(vk, vk_session, event),
                daemon=True
            ).start()


if __name__ == "__main__":
    main()

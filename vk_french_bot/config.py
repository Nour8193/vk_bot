"""
Конфигурация бота ВКонтакте + GigaChat API (v3)

Перед запуском создайте файл .env в корне проекта:

    VK_TOKEN=vk1.a.ВАШ_ТОКЕН
    GIGACHAT_CREDENTIALS=ВАШ_КЛЮЧ_СБЕРА

Или задайте переменные среды напрямую:
    export VK_TOKEN=...
    export GIGACHAT_CREDENTIALS=...

НИКОГДА не вписывайте токены в код напрямую!
"""

import os
import sys

# Загружаем .env если есть python-dotenv
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv не установлен — читаем из os.environ

VK_TOKEN = os.getenv("VK_TOKEN", "")
GIGACHAT_CREDENTIALS = os.getenv("GIGACHAT_CREDENTIALS", "")

if not VK_TOKEN:
    sys.exit("Ошибка: VK_TOKEN не задан. Укажите его в .env или переменных среды.")
if not GIGACHAT_CREDENTIALS:
    sys.exit("Ошибка: GIGACHAT_CREDENTIALS не задан. Укажите его в .env или переменных среды.")

MODULES = {
    "m1": {
        "title_ru": "Знакомство", "title_fr": "Se présenter", "emoji": "👋",
        "goal": "Уметь представиться, назвать имя, возраст, город и профессию",
        "structures": ["Je m'appelle…", "J'ai … ans", "J'habite à…", "Je suis étudiant(e)"],
        "vocabulary": ["bonjour", "nom", "prénom", "âge", "ville", "étudiant", "professeur"],
        "bot_role": "une nouvelle connaissance à l'université",
        "situation": "Tu rencontres un nouvel étudiant. Présentez-vous mutuellement."
    },
    "m2": {
        "title_ru": "Семья и друзья", "title_fr": "La famille", "emoji": "👨‍👩‍👧",
        "goal": "Описывать свою семью, называть родственников",
        "structures": ["Il/Elle s'appelle…", "Mon père/ma mère est…", "J'ai un frère / une sœur"],
        "vocabulary": ["père", "mère", "frère", "sœur", "ami", "grand-père", "grand-mère"],
        "bot_role": "un(e) ami(e) curieux(-se)",
        "situation": "Tu parles de ta famille avec un(e) ami(e) français(e)."
    },
    "m3": {
        "title_ru": "Город", "title_fr": "La ville", "emoji": "🏙️",
        "goal": "Называть места в городе, спрашивать и объяснять дорогу",
        "structures": ["Où est… ?", "C'est à gauche / à droite", "Il y a … près d'ici"],
        "vocabulary": ["rue", "café", "gare", "métro", "bibliothèque", "restaurant", "hôtel"],
        "bot_role": "un passant dans la rue",
        "situation": "Tu es perdu(e) dans une ville française. Demande le chemin."
    },
    "m4": {
        "title_ru": "Покупки", "title_fr": "Les achats", "emoji": "🛒",
        "goal": "Делать покупки, спрашивать цену",
        "structures": ["Combien coûte… ?", "Je voudrais…", "Je prends…", "Vous avez… ?"],
        "vocabulary": ["euro", "prix", "cher", "pas cher", "boulangerie", "marché", "caisse"],
        "bot_role": "un(e) vendeur(-euse) dans une boulangerie",
        "situation": "Tu achètes du pain et des croissants dans une boulangerie."
    },
    "m5": {
        "title_ru": "Свободное время", "title_fr": "Le temps libre", "emoji": "🎨",
        "goal": "Говорить о хобби, выражать предпочтения",
        "structures": ["J'aime / J'adore…", "Je n'aime pas…", "Je fais du sport"],
        "vocabulary": ["lire", "écouter", "regarder", "jouer", "sport", "musique", "cinéma"],
        "bot_role": "un(e) camarade de classe",
        "situation": "Tu parles de tes loisirs avec un(e) camarade français(e)."
    },
    "m6": {
        "title_ru": "Распорядок дня", "title_fr": "La vie quotidienne", "emoji": "⏰",
        "goal": "Описывать свой день, называть время",
        "structures": ["Je me lève à…", "À quelle heure… ?", "Il est … heures"],
        "vocabulary": ["matin", "midi", "soir", "heure", "déjeuner", "dîner", "dormir"],
        "bot_role": "un(e) ami(e) francophone",
        "situation": "Tu décris ta journée typique à un(e) ami(e) français(e)."
    },
    "m7": {
        "title_ru": "Еда и кафе", "title_fr": "La nourriture", "emoji": "🍽️",
        "goal": "Заказывать еду в кафе",
        "structures": ["Je voudrais…, s'il vous plaît", "L'addition, s'il vous plaît"],
        "vocabulary": ["menu", "entrée", "plat", "dessert", "eau", "café", "pain", "fromage"],
        "bot_role": "un(e) serveur(-euse) dans un restaurant parisien",
        "situation": "Tu es au restaurant. Le serveur prend ta commande."
    },
    "m8": {
        "title_ru": "Работа и учёба", "title_fr": "Le travail", "emoji": "💼",
        "goal": "Описывать работу или учёбу",
        "structures": ["Je travaille comme…", "J'étudie à l'université de…"],
        "vocabulary": ["étudiant", "professeur", "médecin", "ingénieur", "université", "cours"],
        "bot_role": "un(e) recruteur(-euse) lors d'un entretien simple",
        "situation": "Tu passes un entretien pour un job étudiant. Présente-toi."
    }
}


def build_system_prompt(user_profile: dict, module_key: str, mode: str) -> str:
    """
    Формирует динамический системный промпт.
    Адаптируется под профиль ошибок конкретного студента.
    """
    module = MODULES[module_key]
    errors = user_profile.get("errors", {})

    base = (
        "Tu es Léa, une tutrice bienveillante qui enseigne le français "
        "à des étudiants russophones débutants (niveau A1 du CECRL).\n\n"
        "RÈGLES IMPORTANTES:\n"
        "- Parle principalement en français, mais si l'étudiant est bloqué ou ne comprend pas, "
        "donne UNE courte explication en russe entre parenthèses. "
        "Exemple: «J'habite à Moscou. (habiter = жить)»\n"
        "- Niveau A1: phrases très courtes, vocabulaire de base, structures simples.\n"
        "- Corrige UNE seule erreur par réponse. Répète la forme correcte naturellement "
        "et demande à l'étudiant de répéter.\n"
        "- Sois toujours encourageante et patiente. 😊\n"
        "- Pose des questions simples pour faire parler l'étudiant.\n"
        "- Réponses courtes (2-3 phrases maximum).\n"
        "- Utilise des émojis pour rendre le dialogue vivant.\n"
    )

    mod_info = (
        f"\nMODULE: {module['title_ru']} ({module['title_fr']})\n"
        f"Objectif: {module['goal']}\n"
        f"Structures: {', '.join(module['structures'])}\n"
        f"Vocabulaire: {', '.join(module['vocabulary'])}\n"
    )

    err_info = ""
    if errors:
        top = sorted(errors.items(), key=lambda x: x[1], reverse=True)[:3]
        err_info = (
            "\nErreurs fréquentes de cet étudiant: " +
            ", ".join(f"{e}({c}×)" for e, c in top) +
            ". Sois particulièrement attentive à ces points.\n"
        )

    modes = {
        "guided": (
            f"\nMODE: Dialogue guidé. Rôle: {module.get('bot_role')}. "
            f"Situation: {module.get('situation')}. "
            "Guide l'étudiant vers l'objectif. Commence par te présenter."
        ),
        "free": (
            "\nMODE: Conversation libre. "
            "L'étudiant parle librement. Réagis naturellement."
        ),
        "diagnostic": (
            "\nMODE: Diagnostic. "
            "Pose des questions pour évaluer le niveau. "
            "Ne corrige PAS en mode diagnostic — observe seulement."
        )
    }

    return base + mod_info + err_info + modes.get(mode, modes["guided"])


# Промпт для LLM-диагностики ошибок (используется в database.py)
ERROR_DETECTION_PROMPT = """Tu es un correcteur de français A1. Analyse la phrase de l'étudiant et identifie les erreurs grammaticales.

Réponds UNIQUEMENT en JSON, sans aucun texte supplémentaire, dans ce format exact:
{"errors": ["nom_erreur1", "nom_erreur2"]}

Erreurs possibles à détecter:
- "élision_je" — manque d'élision: "je aime" au lieu de "j'aime", "je habite" au lieu de "j'habite"
- "conjugaison_être" — mauvaise conjugaison de être: "je est", "tu est"
- "article_genre" — mauvais article: "le école", "le université"
- "conjugaison_aller" — mauvaise conjugaison de aller: "je va"
- "accord_adjectif" — mauvais accord: "une homme grand"
- "conjugaison_avoir" — mauvaise conjugaison de avoir: "j'as", "tu as pas"
- "négation" — négation incomplète: "je parle pas" au lieu de "je ne parle pas"

Si aucune erreur — réponds: {"errors": []}

Phrase à analyser: """

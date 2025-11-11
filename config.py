import os
from dotenv import load_dotenv

load_dotenv()

# Токен бота (заполните в .env файле)
BOT_TOKEN = os.getenv("BOT_TOKEN", "")

# Ссылка на регистрацию
REGISTRATION_URL = os.getenv("REGISTRATION_URL", "https://olddigital.rkomi.ru/event/#visit")

# Ссылка на сайт форума
FORUM_SITE_URL = os.getenv("FORUM_SITE_URL", "https://olddigital.rkomi.ru/event/#visit")

# Ссылка на яндекс форму для вопросов
QUESTION_FORM_URL = os.getenv("QUESTION_FORM_URL", "https://forms.yandex.ru/u/6911bb6795add5069b7bb518")

# URL изображений для треков (графика)
TRACK_IMAGES = {
    "track_gamedev": os.getenv("TRACK_GAMEDEV_IMAGE", ""),
    "track_ai": os.getenv("TRACK_AI_IMAGE", ""),
    "track_drones": os.getenv("TRACK_DRONES_IMAGE", ""),
    "track_media": os.getenv("TRACK_MEDIA_IMAGE", ""),
}

# Путь к Excel файлу для хранения вопросов и отзывов
EXCEL_FILE_PATH = os.getenv("EXCEL_FILE_PATH", "forum_data.xlsx")

# ID админа для рассылки (опционально)
ADMIN_ID = int(os.getenv("ADMIN_ID", "0")) if os.getenv("ADMIN_ID") else None


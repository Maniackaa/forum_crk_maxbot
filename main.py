import os
import asyncio
import json
import aiohttp
import fcntl  # для блокировок файлов на Linux/Unix
from maxapi import Bot, Dispatcher
from maxapi.types import BotStarted, Command, MessageCreated, MessageCallback, CallbackButton, LinkButton
from config import BOT_TOKEN, REGISTRATION_URL, FORUM_SITE_URL, QUESTION_FORM_URL, TRACK_IMAGES
from utils.sheets import excel_manager

API_BASE_URL = "https://platform-api.max.ru"

# Инициализация бота и диспетчера
bot = Bot(BOT_TOKEN)
dp = Dispatcher()

# Глобальная сессия aiohttp для всех запросов
http_session: aiohttp.ClientSession = None

# Состояния для FSM (конечный автомат состояний)
user_states = {}

# Файлы для хранения данных
USERS_DB_FILE = "users_db.json"
STATES_DB_FILE = "user_states.json"

# Множество обработанных callback_id для защиты от повторной обработки
processed_callbacks = set()

# Блокировки для синхронизации доступа к файлам
_states_file_lock = asyncio.Lock()
_users_file_lock = asyncio.Lock()
_excel_file_lock = asyncio.Lock()


def load_users_db():
    """Загрузка базы пользователей из файла"""
    try:
        if os.path.exists(USERS_DB_FILE):
            with open(USERS_DB_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        print(f"Ошибка загрузки базы пользователей: {e}")
    return {"user_ids": []}


def load_user_states():
    """Загрузка состояний пользователей из файла (синхронная версия для внутреннего использования)"""
    global user_states
    try:
        if os.path.exists(STATES_DB_FILE):
            with open(STATES_DB_FILE, 'r', encoding='utf-8') as f:
                # Блокировка файла для чтения (Linux/Unix)
                try:
                    fcntl.flock(f.fileno(), fcntl.LOCK_SH)
                    try:
                        loaded_states = json.load(f)
                    finally:
                        fcntl.flock(f.fileno(), fcntl.LOCK_UN)
                except (OSError, AttributeError):
                    # Если fcntl не работает (Windows), просто читаем
                    loaded_states = json.load(f)
                
                # Преобразуем строковые ключи обратно в int для user_id
                user_states = {}
                for key, value in loaded_states.items():
                    try:
                        # Если ключ - число, преобразуем в int
                        if key.isdigit():
                            user_states[int(key)] = value
                        else:
                            user_states[key] = value
                    except:
                        user_states[key] = value
    except Exception as e:
        print(f"Ошибка загрузки состояний пользователей: {e}")
        user_states = {}


async def save_user_states():
    """Сохранение состояний пользователей в файл (асинхронная версия с блокировкой)"""
    async with _states_file_lock:
        try:
            # Преобразуем int ключи в строки для JSON
            states_to_save = {}
            for key, value in user_states.items():
                states_to_save[str(key)] = value
            
            # Используем временный файл для атомарной записи
            temp_file = STATES_DB_FILE + '.tmp'
            with open(temp_file, 'w', encoding='utf-8') as f:
                # Блокировка файла для записи (Linux/Unix)
                try:
                    fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                    try:
                        json.dump(states_to_save, f, ensure_ascii=False, indent=2)
                        f.flush()
                        os.fsync(f.fileno())  # Принудительная запись на диск
                    finally:
                        fcntl.flock(f.fileno(), fcntl.LOCK_UN)
                except (OSError, AttributeError):
                    # Если fcntl не работает (Windows), просто записываем
                    json.dump(states_to_save, f, ensure_ascii=False, indent=2)
                    f.flush()
                    os.fsync(f.fileno())
            
            # Атомарное переименование (на Linux это атомарная операция)
            os.replace(temp_file, STATES_DB_FILE)
        except Exception as e:
            print(f"Ошибка сохранения состояний пользователей: {e}")
            # Удаляем временный файл при ошибке
            if os.path.exists(temp_file):
                try:
                    os.remove(temp_file)
                except:
                    pass


async def save_user_id(user_id: int, chat_id: int = None):
    """Сохранение ID пользователя и chat_id в базу (асинхронная версия с блокировкой)"""
    try:
        async with _users_file_lock:
            db = load_users_db()
            
            # Инициализируем структуру для пользователей с chat_id
            if "users" not in db:
                db["users"] = {}
            
            # Сохраняем или обновляем информацию о пользователе
            if str(user_id) not in db["users"]:
                db["users"][str(user_id)] = {"user_id": user_id}
                # Добавляем в старый список для обратной совместимости
                if "user_ids" not in db:
                    db["user_ids"] = []
                if user_id not in db["user_ids"]:
                    db["user_ids"].append(user_id)
            
            # Обновляем chat_id, если передан
            if chat_id:
                db["users"][str(user_id)]["chat_id"] = chat_id
            
            # Используем временный файл для атомарной записи
            temp_file = USERS_DB_FILE + '.tmp'
            try:
                with open(temp_file, 'w', encoding='utf-8') as f:
                    # Блокировка файла для записи (Linux/Unix)
                    try:
                        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                        try:
                            json.dump(db, f, ensure_ascii=False, indent=2)
                            f.flush()
                            os.fsync(f.fileno())  # Принудительная запись на диск
                        finally:
                            fcntl.flock(f.fileno(), fcntl.LOCK_UN)
                    except (OSError, AttributeError, IOError):
                        # Если fcntl не работает, просто записываем
                        json.dump(db, f, ensure_ascii=False, indent=2)
                        f.flush()
                        os.fsync(f.fileno())
                
                # Атомарное переименование
                os.replace(temp_file, USERS_DB_FILE)
            except Exception as e:
                print(f"Ошибка сохранения базы пользователей: {e}")
                import traceback
                traceback.print_exc()
                # Удаляем временный файл при ошибке
                if os.path.exists(temp_file):
                    try:
                        os.remove(temp_file)
                    except:
                        pass
    except Exception as e:
        print(f"Критическая ошибка в save_user_id: {e}")
        import traceback
        traceback.print_exc()


def get_chat_id_from_event(event):
    """
    Получение chat_id из события (MessageCreated или MessageCallback)
    Для MessageCallback может потребоваться использовать user_id
    """
    chat_id = None
    
    if hasattr(event, 'message') and event.message:
        if hasattr(event.message, 'recipient') and event.message.recipient:
            chat_id = getattr(event.message.recipient, 'chat_id', None)
        if not chat_id and hasattr(event.message, 'chat_id'):
            chat_id = event.message.chat_id
    
    # Для MessageCallback, если chat_id не найден, используем user_id
    if (not chat_id or chat_id == 0) and hasattr(event, 'callback') and hasattr(event.callback, 'user'):
        chat_id = event.callback.user.user_id
    
    return chat_id


async def delete_message(message_id: str):
    """
    Удаление сообщения через raw MAX API
    Правильный формат: DELETE /messages?message_id={message_id}
    """
    if not message_id or not http_session:
        return False
    
    url = f"{API_BASE_URL}/messages"
    headers = {
        "Authorization": BOT_TOKEN,
        "Content-Type": "application/json"
    }
    params = {"message_id": message_id}
    
    try:
        async with http_session.delete(url, headers=headers, params=params) as response:
            if response.status == 200:
                return True
            elif response.status == 404:
                # Сообщение уже удалено - это нормально
                return False
            else:
                error_text = await response.text()
                print(f"⚠️ Ошибка удаления сообщения {message_id}: {response.status} - {error_text[:200]}")
                return False
    except Exception as e:
        print(f"⚠️ Исключение при удалении сообщения {message_id}: {e}")
        return False


def get_message_id_from_event(event):
    """
    Получение message_id из события (MessageCreated или MessageCallback)
    """
    message_id = None
    
    # Для MessageCreated
    if hasattr(event, 'message') and event.message:
        if hasattr(event.message, 'body') and event.message.body:
            if hasattr(event.message.body, 'mid'):
                message_id = event.message.body.mid
    
    # Для MessageCallback (если нужен message_id сообщения с кнопкой)
    if not message_id and hasattr(event, 'callback') and hasattr(event.callback, 'message'):
        if hasattr(event.callback.message, 'body') and event.callback.message.body:
            if hasattr(event.callback.message.body, 'mid'):
                message_id = event.callback.message.body.mid
    
    return message_id


async def send_message_with_buttons(chat_id: int, text: str, buttons: list, image_url: str = None):
    """
    Отправка сообщения с кнопками через raw MAX API
    Формат кнопок: массив массивов, где каждый внутренний массив - это строка кнопок
    Пример: [[{"type": "callback", "text": "Кнопка", "payload": "test"}]]
    image_url: опциональная ссылка на изображение для отправки
    """
    if not http_session:
        return None
        
    url = f"{API_BASE_URL}/messages"
    headers = {
        "Authorization": BOT_TOKEN,
        "Content-Type": "application/json"
    }
    params = {"chat_id": chat_id}
    
    attachments = []
    
    # Добавляем изображение, если указано
    if image_url:
        attachments.append({
            "type": "image",
            "payload": {
                "url": image_url
            }
        })
    
    # Добавляем кнопки, если указаны
    if buttons:
        attachments.append({
            "type": "inline_keyboard",
            "payload": {
                "buttons": buttons
            }
        })
    
    body = {
        "text": text,
        "attachments": attachments if attachments else []
    }
    
    try:
        async with http_session.post(url, headers=headers, params=params, json=body) as response:
            if response.status == 200:
                return await response.json()
            else:
                error_text = await response.text()
                print(f"Ошибка отправки сообщения с кнопками: {response.status} - {error_text[:200]}")
                return None
    except Exception as e:
        print(f"Исключение при отправке сообщения с кнопками: {e}")
        return None

# Данные о треках
TRACKS_DATA = {
    "track_gamedev": {
        "name": "🎮 БЛОК 1: «Творцы Цифровых Вселенных»",
        "description": "ГЕЙМДЕВ / РАЗРАБОТКА ИГР",
        "speakers": [],
        "schedule": [
            {"time": "11:20-11:50", "event": "(Большой зал) Спикер: Владимир Ковтун — Лекция — «Трудное счастье: зачем нам строить игровую индустрию в каждом городе»"},
            {"time": "11:50-12:20", "event": "(Большой зал) Спикер: Иван Робинашвили — Лекция — «Как стать разработчиком видеоигр в провинции?»"},
            {"time": "11:50-12:20", "event": "(Малый зал) Спикер: Болотов Илья — Лекция — «Лёгкая прогулка или игра на выживание: какие навыки нужны программисту в геймдеве»"},
            {"time": "14:30-15:00", "event": "(Большой зал) Спикер: Эдуард Казначеев — Лекция — «Техническая магия: Как заставить звук в играх быть умным?»"}
        ]
    },
    "track_ai": {
        "name": "🤖 БЛОК 3: «Первопроходцы цифровой трансформации»",
        "description": "ИСКУССТВЕННЫЙ ИНТЕЛЛЕКТ",
        "speakers": [],
        "schedule": [
            {"time": "12:50-13:30", "event": "(Малый зал) Спикеры: Представители цифровых видов спорта — Практическое занятие — «Инновационные виды спорта - двигатель цифровой трансформации общества»"},
            {"time": "12:50-13:30", "event": "(Большой зал) Спикер: Роман Хазеев — Лекция — «Кирпичики ИИ: сервисы, которые нужны всем»"},
            {"time": "13:30-14:00", "event": "(Большой зал) Спикер: Дарья Чукилева — Нетворкинг — «Искусственный интеллект в сфере медиа. Что такое ИИ на самом деле...»"},
            {"time": "15:00-15:30", "event": "(Малый зал) Спикеры: Представители цифровых видов спорта — Практическое занятие — «Инновационные виды спорта - двигатель цифровой трансформации общества»"}
        ]
    },
    "track_drones": {
        "name": "🚁 БЛОК 2: «Герои Воздушного Фронтира»",
        "description": "БЕСПИЛОТНЫЕ ЛЕТАТЕЛЬНЫЕ АППАРАТЫ",
        "speakers": [],
        "schedule": [
            {"time": "11:20-11:50", "event": "(Малый зал) Спикер: Александр Боровлев — Мастер-класс — «Какую роль играют БПЛА в пространственном моделировании»"},
            {"time": "13:30-14:00", "event": "(Малый зал) Спикер: Денис Петров — Практическое занятие/соревнования — «FPV-дроны: от конструкции до применения»"},
            {"time": "15:00-15:30", "event": "(Малый зал) Спикер: Александр Низовцев — Лекция — «Применение БПЛА в электросетях: дистанционный мониторинг, диагностика и повышение надёжности»"}
        ]
    },
    "track_media": {
        "name": "📡 БЛОК 4:  «Медиа будущего: ценности и смыслы»",
        "description": "МЕДИА",
        "speakers": [],
        "schedule": [
            {"time": "14:30-15:00", "event": "(Малый зал) Спикер: Инесса Орел — Тренинг — «Новые медиа: ценности и смыслы»"},
            {"time": "11:00-15:00", "event": "(Подкаст-студия) Активность: Съемка видеоподкастов с IT-специалистами — Формат: Подкаст-студия"}
        ]
    }
}


@dp.bot_started()
async def on_bot_start(event: BotStarted):
    """Обработчик готовности бота"""
    print("Бот готов к работе!")


@dp.message_created(Command('send_feedback'))
async def cmd_send_feedback(event: MessageCreated):
    """Команда для рассылки запросов на обратную связь (только для администратора)"""
    user_id = event.message.sender.user_id
    
    # Проверка на администратора
    from config import ADMIN_ID
    if ADMIN_ID and user_id != ADMIN_ID:
        await event.message.answer("У вас нет прав для выполнения этой команды.")
        return
    
    chat_id = get_chat_id_from_event(event)
    await event.message.answer("Начинаю рассылку запросов на обратную связь...")
    
    # Загружаем список пользователей
    db = load_users_db()
    users = db.get("users", {})
    user_ids = db.get("user_ids", [])
    
    # Формируем список пользователей для рассылки
    user_list = []
    
    # Используем новую структуру с chat_id
    if users:
        for user_id_str, user_data in users.items():
            user_id_val = user_data.get("user_id") or int(user_id_str)
            chat_id_val = user_data.get("chat_id")
            if chat_id_val:
                user_list.append({"user_id": user_id_val, "chat_id": chat_id_val})
    
    # Добавляем пользователей из старой структуры
    if user_ids:
        existing_user_ids = {u["user_id"] for u in user_list}
        for user_id_val in user_ids:
            if user_id_val not in existing_user_ids:
                user_list.append({"user_id": user_id_val, "chat_id": None})
    
    if not user_list:
        await event.message.answer("⚠️ Список пользователей пуст. Попросите пользователей нажать /start.")
        return
    
    success_count = 0
    error_count = 0
    skipped_count = 0
    
    # Загружаем состояния перед рассылкой
    load_user_states()
    
    for i, user_data in enumerate(user_list, 1):
        user_id_val = user_data["user_id"]
        chat_id_val = user_data.get("chat_id")
        
        if not chat_id_val:
            skipped_count += 1
            continue
        
        try:
            await send_feedback_request(user_id_val, chat_id_val)
            # Состояние уже сохранено в send_feedback_request
            success_count += 1
            # Задержка между отправками
            if i < len(user_list):
                await asyncio.sleep(0.5)
        except Exception as e:
            error_count += 1
            print(f"Ошибка отправки пользователю {user_id_val}: {e}")
    
    # Отправляем отчет
    report = (
        f"✅ Рассылка завершена!\n\n"
        f"Успешно: {success_count}\n"
        f"Ошибок: {error_count}\n"
        f"Пропущено (нет chat_id): {skipped_count}\n"
        f"Всего: {len(user_list)}"
    )
    
    if skipped_count > 0:
        report += "\n\n💡 Пользователи без chat_id должны нажать /start в боте."
    
    await event.message.answer(report)


@dp.message_created(Command('start'))
async def cmd_start(event: MessageCreated):
    """Приветственное сообщение"""
    try:
        user_id = event.message.sender.user_id
        chat_id = get_chat_id_from_event(event)
        print(f"Команда /start получена от пользователя {user_id}, chat_id: {chat_id}")
        
        # Сохраняем ID пользователя и chat_id для рассылки
        try:
            await save_user_id(user_id, chat_id)
        except Exception as e:
            print(f"Ошибка сохранения пользователя {user_id}: {e}")
            import traceback
            traceback.print_exc()
            # Продолжаем работу даже если сохранение не удалось
        
        welcome_text = (
            "Рады приветствовать вас на форуме «Цифровая республика. ИТ-герои»\n\n"
            "Это будет точка сборки IT-сообщества, где можно пообщаться с будущими работодателями, "
            "вдохновиться историями успеха и определиться со своей траекторией в IT.\n\n"
            "Когда - 14 ноября 2025 г.\n"
            "Где - Ресурсный молодежный центр\n"
            "г. Сыктывкар, ул. Первомайская, д. 72, 4 этаж"
        )
        
        # Отправляем сообщение с кнопками (структура сохранена)
        buttons = [
            [
                {
                    "type": "link",
                    "text": "Зарегистрироваться",
                    "url": REGISTRATION_URL
                }
            ],
            [
                {
                    "type": "link",
                    "text": "📄 Программа форума",
                    "url": "https://olddigital.rkomi.ru/uploads/documents/programa_it_foruma_na_sayt_2025-10-23_16-15-15.pdf"
                }
            ],
            [
                {
                    "type": "link",
                    "text": "📝 Обратная связь",
                    "url": "https://forms.yandex.ru/u/690b936a84227c94f1ef077f"
                }
            ],
            [
                {
                    "type": "callback",
                    "text": "Я зарегистрировался",
                    "payload": "registered"
                }
            ]
        ]
        
        # Проверяем наличие http_session перед отправкой
        if not http_session:
            print("⚠️ Ошибка: http_session не инициализирован! Бот еще не полностью запущен.")
            await event.message.answer(welcome_text)
            return
        
        result = await send_message_with_buttons(chat_id, welcome_text, buttons)
        if not result:
            # Fallback: используем стандартный метод отправки
            await event.message.answer(welcome_text)
            
    except Exception as e:
        print(f"Критическая ошибка в cmd_start: {e}")
        import traceback
        traceback.print_exc()
        # Пытаемся отправить хотя бы простое сообщение
        try:
            await event.message.answer("Произошла ошибка при обработке команды. Попробуйте позже.")
        except:
            pass




@dp.message_callback()
async def handle_all_callbacks(event: MessageCallback):
    """Универсальный обработчик всех callback - маршрутизация по payload"""
    payload = getattr(event.callback, 'payload', None)
    if not payload:
        return
    
    # Защита от повторной обработки
    callback_id = getattr(event.callback, 'callback_id', None)
    if callback_id and callback_id in processed_callbacks:
        return
    
    if callback_id:
        processed_callbacks.add(callback_id)
        # Очищаем старые callback_id (оставляем последние 1000)
        if len(processed_callbacks) > 1000:
            processed_callbacks.clear()
    
    print(f"[DEBUG] handle_all_callbacks: payload='{payload}'")
    
    # Маршрутизация по payload
    if payload == "registered":
        await handle_registered(event)
    elif payload.startswith("track_"):
        await handle_track_info(event, payload)
    elif payload == "show_menu":
        await handle_show_menu(event)
    elif payload == "send_question":
        await handle_send_question(event)
    elif payload == "cancel_question":
        await handle_cancel_question(event)
    elif payload == "cancel_feedback":
        await handle_cancel_feedback(event)


async def handle_registered(event: MessageCallback):
    """После нажатия на кнопку - показываем информацию о форуме"""
    print(f"[DEBUG] handle_registered: обработка")
    
    # Удаляем старое сообщение
    message_id = get_message_id_from_event(event)
    if message_id:
        await delete_message(message_id)
    forum_info_text = (
        "Форум «Цифровая республика. ИТ-герои».\n\n"
        "Это будет точка сборки IT-сообщества, где можно пообщаться с будущими работодателями, "
        "вдохновиться историями успеха и определиться со своей траекторией в IT.\n\n"
        "4 главных IT-трека форума:\n"
        "GameDev: Раскроем тайны геймдизайна от создателей легендарных «Танков Онлайн» и хитового проекта «Ciliz». "
        "Узнаем, как строят карьеру в игрострое прямо в нашем регионе.\n\n"
        "Искусственный интеллект: Почувствуем мощь AI и узнаем, как нейросети меняют бизнес и нашу жизнь уже сегодня.\n\n"
        "Беспилотники: Не просто дроны, а высокие технологии. Испытаем себя на симуляторе полета и узнаем, "
        "как БПЛА применяют в реальных отраслях.\n\n"
        "Медиа будущего: Разберемся, какие ценности и смыслы правят миром новых медиа и как в этом преуспеть.\n\n"
        "Кроме крутых спикеров участников ждут\n"
        "HR-зона: Прямые разговоры с топовыми работодателями.\n"
        "Лайфхак-сессии: Мастер-классы и тренинги, где научат не теории, а тому, что реально пригодится в работе.\n"
        "Нетворкинг без границ: Находить команду и единомышленников в неформальной обстановке.\n"
        "Техно-арт зона: Технологии на ощупь: фотозоны, демо-стенды, симуляторы.\n"
        "Кружка кофе."
    )
    
    # Отправляем сообщение с кнопками
    buttons = [
        [
            {"type": "callback", "text": "🎮 GameDev", "payload": "track_gamedev"},
            {"type": "callback", "text": "🤖 ИИ", "payload": "track_ai"}
        ],
        [
            {"type": "callback", "text": "🚁 Беспилотники", "payload": "track_drones"},
            {"type": "callback", "text": "📡 Медиа Будущего", "payload": "track_media"}
        ],
        [
            {"type": "callback", "text": "❓ Отправить вопрос", "payload": "send_question"}
        ]
    ]
    
    chat_id = get_chat_id_from_event(event)
    await send_message_with_buttons(chat_id, forum_info_text, buttons)


async def handle_program_show(event: MessageCallback):
    return
    block1 = (
        "БЛОК 1: «Творцы Цифровых Вселенных»\n\n"
        "ГЕЙМДЕВ / РАЗРАБОТКА ИГР\n\n"
        "11:20-11:50 (Большой зал)\n"
        "- Спикер: Владимир Ковтун\n"
        "- Формат: Лекция\n"
        "- Тема: «Трудное счастье: зачем нам строить игровую индустрию в каждом городе»\n\n"
        "11:50-12:20 (Большой зал)\n"
        "- Спикер: Иван Робинашвили\n"
        "- Формат: Лекция\n"
        "- Тема: «Как стать разработчиком видеоигр в провинции?»\n\n"
        "11:50-12:20 (Малый зал)\n"
        "- Спикер: Болотов Илья\n"
        "- Формат: Лекция\n"
        "- Тема: «Лёгкая прогулка или игра на выживание: какие навыки нужны программисту в геймдеве»\n\n"
        "14:30-15:00 (Большой зал)\n"
        "- Спикер: Эдуард Казначеев\n"
        "- Формат: Лекция\n"
        "- Тема: «Техническая магия: Как заставить звук в играх быть умным?»"
    )
    block2 = (
        "БЛОК 2: «Герои Воздушного Фронтира»\n\n"
        "БЕСПИЛОТНЫЕ ЛЕТАТЕЛЬНЫЕ АППАРАТЫ\n\n"
        "11:20-11:50 (Малый зал)\n"
        "- Спикер: Александр Боровлев\n"
        "- Формат: Мастер-класс\n"
        "- Тема: «Какую роль играют БПЛА в пространственном моделировании»\n\n"
        "13:30-14:00 (Малый зал)\n"
        "- Спикер: Денис Петров\n"
        "- Формат: Практическое занятие/соревнования\n"
        "- Тема: «FPV-дроны: от конструкции до применения»\n\n"
        "15:00-15:30 (Малый зал)\n"
        "- Спикер: Александр Низовцев\n"
        "- Формат: Лекция\n"
        "- Тема: «Применение БПЛА в электросетях: дистанционный мониторинг, диагностика и повышение надёжности»"
    )
    block3 = (
        "БЛОК 3: «Первопроходцы цифровой трансформации»\n\n"
        "ИСКУССТВЕННЫЙ ИНТЕЛЛЕКТ\n\n"
        "12:50-13:30 (Малый зал)\n"
        "- Спикеры: Представители цифровых видов спорта\n"
        "- Формат: Практическое занятие\n"
        "- Тема: «Инновационные виды спорта - двигатель цифровой трансформации общества»\n\n"
        "12:50-13:30 (Большой зал)\n"
        "- Спикер: Роман Хазеев\n"
        "- Формат: Лекция\n"
        "- Тема: «Кирпичики ИИ: сервисы, которые нужны всем»\n\n"
        "13:30-14:00 (Большой зал)\n"
        "- Спикер: Дарья Чукилева\n"
        "- Формат: Нетворкинг\n"
        "- Тема: «Искусственный интеллект в сфере медиа. Что такое ИИ на самом деле...»\n\n"
        "15:00-15:30 (Малый зал)\n"
        "- Спикеры: Представители цифровых видов спорта\n"
        "- Формат: Практическое занятие\n"
        "- Тема: «Инновационные виды спорта - двигатель цифровой трансформации общества»"
    )
    block4 = (
        "БЛОК 4:  «Медиа будущего: ценности и смыслы»\n\n"
        "МЕДИА\n\n"
        "14:30-15:00 (Малый зал)\n"
        "- Спикер: Инесса Орел\n"
        "- Формат: Тренинг\n"
        "- Тема: «Новые медиа: ценности и смыслы»\n\n"
        "11:00-15:00 (Подкаст-студия)\n"
        "- Активность: Съемка видеоподкастов с IT-специалистами\n"
        "- Формат: Подкаст-студия"
    )
    # (dead code, preserved intentionally to avoid structural changes)

async def handle_track_info(event: MessageCallback, track_key: str):
    """Показ информации о треке"""
    print(f"[DEBUG] handle_track_info: обработка трека '{track_key}'")
    
    # Удаляем старое сообщение
    message_id = get_message_id_from_event(event)
    if message_id:
        await delete_message(message_id)
    
    track_data = TRACKS_DATA.get(track_key)
    
    if not track_data:
        print(f"  ⚠️ Информация о треке '{track_key}' не найдена в TRACKS_DATA")
        print(f"  Доступные ключи: {list(TRACKS_DATA.keys())}")
        return
    
    # Формируем текст с информацией о треке
    text = f"{track_data['name']}\n\n{track_data['description']}\n\n"
    
    # Добавляем спикеров
    if track_data['speakers']:
        text += "Спикеры:\n"
        for speaker in track_data['speakers']:
            text += f"• {speaker['name']} ({speaker['time']})\n"
            if speaker.get('bio'):
                text += f"  {speaker['bio']}\n"
        text += "\n"
    
    # Добавляем расписание
    if track_data['schedule']:
        text += "Расписание:\n"
        for item in track_data['schedule']:
            text += f"• {item['time']} - {item['event']}\n"
    
    # Отправляем сообщение с кнопками и изображением (если есть)
    buttons = [
        [
            {"type": "callback", "text": "◀️ Назад к меню", "payload": "show_menu"},
            {"type": "callback", "text": "❓ Задать вопрос спикеру", "payload": "send_question"}
        ]
    ]
    
    # Получаем URL изображения для трека
    image_url = TRACK_IMAGES.get(track_key, None)
    
    chat_id = get_chat_id_from_event(event)
    await send_message_with_buttons(chat_id, text, buttons, image_url=image_url)
    # В MAX API нет отдельного эндпоинта для ответа на callback,
    # поэтому не вызываем event.answer() чтобы избежать ошибок


async def handle_show_menu(event: MessageCallback):
    """Возврат к главному меню"""
    print(f"[DEBUG] handle_show_menu: обработка")
    
    # Удаляем старое сообщение
    message_id = get_message_id_from_event(event)
    if message_id:
        await delete_message(message_id)
    forum_info_text = (
        "Форум «Цифровая республика. ИТ-герои».\n\n"
        "Выберите интересующий трек:"
    )
    
    # Отправляем сообщение с кнопками
    buttons = [
        [
            {"type": "callback", "text": "🎮 GameDev", "payload": "track_gamedev"},
            {"type": "callback", "text": "🤖 ИИ", "payload": "track_ai"}
        ],
        [
            {"type": "callback", "text": "🚁 Беспилотники", "payload": "track_drones"},
            {"type": "callback", "text": "📡 Медиа Будущего", "payload": "track_media"}
        ],
        [
            {"type": "callback", "text": "❓ Отправить вопрос", "payload": "send_question"}
        ]
    ]
    
    chat_id = get_chat_id_from_event(event)
    await send_message_with_buttons(chat_id, forum_info_text, buttons)


async def handle_send_question(event: MessageCallback):
    """Обработчик отправки вопроса - отправляем ссылку на яндекс форму"""
    print(f"[DEBUG] handle_send_question: обработка")
    
    # Удаляем старое сообщение
    message_id = get_message_id_from_event(event)
    if message_id:
        await delete_message(message_id)
    
    chat_id = get_chat_id_from_event(event)
    
    if not QUESTION_FORM_URL:
        text = (
            "Для отправки вопроса заполните форму по ссылке.\n"
            "⚠️ Ссылка на форму не настроена. Обратитесь к администратору."
        )
        buttons = [
            [
                {"type": "callback", "text": "◀️ Назад к меню", "payload": "show_menu"}
            ]
        ]
    else:
        text = (
            "Для отправки вопроса спикерам заполните форму по ссылке ниже:\n\n"
            "В форме укажите:\n"
            "• ФИО спикера\n"
            "• Ваш вопрос"
        )
        buttons = [
            [
                {
                    "type": "link",
                    "text": "Открыть форму для вопроса",
                    "url": QUESTION_FORM_URL
                }
            ],
            [
                {"type": "callback", "text": "◀️ Назад к меню", "payload": "show_menu"}
            ]
        ]
    
    await send_message_with_buttons(chat_id, text, buttons)


async def handle_cancel_question(event: MessageCallback):
    """Отмена отправки вопроса"""
    print(f"[DEBUG] handle_cancel_question: обработка")
    
    # Удаляем старое сообщение
    message_id = get_message_id_from_event(event)
    if message_id:
        await delete_message(message_id)
    
    user_id = event.callback.user.user_id
    if user_id in user_states:
        del user_states[user_id]
    
    # Не вызываем event.answer() для избежания ошибок с chat_id = 0
    
    # Возвращаем к меню
    forum_info_text = "Форум «Цифровая республика. ИТ-герои».\n\nВыберите интересующий трек:"
    # Отправляем сообщение с кнопками
    buttons = [
        [
            {"type": "callback", "text": "🎮 GameDev", "payload": "track_gamedev"},
            {"type": "callback", "text": "🤖 ИИ", "payload": "track_ai"}
        ],
        [
            {"type": "callback", "text": "🚁 Беспилотники", "payload": "track_drones"},
            {"type": "callback", "text": "📡 Медиа Будущего", "payload": "track_media"}
        ],
        [
            {"type": "callback", "text": "❓ Отправить вопрос", "payload": "send_question"}
        ]
    ]
    
    chat_id = get_chat_id_from_event(event)
    await send_message_with_buttons(chat_id, forum_info_text, buttons)
    # В MAX API нет отдельного эндпоинта для ответа на callback,
    # поэтому не вызываем event.answer() чтобы избежать ошибок


@dp.message_created()
async def handle_message(event: MessageCreated):
    """Обработка обычных сообщений (для вопросов и отзывов)"""
    # Игнорируем команды (они обрабатываются отдельно)
    if not event.message.body or not event.message.body.text:
        return
    if event.message.body.text.startswith('/'):
        return
    
    user_id = event.message.sender.user_id
    text = event.message.body.text
    # В maxapi User имеет first_name и last_name, но не name
    user_name = f"{event.message.sender.first_name} {event.message.sender.last_name or ''}".strip() or "Неизвестный"
    
    # Загружаем состояния из файла перед проверкой (на случай если они были сохранены из другого процесса)
    # Но не перезаписываем текущие состояния, а объединяем их
    saved_states = {}
    try:
        if os.path.exists(STATES_DB_FILE):
            with open(STATES_DB_FILE, 'r', encoding='utf-8') as f:
                loaded_states = json.load(f)
                for key, value in loaded_states.items():
                    try:
                        if key.isdigit():
                            saved_states[int(key)] = value
                        else:
                            saved_states[key] = value
                    except:
                        saved_states[key] = value
    except Exception as e:
        print(f"Ошибка загрузки состояний: {e}")
    
    # Объединяем сохраненные состояния с текущими (приоритет у текущих)
    for key, value in saved_states.items():
        if key not in user_states:
            user_states[key] = value
    
    # Проверяем состояние пользователя
    user_state = user_states.get(user_id, "")
    
    # Обработка вопроса больше не нужна - используем яндекс форму
    
    # Обработка отзыва (состояние waiting_feedback_*)
    if user_state and user_state.startswith("waiting_feedback"):
        print(f"[DEBUG] Обработка feedback для пользователя {user_id}, состояние: {user_state}")
        await handle_feedback(event, user_id, user_name)
        return
    
    # Если пользователь не в состоянии ожидания feedback, игнорируем сообщение
    # (это нормальное поведение - бот обрабатывает только команды и ответы на вопросы)


async def handle_feedback(event: MessageCreated, user_id: int, user_name: str):
    """Обработка ответов на вопросы обратной связи - вопросы задаются по очереди"""
    # Загружаем состояния из файла перед обработкой
    load_user_states()
    
    state = user_states.get(user_id, "")
    # Загружаем сохраненные ответы из состояния
    feedback_data = user_states.get(f"feedback_{user_id}", {})
    if not feedback_data:
        # Инициализируем структуру если ее нет
        feedback_data = {
            "q1_benefit": "",
            "q2_directions": "",
            "q3_suggestions": ""
        }
    
    text = event.message.body.text if event.message.body else ""
    chat_id = get_chat_id_from_event(event)
    
    print(f"[DEBUG] handle_feedback: user_id={user_id}, state={state}, text={text[:50]}...")
    print(f"[DEBUG] Текущие сохраненные ответы: q1={feedback_data.get('q1_benefit', '')[:30]}..., q2={feedback_data.get('q2_directions', '')[:30]}..., q3={feedback_data.get('q3_suggestions', '')[:30]}...")
    
    if state == "waiting_feedback_q1":
        # Сохраняем ответ на первый вопрос
        feedback_data["q1_benefit"] = text
        user_states[f"feedback_{user_id}"] = feedback_data
        
        # Переходим ко второму вопросу
        user_states[user_id] = "waiting_feedback_q2"
        await save_user_states()
        print(f"[DEBUG] Сохранен ответ на вопрос 1: '{text[:50]}...'")
        print(f"[DEBUG] Переход к вопросу 2, состояние: waiting_feedback_q2")
        print(f"[DEBUG] Текущие ответы: q1={feedback_data.get('q1_benefit', 'НЕТ')[:30]}...")
        
        # Сохраняем message_id вопроса в состоянии для удаления
        question_message_id = user_states.get(f"question_msg_id_{user_id}", None)
        if question_message_id:
            await delete_message(question_message_id)
            del user_states[f"question_msg_id_{user_id}"]
        
        question2_text = (
            "Спасибо за ответ!\n\n"
            "Вопрос 2 из 3:\n"
            "📌 Интересные направления\n"
            "Назовите самую понравившуюся секцию или направление форума:\n\n"
            "• 🚁 «Герои Воздушного Фронтира» (Беспилотные летательные аппараты)\n"
            "• 🎮 «Творцы Цифровых Вселенных» (GameDev/разработка игр)\n"
            "• 🤖 «Первопроходцы цифровой трансформации» (Искусственный интеллект)\n"
            "• 📡 «Медиа будущего: ценности и смыслы» (Медиа)\n\n"
            "Или напишите свой вариант."
        )
        
        buttons = [
            [
                {"type": "callback", "text": "❌ Отмена", "payload": "cancel_feedback"}
            ]
        ]
        
        # Отправляем второй вопрос и сохраняем его message_id
        result = await send_message_with_buttons(chat_id, question2_text, buttons)
        if result and isinstance(result, dict):
            # Извлекаем message_id из ответа API
            msg_id = None
            if "message" in result and "body" in result["message"]:
                msg_id = result["message"]["body"].get("mid")
            if msg_id:
                user_states[f"question_msg_id_{user_id}"] = msg_id
                await save_user_states()
        
    elif state == "waiting_feedback_q2":
        # Сохраняем ответ на второй вопрос (feedback_data уже загружен выше)
        feedback_data["q2_directions"] = text
        user_states[f"feedback_{user_id}"] = feedback_data
        
        # Переходим к третьему вопросу
        user_states[user_id] = "waiting_feedback_q3"
        await save_user_states()
        print(f"[DEBUG] Сохранен ответ на вопрос 2: '{text[:50]}...'")
        print(f"[DEBUG] Переход к вопросу 3, состояние: waiting_feedback_q3")
        print(f"[DEBUG] Текущие ответы: q1={feedback_data.get('q1_benefit', 'НЕТ')[:30]}..., q2={feedback_data.get('q2_directions', 'НЕТ')[:30]}...")
        
        # Удаляем сообщение со вторым вопросом
        question_message_id = user_states.get(f"question_msg_id_{user_id}", None)
        if question_message_id:
            await delete_message(question_message_id)
            del user_states[f"question_msg_id_{user_id}"]
        
        question3_text = (
            "Спасибо за ответ!\n\n"
            "Вопрос 3 из 3:\n"
            "📌 Предложения по улучшению\n"
            "Что стоило бы добавить или убрать в программе будущего форума? "
            "Что улучшить в организации и пр."
        )
        
        buttons = [
            [
                {"type": "callback", "text": "❌ Отмена", "payload": "cancel_feedback"}
            ]
        ]
        
        # Отправляем третий вопрос и сохраняем его message_id
        result = await send_message_with_buttons(chat_id, question3_text, buttons)
        if result and isinstance(result, dict):
            # Извлекаем message_id из ответа API
            msg_id = None
            if "message" in result and "body" in result["message"]:
                msg_id = result["message"]["body"].get("mid")
            if msg_id:
                user_states[f"question_msg_id_{user_id}"] = msg_id
                await save_user_states()
        
    elif state == "waiting_feedback_q3":
        # Загружаем сохраненные ответы (на случай если они были потеряны)
        feedback_data = user_states.get(f"feedback_{user_id}", {})
        if not feedback_data:
            feedback_data = {}
        
        # Сохраняем ответ на третий вопрос
        feedback_data["q3_suggestions"] = text
        user_states[f"feedback_{user_id}"] = feedback_data
        await save_user_states()  # Сохраняем промежуточное состояние
        
        print(f"[DEBUG] Сохранен ответ на вопрос 3, все ответы собраны")
        print(f"[DEBUG] Собранные ответы:")
        print(f"  Q1 (benefit): {feedback_data.get('q1_benefit', 'НЕ СОХРАНЕНО')}")
        print(f"  Q2 (directions): {feedback_data.get('q2_directions', 'НЕ СОХРАНЕНО')}")
        print(f"  Q3 (suggestions): {feedback_data.get('q3_suggestions', 'НЕ СОХРАНЕНО')}")
        
        # Проверяем, что все ответы есть
        if not feedback_data.get('q1_benefit') or not feedback_data.get('q2_directions') or not feedback_data.get('q3_suggestions'):
            print(f"[DEBUG] ⚠️ ВНИМАНИЕ: Не все ответы собраны! Недостающие ответы будут помечены как 'Не указано'")
        
        # Удаляем сообщение с третьим вопросом
        question_message_id = user_states.get(f"question_msg_id_{user_id}", None)
        if question_message_id:
            await delete_message(question_message_id)
            if f"question_msg_id_{user_id}" in user_states:
                del user_states[f"question_msg_id_{user_id}"]
        
        # Сохраняем отзыв в Excel (ответы в отдельных столбцах)
        print(f"[DEBUG] Вызываю excel_manager.save_feedback для user_id={user_id}")
        print(f"[DEBUG] Ответы для сохранения:")
        print(f"  Q1 (benefit): {feedback_data.get('q1_benefit', 'НЕТ')[:50]}...")
        print(f"  Q2 (directions): {feedback_data.get('q2_directions', 'НЕТ')[:50]}...")
        print(f"  Q3 (suggestions): {feedback_data.get('q3_suggestions', 'НЕТ')[:50]}...")
        
        result = await excel_manager.save_feedback(
            user_id=str(user_id),
            user_name=user_name,
            feedback_data={
                "q1_benefit": feedback_data.get("q1_benefit", ""),
                "q2_directions": feedback_data.get("q2_directions", ""),
                "q3_suggestions": feedback_data.get("q3_suggestions", "")
            }
        )
        print(f"[DEBUG] Результат сохранения в Excel: {result}")
        
        if result:
            print(f"[DEBUG] ✅ Отзыв успешно сохранен в Excel для пользователя {user_id}")
        else:
            print(f"[DEBUG] ❌ Ошибка сохранения отзыва в Excel для пользователя {user_id}")
        
        # Очищаем состояния
        if user_id in user_states:
            del user_states[user_id]
        if f"feedback_{user_id}" in user_states:
            del user_states[f"feedback_{user_id}"]
        await save_user_states()
        print(f"[DEBUG] Состояния очищены после сохранения отзыва")
        
        await event.message.answer(
            "✅ Спасибо за обратную связь! Ваше мнение сделает наши будущие события еще лучше."
        )
    else:
        print(f"[DEBUG] Неизвестное состояние feedback: '{state}' для пользователя {user_id}")


async def send_feedback_request(user_id: int, chat_id: int):
    """Отправка запроса на обратную связь пользователю - задаем вопросы по очереди"""
    # Загружаем текущие состояния (если есть)
    load_user_states()
    
    # Инициализируем состояние для сбора отзыва
    user_states[user_id] = "waiting_feedback_q1"
    user_states[f"feedback_{user_id}"] = {
        "q1_benefit": "",
        "q2_directions": "",
        "q3_suggestions": ""
    }
    save_user_states()  # Сохраняем состояния в файл
    
    print(f"[DEBUG] send_feedback_request: Сохранено состояние для пользователя {user_id}: waiting_feedback_q1")
    
    # Отправляем первый вопрос
    question1_text = (
        "Уважаемые участники форума,\n\n"
        "Мы рады, что вы посетили наше мероприятие, и хотим услышать ваше мнение. "
        "Ваши отзывы помогают нам улучшать организацию и содержание мероприятий.\n\n"
        "Вопрос 1 из 3:\n"
        "📌 Польза форума\n"
        "Напишите ваше мнение о форуме. Что было полезно? Что вам понравилось?"
    )
    
    buttons = [
        [
            {"type": "callback", "text": "❌ Отмена", "payload": "cancel_feedback"}
        ]
    ]
    
    # Отправляем первый вопрос и сохраняем его message_id для удаления
    result = await send_message_with_buttons(chat_id, question1_text, buttons)
    if result and isinstance(result, dict):
        # Извлекаем message_id из ответа API
        msg_id = None
        if "message" in result and "body" in result["message"]:
            msg_id = result["message"]["body"].get("mid")
        if msg_id:
            user_states[f"question_msg_id_{user_id}"] = msg_id
            await save_user_states()


async def handle_cancel_feedback(event: MessageCallback):
    """Отмена заполнения обратной связи"""
    print(f"[DEBUG] handle_cancel_feedback: обработка")
    
    user_id = event.callback.user.user_id
    
    # Удаляем сохраненный message_id вопроса, если есть
    question_message_id = user_states.get(f"question_msg_id_{user_id}", None)
    if question_message_id:
        await delete_message(question_message_id)
    
    # Удаляем старое сообщение (сообщение с кнопкой)
    message_id = get_message_id_from_event(event)
    if message_id:
        await delete_message(message_id)
    
    # Очищаем состояния
    if user_id in user_states:
        del user_states[user_id]
    if f"feedback_{user_id}" in user_states:
        del user_states[f"feedback_{user_id}"]
    if f"question_msg_id_{user_id}" in user_states:
        del user_states[f"question_msg_id_{user_id}"]
    save_user_states()  # Сохраняем изменения в файл
    
    chat_id = get_chat_id_from_event(event)
    await send_message_with_buttons(chat_id, "Заполнение обратной связи отменено", [])


# Функция для рассылки отзывов (вызывается вручную или по расписанию)
async def send_feedback_to_all_users(user_ids: list):
    """Рассылка запросов на обратную связь всем пользователям"""
    db = load_users_db()
    for user_id in user_ids:
        try:
            # Для рассылки нужен chat_id, в реальном сценарии нужно его сохранять
            # Здесь используем user_id как chat_id для диалога
            await send_feedback_request(user_id, user_id)
        except Exception as e:
            print(f"Ошибка отправки пользователю {user_id}: {e}")


async def main():
    """Основная функция запуска бота"""
    global http_session
    
    # Загружаем состояния пользователей из файла
    load_user_states()
    
    # Создаем глобальную сессию aiohttp
    http_session = aiohttp.ClientSession()
    
    try:
        print("Бот запущен!")
        print(f"Токен бота: {BOT_TOKEN[:20]}...")
        print("Начинаю polling...")
        await dp.start_polling(bot)
    except KeyboardInterrupt:
        print("\nБот остановлен")
    except Exception as e:
        print(f"Ошибка при запуске бота: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Закрываем сессию при завершении
        if http_session:
            await http_session.close()
            print("HTTP сессия закрыта")


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nБот остановлен пользователем")

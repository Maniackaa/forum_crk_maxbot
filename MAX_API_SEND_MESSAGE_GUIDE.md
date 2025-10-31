# Руководство по отправке сообщений в MAX API

## Правильный формат запроса для отправки сообщений

Для отправки сообщений в MAX API используйте следующий формат:

**Эндпоинт:** `POST https://platform-api.max.ru/messages`

**Заголовки:**
```
Authorization: <BOT_TOKEN>
Content-Type: application/json
```

**Параметры запроса (query params):**
- Для отправки в чат: `?chat_id=<chat_id>`
- Для отправки пользователю: `?user_id=<user_id>`

**Тело запроса (JSON body):**
```json
{
  "text": "Текст сообщения",
  "reply_to": {
    "message_id": "mid.xxx"  // опционально, для ответа на сообщение
  }
}
```

## Важные моменты

1. **`chat_id` или `user_id` передаются как query параметры, НЕ в JSON body**
2. **`text` передается в JSON body**
3. **Не используйте объект `recipient` в body** — это не работает
4. **Для диалогов (личных сообщений) используйте `chat_id` из обновления**
5. **Кнопки передаются в `attachments` с типом `inline_keyboard` и структурой `payload.buttons`**

## Пример кода на Python (aiohttp)

```python
import aiohttp

async def send_message(session: aiohttp.ClientSession, chat_id: int, text: str, reply_to_message_id: str = None):
    url = "https://platform-api.max.ru/messages"
    headers = {
        "Authorization": BOT_TOKEN,
        "Content-Type": "application/json"
    }
    
    # chat_id как query параметр
    params = {"chat_id": chat_id}
    
    # text в JSON body
    body = {"text": text}
    
    if reply_to_message_id:
        body["reply_to"] = {
            "message_id": reply_to_message_id
        }
    
    async with session.post(url, headers=headers, params=params, json=body) as response:
        if response.status == 200:
            return await response.json()
        else:
            error = await response.text()
            raise Exception(f"Ошибка отправки: {response.status} - {error}")
```

## Источники

- Библиотека: https://github.com/max-messenger/max-botapi-python
- Метод: `maxapi.methods.send_message.SendMessage`
- Формат: `chat_id`/`user_id` в query params, `text` в JSON body

## Типичные ошибки

❌ **Неправильно:**
```json
{
  "recipient": {"user_id": 123},
  "body": {"text": "Привет"}
}
```

❌ **Неправильно:**
```json
{
  "chat_id": 123,
  "text": "Привет"
}
```

✅ **Правильно:**
```
POST /messages?chat_id=123
Body: {"text": "Привет"}
```

## Отправка сообщений с кнопками

Для отправки сообщений с inline-кнопками используйте следующий формат:

**Тело запроса (JSON body) с кнопками:**
```json
{
  "text": "Это сообщение с inline-клавиатурой",
  "attachments": [
    {
      "type": "inline_keyboard",
      "payload": {
        "buttons": [
          [
            {
              "type": "callback",
              "text": "Нажми меня!",
              "payload": "button1_pressed"
            },
            {
              "type": "callback",
              "text": "Другая кнопка",
              "payload": "button2_pressed"
            }
          ],
          [
            {
              "type": "link",
              "text": "Открыть ссылку",
              "url": "https://example.com"
            }
          ]
        ]
      }
    }
  ]
}
```

**Важные моменты для кнопок:**

1. **Кнопки передаются в `attachments`**, а не в отдельном поле `buttons`
2. **Тип attachment должен быть `"inline_keyboard"`** (не `"button"`, не `"callback"`)
3. **Структура:** `attachments[0].payload.buttons` - это массив массивов
   - Внешний массив = строки кнопок
   - Внутренний массив = кнопки в строке
4. **Типы кнопок:**
   - `"callback"` - кнопка с callback (payload обязателен)
   - `"link"` - кнопка-ссылка (url обязателен)
5. **Для callback-кнопок:** обязательно поле `payload` (строка) - это значение, которое вернется при нажатии
6. **Для link-кнопок:** обязательно поле `url` (строка) - адрес для перехода

**Пример кода на Python (aiohttp) с кнопками:**

```python
import aiohttp

async def send_message_with_buttons(session: aiohttp.ClientSession, chat_id: int, text: str):
    url = "https://platform-api.max.ru/messages"
    headers = {
        "Authorization": BOT_TOKEN,
        "Content-Type": "application/json"
    }
    params = {"chat_id": chat_id}
    
    body = {
        "text": text,
        "attachments": [
            {
                "type": "inline_keyboard",
                "payload": {
                    "buttons": [
                        [
                            {
                                "type": "callback",
                                "text": "Кнопка 1",
                                "payload": "button1"
                            },
                            {
                                "type": "callback",
                                "text": "Кнопка 2",
                                "payload": "button2"
                            }
                        ],
                        [
                            {
                                "type": "link",
                                "text": "Открыть сайт",
                                "url": "https://example.com"
                            }
                        ]
                    ]
                }
            }
        ]
    }
    
    async with session.post(url, headers=headers, params=params, json=body) as response:
        if response.status == 200:
            return await response.json()
        else:
            error = await response.text()
            raise Exception(f"Ошибка отправки: {response.status} - {error}")
```

## Обработка callback от кнопок

При нажатии на callback-кнопку бот получает обновление типа `message_callback` через `/updates`.

**Формат обновления:**
```json
{
  "update_type": "message_callback",
  "callback": {
    "callback_id": "callback.xxx",
    "payload": "button1",
    "user": {
      "user_id": 123,
      "name": "Имя пользователя"
    }
  },
  "message": {
    "body": {
      "mid": "mid.xxx"
    }
  }
}
```

**Обработка callback:**

⚠️ **Важно:** В MAX API нет отдельного эндпоинта для ответа на callback (эндпоинт `/callbacks` возвращает 404).

⚠️ **Важно для `maxapi` библиотеки:** 
- **НЕ вызывайте `event.answer(notification="")`** для `MessageCallback` событий!
- Это вызовет ошибку `Invalid chatId: 0`, так как у `MessageCallback` нет корректного `chat_id` для отправки уведомления.
- Вместо этого просто отправьте новое сообщение пользователю.

Вместо этого при получении `message_callback` вы можете:
1. Обработать payload кнопки
2. Отправить ответное сообщение пользователю
3. Изменить исходное сообщение (если нужно)

**Пример обработки callback (raw API с aiohttp):**
```python
async def handle_callback(session: aiohttp.ClientSession, callback_data: dict, update: dict):
    callback_id = callback_data.get('callback_id')
    payload = callback_data.get('payload')
    
    # Получаем chat_id из update для отправки ответа
    message_data = update.get("message", {})
    recipient = message_data.get("recipient", {})
    chat_id = recipient.get("chat_id")
    
    # Если chat_id не найден или равен 0, используем user_id из callback
    if not chat_id or chat_id == 0:
        user_data = callback_data.get("user", {})
        chat_id = user_data.get("user_id")  # Для личных диалогов это одно и то же
    
    # Отправляем ответное сообщение
    answer_text = f"✅ Кнопка '{payload}' нажата!"
    await send_message(session, chat_id, answer_text)
    
    print(f"✓ Callback обработан: payload={payload}")


async def send_message(session: aiohttp.ClientSession, chat_id: int, text: str):
    """Отправка сообщения"""
    url = "https://platform-api.max.ru/messages"
    headers = {
        "Authorization": BOT_TOKEN,
        "Content-Type": "application/json"
    }
    params = {"chat_id": chat_id}
    body = {"text": text}
    
    async with session.post(url, headers=headers, params=params, json=body) as response:
        if response.status == 200:
            return await response.json()
        else:
            error = await response.text()
            raise Exception(f"Ошибка: {response.status} - {error}")
```

**Пример обработки callback в `maxapi` библиотеке:**
```python
from maxapi import Bot, Dispatcher
from maxapi.types import MessageCallback

bot = Bot(BOT_TOKEN)
dp = Dispatcher()

def get_chat_id_from_event(event):
    """Получение chat_id из события (MessageCreated или MessageCallback)"""
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

@dp.message_callback(lambda c: c.callback.payload == "button_pressed")
async def handle_button_callback(event: MessageCallback):
    user_id = event.callback.user.user_id
    payload = event.callback.payload
    
    # Получаем chat_id (важно для callback!)
    chat_id = get_chat_id_from_event(event)
    
    # Отправляем новое сообщение
    await send_message_with_buttons(chat_id, f"Кнопка '{payload}' нажата!", [])
    
    # ⚠️ НЕ вызывайте event.answer() - это вызовет ошибку Invalid chatId: 0
    # await event.answer(notification="")  # ❌ НЕ ДЕЛАЙТЕ ТАК!
```

## Типичные ошибки с кнопками

❌ **Неправильно - кнопки в отдельном поле:**
```json
{
  "text": "Привет",
  "buttons": [...]
}
```

❌ **Неправильно - неправильный тип attachment:**
```json
{
  "text": "Привет",
  "attachments": [
    {
      "type": "callback",
      "text": "Кнопка",
      "payload": "test"
    }
  ]
}
```

❌ **Неправильно - кнопки не в payload.buttons:**
```json
{
  "text": "Привет",
  "attachments": [
    {
      "type": "inline_keyboard",
      "buttons": [...]
    }
  ]
}
```

✅ **Правильно:**
```json
{
  "text": "Привет",
  "attachments": [
    {
      "type": "inline_keyboard",
      "payload": {
        "buttons": [
          [
            {
              "type": "callback",
              "text": "Кнопка",
              "payload": "test"
            }
          ]
        ]
      }
    }
  ]
}
```

## Удаление сообщений

MAX API поддерживает удаление сообщений через метод `DELETE`.

**Эндпоинт:** `DELETE https://platform-api.max.ru/messages?message_id={message_id}`

**Заголовки:**
```
Authorization: <BOT_TOKEN>
Content-Type: application/json
```

**Параметры запроса (query params):**
- `message_id` - ID сообщения, которое нужно удалить (например, `mid.0000000002dc43ec019a3a05752119a6`)

**Важные моменты:**

1. **`message_id` передается как query параметр, НЕ в URL path**
2. **Работает для обычных сообщений и сообщений с кнопками**
3. **Возвращает `{"success": true}` при успешном удалении**
4. **При 404 - сообщение уже удалено или не найдено (это нормально)**

**Пример кода на Python (aiohttp):**

```python
import aiohttp

async def delete_message(session: aiohttp.ClientSession, message_id: str):
    """
    Удаление сообщения через raw MAX API
    Правильный формат: DELETE /messages?message_id={message_id}
    """
    if not message_id:
        return False
    
    url = f"https://platform-api.max.ru/messages"
    headers = {
        "Authorization": BOT_TOKEN,
        "Content-Type": "application/json"
    }
    params = {"message_id": message_id}
    
    try:
        async with session.delete(url, headers=headers, params=params) as response:
            if response.status == 200:
                data = await response.json()
                return data.get("success", False)
            elif response.status == 404:
                # Сообщение уже удалено или не найдено
                return False
            else:
                error_text = await response.text()
                print(f"Ошибка удаления сообщения {message_id}: {response.status} - {error_text[:200]}")
                return False
    except Exception as e:
        print(f"Исключение при удалении сообщения {message_id}: {e}")
        return False
```

**Типичные ошибки при удалении:**

❌ **Неправильно - message_id в URL path:**
```
DELETE /messages/mid.0000000002dc43ec019a3a05752119a6
```
Результат: `405 Method Not Allowed`

❌ **Неправильно - message_id в JSON body:**
```
DELETE /messages
Body: {"message_id": "mid.xxx"}
```
Результат: `400 Bad Request` (если API вообще принимает body для DELETE)

✅ **Правильно:**
```
DELETE /messages?message_id=mid.0000000002dc43ec019a3a05752119a6
```
Результат: `200 OK` с `{"success": true}`

**Применение в боте:**

Удаление сообщений полезно для:
- Удаления старых сообщений с кнопками при нажатии на новую
- Очистки диалога от устаревших сообщений
- Создания эффекта "обновления" сообщения (удалить старое + отправить новое)

**Пример использования в обработчике callback:**

```python
@dp.message_callback(lambda c: c.callback.payload == "button_pressed")
async def handle_button_callback(event: MessageCallback):
    # Получаем message_id сообщения с кнопкой
    message_id = get_message_id_from_event(event)
    
    # Удаляем старое сообщение
    if message_id:
        await delete_message(message_id)
    
    # Отправляем новое сообщение
    chat_id = get_chat_id_from_event(event)
    await send_message_with_buttons(chat_id, "Новое сообщение!", buttons)
```

**Примечание:** Редактирование сообщений через `PATCH /messages/{message_id}` или `PUT /messages/{message_id}` в MAX API **не поддерживается** (возвращает 405). Используйте удаление + отправку нового сообщения.



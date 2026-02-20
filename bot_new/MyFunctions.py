from ast import main
import asyncio
import json
import os
import configs
from pyrogram import Client
from pyrogram.types import Message
from gspread.utils import rowcol_to_a1
from pyrogram.errors import PeerIdInvalid
from pyrogram.enums import MessageEntityType
from types import SimpleNamespace
import datetime

JSON_FILE = "prestart_users.json"
DISABLED_USERS_FILE = "disabled_users.json"

def get_data_from_sheet(sheet):
    """
    Возвращает двумерный массив [IDs, flags], вычитанный из таблицы:
      - [0]: столбец с ID
      - [1]: столбец с галочками (TRUE/FALSE)
    """
    column_data1 = sheet.col_values(configs.COLLUM_ID)         # Столбец с ID
    column_data2 = sheet.col_values(configs.COLLUM_CHECKBOX)   # Столбец с галочками
    return [column_data1, column_data2]

def get_FIO_from_sheet(sheet):
    """
    Возвращает список значений из колонки ФИО.
    """
    return sheet.col_values(configs.COLLUM_FIO)

def get_number_of_task_from_sheet(sheet):
    """
    Возвращает список значений из колонки, где хранятся имена (исполнители) задач.
    """
    return sheet.col_values(configs.COLLUM_NAME_TASKS)

def update_this_cell(row, col, new_value, sheet):
    """
    Обновляет значение ячейки (row, col) в Google-таблице на new_value.
    """
    try:
        sheet.update_cell(row, col, new_value)
        print(f"Ячейка ({row}, {col}) успешно обновлена на: {new_value}")
    except Exception as e:
        print(f"Ошибка при обновлении ячейки ({row}, {col}): {e}")

def check_condition(sheet, id):
    """
    Проверяет, есть ли указанный ID в первом столбце данных (COLLUM_ID).
    Возвращает 1, если ID найден, иначе 0.
    """
    data = get_data_from_sheet(sheet)
    start_index = configs.CELL_OF_START_DATA - 1
    while start_index < len(data[0]):
        if str(id) == data[0][start_index]:
            return 1
        start_index += 1
    return 0

def is_admin(user_id):
    return user_id in configs.ADMINS

def process_premium_emoji_message(msg):
    """
    Обрабатывает премиум-эмодзи в тексте:
    оборачивает каждую CUSTOM_EMOJI в <emoji id=ID>...</emoji>.
    """
    if not msg or not msg.text:
        return msg.text if msg and msg.text else ""

    text = msg.text
    entities = msg.entities or []
    custom_entities = [
        e for e in entities
        if e.type == MessageEntityType.CUSTOM_EMOJI and hasattr(e, "custom_emoji_id")
    ]
    if not custom_entities:
        return text

    custom_entities.sort(key=lambda e: e.offset)
    parts = []
    last_offset = 0

    for e in custom_entities:
        parts.append(text[last_offset:e.offset])
        original_emoji = text[e.offset:e.offset + e.length]
        parts.append(f"<emoji id={e.custom_emoji_id}>{original_emoji}</emoji>")
        last_offset = e.offset + e.length

    parts.append(text[last_offset:])
    return "".join(parts)

def prepare_message_text(message: Message) -> (bool, str):
    """
    Определяет, содержит ли message медиа, и возвращает:
      - is_media (bool),
      - processed_text (str) — текст/заголовок сообщения с обработанными премиум-эмодзи.
    """
    is_media = bool(message.photo or message.video or message.video_note)
    if is_media:
        raw_text = message.caption or ""
        dummy_msg = SimpleNamespace(text=raw_text, entities=message.caption_entities)
        processed_text = process_premium_emoji_message(dummy_msg)
    else:
        processed_text = process_premium_emoji_message(message)
    return is_media, processed_text

async def send_message_to_users_name(client: Client, message: Message, sheet):
    print("Вызвана функция отправки персонализированного сообщения")

    data = get_data_from_sheet(sheet)
    fio_list = get_FIO_from_sheet(sheet)
    start_data_index = configs.CELL_OF_START_DATA - 1

    ids = data[0][start_data_index:]
    check_flags = data[1][start_data_index:]
    fio_data = fio_list[start_data_index:]

    is_media = bool(message.photo or message.video or message.video_note)
    base_text = message.caption if is_media else message.text
    base_text = (
        process_premium_emoji_message(SimpleNamespace(text=base_text, entities=message.caption_entities))
        if is_media else process_premium_emoji_message(message)
    )

    for offset, chat_id in enumerate(ids):
        row_index = start_data_index + offset + 1
        if check_flags[offset] == "TRUE":
            try:
                # Проверка валидности chat_id перед отправкой
                peer = await client.resolve_peer(chat_id)
                if not peer:
                    print(f"Неверный ID чата: {chat_id}")
                    continue

                middle_word = get_middle_word(fio_data[offset])
                personalized_text = base_text.replace("[name]", middle_word) if middle_word != -1 else base_text

                await send_message_to_user_with_name(
                    client=client,
                    chat_id=chat_id,
                    is_media=is_media,
                    message=message,
                    personalized_text=personalized_text,
                    sheet=sheet,
                    row_index=row_index
                )
                await asyncio.sleep(60)
            except PeerIdInvalid:
                print(f"Некорректный ID чата: {chat_id}")
                continue
            except Exception as e:
                print(f"Ошибка отправки для {chat_id}: {str(e)}")
                continue

async def send_message_to_users(client: Client, message: Message, sheet):
    print("Вызвана функция отправки сообщения без персонализации")

    data = get_data_from_sheet(sheet)
    is_media, processed_text = prepare_message_text(message)
    start_data_index = configs.CELL_OF_START_DATA - 1
    data_ids = data[0][start_data_index:]
    data_checks = data[1][start_data_index:]

    for offset, chat_id in enumerate(data_ids):
        row_number = start_data_index + offset + 1
        if data_checks[offset] == "TRUE":
            try:
                # Проверка валидности chat_id
                peer = await client.resolve_peer(chat_id)
                if not peer:
                    print(f"Неверный ID чата: {chat_id}")
                    continue

                await send_message_to_user_with_name(
                    client=client,
                    chat_id=chat_id,
                    is_media=is_media,
                    message=message,
                    personalized_text=processed_text,
                    sheet=sheet,
                    row_index=row_number
                )
                await asyncio.sleep(60)
            except PeerIdInvalid:
                print(f"Некорректный ID чата: {chat_id}")
                continue
            except Exception as e:
                print(f"Ошибка отправки для {chat_id}: {str(e)}")
                continue

async def send_message_to_user_with_name(client: Client, chat_id, is_media: bool,
                                         message: Message, personalized_text: str,
                                         sheet, row_index: int):

    """
    Отправляет (персонализированное) сообщение конкретному пользователю,
    обновляет столбцы флага (FALSE) и статуса (время отправки).
    """
    try:
        if message.photo:
            await client.send_photo(chat_id=chat_id, photo=message.photo.file_id, caption=personalized_text)
        elif message.video:
            await client.send_video(chat_id=chat_id, video=message.video.file_id, caption=personalized_text)
        elif message.document:
            await client.send_document(chat_id=chat_id, document=message.document.file_id, caption=personalized_text)
        elif message.audio:
            await client.send_audio(chat_id=chat_id, audio=message.audio.file_id, caption=personalized_text)
        elif message.voice:
            await client.send_voice(chat_id=chat_id, voice=message.voice.file_id, caption=personalized_text)
        elif message.video_note:
            await client.send_video_note(chat_id=chat_id, video_note=message.video_note.file_id)
        else:
            await client.send_message(chat_id=chat_id, text=personalized_text)

        current_time = datetime.datetime.now().strftime("%H:%M:%S %d.%m.%Y")
        status_text = f"Отправлено ({current_time})"

        update_this_cell(row_index, configs.COLLUM_CHECKBOX, "FALSE", sheet)
        update_this_cell(row_index, configs.COLLUM_STATUS, status_text, sheet)
        print(f"Сообщение успешно отправлено пользователю с ID {chat_id}.")
    except Exception as e:
        update_this_cell(row_index, configs.COLLUM_CHECKBOX, "FALSE", sheet)
        update_this_cell(row_index, configs.COLLUM_STATUS, "Ошибка!", sheet)
        print(f"Ошибка при отправке сообщения пользователю с ID {chat_id}: {e}")

def task(data, sheet, id):
    """
    Добавляет строку в таблицу задач (Tasks),
    используя performer, task, description, deadline из data.
    """
    number = get_number_of_task_from_sheet(sheet)
    row = len(number) + 1
    update_this_cell(row, configs.COLLUM_NAME_TASKS, data['performer'], sheet)
    update_this_cell(row, configs.COLLUM_TASK_TASKS, data['task'], sheet)
    update_this_cell(row, configs.COLLUM_DESCRIPTION_TASKS, data['description'], sheet)
    update_this_cell(row, configs.COLLUM_DEADLINE_TASKS, data['deadline'], sheet)

def team(data, sheet, id):
    """
    Добавляет строку в таблицу команды (Team),
    используя FIO, place и записывая также ID.
    """
    number = get_number_of_task_from_sheet(sheet)
    row = len(number) + 1
    update_this_cell(row, configs.COLLUM_NAME_TEAM, data['FIO'], sheet)
    update_this_cell(row, configs.COLLUM_FILIAL_TEAM, data['place'], sheet)
    update_this_cell(row, configs.COLLUM_ID_TEAM, id, sheet)

def update_user_note(chat_id, user_id, sheet, new_message):
    """
    Добавляет (или дополняет) примечание к ячейке напротив конкретного chat_id:
      - Если пишет сам ребёнок, пишется "-Ребенок: ..."
      - Если пишет админ (user_id != chat_id), пишется "-Админ: ..."
    """
    user_index = S_of_user(chat_id, sheet)
    if user_index is None:
        print(f"Пользователь с chat_id {chat_id} не найден в таблице.")
        return

    collum_user = int(user_index) + 1
    note_text = sheet.get_note(rowcol_to_a1(collum_user, configs.COLLUM_STATUS))

    if user_id == chat_id:
        add = f"\n-Ребенок: {new_message}\n"
    else:
        add = f"\n-Админ: {new_message}\n"

    new_note = str(note_text) + str(add)
    sheet.update_note(rowcol_to_a1(collum_user, configs.COLLUM_STATUS), new_note)

def S_of_user(id, sheet):
    """
    Возвращает индекс (с 0) в столбце COLLUM_ID, где найдено совпадение с id.
    Если нет — возвращает None.
    """
    try:
        return sheet.col_values(configs.COLLUM_ID).index(str(id))
    except ValueError:
        return None

def get_middle_word(sentence):
    """
    Для строки из трёх слов (ФИО), возвращает второе (имя).
    Если слов не три — возвращает -1.
    """
    words = sentence.split()
    if len(words) == 3:
        return words[1]
    return -1

async def cancel_dialog(client, chat_id, seconds: int):
    """
    Асинхронный таймер: ждем seconds секунд. Если пользователь не ответит за это время —
    сбрасываем диалог и уведомляем его.
    """
    try:
        await asyncio.sleep(seconds)
        if chat_id in main.user_states:
            del main.user_states[chat_id]
        if chat_id in main.user_data:
            del main.user_data[chat_id]
        if chat_id in main.user_timers:
            del main.user_timers[chat_id]

        await client.send_message(
            chat_id,
            f"Время ожидания ({seconds} секунд) истекло. Заполнение отменено.\n"
            "Введите /team, если хотите попробовать снова."
        )
        print(f"Таймер истёк: сброс данных у chat_id={chat_id}")
    except asyncio.CancelledError:
        pass

def load_prestart_users():
    """
    Загружает список ID пользователей из JSON-файла.
    Если файл не существует или пуст — возвращает пустое множество.
    """
    if not os.path.exists(JSON_FILE):
        return set()

    try:
        with open(JSON_FILE, "r", encoding="utf-8") as f:
            # Проверяем, не пустой ли файл
            content = f.read().strip()
            if not content:
                return set()

            data = json.loads(content)
            return set(data)

    except (json.JSONDecodeError, Exception) as e:
        print(f"⚠️ Ошибка при чтении {JSON_FILE}: {e}")
        return set()

def save_prestart_users(user_ids):
    """
    Сохраняет множество user_ids в JSON-файл.
    """
    try:
        with open(JSON_FILE, "w", encoding="utf-8") as f:
            json.dump(
                list(user_ids),
                f,
                ensure_ascii=False,
                indent=2
            )
    except Exception as e:
        print(f"⚠️ Ошибка при сохранении в {JSON_FILE}: {e}")

async def send_message_to_unreg_users(user_ids, original_msg, client: Client):
    from pyrogram.errors import PeerIdInvalid

    _, caption = prepare_message_text(original_msg)
    failed_ids = []

    for user_id in user_ids:
        try:
            # Отправляем как есть
            if original_msg.photo:
                await client.send_photo(chat_id=user_id, photo=original_msg.photo.file_id, caption=caption)
            elif original_msg.video:
                await client.send_video(chat_id=user_id, video=original_msg.video.file_id, caption=caption)
            elif original_msg.document:
                await client.send_document(chat_id=user_id, document=original_msg.document.file_id, caption=caption)
            elif original_msg.audio:
                await client.send_audio(chat_id=user_id, audio=original_msg.audio.file_id, caption=caption)
            elif original_msg.voice:
                await client.send_voice(chat_id=user_id, voice=original_msg.voice.file_id, caption=caption)
            elif original_msg.video_note:
                await client.send_video_note(chat_id=user_id, video_note=original_msg.video_note.file_id)
            else:
                await client.send_message(chat_id=user_id, text=caption)

            print(f"✅ Сообщение отправлено: {user_id}")
            # Добавляем задержку в 3 секунды между сообщениями
            await asyncio.sleep(10)

        except Exception as e:
            print(f"❌ Общая ошибка для {user_id}: {e}")
            failed_ids.append(user_id)

def is_global_disabled():
    """
    Проверяет, отключен ли бот глобально.
    """
    try:
        with open(DISABLED_USERS_FILE, "r", encoding="utf-8") as f:
            content = f.read().strip()
            if not content:
                return False
            data = json.loads(content)
            return data.get("global_disabled", False)
    except (json.JSONDecodeError, Exception) as e:
        print(f"⚠️ Ошибка при чтении {DISABLED_USERS_FILE}: {e}")
        return False

def toggle_global_disabled():
    """
    Переключает глобальное состояние бота (включает/отключает).
    Возвращает True, если бот был отключен, False если включен.
    """
    try:
        with open(DISABLED_USERS_FILE, "r", encoding="utf-8") as f:
            content = f.read().strip()
            if not content:
                data = {"global_disabled": True, "disabled_users": []}
            else:
                data = json.loads(content)
                data["global_disabled"] = not data.get("global_disabled", False)
        
        with open(DISABLED_USERS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        return data["global_disabled"]
    except Exception as e:
        print(f"⚠️ Ошибка при сохранении в {DISABLED_USERS_FILE}: {e}")
        return False

def load_disabled_users():
    """
    Загружает список ID отключенных пользователей из JSON-файла.
    Если файл не существует или пуст — возвращает пустой список.
    """
    if not os.path.exists(DISABLED_USERS_FILE):
        # Создаем файл с правильной структурой
        with open(DISABLED_USERS_FILE, "w", encoding="utf-8") as f:
            json.dump({"disabled_users": []}, f, ensure_ascii=False, indent=2)
        return []

    try:
        with open(DISABLED_USERS_FILE, "r", encoding="utf-8") as f:
            content = f.read().strip()
            if not content:
                return []
            data = json.loads(content)
            # Преобразуем все ID в числа
            return [int(uid) for uid in data.get("disabled_users", [])]
    except (json.JSONDecodeError, Exception) as e:
        print(f"⚠️ Ошибка при чтении {DISABLED_USERS_FILE}: {e}")
        return []

def save_disabled_users(disabled_users):
    """
    Сохраняет список отключенных пользователей в JSON-файл.
    """
    try:
        data = {"disabled_users": disabled_users}
        with open(DISABLED_USERS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"⚠️ Ошибка при сохранении в {DISABLED_USERS_FILE}: {e}")

def is_user_disabled(user_id):
    """
    Проверяет, отключен ли пользователь.
    """
    disabled_users = load_disabled_users()
    return int(user_id) in disabled_users

def toggle_user_disabled(user_id):
    """
    Переключает статус пользователя (включает/отключает).
    Возвращает True, если пользователь был отключен, False если включен.
    """
    disabled_users = load_disabled_users()
    user_id = int(user_id)  # Преобразуем в число
    if user_id in disabled_users:
        disabled_users.remove(user_id)
        save_disabled_users(disabled_users)
        return False
    else:
        disabled_users.append(user_id)
        save_disabled_users(disabled_users)
        return True

def load_command_messages():
    """Загружает сообщения команд из файла"""
    try:
        if os.path.exists('command_messages.json'):
            with open('command_messages.json', 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}
    except Exception as e:
        print(f"Ошибка при загрузке сообщений команд: {e}")
        return {}

def save_command_messages(messages):
    """Сохраняет сообщения команд в файл"""
    try:
        with open('command_messages.json', 'w', encoding='utf-8') as f:
            json.dump(messages, f, ensure_ascii=False, indent=4)
        return True
    except Exception as e:
        print(f"Ошибка при сохранении сообщений команд: {e}")
        return False

def get_command_message(command_name, **kwargs):
    """Получает сообщение для команды с подстановкой параметров"""
    messages = load_command_messages()
    message = messages.get(command_name, "")
    try:
        return message.format(**kwargs)
    except Exception:
        return message

def update_command_message(command_name, new_message):
    """Обновляет сообщение для команды"""
    messages = load_command_messages()
    messages[command_name] = new_message
    return save_command_messages(messages)

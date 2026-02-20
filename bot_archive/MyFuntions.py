import configs
from pyrogram import Client
from pyrogram.types import Message
from gspread.utils import rowcol_to_a1
from pyrogram.enums import MessageEntityType
from types import SimpleNamespace
import datetime


def get_data_from_sheet(sheet):

    # Считывание данных из двух столбцов (например, первого столбца)
    column_data1 = sheet.col_values(configs.COLLUM_ID)  # Столбец с ID
    column_data2 = sheet.col_values(configs.COLLUM_CHECKBOX)  # Стобец с галочками
    double_column_data = [column_data1, column_data2] # объединяем в двумерный массив
    return double_column_data

def get_FIO_from_sheet(sheet):

    # Считывание данных из двух столбцов (например, первого столбца)
    column_data = sheet.col_values(configs.COLLUM_FIO)  # Столбец с ФИО

    return column_data
def get_number_of_task_from_sheet(sheet):

    # Считывание данных из двух столбцов (например, первого столбца)
    column_data = sheet.col_values(configs.COLLUM_NAME_TASKS)  # Столбец с именами исполнителей
    return  column_data

def prepare_message_text(message: Message) -> (bool, str):
    """
    Обрабатывает исходное сообщение и возвращает флаг is_photo и обработанный текст.
    Если сообщение содержит фото, используется caption и caption_entities.
    """
    is_photo = bool(message.photo)
    if is_photo:
        raw_text = message.caption or ""
        dummy_msg = SimpleNamespace(text=raw_text, entities=message.caption_entities)
        processed_text = process_premium_emoji_message(dummy_msg)
    else:
        processed_text = process_premium_emoji_message(message)
    return is_photo, processed_text


async def send_message_to_users(client: Client, message: Message, sheet):

    print("Вызвана функция отправки сообщения без персонализации")
    data = get_data_from_sheet(sheet)
    is_photo, processed_text = prepare_message_text(message)

    # Определяем, с какого индекса в списках начинаются реальные данные
    start_data_index = configs.CELL_OF_START_DATA - 1  # индексация списков начинается с 0
    data_ids = data[0][start_data_index:]
    data_checks = data[1][start_data_index:]

    # Перебираем реальные данные, передавая в цикл номер строки таблицы
    for offset, chat_id in enumerate(data_ids):
        row_number = start_data_index + offset + 1  # +1, чтобы получить номер строки (если строки начинаются с 1)
        if data_checks[offset] == "TRUE":
            await send_message_to_user_with_name(client, chat_id, is_photo, message, processed_text, sheet, row_number)


async def send_message_to_users_name(client: Client, message: Message, sheet):
    """
    Отправляет персонализированное сообщение (с именем пользователя) всем отмеченным в таблице пользователям.

    Логика:
      1. Получаем данные: список chat_id и список флагов (TRUE/FALSE) для отправки,
         а также список ФИО для персонализации.
      2. Определяем, что отправлять: если сообщение содержит фото — берем caption, иначе message.text.
      3. Проверяем, содержит ли сообщение перенос строки:
         - Если нет — уведомляем администратора и отменяем выполнение команды.
      4. Для каждого пользователя (с учетом смещения, заданного в configs.CELL_OF_START_DATA)
         проверяем условие и формируем персонализированное сообщение:
            - Выделяем часть текста до и после первого переноса строки.
            - Из ФИО извлекаем центральное слово (имя).
            - Собираем итоговое сообщение.
      5. Отправляем сообщение выбранным пользователям и обновляем статус в таблице.
    """
    print("Вызвана функция отправки персонализированного сообщения")

    # Получаем данные из таблицы
    data = get_data_from_sheet(sheet)
    fio_list = get_FIO_from_sheet(sheet)

    # Определяем смещение: данные начинаются с определённой строки (в списках с индексом)
    start_data_index = configs.CELL_OF_START_DATA - 1
    ids = data[0][start_data_index:]
    check_flags = data[1][start_data_index:]
    fio_data = fio_list[start_data_index:]

    # Определяем, что отправлять: текст или фото
    is_photo = bool(message.photo)
    base_text = message.caption if is_photo else message.text


    # Обрабатываем base_text через process_premium_emoji_message для поддержки премиум эмодзи.
    base_text = (
        process_premium_emoji_message(SimpleNamespace(text=base_text, entities=message.caption_entities))
        if is_photo else process_premium_emoji_message(message)
    )

    # Перебираем данные, корректно вычисляя номер строки таблицы
    for offset, chat_id in enumerate(ids):
        row_index = start_data_index + offset + 1  # +1, если нумерация строк в таблице начинается с 1
        if check_flags[offset] == "TRUE":
            # Формируем персонализированное сообщение, вставляя имя пользователя

            personalized_text = base_text.replace("[name]",get_middle_word(fio_data[offset]))
            # Отправляем персонализированное сообщение и обновляем статус в таблице
            await send_message_to_user_with_name(client, chat_id, is_photo, message, personalized_text, sheet, row_index)



async def send_message_to_user_with_name(client: Client, chat_id, is_photo: bool, message: Message,
                                         personalized_text: str, sheet, row_index: int):
    """
    Отправляет персонализированное сообщение одному пользователю и обновляет статус в таблице.

    Аргументы:
        client (Client): Клиент Pyrogram.
        chat_id: ID чата пользователя.
        is_photo (bool): True, если сообщение содержит фото.
        message (Message): Исходное сообщение от администратора.
        personalized_text (str): Персонализированное сообщение, подготовленное функцией prepare_personalized_message.
        sheet: Таблица для обновления статуса.
        row_index (int): Номер строки в таблице, которую нужно обновить.
    """
    try:
        if is_photo:
            await client.send_photo(
                chat_id=chat_id,
                photo=message.photo.file_id,
                caption=personalized_text
            )
        else:
            await client.send_message(
                chat_id=chat_id,
                text=personalized_text
            )

        # Получаем текущее время в формате HH:MM:SS DD.MM.YYYY
        current_time = datetime.datetime.now().strftime("%H:%M:%S %d.%m.%Y")
        status_text = f"Отправлено ({current_time})"

        update_this_cell(row_index, configs.COLLUM_CHECKBOX, "FALSE", sheet)
        update_this_cell(row_index, configs.COLLUM_STATUS, status_text, sheet)
        print(f"Сообщение успешно отправлено пользователю с ID {chat_id}.")
    except Exception as e:
        update_this_cell(row_index, configs.COLLUM_CHECKBOX, "FALSE", sheet)
        update_this_cell(row_index, configs.COLLUM_STATUS, "Ошибка!", sheet)
        print(f"Ошибка при отправке сообщения пользователю с ID {chat_id}: {e}")



def is_admin(user_id):
    return user_id in configs.ADMINS


def update_this_cell(row, col, new_value,sheet):
    """
    Изменяет значение ячейки по номеру строки и столбца в Google Таблице.

    Args:
        row (int): Номер строки (начиная с 1).
        col (int): Номер столбца (начиная с 1).
        new_value (str): Новое значение для ячейки.
    """
    try:
        # Обновляем значение ячейки по номеру строки и столбца
        sheet.update_cell(row, col, new_value)
        print(f"Ячейка ({row}, {col}) успешно обновлена на: {new_value}")
    except Exception as e:
        print(f"Ошибка при обновлении ячейки ({row}, {col}): {e}")


def check_condition(sheet, id):
    """
    Проверяет, есть ли указанный ID в первом столбце данных.

    Args:
        sheet: Google Таблица или другой источник данных.
        id: ID для поиска.

    Returns:
        int: 1, если ID найден, 0 - если не найден.
    """
    data = get_data_from_sheet(sheet)
    n = configs.CELL_OF_START_DATA - 1

    # Проверяем наличие ID в массиве
    while n < len(data[0]):
        if str(id) == data[0][n]:  # Приводим ID к строке для корректного сравнения
            return 1  # Возвращаем 1, если найден
        n += 1

    return 0  # Возвращаем 0, если не найден

def task (data,sheet,id): # в этой функции нужно сделать так, чтобы он вносил все эти данные в певую свободную строку в отдельной таблице
    number = get_number_of_task_from_sheet(sheet)
    update_this_cell(len(number) + 1, configs.COLLUM_NAME_TASKS, data['performer'], sheet)
    update_this_cell(len(number) + 1, configs.COLLUM_TASK_TASKS, data['task'], sheet)
    update_this_cell(len(number) + 1, configs.COLLUM_DESCRIPTION_TASKS, data['description'], sheet)
    update_this_cell(len(number) + 1, configs.COLLUM_DEADLINE_TASKS, data['deadline'], sheet)

def team (data,sheet,id): # в этой функции нужно сделать так, чтобы он вносил все эти данные в певую свободную строку в отдельной таблице
    number = get_number_of_task_from_sheet(sheet)
    update_this_cell(len(number) + 1, configs.COLLUM_NAME_TEAM, data['FIO'], sheet)
    update_this_cell(len(number) + 1, configs.COLLUM_FILIAL_TEAM, data['place'], sheet)
    update_this_cell(len(number) + 1, configs.COLLUM_ID_TEAM, id, sheet)


def update_user_note(chat_id, user_id, sheet, new_message): #Добавляет сообщение к коментарию в ячейке напротив конкретного ребенка

    user_index=S_of_user(chat_id, sheet) #Получаем индекс строки, в которой находится chat_id

    if user_index is None: # Проверяем, нашелся ли индекс. Если строки с индексом не нашлось, просто выходим из функции.
        print(f"Пользователь с chat_id {chat_id} не найден в таблице.")
        return

    # Индекс строки в таблице (приводим к порядковому номеру, начиная с 1)
    collum_user= int(S_of_user(chat_id,sheet)) + 1

    # Получаем существующее примечание из ячейки
    note_text = sheet.get_note(rowcol_to_a1(collum_user,configs.COLLUM_STATUS))

    #Выбираем, как величать отправившего сообщение. Если id совпадает с id чата, то сообщение отправил ребенок. Добавляем соответствующее обозначение
    if user_id == chat_id:
        add = f"\n-Ребенок: {new_message}\n"
    else:
        add = f"\n-Админ: {new_message}\n"

    # Добавляем сформированное выше сообщение к полученному значению ячейки
    new_note = str(note_text) + str(add)

    sheet.update_note(rowcol_to_a1(collum_user,configs.COLLUM_STATUS), new_note) #Добавляем в таблицу

def S_of_user(id,sheet): # определяет, в какой строке в гугл таблице находится пользователь с конкретным id
    try:
        index = sheet.col_values(configs.COLLUM_ID).index(f"{id}")
        return index
    except ValueError:
        return None  # Возвращаем None, если число не найдено


def extract_words_before_newline(text): #Возвращает все до символа переноса строки
    """
    Извлекает все слова до символа переноса строки (\n) из строки текста.

    Args:
        text (str): Исходный текст.

    Returns:
        str: Слова до первого переноса строки, объединённые в строку.
    """
    # Найти позицию первого переноса строки
    newline_index = text.find("\n")

    # Если переноса строки нет, вернуть весь текст
    if newline_index == -1:
        return -1

    # Вернуть текст до переноса строки
    return text[:newline_index].strip()

def extract_words_after_newline(text): #Возвращает все после символа переноса строки
    """
    Извлекает все слова до символа переноса строки (\n) из строки текста.

    Args:
        text (str): Исходный текст.

    Returns:
        str: Слова до первого переноса строки, объединённые в строку.
    """
    # Найти позицию первого переноса строки
    newline_index = text.find("\n")

    # Если переноса строки нет, вернуть весь текст
    if newline_index == -1:
        return -1

    # Вернуть текст до переноса строки
    return text[newline_index:].strip()

def get_middle_word(sentence):  #Возвращает центральное слово (Имя из ФИО)
    # Разделяем строку на слова
    words = sentence.split()
    # Проверяем, что слов ровно три
    if len(words) == 3:
        return words[1]  # Центральное слово
    else:
        return -1


def process_premium_emoji_message(msg):
    """
    Обрабатывает сообщение: оборачивает каждую премиум-эмодзи в теги вида
    <emoji id=ID>эмодзи</emoji>.

    Если премиум-эмодзи не найдены, возвращает исходный текст.

    :param msg: объект Message (ожидается, что msg.text и msg.entities заданы)
    :return: строка с обработанными эмодзи
    """
    if not msg or not msg.text:
        return msg.text if msg and msg.text else ""

    text = msg.text
    entities = msg.entities or []

    # Выбираем только сущности типа CUSTOM_EMOJI (премиум-эмодзи)
    custom_entities = [
        e for e in entities
        if e.type == MessageEntityType.CUSTOM_EMOJI and hasattr(e, "custom_emoji_id")
    ]

    # Если премиум-эмодзи не найдены, возвращаем оригинальный текст
    if not custom_entities:
        return text

    # Сортируем сущности по порядку в тексте
    custom_entities.sort(key=lambda e: e.offset)

    parts = []
    last_offset = 0

    for e in custom_entities:
        # Добавляем кусок текста до эмодзи
        parts.append(text[last_offset:e.offset])
        # Извлекаем оригинальный символ эмодзи из текста
        original_emoji = text[e.offset:e.offset + e.length]
        # Оборачиваем его в нужные теги
        parts.append(f"<emoji id={e.custom_emoji_id}>{original_emoji}</emoji>")
        last_offset = e.offset + e.length

    # Добавляем остаток текста после последней эмодзи
    parts.append(text[last_offset:])

    return "".join(parts)

def extract_after_first_space(s: str) -> str:
    """
    Возвращает подстроку, которая следует после первого пробела.
    Если пробела нет, возвращает пустую строку.
    """
    parts = s.split(" ", 1)
    return parts[1] if len(parts) > 1 else ""
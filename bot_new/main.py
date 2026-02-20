from pyrogram import Client, filters, enums
from decouple import config
from pyrogram.types import Message
from pyrogram.handlers import MessageHandler
import asyncio
import configs
import MyFunctions
from MyFunctions import send_message_to_users_name
from MyFunctions import send_message_to_users
from MyFunctions import is_admin
from MyFunctions import check_condition
from MyFunctions import is_user_disabled
from MyFunctions import is_global_disabled
import __init__
import logging
import os
from logging.handlers import RotatingFileHandler
from types import SimpleNamespace

ignorFlag = False
sn_active = False  # Флаг для контроля процесса рассылки

# Настройка логирования
if not os.path.exists('logs'):
    os.makedirs('logs')

# Создаем обработчик для файла с ротацией
file_handler = RotatingFileHandler(
    'logs/bot.log',
    maxBytes=10*1024*1024,  # 10MB
    backupCount=5
)
file_handler.setFormatter(logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
))

# Настраиваем корневой логгер
logging.basicConfig(
    level=logging.INFO,
    handlers=[file_handler]
)

# Создаем логгер для нашего бота
logger = logging.getLogger('telegram_bot')

# Инициализация бота (Pyrogram Client)
bot = Client(
    name=config('LOGIN'),
    api_id=config('API_ID'),
    api_hash=config('API_HASH'),
    phone_number=config('PHONE')
)

@bot.on_message(filters.all, group=-1)
async def read_all_messages(client, message):
    """
    Хендлер на все входящие сообщения (группа -1).
    Сразу записывает текст сообщения в примечание (note) в Google-таблицу.
    """
    user_id = message.from_user.id
    
    # Проверяем, отключен ли бот глобально или пользователь
    if ignorFlag:
        return  # Игнорируем сообщения от отключенных пользователей
    
    logger.info(f"Получено сообщение от пользователя {user_id}: {message.text}")
    MyFunctions.update_user_note(message.chat.id, user_id, __init__.sheet, message.text)
    MyFunctions.update_user_note(message.chat.id, user_id, __init__.case_sheet, message.text)

@bot.on_message(filters.command("disable"))
async def handle_disable(client: Client, message: Message):
    global ignorFlag
    if not is_admin(message.from_user.id):
        await message.reply("🚫 Эта команда доступна только администраторам!")
        return
    ignorFlag = not ignorFlag
    status = "активировано" if ignorFlag else "деактивировано"
    await message.reply(f"🔄 Режим игнорирования сообщений {status}!")

@bot.on_message(filters.command("help"))
async def handle_help(client: Client, message: Message):
    await message.reply(
        "Доступные команды:\n"
        "/start - Приветственное сообщение\n"
        "/help - Список команд\n"
        "/Положение - Ссылка на положение\n"
        "/Эссе - Ссылка на шаблон эссе\n"
        "/id - Узнать свой ID\n"
        "/chat - Добавляет в общий чат (при наличии доступа)\n"
    )

@bot.on_message(filters.command("id"))
async def handle_id(client: Client, message: Message):
    await message.reply(
        configs.COMMAND_MESSAGES["id"].format(
            user_id=message.from_user.id,
            chat_id=message.chat.id
        )
    )


user_results_state = {}   # chat_id: этап (0, 1, 2)
user_results_data = {}    # chat_id: список ответов
user_results_timer = {}   # chat_id: asyncio.Task

# Массив с номерами столбцов для ручной настройки (индексы начинаются с 1)
# Пример: [7, 8, 12, 13, 14, 15, 20] — подставьте свои номера столбцов
RESULTS_COLUMNS = [11, 12, 13, 14, 15, 16, 32, 20, 21, 22, 23, 24]  # <-- настройте под свою таблицу


@bot.on_message(filters.command("results"))
async def start_results_handler(client, message):
    """
    Запуск диалога для внесения оценок (2, 4, 1, 5 чисел) с премиум-эмодзи.
    """
    chat_id = message.chat.id

    # Сброс предыдущих данных
    user_results_state.pop(chat_id, None)
    user_results_data.pop(chat_id, None)
    if chat_id in user_results_timer:
        user_results_timer[chat_id].cancel()
        del user_results_timer[chat_id]

    user_results_state[chat_id] = 0
    user_results_data[chat_id] = []

    instruction = (
        'Поздравляем с завершением дистанционного этапа<emoji id=5411590687663608498>⚡</emoji>\n\n'
        'Сообщите Вашу оценку за эссе.\n'
        'Введите 2 числа через пробел, соответствующие Вашим баллам по критериям:\n'
        '<emoji id=5390932676653898005>➖</emoji> Содержание\n'
        '<emoji id=5390932676653898005>➖</emoji> Качество речи\n\n'
        'Пример: 10 10\n'
        '(без кавычек и иных символов. Только 2 числа в порядке, соответствующем перечисленным критериям).'
    )
    await message.reply_text(instruction)
    user_results_timer[chat_id] = asyncio.create_task(MyFunctions.cancel_dialog(client, chat_id, 120))

@bot.on_message(
    filters.text
    & ~filters.command(["results"])
    & filters.create(lambda _, __, msg: msg.chat.id in user_results_state)
)
async def results_step_handler(client, message):
    chat_id = message.chat.id
    step = user_results_state.get(chat_id, 0)
    data = user_results_data.get(chat_id, [])

    expected_counts = [2, 4, 1, 5]
    prompts = [
        (
            'Сообщите Вашу оценку за видеовизитку.\n'
            'Введите 4 числа через пробел, соответствующие Вашим баллам по критериям:\n'
            '<emoji id=5390932676653898005>➖</emoji> Самопрезентация\n'
            '<emoji id=5390932676653898005>➖</emoji> Качество речи\n'
            '<emoji id=5390932676653898005>➖</emoji> Содержание\n'
            '<emoji id=5390932676653898005>➖</emoji> Наглядность\n\n'
            'Пример: 10 10 10 10\n'
            '(без кавычек и иных символов. Только 4 числа в порядке, соответствующем перечисленным критериям).'
        ),
        (
            'Сообщите Вашу оценку за задание "Твори добро" <emoji id=5422512664943288992>🍄</emoji>\n'
            'Одно число без кавычек и и иных символов.'
        ),
        (
            'Сообщите Вашу оценку за решение кейса<emoji id=5411590687663608498>⚡</emoji>.\n'
            'Введите 5 чисел через пробел, соответствующие Вашим баллам по критериям:\n'
            '<emoji id=5390932676653898005>➖</emoji> Аналитика\n'
            '<emoji id=5390932676653898005>➖</emoji> Качество идеи\n'
            '<emoji id=5390932676653898005>➖</emoji> Проработанность проекта\n'
            '<emoji id=5390932676653898005>➖</emoji> Полнота ресурсов\n'
            '<emoji id=5390932676653898005>➖</emoji> Презентация проекта\n\n'
            'Пример: 10 10 10 10 10\n'
            '(без кавычек и иных символов. Только 5 чисел в порядке, соответствующем перечисленным критериям).'
        )
    ]

    # Проверка формата: нужное количество чисел через пробел
    if step < 4:
        parts = message.text.strip().split()
        if len(parts) != expected_counts[step] or not all(p.lstrip('-').isdigit() for p in parts):
            await message.reply(
                f"Пожалуйста, введите {' '.join(['ровно', str(expected_counts[step]), 'число' if expected_counts[step]==1 else 'числа'])} через пробел."
            )
            return

        data.extend(parts)
        user_results_data[chat_id] = data

        if step < 3:
            user_results_state[chat_id] += 1
            await message.reply(prompts[step])
        else:
            # После ввода всех чисел — спрашиваем сумму
            total = sum(int(x) for x in data)
            user_results_state[chat_id] = 4  # этап подтверждения суммы
            await message.reply(
                f"Ваша общая сумма баллов без тестов - {total}?\n\n"
                "Если всё верно, напишите: Да\n"
                "Если нет — напишите: Нет. Диалог завершится."
            )
    else:
        # Этап подтверждения суммы
        answer = message.text.strip().lower()
        if answer == "да":
            answers = [int(x) for x in data]

            # Получаем объект таблицы и лист "Кейсы"
            spreadsheet = __init__.sheet.spreadsheet
            cases_sheet = spreadsheet.worksheet("Кейсы")  # Для gspread

            # Определяем индекс столбца с ID (например, "ID тт" — третий столбец)
            id_column_index = 3  # Укажите нужный индекс (начиная с 1)
            id_column_values = cases_sheet.col_values(id_column_index)
            user_id = str(message.from_user.id)

            try:
                user_row = id_column_values.index(user_id) + 1
            except ValueError:
                await message.reply("Ваш ID не найден на листе 'Кейсы'. Пожалуйста, обратитесь к организатору.")
                # Сброс состояния
                user_results_state.pop(chat_id, None)
                user_results_data.pop(chat_id, None)
                return

            try:
                for i, answer in enumerate(answers):
                    col = RESULTS_COLUMNS[i]
                    MyFunctions.update_this_cell(user_row, col, answer, cases_sheet)
                await message.reply("Ваш ответ записан!")
            except Exception as e:
                await message.reply(f"Произошла ошибка при сохранении: {e}")
            # Сброс состояния
            user_results_state.pop(chat_id, None)
            user_results_data.pop(chat_id, None)
        else:
            # Если не подтвердил сумму — сбрасываем и завершаем диалог
            user_results_state.pop(chat_id, None)
            user_results_data.pop(chat_id, None)
            await message.reply("Диалог завершён. Если хотите попробовать снова — используйте /results.")

@bot.on_message(filters.command("start") | filters.command("Start"))
async def handle_start_command(client: Client, message: Message):
    """
    Обработчик команды /start
    """
    # Определяем, какая команда была использована
    command_name = "start" if message.command[0] == "start" else "Start"
    
    # Получаем сообщение из конфига
    start_message = configs.COMMAND_MESSAGES[command_name].format(
        form=configs.FORM,
        user_id=message.from_user.id
    )
    
    # Обрабатываем премиум эмодзи
    processed_message = MyFunctions.process_premium_emoji_message(
        SimpleNamespace(text=start_message, entities=[])
    )
    
    await message.reply(processed_message)

@bot.on_message(filters.command("chat"))
async def handle_chat_command(client: Client, message: Message):
    """
    Проверяет, есть ли у пользователя доступ к добавлению в общий чат (через check_condition),
    и, если да, добавляет его в группу (GROUP_ID).
    """
    async for dialog in client.get_dialogs(): pass
    user_id = message.from_user.id
    condition = check_condition(__init__.sheet, user_id)

    if condition == 1:
        try:
            # Убедимся, что бот "видит" группу
            chat_id = int(configs.GROUP_ID)
            chat = await client.get_chat(chat_id)

            # Убедимся, что бот "знает" пользователя
            user = await client.get_users(user_id)

            # Добавляем пользователя в группу
            await client.add_chat_members(chat_id=chat_id, user_ids=user_id)
            await message.reply(configs.COMMAND_MESSAGES["chat"])
        except Exception as e:
            await message.reply(f"Ошибка при добавлении в чат: {e}\nПожалуйста, сообщите администратору об ошибке.")
    else:
        await message.reply("У вас нет доступа для добавления в чат.")

@bot.on_message(filters.command("add_to_chat") & filters.me)
async def handle_add_to_chat_command(client: Client, message: Message):
    """
    Команда для добавления текущего пользователя в другой чат (админская).
    """
    if is_admin(message.from_user.id):
        try:
            chat_id = MyFunctions.extract_after_first_space(message.text)  # ID группы, в которую нужно добавить
            await client.add_chat_members(chat_id=chat_id, user_ids=message.chat.id)
            await message.reply("Добавление в чат выполнено.")
        except Exception as e:
            await message.reply(f"Ошибка при добавлении в чат: {e}")
    else:
        await message.reply("У вас нет доступа для добавления в чат.")


@bot.on_message(filters.command("sn"))
async def special_command_handler(client: Client, message: Message):
    """
    Запрашивает у админа следующее сообщение (в течение 2 минут), которое будет массово отправлено.
    Если в тексте будет '[name]', то рассылка будет персонализированной (имена подставятся).
    Если нет — простая рассылка.
    Работает с двумя листами: основным и листом "Кейсы".
    """
    global sn_active
    if message.from_user and is_admin(message.from_user.id):
        if sn_active:
            await message.reply("⚠️ Рассылка уже активна. Сначала остановите текущую рассылку командой /stop_sn")
            return

        await message.reply(configs.COMMAND_MESSAGES["sn"])

        async for dialog in client.get_dialogs(): pass

        filter_next_message = filters.user(message.from_user.id) & filters.chat(message.chat.id)
        handler_ref = None
        timer_task = None

        async def capture_next_message(_client: Client, next_msg: Message):
            global sn_active
            is_media = bool(next_msg.photo or next_msg.video or next_msg.video_note)
            text_to_check = next_msg.caption if is_media else next_msg.text

            try:
                sn_active = True
                if text_to_check and "[name]" in text_to_check:
                    # Рассылка по основному листу
                    await send_message_to_users_name(_client, next_msg, __init__.sheet)
                    # Рассылка по листу Кейсы
                    await send_message_to_users_name(_client, next_msg, __init__.case_sheet)
                else:
                    # Рассылка по основному листу
                    await send_message_to_users(_client, next_msg, __init__.sheet)
                    # Рассылка по листу Кейсы
                    await send_message_to_users(_client, next_msg, __init__.case_sheet)

                # Уведомление об успехе
                await message.reply("✅ Рассылка успешно запущена!")

            except Exception as e:
                await message.reply(f"🚫 Ошибка при рассылке: {str(e)}")
            finally:
                sn_active = False
                bot.remove_handler(handler_ref)
                if timer_task:
                    timer_task.cancel()

        async def timer_func():
            try:
                await asyncio.sleep(120)
                bot.remove_handler(handler_ref)
                await message.reply(
                    "⏳ Время истекло! Повторите /sn для новой рассылки."
                )
            except asyncio.CancelledError:
                pass

        handler_ref = MessageHandler(capture_next_message, filter_next_message)
        bot.add_handler(handler_ref)
        timer_task = asyncio.create_task(timer_func())
    else:
        await message.reply("Извините, эта команда доступна только администраторам.")

@bot.on_message(filters.command("stop_sn"))
async def stop_sn_handler(client: Client, message: Message):
    """
    Останавливает текущую рассылку
    """
    global sn_active
    if not is_admin(message.from_user.id):
        await message.reply("Извините, эта команда доступна только администраторам.")
        return

    if not sn_active:
        await message.reply("ℹ️ Нет активной рассылки для остановки.")
        return

    sn_active = False
    await message.reply("🛑 Рассылка остановлена!")

# ------------------------
#   Логика пошагового диалога "/team"
# ------------------------
user_states = {}  # Хранение состояния диалога
user_data = {}    # Временные данные
user_timers = {}  # Ссылка на асинхронные таймеры

@bot.on_message(filters.command("team"))
async def start_team_handler(client, message):
    """
    Запуск диалога для внесения нового участника в таблицу "Team".
    Шаг 1: спрашиваем ФИО.
    """
    chat_id = message.chat.id

    # Сбрасываем предыдущие данные
    user_states.pop(chat_id, None)
    user_data.pop(chat_id, None)
    if chat_id in user_timers:
        user_timers[chat_id].cancel()
        del user_timers[chat_id]

    user_states[chat_id] = "waiting_FIO"
    user_data[chat_id] = {}

    await message.reply_text(configs.COMMAND_MESSAGES["team"])
    user_timers[chat_id] = asyncio.create_task(MyFunctions.cancel_dialog(client, chat_id, 60))

@bot.on_message(
    filters.text
    & ~filters.command(["team"])
    & filters.create(lambda _, __, msg: msg.chat.id in user_states)
)

@bot.on_message(filters.command("replace_emoji", prefixes="/") & filters.me)
async def replace_emoji_handler(client, message):
    """
    Пример обработки премиум-эмодзи: бот берёт текст сообщения, на которое мы отвечаем,
    пропускает через process_premium_emoji_message и присылает в ответ результат.
    """
    if not message.reply_to_message:
        await message.reply("Ответьте командой на сообщение, содержащее премиум-эмодзи.")
        return

    processed_text = MyFunctions.process_premium_emoji_message(message.reply_to_message)
    await message.reply(processed_text)

@bot.on_message(filters.command("Вызов"))
async def handle_challenge_command(client: Client, message: Message):
    """
    Обработчик команды /Вызов.
    Запрашивает у пользователя текст вызова и записывает его в таблицу.
    """
    user_id = message.from_user.id
    user_index = MyFunctions.S_of_user(user_id, __init__.sheet)
    
    if user_index is None:
        await message.reply("Вы не найдены в базе данных. Пожалуйста, сначала зарегистрируйтесь.")
        return

    await message.reply(configs.COMMAND_MESSAGES["вызов"])

    filter_next_message = filters.user(user_id) & filters.chat(message.chat.id)
    handler_ref = None
    timer_task = None

    async def capture_next_message(_client: Client, next_msg: Message):
        challenge_text = next_msg.text

        # Проверяем формат вызова
        if not challenge_text or not challenge_text[0].isupper() or not challenge_text.endswith('!'):
            await next_msg.reply(
                "Пожалуйста, напишите вызов правильно:\n"
                "- Первое слово с большой буквы\n"
                "- В конце восклицательный знак\n"
                "Например: Создавай будущее!"
            )
            bot.remove_handler(handler_ref)
            timer_task.cancel()
            return

        # Записываем вызов в таблицу
        try:
            MyFunctions.update_this_cell(
                user_index + 1,  # +1 потому что S_of_user возвращает индекс с 0
                configs.COLLUM_CHALLENGE,
                challenge_text,
                __init__.sheet
            )
            await next_msg.reply("Ваш вызов записан!")
        except Exception as e:
            await next_msg.reply(f"Произошла ошибка при записи вызова: {e}")

        bot.remove_handler(handler_ref)
        timer_task.cancel()

    async def timer_func():
        try:
            await asyncio.sleep(120)
            bot.remove_handler(handler_ref)
            await message.reply("⏰ Время истекло! Повторите команду /Вызов для ввода вызова.")
        except asyncio.CancelledError:
            pass

    handler_ref = MessageHandler(capture_next_message, filter_next_message)
    bot.add_handler(handler_ref)
    timer_task = asyncio.create_task(timer_func())

@bot.on_message(filters.command("эссе"))
async def handle_essay_command(client: Client, message: Message):
    """
    Обработчик команды /эссе
    Записывает ссылку на эссе в таблицу
    """

    user_id = message.from_user.id
    user_index = MyFunctions.S_of_user(user_id, __init__.sheet)
    
    if user_index is None:
        await message.reply("Вы не найдены в базе данных. Пожалуйста, сначала зарегистрируйтесь.")
        return

    # Проверяем, не заполнена ли уже ячейка
    try:
        # Получаем значение ячейки
        cell_value = __init__.sheet.cell(user_index + 1, configs.COLLUM_ESSAY).value
        if cell_value and cell_value.strip():
            await message.reply("Вы уже отправили ссылку на эссе. Если вы хотите изменить её, обратитесь к администратору.")
            return
    except Exception as e:
        print(f"Ошибка при проверке ячейки: {e}")
        # Продолжаем выполнение, если возникла ошибка при проверке

    await message.reply(configs.COMMAND_MESSAGES["эссе"])

    filter_next_message = filters.user(user_id) & filters.chat(message.chat.id)
    handler_ref = None
    timer_task = None

    async def capture_next_message(_client: Client, next_msg: Message):
        essay_link = next_msg.text

        # Проверяем формат ссылки
        if not essay_link.startswith("https://"):
            await next_msg.reply(
                "Пожалуйста, выполните снова команду /эссе и отправьте корректную ссылку, начинающуюся с https://"
            )
            bot.remove_handler(handler_ref)
            timer_task.cancel()
            return

        # Записываем ссылку в таблицу
        try:
            MyFunctions.update_this_cell(
                user_index + 1,  # +1 потому что S_of_user возвращает индекс с 0
                configs.COLLUM_ESSAY,
                essay_link,
                __init__.sheet
            )
            await next_msg.reply("Ссылка на эссе записана!")
        except Exception as e:
            await next_msg.reply(f"Произошла ошибка при записи ссылки: {e}")

        bot.remove_handler(handler_ref)
        timer_task.cancel()

    async def timer_func():
        try:
            await asyncio.sleep(120)
            bot.remove_handler(handler_ref)
            await message.reply("⏰ Время истекло! Повторите команду /эссе для ввода ссылки.")
        except asyncio.CancelledError:
            pass

    handler_ref = MessageHandler(capture_next_message, filter_next_message)
    bot.add_handler(handler_ref)
    timer_task = asyncio.create_task(timer_func())

@bot.on_message(filters.command("Визитка"))
async def handle_video_command(client: Client, message: Message):
    """
    Обработчик команды /Визитка
    Записывает ссылку на видеовизитку в таблицу и дату отправки
    """
    user_id = message.from_user.id
    user_index = MyFunctions.S_of_user(user_id, __init__.sheet)
    
    if user_index is None:
        await message.reply("Вы не найдены в базе данных. Пожалуйста, сначала зарегистрируйтесь.")
        return

    # Проверяем, не заполнена ли уже ячейка
    try:
        # Получаем значение ячейки
        cell_value = __init__.sheet.cell(user_index + 1, configs.COLLUM_VIDEO).value
        if cell_value and cell_value.strip():
            await message.reply("Вы уже отправили ссылку на видеовизитку. Если вы хотите изменить её, обратитесь к администратору.")
            return
    except Exception as e:
        print(f"Ошибка при проверке ячейки: {e}")
        # Продолжаем выполнение, если возникла ошибка при проверке

    await message.reply(configs.COMMAND_MESSAGES["визитка"])

    filter_next_message = filters.user(user_id) & filters.chat(message.chat.id)
    handler_ref = None
    timer_task = None

    async def capture_next_message(_client: Client, next_msg: Message):
        video_link = next_msg.text

        # Проверяем формат ссылки
        if not video_link.startswith(("https://")):
            await next_msg.reply(
                "Пожалуйста, отправьте корректную ссылку, начинающуюся с https://"
            )
            bot.remove_handler(handler_ref)
            timer_task.cancel()
            return

        # Проверяем, не заполнена ли ячейка за время ожидания
        try:
            cell_value = __init__.sheet.cell(user_index + 1, configs.COLLUM_VIDEO).value
            if cell_value and cell_value.strip():
                await next_msg.reply("Извините, но ячейка уже заполнена. Если вы хотите изменить ссылку, обратитесь к администратору.")
                bot.remove_handler(handler_ref)
                timer_task.cancel()
                return
        except Exception as e:
            print(f"Ошибка при проверке ячейки: {e}")
            # Продолжаем выполнение, если возникла ошибка при проверке

        # Записываем ссылку и дату в таблицу
        try:
            # Записываем ссылку
            MyFunctions.update_this_cell(
                user_index + 1,  # +1 потому что S_of_user возвращает индекс с 0
                configs.COLLUM_VIDEO,
                video_link,
                __init__.sheet
            )

            # Записываем текущую дату
            from datetime import datetime
            current_date = datetime.now().strftime("%d.%m.%Y")
            MyFunctions.update_this_cell(
                user_index + 1,
                configs.COLLUM_VIDEO_DATE,
                current_date,
                __init__.sheet
            )

            await next_msg.reply("Ссылка на видеовизитку и дата отправки записаны!")
        except Exception as e:
            await next_msg.reply(f"Произошла ошибка при записи: {e}")

        bot.remove_handler(handler_ref)
        timer_task.cancel()

    async def timer_func():
        try:
            await asyncio.sleep(120)
            bot.remove_handler(handler_ref)
            await message.reply("⏰ Время истекло! Повторите команду /Визитка для ввода ссылки.")
        except asyncio.CancelledError:
            pass

    handler_ref = MessageHandler(capture_next_message, filter_next_message)
    bot.add_handler(handler_ref)
    timer_task = asyncio.create_task(timer_func())

@bot.on_message(filters.command("message"))
async def handle_message_command(client: Client, message: Message):
    """
    Обработчик команды /message для настройки сообщений команд
    """
    if not is_admin(message.from_user.id):
        await message.reply("Извините, эта команда доступна только администраторам.")
        return

    # Получаем название команды из аргументов
    try:
        command_name = message.text.split()[1]
    except IndexError:
        await message.reply("Пожалуйста, укажите название команды: /message <command_name>")
        return

    # Проверяем, существует ли такая команда в COMMAND_MESSAGES
    if command_name not in configs.COMMAND_MESSAGES:
        await message.reply(f"Команда '{command_name}' не найдена в списке доступных команд.")
        return

    await message.reply(
        f"Введите новое сообщение для команды {command_name}.\n"
        "Вы можете использовать премиум эмодзи.\n"
        "У вас есть 2 минуты на отправку сообщения.\n\n"
        "Предыдущее сообщение: \n" + configs.COMMAND_MESSAGES[command_name]
    )

    filter_next_message = filters.user(message.from_user.id) & filters.chat(message.chat.id)
    handler_ref = None
    timer_task = None

    async def capture_next_message(_client: Client, next_msg: Message):
        new_message = next_msg.text

        # Обрабатываем премиум эмодзи
        processed_message = MyFunctions.process_premium_emoji_message(next_msg)

        # Сохраняем новое сообщение
        if MyFunctions.update_command_message(command_name, new_message):
            # Обновляем сообщение в конфиге
            configs.COMMAND_MESSAGES[command_name] = new_message

            
            await next_msg.reply("Сообщение успешно обновлено!")
        else:
            await next_msg.reply("Ошибка при сохранении сообщения.")

        bot.remove_handler(handler_ref)
        timer_task.cancel()

    async def timer_func():
        try:
            await asyncio.sleep(120)
            bot.remove_handler(handler_ref)
            await message.reply("⏰ Время истекло! Повторите команду /message для настройки сообщения.")
        except asyncio.CancelledError:
            pass

    handler_ref = MessageHandler(capture_next_message, filter_next_message)
    bot.add_handler(handler_ref)
    timer_task = asyncio.create_task(timer_func())


@bot.on_message(filters.command("СдалЗнакомство"))
async def handle_acquaintance_submission(client: Client, message: Message):
    user_id = message.from_user.id
    user_index = MyFunctions.S_of_user(user_id, __init__.sheet)

    if user_index is None:
        await message.reply("Вы не найдены в базе данных. Пожалуйста, сначала зарегистрируйтесь.")
        return

    await message.reply("Отправьте скрин экрана с подтверждением отправки этапа")

    filter_next_message = filters.user(user_id) & filters.chat(message.chat.id)
    handler_ref = None
    timer_task = None
    is_handler_active = True

    async def safe_cleanup():
        """Безопасная очистка ресурсов"""
        nonlocal is_handler_active

        if is_handler_active:
            is_handler_active = False

            # Безопасное удаление обработчика в Pyrogram
            if handler_ref:
                try:
                    client.remove_handler(handler_ref)
                except (ValueError, AttributeError):
                    # Обработчик уже был удален
                    pass
                except Exception as e:
                    print(f"Ошибка при удалении обработчика: {e}")

            # Безопасная отмена таймера
            if timer_task and not timer_task.done():
                timer_task.cancel()
                try:
                    await timer_task
                except asyncio.CancelledError:
                    pass

    async def capture_next_message(_client: Client, next_msg: Message):
        if not is_handler_active:
            return

        if not next_msg.photo:
            await next_msg.reply(
                "Пожалуйста, отправьте скриншот в виде изображения с подтверждением отправки."
            )
            await safe_cleanup()
            return

        try:
            MyFunctions.update_this_cell(
                user_index + 1,
                configs.COLLUM_ACQUAINTANCE_STATUS,
                "Сдано",
                __init__.sheet
            )
            await next_msg.reply("Принято!")
        except Exception as e:
            await next_msg.reply(f"Произошла ошибка при обновлении статуса: {e}")

        await safe_cleanup()

    async def timer_func():
        try:
            await asyncio.sleep(120)
            if is_handler_active:
                await safe_cleanup()
                await message.reply("⏰ Время истекло! Повторите команду /Сдал_Знакомство для отправки скриншота.")
        except asyncio.CancelledError:
            pass

    handler_ref = MessageHandler(capture_next_message, filter_next_message)
    client.add_handler(handler_ref)
    timer_task = asyncio.create_task(timer_func())



bot.run()

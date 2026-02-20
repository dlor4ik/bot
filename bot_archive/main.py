from pyrogram import Client, filters
from decouple import config
from pyrogram.types import Message
from pyrogram.handlers import MessageHandler
import asyncio
import configs
import MyFuntions
from MyFuntions import send_message_to_users_name
from MyFuntions import send_message_to_users
from MyFuntions import is_admin
from MyFuntions import check_condition
from MyFuntions import extract_after_first_space
import __init__


bot = Client(name=config('LOGIN'),
             api_id=config('API_ID'),
             api_hash=config('API_HASH'),
             phone_number=config('PHONE'))

@bot.on_message(filters.all, group=-1)
async def read_all_messages(client, message):
    user_id = message.from_user.id
    MyFuntions.update_user_note(message.chat.id,user_id,__init__.sheet,message.text)



@bot.on_message(filters.command("start"))
async def handle_start(client: Client, message: Message):
    await client.read_chat_history(message.chat.id)

    await message.reply("Привет! Я ваш помощник-бот. Введите /help для получения списка команд.")



@bot.on_message(filters.command("help"))
async def handle_start(client: Client, message: Message):
    await message.reply(
            "Доступные команды:\n"
            "/start - Приветственное сообщение\n"
            "/help - Список команд")




@bot.on_message(filters.command("Положение") & filters.group)
async def command_handler(client: Client, message: Message):
    await message.reply(configs.PLOJENIE)

@bot.on_message(filters.command("Эссе") & filters.group)
async def command_handler(client: Client, message: Message):
    await message.reply(configs.ESSAY)

@bot.on_message(filters.command("id"))
async def handle_id(client: Client, message: Message):
    await message.reply(f"Ваш ID: {message.from_user.id}\n"
                        f"ID чата: {message.chat.id}")

@bot.on_message(filters.command("PreStart"))
async def command_handler(client: Client, message: Message):
    await message.reply(f"Добро пожаловать в предварительный набор 'Большое Дело' 2025. \n"
                        f"Чтобы вступить в сборную:\n"
                        f"-Пройдите форму по ссылке.\n"
                        f"-После введите /chat \n"                        
                        f"Форма для заполнения: {configs.FORM} \n "
                        f"*Для заполнения вам понадобится ID вашего tg аккаунта. Ваш ID: {message.from_user.id}")


@bot.on_message(filters.command("chat"))
async def handle_chat_command(client: Client, message: Message):
    # Проверяем значение функции

    user_id = message.from_user.id  # ID пользователя, который отправил команду
    condition = check_condition(__init__.sheet, message.from_user.id)

    if condition == 1:
        try:
            # Добавляем пользователя в чат
            chat_id = configs.GROUP_ID  # ID группы, в которую нужно добавить

            await client.add_chat_members(chat_id=chat_id, user_ids=user_id)
            await message.reply("Вы успешно добавлены в чат!")
        except Exception as e:
            await message.reply(f"Ошибка при добавлении в чат: {e}")
    else:
        # Если функция возвращает 0
        await message.reply("У вас нет доступа для добавления в чат.")

@bot.on_message(filters.command("add_to_chat") & filters.me)
async def handle_chat_command(client: Client, message: Message):
    print("Команда сработала")
    # Проверяем значение функции
    if is_admin(message.from_user.id) == 1:
        try:
            # Добавляем пользователя в чат
            chat_id = extract_after_first_space(message.text)  # ID группы, в которую нужно добавить
            print(f"id чата - !{chat_id}!")
            print(f"id диалога (собеседника) - !{message.chat.id}!")
            await client.add_chat_members(chat_id=f"{chat_id}", user_ids=message.chat.id)
            await message.reply("Вы успешно добавлены в чат!")
        except Exception as e:
            await message.reply(f"Ошибка при добавлении в чат: {e}")
    else:
        # Если функция возвращает 0
        await message.reply("У вас нет доступа для добавления в чат.")



"""# Обработчик для других сообщений
@bot.on_message(filters.text)
async def fallback_handler(client: Client, message: Message):
    if message.text not in ['/start', '/help']:
        await message.reply(
            "Команда не распознана.\n"
            "Доступные команды:\n"
            "/start - Приветственное сообщение\n"
            "/help - Список команд"
        ) 
# Список разрешённых ID пользователей (или логинов)"""


@bot.on_message(filters.command("Special_Name"))  # Обработчик команды
async def special_command_handler(client: Client, message: Message):
    if message.from_user and is_admin(message.from_user.id):
        await message.reply(
            "Вы активировали специальную команду для отправки персонализированного сообщения.\n\n"
            "Для отправки персонализированного сообщения вставьте [name] на место, где должно располагаться имя получателя.\n\n"
            "(У вас есть 2 минуты на отправку сообщения)."
        )

        # Фильтр для следующего сообщения от того же пользователя в том же чате
        filter_next_message = filters.user(message.from_user.id) & filters.chat(message.chat.id)

        # Готовим переменные для ссылки на обработчик и задачу таймера
        handler_ref = None
        timer_task = None

        async def capture_next_message(client: Client, next_message: Message):
            """Обрабатывает следующее сообщение администратора."""
            is_photo = bool(next_message.photo)
            text_to_check = next_message.caption if is_photo else next_message.text

            # Проверяем, содержит ли текст подстроку "[name]"
            if text_to_check and "[name]" in text_to_check:
                await send_message_to_users_name(client, next_message, __init__.sheet)
            else:
                await send_message_to_users(client, next_message, __init__.sheet)

            # Удаляем временный обработчик
            bot.remove_handler(handler_ref)
            # Отменяем таймер (чтобы не выводить "Время истекло" после ответа)
            timer_task.cancel()

        async def timer_func():
            """Таймер: ждём 2 минуты (120 секунд). Если пользователь не ответил, удаляем обработчик."""
            try:
                await asyncio.sleep(120)
                # Если за 2 минуты не было ответа — удаляем обработчик
                bot.remove_handler(handler_ref)
                await message.reply("⏳ Время истекло! Отправьте команду /special заново, если хотите повторить.")
            except asyncio.CancelledError:
                # Если таймер отменили (т.е. пользователь успел ответить), просто выходим
                pass

        # Создаём объект MessageHandler и сохраняем его в handler_ref
        handler_ref = MessageHandler(capture_next_message, filter_next_message)
        bot.add_handler(handler_ref)

        # Запускаем таймер
        timer_task = asyncio.create_task(timer_func())

    else:
        await message.reply("Извините, эта команда доступна только администраторам.")





# Словарь, в котором будем хранить состояние диалога для каждого чата (или пользователя).
user_states = {}

# Словарь, в котором будем временно хранить данные пользователя (перформера, задачу и т.д.).
user_data = {}

# Словарь для хранения асинхронных задач (таймеров)
user_timers = {}

@bot.on_message(filters.command("team"))
async def start_task_handler(client, message):
    chat_id = message.chat.id

    # Сбрасываем старые данные и таймер, если остались
    user_states.pop(chat_id, None)
    user_data.pop(chat_id, None)

    if chat_id in user_timers:
        user_timers[chat_id].cancel()
        del user_timers[chat_id]

    # Устанавливаем первое состояние
    user_states[chat_id] = "waiting_FIO"
    user_data[chat_id] = {}

    # Отправляем первый вопрос
    await message.reply_text(
        "Здравствуйте! Вы ввели команду для включения в кадровый список 'Большого Дела'.\n"
        "**Пожалуйста, введите ваше ФИО** \n\n"
        "Не отвечайте 60 секунд, если хотите прекратить ввод."
    )

    # Запускаем таймер на 60 секунд
    user_timers[chat_id] = asyncio.create_task(cancel_dialog(client, chat_id, 60))

@bot.on_message(
    filters.text
    & ~filters.command(["team"])
    & filters.create(lambda _, __, msg: msg.chat.id in user_states)
)
async def text_handler(client, message):
    chat_id = message.chat.id

    # Если состояние уже сброшено (или таймер сработал), выходим
    if chat_id not in user_states:
        return

    # Текущая «ступень» диалога
    state = user_states[chat_id]

    # Пользователь ответил — отменяем предыдущий таймер
    if chat_id in user_timers:
        user_timers[chat_id].cancel()
        del user_timers[chat_id]

    if state == "waiting_FIO":
        # Сохраняем ответ
        user_data[chat_id]["FIO"] = message.text

        # Следующее состояние
        user_states[chat_id] = "waiting_place"
        await message.reply_text("К какому филиалу Вы относитесь (Москва, Уфа, Нижний Новгород, Все)?")

        # Запускаем новый таймер на 60 секунд
        user_timers[chat_id] = asyncio.create_task(cancel_dialog(client, chat_id, 60))

    elif state == "waiting_place":
        # Сохраняем ответ
        user_data[chat_id]["place"] = message.text

        await message.reply_text(
            "Данные записаны. Спасибо, что Вы с нами!\n"
            f"*Для справки: id вашего телеграмм-аккаунта — {chat_id}"
        )

        # Формируем текст задачи
        team_text = (
            "У Вас новый член команды!\n\n"
            f"**ФИО:** {user_data[chat_id]['FIO']}\n"
            f"**Филиал:** {user_data[chat_id]['place']}\n"
        )

        # Пример передачи задачи другому пользователю
        recipient_id = configs.ADMINS_ID['Алексей']
        try:
            await client.send_message(chat_id=recipient_id, text=team_text)
            print(f"Задача успешно отправлена пользователю с ID {recipient_id}.")
        except Exception as e:
            print(f"Ошибка при отправке задачи пользователю с ID {recipient_id}: {e}")

        # Сохраняем в таблицу
        MyFuntions.team(user_data[chat_id], __init__.team_sheet, chat_id)

        # Диалог завершён — сбрасываем все данные
        del user_states[chat_id]
        del user_data[chat_id]

        # Если вдруг остался таймер (не должен, но на всякий случай)
        if chat_id in user_timers:
            user_timers[chat_id].cancel()
            del user_timers[chat_id]

async def cancel_dialog(client, chat_id, seconds: int):
    """
    Асинхронный таймер: ждем seconds секунд. Если пользователь не ответит за это время —
    сбрасываем диалог и уведомляем его.
    """
    try:
        await asyncio.sleep(seconds)
        # Если после ожидания пользователь всё ещё в диалоге, сбрасываем
        if chat_id in user_states:
            del user_states[chat_id]
        if chat_id in user_data:
            del user_data[chat_id]
        if chat_id in user_timers:
            del user_timers[chat_id]

        # Уведомляем пользователя
        await client.send_message(
            chat_id,
            f"Время ожидания ({seconds} секунд) истекло. Заполнение отменено.\n"
            "Введите /team, если хотите попробовать снова."
        )
        print(f"Таймер истёк: сброс данных у chat_id={chat_id}")
    except asyncio.CancelledError:
        # Таймер отменён — пользователь успел ответить
        pass



@bot.on_message(filters.command("replace_emoji", prefixes="/") & filters.me)
async def replace_emoji_handler(client, message):
    # Проверяем, что команда отправлена в ответ на сообщение
    if not message.reply_to_message:
        await message.reply("Ответьте командой на сообщение с текстом.")
        return

    # Обрабатываем сообщение, на которое отвечаем, через нашу функцию
    processed_text = MyFuntions.process_premium_emoji_message(message.reply_to_message)

    # Отправляем результат
    await message.reply(processed_text)





bot.run()
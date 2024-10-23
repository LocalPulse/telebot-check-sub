import time
import os
import telebot
from telebot import types
from requests.exceptions import ReadTimeout
from telebot.apihelper import ApiTelegramException

API_TOKEN = ''
ADMIN_USERNAMES = ['glock84', '@odysseyofdreams', '@AkiraDou']  # Список пользователей, которые могут управлять ботом
CHANNELS_FILE = 'channels.txt'  # Файл для хранения списка каналов

bot = telebot.TeleBot(API_TOKEN)


# Загрузка каналов из текстового файла
def load_channels():
    if os.path.exists(CHANNELS_FILE):
        with open(CHANNELS_FILE, 'r') as file:
            return [line.strip() for line in file.readlines()]
    return []


# Сохранение каналов в текстовый файл
def save_channels(channels):
    with open(CHANNELS_FILE, 'w') as file:
        for channel in channels:
            file.write(f"{channel}\n")


# Изначально загружаем каналы из файла
channels = load_channels()


# Проверка, является ли пользователь администратором (по юзернейму)
def is_admin(username):
    return username in ADMIN_USERNAMES


# Функция проверки подписки пользователя на все каналы
def check_subscription(user_id):
    for channel in channels:
        try:
            status = bot.get_chat_member(channel, user_id).status
            if status not in ['member', 'administrator', 'creator']:
                return False
        except telebot.apihelper.ApiTelegramException as e:
            print(f"Ошибка при проверке канала {channel}: {e}")
            return False
    return True


# Функция для обработки запросов с повторной попыткой при возникновении ошибок
def retry_request(func, *args, max_retries=5, delay=5, **kwargs):
    retries = 0
    while retries < max_retries:
        try:
            return func(*args, **kwargs)
        except ApiTelegramException as e:
            if e.error_code == 502:
                print(f"Ошибка 502. Повторная попытка через {delay} секунд...")
                retries += 1
                time.sleep(delay)
            else:
                raise  # Если это не ошибка 502, выбрасываем исключение дальше
    print("Превышено количество повторных попыток.")
    return None


# Пример использования функции retry_request
def check_user_subscription(user_id, channel_id):
    result = retry_request(bot.get_chat_member, channel_id, user_id)
    if result:
        return result.status in ['member', 'administrator', 'creator']
    else:
        return False  # Если запрос не удался после нескольких попыток


# Обработчик текстовых сообщений в чате
@bot.message_handler(func=lambda message: message.chat.type != 'private', content_types=['text'])
def handle_message(message):
    user_id = message.from_user.id
    username = message.from_user.username
    mention = f"@{username}" if username else message.from_user.first_name  # Упоминание через @username или по имени

    try:
        user_status = bot.get_chat_member(message.chat.id, user_id).status
        if user_status in ['administrator', 'creator']:
            return  # Do not delete the message if the user is an admin
    except telebot.apihelper.ApiTelegramException as e:
        print(f"Error checking user status in group: {e}")

    # Если пользователь не подписан на все каналы
    if not check_subscription(user_id):
        bot.delete_message(message.chat.id, message.message_id)  # Удаляем сообщение пользователя

        # Создаем кнопки для подписки
        markup = types.InlineKeyboardMarkup()
        for channel in channels:
            button = types.InlineKeyboardButton(text=f"Подписаться на {channel}", url=f"https://t.me/{channel[1:]}")
            markup.add(button)
        button_done = types.InlineKeyboardButton(text="Готово", callback_data="done")
        markup.add(button_done)

        # Отправляем сообщение с упоминанием и кнопками в чат
        bot.send_message(message.chat.id, f"{mention}, чтобы писать в этом чате, подпишитесь на все каналы:",
                         reply_markup=markup)


# Обработчик нажатий на кнопки
@bot.callback_query_handler(func=lambda call: call.data == 'done')
def check_again(call):
    user_id = call.from_user.id

    # Повторная проверка подписки
    if check_subscription(user_id):
        bot.send_message(call.message.chat.id, f"{call.from_user.first_name}, спасибо, теперь вы можете писать в чате!")
    else:
        bot.send_message(call.message.chat.id, "Вы ещё не подписались на все каналы.")


# Команда для добавления канала (доступна только в личных сообщениях)
@bot.message_handler(commands=['add_channel'])
def add_channel(message):
    username = message.from_user.username
    if message.chat.type == 'private' and is_admin(username):
        try:
            new_channel = message.text.split()[1]  # Берем второй аргумент как канал
            if new_channel not in channels:
                channels.append(new_channel)
                save_channels(channels)
                bot.reply_to(message, f"Канал {new_channel} добавлен в список!")
            else:
                bot.reply_to(message, f"Канал {new_channel} уже есть в списке.")
        except IndexError:
            bot.reply_to(message, "Пожалуйста, укажите канал после команды. Пример: /add_channel @example")
    else:
        bot.reply_to(message, "Команда доступна только администраторам через личные сообщения.")


# Команда для удаления канала (доступна только в личных сообщениях)
@bot.message_handler(commands=['remove_channel'])
def remove_channel(message):
    username = message.from_user.username
    if message.chat.type == 'private' and is_admin(username):
        try:
            channel_to_remove = message.text.split()[1]  # Берем второй аргумент как канал
            if channel_to_remove in channels:
                channels.remove(channel_to_remove)
                save_channels(channels)
                bot.reply_to(message, f"Канал {channel_to_remove} удален из списка.")
            else:
                bot.reply_to(message, f"Канал {channel_to_remove} не найден в списке.")
        except IndexError:
            bot.reply_to(message, "Пожалуйста, укажите канал после команды. Пример: /remove_channel @example")
    else:
        bot.reply_to(message, "Команда доступна только администраторам через личные сообщения.")


# Команда для просмотра списка каналов (доступна только в личных сообщениях)
@bot.message_handler(commands=['list_channels'])
def list_channels(message):
    username = message.from_user.username
    if message.chat.type == 'private' and is_admin(username):
        if channels:
            bot.reply_to(message, f"Текущий список каналов для подписки:\n" + "\n".join(channels))
        else:
            bot.reply_to(message, "Список каналов пуст.")
    else:
        bot.reply_to(message, "Команда доступна только администраторам через личные сообщения.")


# Основной цикл бота с увеличенным таймаутом
def start_polling():
    while True:
        try:
            bot.polling(none_stop=True, timeout=20, long_polling_timeout=20)
        except ReadTimeout:
            print("ReadTimeout произошла, перезапуск через 5 секунд...")
            time.sleep(5)  # Ждем несколько секунд перед повторным запуском
        except ApiTelegramException as e:
            print(f"Произошла ошибка API Telegram: {e}")
            time.sleep(5)
        except Exception as e:
            print(f"Неожиданная ошибка: {e}")
            time.sleep(5)


start_polling()

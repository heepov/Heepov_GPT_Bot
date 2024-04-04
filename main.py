import sys
import logging
from loguru import logger

from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
import os
import g4f
from g4f.client import Client
import nest_asyncio
from pytgpt.utils import Conversation
import conf

nest_asyncio.apply()

import pytgpt.phind as phind
from pytgpt.imager import Imager

# Удалить обработчик по умолчанию и добавить новый обработчик с форматированием
logger.remove()
logger.add(sys.stdout, format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level}</level> | <cyan>{message}</cyan>")
log_img = "IMG  | "
log_gpt = "GPT  | "
log_main = "MAIN | "

# Включите логирование
logging.basicConfig(level=logging.INFO)
logging.getLogger('seleniumwire').setLevel(logging.ERROR)
logging.getLogger('undetected_chromedriver').setLevel(logging.ERROR)

# Инициализация бота
API_TOKEN = conf.API_TOKEN_TEST
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

# Словарь для хранения истории разговоров
conversation_history = {}
conversation_dict = {}

# Функция для обрезки истории разговора
def trim_history(history, max_length=4096):
    current_length = sum(len(message["content"]) for message in history)
    while history and current_length > max_length:
        removed_message = history.pop(0)
        current_length -= len(removed_message["content"])
    return history

@dp.message_handler(commands=['clear'])
async def process_clear_command(message: types.Message):
    user_id = message.from_user.id
    conversation_history[user_id] = []
    conversation_dict[user_id] = Conversation()
    await message.reply("Контекст сброшен.")
    logging.info(f"{user_id} reset contest [clear]")

@dp.message_handler(commands=['img'])
async def img_generate(message: types.Message):
    user_id = message.from_user.id
    # Разделяем текст сообщения на части по пробелам
    command_parts = message.text.split()
    # Проверяем, есть ли как минимум две части (команда и аргументы)
    if len(command_parts) >= 2:
        # Получаем аргументы после команды
        user_input = ' '.join(message.text.split()[1:])
        try:
            img_ai = Imager()
            logger.info(f"{log_img}User: {user_id}, prompt: {user_input}")
            generated_images = img_ai.generate(prompt=user_input, amount=2, stream=True)
            await message.answer("Генерация двух изображений по вашему запросу...")
            # Отправляем каждое изображение по отдельности
            for img_data in generated_images:
                # Сохраняем изображение на диск
                img_path = "temp_img.jpg"  # Путь для временного сохранения изображения
                with open(img_path, 'wb') as img_file:
                    img_file.write(img_data)
                
                # Отправляем изображение из файла
                with open(img_path, 'rb') as img_file:
                    await message.reply_photo(img_file)
                    logger.info(f"{log_img}User: {user_id}, respon: {img_file.name}")
                
                # Удаляем временный файл
                os.remove(img_path)
                
        except Exception as e:
            await message.reply(f"Произошла ошибка при отправке изображения, попробуйте еще раз.")
            logger.error(f"{log_img}User: {user_id}, error: {e}")
    else:
        await message.reply("Вы не указали тему для поиска фотографий. Пожалуйста, укажите тему после команды /img")

@dp.message_handler(commands=['gpt'])
async def prompt_generate_gpt(message: types.Message):
    user_id = message.from_user.id
    command_parts = message.text.split()

    if len(command_parts) >= 2:
        # Получаем аргументы после команды
        user_input = ' '.join(message.text.split()[1:])
        
        if user_id not in conversation_history:
            conversation_history[user_id] = []

        conversation_history[user_id].append({"role": "user", "content": user_input})
        conversation_history[user_id] = trim_history(conversation_history[user_id])

        chat_history = conversation_history[user_id]
        sent_message = await message.answer(conf.PROMPT_PROCESSING)
        message_id = sent_message.message_id
        logger.info(f"{log_gpt}User: {user_id}, prompt: {user_input}")
        try:
            client = Client()
            
            response = client.chat.completions.create(
                model=g4f.models.default,
                messages=chat_history,
                provider=g4f.Provider.FlowGpt
            )
            chat_gpt_response = response.choices[0].message.content
            
            conversation_history[user_id].append({"role": "assistant", "content": chat_gpt_response})
            
            await bot.edit_message_text(chat_gpt_response, message_id=message_id, chat_id=message.chat.id, parse_mode='Markdown')
            logger.info(f"{log_gpt}User: {user_id}, respon: {chat_gpt_response}")
        except Exception as e:
            await bot.edit_message_text("Произошла ошибка", message_id=message_id, chat_id=message.chat.id, parse_mode='Markdown')
            logger.error(f"{log_gpt}User: {user_id}, error: {e}")
    else:
        await message.reply("Вы не указали свой запрос. Пожалуйста, укажите запрос после команды /gpt4")

@dp.message_handler()
async def prompt_generate_main(message: types.Message):
    user_id = message.from_user.id
    user_input = message.text
    
    if user_id in conversation_dict:
        conversation = conversation_dict.get(user_id)
    else:
        conversation = Conversation()
        conversation_dict[user_id] = conversation
    
    sent_message = await message.answer(conf.PROMPT_PROCESSING)
    message_id = sent_message.message_id
    logger.info(f"{log_main}User: {user_id}, prompt: {message.text}")
    try:
        bot_ai = phind.PHIND(conversation)        
        response = bot_ai.chat(user_input)
        await bot.edit_message_text(response, message_id=message_id, chat_id=message.chat.id, parse_mode='Markdown')
        logger.info(f"{log_main}User: {user_id}, respon: {response}")
    except Exception as e:
        await bot.edit_message_text("Произошла ошибка", message_id=message_id, chat_id=message.chat.id, parse_mode='Markdown')
        logger.error(f"{log_main}User: {user_id}, error: {e}")

# Запуск бота
if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
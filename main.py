import os
import logging
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InputMediaPhoto
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ConversationHandler,
    ContextTypes,
)

# Токен бота
TOKEN = 'BOT_TOKEN'

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    filename='bot_log.log'
)
logger = logging.getLogger(__name__)

# Состояния для ConversationHandler
CHOOSING_TYPE, ENTERING_NAME, ENTERING_PRICE, ENTERING_CONTACT, SENDING_PHOTOS = range(5)

# Список для хранения объявлений
announcements = []

# Создание директории для фотографий
PHOTOS_DIR = 'photos'
if not os.path.exists(PHOTOS_DIR):
    os.makedirs(PHOTOS_DIR)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Обработчик команды /start
    """
    keyboard = [
        [KeyboardButton("📝 Подать объявление"), KeyboardButton("👀 Смотреть объявления")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text(
        "👋 Добро пожаловать в бот объявлений!\n"
        "Выберите действие:",
        reply_markup=reply_markup
    )
    return ConversationHandler.END


async def create_ad(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Начало создания объявления
    """
    keyboard = [
        [KeyboardButton("🛒 Куплю"), KeyboardButton("💰 Продам")],
        [KeyboardButton("❌ Отмена")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text(
        "Выберите тип объявления:",
        reply_markup=reply_markup
    )
    return CHOOSING_TYPE


async def handle_type(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Обработка выбора типа объявления
    """
    text = update.message.text.replace('🛒 ', '').replace('💰 ', '')

    if text == "❌ Отмена":
        return await cancel(update, context)

    if text not in ["Куплю", "Продам"]:
        await update.message.reply_text("Пожалуйста, используйте кнопки для выбора!")
        return CHOOSING_TYPE

    context.user_data['type'] = text
    keyboard = [[KeyboardButton("❌ Отмена")]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text(
        "Введите название товара:",
        reply_markup=reply_markup
    )
    return ENTERING_NAME


async def handle_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Обработка названия товара
    """
    if update.message.text == "❌ Отмена":
        return await cancel(update, context)

    context.user_data['name'] = update.message.text
    await update.message.reply_text(
        "Введите цену (только цифры):"
    )
    return ENTERING_PRICE


async def handle_price(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Обработка цены
    """
    if update.message.text == "❌ Отмена":
        return await cancel(update, context)

    try:
        price = float(update.message.text.replace(' ', ''))
        if context.user_data['type'] == "Куплю":
            context.user_data['price'] = f"{price:} ₽"
        else:
            context.user_data['price'] = f"{price:} ₽"
    except ValueError:
        await update.message.reply_text("Пожалуйста, введите корректную цену (только цифры)")
        return ENTERING_PRICE

    await update.message.reply_text(
        "Введите контактные данные для связи:\n"
        "(например, номер телефона или username в Telegram)"
    )
    return ENTERING_CONTACT


async def handle_contact(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Обработка контактной информации
    """
    if update.message.text == "❌ Отмена":
        return await cancel(update, context)

    context.user_data['contact'] = update.message.text

    # Если тип объявления "Куплю", сразу сохраняем объявление
    if context.user_data['type'] == "Куплю":
        context.user_data['photos'] = []  # Пустой список фотографий
        return await save_announcement(update, context)

    # Если тип "Продам", предлагаем загрузить фото
    keyboard = [
        [KeyboardButton("✅ Завершить без фото")],
        [KeyboardButton("❌ Отмена")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text(
        "Отправьте фотографии товара (до 5 штук)\n"
        "После отправки всех фото нажмите 'Завершить без фото'",
        reply_markup=reply_markup
    )
    context.user_data['photos'] = []
    return SENDING_PHOTOS


async def handle_photos(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Обработка фотографий
    """
    if update.message.text == "❌ Отмена":
        return await cancel(update, context)

    if update.message.text == "✅ Завершить без фото":
        return await save_announcement(update, context)

    if update.message.photo:
        if len(context.user_data.get('photos', [])) >= 5:
            await update.message.reply_text("Достигнут лимит в 5 фотографий. Нажмите 'Завершить без фото'")
            return SENDING_PHOTOS

        photo = update.message.photo[-1]  # Получаем фото наилучшего качества
        try:
            file = await photo.get_file()
            # Создаем уникальную директорию для каждого объявления
            ad_dir = f"{PHOTOS_DIR}/ad_{len(announcements)}"
            if not os.path.exists(ad_dir):
                os.makedirs(ad_dir)

            file_name = f"{ad_dir}/photo_{len(context.user_data.get('photos', []))}.jpg"
            await file.download_to_drive(file_name)

            # Инициализируем список фотографий, если его нет
            if 'photos' not in context.user_data:
                context.user_data['photos'] = []

            # Сохраняем путь к файлу и file_id фото
            context.user_data['photos'].append({
                'path': file_name,
                'file_id': photo.file_id
            })

            await update.message.reply_text(
                f"Фото #{len(context.user_data['photos'])} загружено.\n"
                f"Можете отправить еще {5 - len(context.user_data['photos'])} фото или нажать 'Завершить без фото'"
            )
        except Exception as e:
            logger.error(f"Ошибка при сохранении фото: {e}")
            await update.message.reply_text("Ошибка при сохранении фото. Попробуйте еще раз.")

    return SENDING_PHOTOS


async def save_announcement(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Сохранение объявления
    """
    announcement = {
        'type': context.user_data['type'],
        'name': context.user_data['name'],
        'price': context.user_data['price'],
        'contact': context.user_data['contact'],
        'photos': context.user_data.get('photos', []).copy()  # Создаем копию списка фотографий
    }
    announcements.append(announcement)

    keyboard = [
        [KeyboardButton("📝 Подать объявление"), KeyboardButton("👀 Смотреть объявления")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

    # Очищаем данные пользователя
    context.user_data.clear()

    await update.message.reply_text(
        "✅ Объявление успешно создано!",
        reply_markup=reply_markup
    )
    return ConversationHandler.END


async def view_announcements(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Просмотр всех объявлений
    """
    if not announcements:
        await update.message.reply_text("📭 Пока нет объявлений.")
        return

    for i, ad in enumerate(announcements, 1):
        message = (
            f"📌 Объявление #{i}\n"
            f"Тип: {ad['type']}\n"
            f"Товар: {ad['name']}\n"
            f"{'Бюджет' if ad['type'] == 'Куплю' else 'Цена'}: {ad['price']}\n"
            f"Контакт: {ad['contact']}"
        )

        if ad['photos']:
            try:
                # Создаем группу медиа с подписью для первого фото
                media_group = []
                first_photo = True
                for photo in ad['photos']:
                    if first_photo:
                        media_group.append(InputMediaPhoto(
                            media=photo['file_id'],
                            caption=message
                        ))
                        first_photo = False
                    else:
                        media_group.append(InputMediaPhoto(
                            media=photo['file_id']
                        ))

                # Отправляем все фото группой
                await update.message.reply_media_group(media=media_group)
            except Exception as e:
                logger.error(f"Ошибка при отправке фото: {e}")
                await update.message.reply_text(message)
        else:
            await update.message.reply_text(message)


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Отмена текущей операции
    """
    keyboard = [
        [KeyboardButton("📝 Подать объявление"), KeyboardButton("👀 Смотреть объявления")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text(
        "❌ Операция отменена.",
        reply_markup=reply_markup
    )
    return ConversationHandler.END


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Обработка ошибок
    """
    logger.error(f"Update {update} caused error {context.error}")
    try:
        if update and update.message:
            await update.message.reply_text(
                "😔 Произошла ошибка при обработке запроса.\n"
                "Пожалуйста, попробуйте позже или начните сначала."
            )
    except Exception as e:
        logger.error(f"Ошибка при отправке сообщения об ошибке: {e}")


def main() -> None:
    """
    Основная функция запуска бота
    """
    # Создаем объект приложения
    application = Application.builder().token(TOKEN).build()

    # Создаем обработчик разговора
    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler('start', start),
            MessageHandler(filters.Regex('^(📝 Подать объявление)$'), create_ad),
            MessageHandler(filters.Regex('^(👀 Смотреть объявления)$'), view_announcements),
        ],
        states={
            CHOOSING_TYPE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_type)],
            ENTERING_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_name)],
            ENTERING_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_price)],
            ENTERING_CONTACT: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_contact)],
            SENDING_PHOTOS: [
                MessageHandler(filters.PHOTO | filters.TEXT & ~filters.COMMAND, handle_photos),
            ],
        },
        fallbacks=[
            CommandHandler('cancel', cancel),
            MessageHandler(filters.Regex('^❌ Отмена$'), cancel),
        ],
    )

    # Добавляем обработчики
    application.add_handler(conv_handler)
    application.add_handler(MessageHandler(filters.Regex('^(👀 Смотреть объявления)$'), view_announcements))
    application.add_error_handler(error_handler)

    # Запускаем бота
    print("Бот запущен...")
    application.run_polling()


if __name__ == '__main__':
    main()
import os
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

# Токены
BOT_TOKEN = os.environ.get('BOT_TOKEN')
OZON_API_KEY = os.environ.get('OZON_API_KEY')
OZON_CLIENT_ID = os.environ.get('OZON_CLIENT_ID')

# Кэш товаров
products_cache = {}
user_carts = {}
user_orders = {}
current_product_index = {}

class OzonSellerAPI:
    def __init__(self):
        self.headers = {
            "Client-Id": OZON_CLIENT_ID,
            "Api-Key": OZON_API_KEY,
            "Content-Type": "application/json"
        }
    
    def get_products_list(self, limit=50):
        """Получает список товаров из Ozon - ПРАВИЛЬНЫЙ ENDPOINT"""
        try:
            print(f"🔍 Отправляем запрос к Ozon API...")
            print(f"🔑 Client-ID: {OZON_CLIENT_ID}")
            print(f"🔑 API Key: {OZON_API_KEY[:10]}...")
            
            # ПРАВИЛЬНЫЙ ENDPOINT
            response = requests.post(
                "https://api-seller.ozon.ru/v3/product/info/attributes",  # ИЗМЕНИЛИ URL
                headers=self.headers,
                json={
                    "filter": {},
                    "limit": limit,
                    "sort_dir": "ASC"
                },
                timeout=10
            )
            
            print(f"📡 Ответ от Ozon: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                print(f"✅ Успешный ответ от Ozon API")
                if 'result' in data and 'items' in data['result']:
                    print(f"📦 Найдено товаров: {len(data['result']['items'])}")
                return data
            else:
                print(f"❌ Ошибка Ozon API: {response.status_code}")
                print(f"💬 Текст ошибки: {response.text[:200]}")
                return None
                
        except Exception as e:
            print(f"❌ Исключение при запросе к Ozon: {e}")
            return None
    
    def get_product_prices(self, product_ids):
        """Получает цены для списка товаров - ПРАВИЛЬНЫЙ ENDPOINT"""
        try:
            print(f"🔍 Запрашиваем цены для {len(product_ids)} товаров...")
            
            # ПРАВИЛЬНЫЙ ENDPOINT
            response = requests.post(
                "https://api-seller.ozon.ru/v3/product/info/prices",  # ИЗМЕНИЛИ URL
                headers=self.headers,
                json={
                    "product_id": product_ids,
                    "visibility": "ALL"
                },
                timeout=10
            )
            
            print(f"📡 Ответ цен: {response.status_code}")
            
            if response.status_code == 200:
                return response.json()
            else:
                print(f"❌ Ошибка получения цен: {response.status_code}")
                print(f"💬 Текст ошибки: {response.text[:200]}")
                return None
        except Exception as e:
            print(f"❌ Ошибка запроса цен: {e}")
            return None

# Инициализация API
ozon_api = OzonSellerAPI()

async def load_real_products():
    """Загружает реальные товары с ценами из Ozon API"""
    global products_cache
    
    print("🔄 Загрузка товаров из Ozon...")
    
    # Проверяем наличие API ключей
    if not OZON_CLIENT_ID or not OZON_API_KEY:
        print("❌ API ключи не настроены!")
        products_cache = {}
        return {}
    
    # Получаем список товаров
    products_data = ozon_api.get_products_list(limit=50)
    
    if not products_data:
        print("❌ Не удалось получить данные от Ozon API")
        products_cache = {}
        return {}
    
    if 'result' not in products_data or 'items' not in products_data['result']:
        print("❌ Неверный формат ответа от Ozon API")
        products_cache = {}
        return {}
    
    products = {}
    product_counter = 1
    
    # Обрабатываем товары
    for item in products_data['result']['items']:
        try:
            product_id = item.get('id', '')
            offer_id = item.get('offer_id', '')
            name = item.get('name', f'Товар {offer_id}')
            
            # Получаем цену (упрощенно - в реальности нужно из prices)
            price = 1999  # Заглушка, нужно получить из API цен
            
            product_key = product_counter
            
            products[product_key] = {
                'ozon_id': product_id,
                'offer_id': offer_id,
                'name': name,
                'price': price,
                'image': "📦",
                'description': "Товар из нашего магазина",
                'quantity': 1
            }
            
            product_counter += 1
            
        except Exception as e:
            print(f"❌ Ошибка обработки товара: {e}")
            continue
    
    print(f"✅ Загружено {len(products)} товаров из Ozon")
    products_cache = products
    return products

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Приветствие и главное меню"""
    user = update.message.from_user
    
    # Загружаем товары при старте
    if not products_cache:
        await load_real_products()
    
    # Проверяем есть ли товары
    if not products_cache:
        keyboard = [
            [InlineKeyboardButton("🔄 Попробовать снова", callback_data="refresh_products")],
            [InlineKeyboardButton("📞 Поддержка", callback_data="support")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "❌ *Товары временно недоступны*\n\n"
            "Не удалось загрузить товары из магазина.\n"
            "Попробуйте обновить или обратитесь в поддержку.",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        return
    
    keyboard = [
        [InlineKeyboardButton("🛍️ Смотреть товары", callback_data="view_products")],
        [InlineKeyboardButton("🛒 Моя корзина", callback_data="cart")],
        [InlineKeyboardButton("📦 Мои заказы", callback_data="my_orders")],
        [InlineKeyboardButton("🔄 Обновить товары", callback_data="refresh_products")],
        [InlineKeyboardButton("📞 Поддержка", callback_data="support")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    welcome_text = (
        f"👋 Привет, {user.first_name}!\n\n"
        "🏪 *Добро пожаловать в наш Ozon магазин!*\n\n"
        f"📦 *Доступно товаров:* {len(products_cache)}\n"
        "🛒 Делайте заказы прямо в Telegram!\n\n"
        "Нажмите 'Смотреть товары' чтобы начать покупки:"
    )
    
    await update.message.reply_text(welcome_text, reply_markup=reply_markup, parse_mode='Markdown')

# ... остальные функции (view_products, show_product, add_to_cart и т.д.) остаются без изменений

async def refresh_products(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обновление списка товаров"""
    query = update.callback_query
    await query.answer()
    
    await load_real_products()
    
    if not products_cache:
        keyboard = [[InlineKeyboardButton("📞 Поддержка", callback_data="support")]]
        await query.edit_message_text(
            "❌ Не удалось загрузить товары\n"
            "Попробуйте позже или обратитесь в поддержку",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return
    
    keyboard = [[InlineKeyboardButton("🛍️ Смотреть товары", callback_data="view_products")]]
    
    await query.edit_message_text(
        f"✅ Товары обновлены!\n"
        f"📦 Загружено товаров: {len(products_cache)}",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def support(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Поддержка"""
    query = update.callback_query
    await query.answer()
    
    keyboard = [
        [InlineKeyboardButton("📞 Написать менеджеру", url="https://t.me/your_manager")],
        [InlineKeyboardButton("🌐 Наш Ozon магазин", url="https://ozon.ru/t/your-store")],
        [InlineKeyboardButton("↩️ Назад", callback_data="back_main")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "📞 *Служба поддержки*\n\n"
        "🕒 Время работы: 9:00-21:00\n"
        "📞 Телефон: +7 (XXX) XXX-XX-XX\n"
        "✉️ Email: support@yourstore.ru\n\n"
        "Свяжитесь с нами для консультации или помощи с заказом!",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик callback-ов"""
    query = update.callback_query
    data = query.data
    
    if data == "view_products":
        await view_products(update, context)
    elif data in ["product_prev", "product_next"]:
        await handle_product_navigation(update, context)
    elif data.startswith("add_"):
        await add_to_cart(update, context)
    elif data == "cart":
        await show_cart(update, context)
    elif data == "checkout":
        await checkout(update, context)
    elif data == "clear_cart":
        user_id = query.from_user.id
        user_carts[user_id] = {}
        await show_cart(update, context)
    elif data == "my_orders":
        await show_my_orders(update, context)
    elif data == "refresh_products":
        await refresh_products(update, context)
    elif data == "support":
        await support(update, context)
    elif data == "back_main":
        await start(update, context)

def main():
    """Запуск бота"""
    if not BOT_TOKEN:
        print("❌ BOT_TOKEN не найден!")
        return
    
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Обработчики
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("refresh", refresh_products))
    application.add_handler(CallbackQueryHandler(handle_callback))
    
    # Предзагрузка товаров
    print("🔄 Загрузка товаров из Ozon...")
    
    print("🛍️ Ozon Client Bot запущен!")
    application.run_polling()

if __name__ == '__main__':
    main()

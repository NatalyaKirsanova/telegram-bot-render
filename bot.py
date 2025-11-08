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
        """Получает список товаров из Ozon с детальной диагностикой"""
        try:
            print(f"🔍 Отправляем запрос к Ozon API...")
            print(f"🔑 Client-ID: {OZON_CLIENT_ID[:10]}...")
            print(f"🔑 API Key: {OZON_API_KEY[:10]}...")
            
            response = requests.post(
                "https://api-seller.ozon.ru/v2/product/list",
                headers=self.headers,
                json={
                    "filter": {"visibility": "ALL"},
                    "limit": limit
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
        """Получает цены для списка товаров"""
        try:
            print(f"🔍 Запрашиваем цены для {len(product_ids)} товаров...")
            
            response = requests.post(
                "https://api-seller.ozon.ru/v1/product/info/prices",
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
    product_ids = []
    
    # Собираем ID товаров для получения цен
    for item in products_data['result']['items']:
        try:
            product_id = item['product_id']
            product_ids.append(product_id)
        except Exception as e:
            print(f"❌ Ошибка сбора ID товаров: {e}")
            continue
    
    print(f"📋 Собрано ID товаров: {len(product_ids)}")
    
    # Получаем цены для всех товаров
    prices_data = ozon_api.get_product_prices(product_ids)
    prices_map = {}
    
    if prices_data and 'result' in prices_data:
        for price_item in prices_data['result']['items']:
            product_id = price_item['product_id']
            price = price_item['price']
            prices_map[str(product_id)] = price
        print(f"✅ Получены цены для {len(prices_map)} товаров")
    else:
        print("❌ Не удалось получить цены товаров")
    
    # Обрабатываем товары
    for item in products_data['result']['items']:
        try:
            product_id = item['product_id']
            offer_id = item['offer_id']
            name = item.get('name', f'Товар {offer_id}')
            
            # Получаем цену из prices_map
            price = prices_map.get(str(product_id), 0)
            
            # Пропускаем товары без цены
            if price == 0:
                print(f"⚠️ Пропускаем товар без цены: {name}")
                continue
            
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
    
    print(f"✅ Загружено {len(products)} товаров с ценами из Ozon")
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
            [InlineKeyboardButton("🔧 Диагностика", callback_data="diagnostics")],
            [InlineKeyboardButton("📞 Поддержка", callback_data="support")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "❌ *Товары временно недоступны*\n\n"
            "Не удалось загрузить товары из магазина.\n"
            "Возможные причины:\n"
            "• Проблемы с API Ozon\n"
            "• Не настроены API ключи\n"
            "• Нет товаров в магазине\n\n"
            "Попробуйте обновить или проверьте диагностику.",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        return
    
    keyboard = [
        [InlineKeyboardButton("🛍️ Смотреть товары", callback_data="view_products")],
        [InlineKeyboardButton("🛒 Моя корзина", callback_data="cart")],
        [InlineKeyboardButton("📦 Мои заказы", callback_data="my_orders")],
        [InlineKeyboardButton("🔄 Обновить товары", callback_data="refresh_products")],
        [InlineKeyboardButton("🔧 Диагностика", callback_data="diagnostics")],
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

async def diagnostics(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Диагностика проблем с API"""
    query = update.callback_query
    if query:
        await query.answer()
    
    # Проверяем настройки
    diagnostics_text = "🔧 *Диагностика системы:*\n\n"
    
    # Проверка переменных окружения
    if not OZON_CLIENT_ID:
        diagnostics_text += "❌ OZON_CLIENT_ID не настроен\n"
    else:
        diagnostics_text += f"✅ OZON_CLIENT_ID: {OZON_CLIENT_ID[:10]}...\n"
    
    if not OZON_API_KEY:
        diagnostics_text += "❌ OZON_API_KEY не настроен\n"
    else:
        diagnostics_text += f"✅ OZON_API_KEY: {OZON_API_KEY[:10]}...\n"
    
    if not BOT_TOKEN:
        diagnostics_text += "❌ BOT_TOKEN не настроен\n"
    else:
        diagnostics_text += f"✅ BOT_TOKEN: {BOT_TOKEN[:10]}...\n"
    
    diagnostics_text += f"\n📦 Загружено товаров: {len(products_cache)}\n"
    
    # Тестируем подключение к Ozon API
    diagnostics_text += "\n🔍 *Тест подключения к Ozon API:*\n"
    
    try:
        test_response = requests.post(
            "https://api-seller.ozon.ru/v2/product/list",
            headers=ozon_api.headers,
            json={"limit": 1},
            timeout=10
        )
        
        if test_response.status_code == 200:
            diagnostics_text += "✅ Подключение к Ozon API работает\n"
            data = test_response.json()
            if 'result' in data and 'items' in data['result']:
                diagnostics_text += f"✅ Товаров в магазине: {len(data['result']['items'])}\n"
            else:
                diagnostics_text += "⚠️ Неверный формат ответа API\n"
        elif test_response.status_code == 403:
            diagnostics_text += "❌ Ошибка 403: Неверный API ключ или права доступа\n"
        elif test_response.status_code == 401:
            diagnostics_text += "❌ Ошибка 401: Неавторизованный доступ\n"
        else:
            diagnostics_text += f"❌ Ошибка {test_response.status_code}: {test_response.text[:100]}\n"
            
    except Exception as e:
        diagnostics_text += f"❌ Ошибка подключения: {str(e)}\n"
    
    keyboard = [
        [InlineKeyboardButton("🔄 Обновить товары", callback_data="refresh_products")],
        [InlineKeyboardButton("📞 Поддержка", callback_data="support")],
        [InlineKeyboardButton("↩️ Главное меню", callback_data="back_main")]
    ]
    
    if query:
        await query.edit_message_text(diagnostics_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    else:
        await update.message.reply_text(diagnostics_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

# ... остальные функции (view_products, show_product, add_to_cart и т.д.) остаются без изменений

async def refresh_products(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обновление списка товаров"""
    query = update.callback_query
    await query.answer()
    
    await load_real_products()
    
    if not products_cache:
        keyboard = [
            [InlineKeyboardButton("🔧 Диагностика", callback_data="diagnostics")],
            [InlineKeyboardButton("📞 Поддержка", callback_data="support")]
        ]
        await query.edit_message_text(
            "❌ Не удалось загрузить товары\n"
            "Проверьте диагностику для выявления проблемы",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return
    
    keyboard = [[InlineKeyboardButton("🛍️ Смотреть товары", callback_data="view_products")]]
    
    await query.edit_message_text(
        f"✅ Товары обновлены!\n"
        f"📦 Загружено товаров: {len(products_cache)}",
        reply_markup=InlineKeyboardMarkup(keyboard)
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
    elif data == "diagnostics":
        await diagnostics(update, context)
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
    application.add_handler(CommandHandler("diagnostics", diagnostics))
    application.add_handler(CallbackQueryHandler(handle_callback))
    
    # Предзагрузка товаров
    print("🔄 Загрузка товаров из Ozon...")
    
    print("🛍️ Ozon Client Bot запущен!")
    application.run_polling()

if __name__ == '__main__':
    main()

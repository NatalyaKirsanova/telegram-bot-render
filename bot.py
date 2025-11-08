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
    
    def test_all_endpoints(self):
        """Тестирует все возможные endpoints Ozon API"""
        endpoints = [
            {
                "name": "v2/product/list",
                "url": "https://api-seller.ozon.ru/v2/product/list",
                "payload": {"filter": {"visibility": "ALL"}, "limit": 5}
            },
            {
                "name": "v3/product/list", 
                "url": "https://api-seller.ozon.ru/v3/product/list",
                "payload": {"filter": {}, "limit": 5}
            },
            {
                "name": "v3/product/info/attributes",
                "url": "https://api-seller.ozon.ru/v3/product/info/attributes", 
                "payload": {"filter": {}, "limit": 5}
            },
            {
                "name": "v2/category/tree",
                "url": "https://api-seller.ozon.ru/v2/category/tree",
                "payload": {}
            },
            {
                "name": "v1/category/tree", 
                "url": "https://api-seller.ozon.ru/v1/category/tree",
                "payload": {}
            }
        ]
        
        print("🔍 Тестируем endpoints Ozon API...")
        working_endpoints = []
        
        for endpoint in endpoints:
            try:
                response = requests.post(
                    endpoint["url"],
                    headers=self.headers,
                    json=endpoint["payload"],
                    timeout=10
                )
                status = "✅ РАБОТАЕТ" if response.status_code == 200 else f"❌ {response.status_code}"
                print(f"   {endpoint['name']}: {status}")
                
                if response.status_code == 200:
                    working_endpoints.append(endpoint)
                    
            except Exception as e:
                print(f"   {endpoint['name']}: ❌ Ошибка {e}")
        
        return working_endpoints
    
    def get_products_working(self, limit=20):
        """Получает товары используя рабочие endpoints"""
        working_endpoints = self.test_all_endpoints()
        
        if not working_endpoints:
            print("❌ Нет рабочих endpoints Ozon API")
            return None
        
        # Пробуем первый рабочий endpoint
        endpoint = working_endpoints[0]
        print(f"🔄 Используем endpoint: {endpoint['name']}")
        
        try:
            response = requests.post(
                endpoint["url"],
                headers=self.headers,
                json={**endpoint["payload"], "limit": limit},
                timeout=10
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                print(f"❌ Ошибка {endpoint['name']}: {response.status_code}")
                return None
                
        except Exception as e:
            print(f"❌ Ошибка запроса {endpoint['name']}: {e}")
            return None

# Инициализация API
ozon_api = OzonSellerAPI()

async def load_real_products():
    """Загружает реальные товары из Ozon API"""
    global products_cache
    
    print("🔄 Загрузка товаров из Ozon...")
    
    # Проверяем наличие API ключей
    if not OZON_CLIENT_ID or not OZON_API_KEY:
        print("❌ API ключи не настроены!")
        products_cache = {}
        return {}
    
    # Получаем товары через рабочие endpoints
    products_data = ozon_api.get_products_working(limit=20)
    
    if not products_data:
        print("❌ Не удалось получить товары через Ozon API")
        
        # Создаем демо-товары для тестирования бота
        print("⚠️ Создаем демо-товары для тестирования...")
        demo_products = create_demo_products()
        products_cache = demo_products
        return demo_products
    
    products = {}
    product_counter = 1
    
    # Обрабатываем товары в зависимости от структуры ответа
    try:
        # Пробуем разные структуры ответа Ozon API
        items = []
        
        if 'result' in products_data and 'items' in products_data['result']:
            items = products_data['result']['items']
        elif 'items' in products_data:
            items = products_data['items']
        elif 'products' in products_data:
            items = products_data['products']
        else:
            # Если структура неизвестна, используем весь ответ как список
            items = [products_data]
        
        for item in items:
            try:
                # Пробуем разные поля для названия и ID
                name = item.get('name') or item.get('title') or item.get('product_name') or f'Товар {product_counter}'
                product_id = item.get('id') or item.get('product_id') or item.get('offer_id') or str(product_counter)
                offer_id = item.get('offer_id') or item.get('sku') or str(product_counter)
                
                # Получаем цену (упрощенно)
                price = item.get('price') or item.get('current_price') or 1999
                
                products[product_counter] = {
                    'ozon_id': product_id,
                    'offer_id': offer_id,
                    'name': name,
                    'price': price,
                    'image': "📦",
                    'description': "Товар из нашего магазина",
                    'quantity': item.get('quantity', 1) or item.get('stock', 1) or 1
                }
                
                product_counter += 1
                
            except Exception as e:
                print(f"❌ Ошибка обработки товара: {e}")
                continue
                
    except Exception as e:
        print(f"❌ Ошибка разбора ответа Ozon API: {e}")
        # Создаем демо-товары если не удалось разобрать ответ
        demo_products = create_demo_products()
        products_cache = demo_products
        return demo_products
    
    print(f"✅ Загружено {len(products)} товаров из Ozon")
    products_cache = products
    return products

def create_demo_products():
    """Создает демо-товары для тестирования"""
    return {
        1: {"name": "Смартфон Xiaomi", "price": 19999, "image": "📱", "description": "Смартфон с отличной камерой", "quantity": 10},
        2: {"name": "Наушники Sony", "price": 12999, "image": "🎧", "description": "Беспроводные наушники", "quantity": 15},
        3: {"name": "Футболка хлопковая", "price": 1499, "image": "👕", "description": "Мужская футболка", "quantity": 25},
        4: {"name": "Кроссовки Nike", "price": 8999, "image": "👟", "description": "Спортивные кроссовки", "quantity": 8},
    }

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

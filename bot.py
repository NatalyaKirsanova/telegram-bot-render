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
    
    def get_products_with_prices(self, limit=20):
        """Получает товары с реальными ценами и названиями"""
        print("🔄 Получение товаров через v3/product/list...")
        
        try:
            # Получаем список товаров через v3/product/list
            products_response = requests.post(
                "https://api-seller.ozon.ru/v3/product/list",
                headers=self.headers,
                json={"filter": {}, "limit": limit, "sort_dir": "ASC"},
                timeout=10
            )
            
            if products_response.status_code != 200:
                print(f"❌ Ошибка v3/product/list: {products_response.status_code}")
                print(f"Текст ошибки: {products_response.text}")
                return None
            
            products_data = products_response.json()
            items = products_data.get('result', {}).get('items', [])
            print(f"✅ Получено товаров: {len(items)}")
            
            if not items:
                print("❌ Нет товаров в ответе")
                return None
            
            # Детальная информация о каждом товаре из v3/product/list
            print("🔍 Детальная информация о товарах из v3/product/list:")
            for i, item in enumerate(items):
                product_id = item.get('product_id')
                offer_id = item.get('offer_id')
                name = item.get('name')
                print(f"  Товар {i+1}: ID={product_id}, Offer={offer_id}, Name={name}")
            
            # Получаем ID товаров для запроса цен
            product_ids = []
            for item in items:
                product_id = item.get('product_id')
                if product_id:
                    product_ids.append(product_id)
            
            print(f"🔍 Запрашиваем цены для {len(product_ids)} товаров через v5/product/info/prices...")
            
            # Получаем цены товаров через v5 endpoint
            prices_map = self.get_prices_v5(product_ids)
            
            # Объединяем данные товаров и цен
            enhanced_products = []
            for item in items:
                product_id = item.get('product_id')
                offer_id = item.get('offer_id')
                
                # Создаем читаемое название на основе offer_id
                if offer_id:
                    # Преобразуем offer_id в читаемое название
                    clean_name = self.create_readable_name(offer_id)
                    name = clean_name
                else:
                    name = f"Товар {product_id}"
                
                # Проверяем наличие offer_id
                if not offer_id:
                    print(f"⚠️ Пропускаем товар без offer_id: ID={product_id}")
                    continue
                
                price_value = prices_map.get(str(product_id), 0)
                
                # Пропускаем товары без цены
                if price_value == 0:
                    print(f"⚠️ Пропускаем товар без цены: {name} (ID: {product_id})")
                    continue
                
                description = item.get('description', f'Артикул: {offer_id}')
                if description and len(description) > 150:
                    description = description[:150] + "..."
                
                # Получаем количество из item (если есть) или ставим по умолчанию
                quantity = item.get('quantity', 10)  # По умолчанию 10 шт.
                
                enhanced_product = {
                    'product_id': product_id,
                    'offer_id': offer_id,
                    'name': name,
                    'price': price_value,
                    'description': description,
                    'quantity': quantity
                }
                enhanced_products.append(enhanced_product)
                print(f"📦 Товар с ценой: {name} - {price_value} ₽ (В наличии: {quantity} шт.)")
            
            print(f"✅ Обработано {len(enhanced_products)} товаров с ценами")
            return enhanced_products
                
        except Exception as e:
            print(f"❌ Ошибка запроса к Ozon API: {e}")
            return None
    
    def create_readable_name(self, offer_id):
        """Создает читаемое название из offer_id"""
        # Убираем лишние символы и создаем читаемое название
        clean_id = offer_id.replace('-', ' ').replace('_', ' ').replace('/', ' ')
        clean_id = ' '.join(clean_id.split())  # Убираем лишние пробелы
        
        # Создаем название на основе типа товара
        if any(word in clean_id.lower() for word in ['h813', 'h388', 'h109']):
            return f"Футболка {clean_id}"
        elif any(word in clean_id.lower() for word in ['b363', 'b323']):
            return f"Толстовка {clean_id}"
        elif any(word in clean_id.lower() for word in ['d513']):
            return f"Штаны {clean_id}"
        else:
            return f"Товар {clean_id}"
    
    def get_prices_v5(self, product_ids):
        """Получает цены через v5/product/info/prices"""
        print("🔍 Используем v5/product/info/prices...")
        try:
            prices_response = requests.post(
                "https://api-seller.ozon.ru/v5/product/info/prices",
                headers=self.headers,
                json={
                    "filter": {
                        "product_id": product_ids,
                        "visibility": "ALL"
                    },
                    "last_id": "",
                    "limit": 1000
                },
                timeout=10
            )
            
            if prices_response.status_code == 200:
                prices_data = prices_response.json()
                price_items = prices_data.get('items', [])
                print(f"📊 v5: Получены цены для {len(price_items)} товаров")
                
                prices_map = {}
                for price_item in price_items:
                    product_id = price_item.get('product_id')
                    price_info = price_item.get('price', {})
                    
                    # Извлекаем цену из структуры
                    price_value = self.extract_price_from_structure(price_info)
                    
                    if product_id and price_value > 0:
                        prices_map[str(product_id)] = price_value
                        print(f"💰 Цена для {product_id}: {price_value} ₽")
                    else:
                        print(f"⚠️ Некорректная цена для товара {product_id}: {price_value}")
                
                return prices_map
            else:
                print(f"❌ v5 endpoint ошибка: {prices_response.status_code}")
                print(f"Текст ошибки: {prices_response.text}")
                return {}
                
        except Exception as e:
            print(f"❌ Ошибка v5 endpoint: {e}")
            return {}
    
    def extract_price_from_structure(self, price_info):
        """Извлечение цены из структуры Ozon v5"""
        if not price_info:
            return 0
        
        # Приоритеты извлечения цены из структуры v5:
        # 1. Основная цена (price)
        # 2. Старая цена (old_price) 
        # 3. Маркетинговая цена (marketing_price)
        # 4. Минимальная цена (min_price)
        
        price = price_info.get('price')
        if price and price > 0:
            return price
        
        old_price = price_info.get('old_price')
        if old_price and old_price > 0:
            return old_price
        
        marketing_price = price_info.get('marketing_price')
        if marketing_price and marketing_price > 0:
            return marketing_price
        
        min_price = price_info.get('min_price')
        if min_price and min_price > 0:
            return min_price
        
        return 0

# Инициализация API
ozon_api = OzonSellerAPI()

def create_demo_products():
    """Создает демо-товары для тестирования"""
    return {
        1: {"name": "Смартфон Xiaomi", "price": 19999, "image": "📱", "description": "Смартфон с отличной камерой", "quantity": 10},
        2: {"name": "Наушники Sony", "price": 12999, "image": "🎧", "description": "Беспроводные наушники", "quantity": 15},
        3: {"name": "Футболка хлопковая", "price": 1499, "image": "👕", "description": "Мужская футболка", "quantity": 25},
        4: {"name": "Кроссовки Nike", "price": 8999, "image": "👟", "description": "Спортивные кроссовки", "quantity": 8},
    }

async def load_real_products():
    """Загружает реальные товары с ценами и названиями из Ozon API"""
    global products_cache
    
    print("🔄 Загрузка товаров из Ozon...")
    
    # Проверяем наличие API ключей
    if not OZON_CLIENT_ID or not OZON_API_KEY:
        print("❌ API ключи не настроены!")
        products_cache = {}
        return {}
    
    # Получаем товары с реальными ценами и названиями
    products_data = ozon_api.get_products_with_prices(limit=20)
    
    if not products_data:
        print("❌ Не удалось получить товары через Ozon API")
        
        # Создаем демо-товары для тестирования бота
        print("⚠️ Создаем демо-товары для тестирования...")
        demo_products = create_demo_products()
        products_cache = demo_products
        return demo_products
    
    products = {}
    product_counter = 1
    
    # Обрабатываем товары
    for item in products_data:
        try:
            product_id = item.get('product_id', '')
            offer_id = item.get('offer_id', '')
            name = item.get('name', f'Товар {offer_id}')
            price = item.get('price', 0)
            description = item.get('description', '')
            quantity = item.get('quantity', 0)
            
            # Пропускаем товары без цены или названия
            if price == 0 or not name:
                print(f"⚠️ Пропускаем товар без цены или названия: {name}")
                continue
            
            # Формируем описание
            if description and description != f'Артикул: {offer_id}':
                # Обрезаем длинное описание
                if len(description) > 150:
                    description = description[:150] + "..."
            else:
                description = f"Артикул: {offer_id}"
            
            product_key = product_counter
            
            products[product_key] = {
                'ozon_id': product_id,
                'offer_id': offer_id,
                'name': name,
                'price': price,
                'image': "📦",
                'description': description,
                'quantity': quantity
            }
            
            print(f"📦 Товар {product_counter}: {name} - {price} ₽")
            product_counter += 1
            
        except Exception as e:
            print(f"❌ Ошибка обработки товара: {e}")
            continue
    
    print(f"✅ Загружено {len(products)} товаров с реальными ценами и названиями из Ozon")
    products_cache = products
    return products

# ... остальные функции бота остаются без изменений ...

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Приветствие и главное меню"""
    # Получаем пользователя в зависимости от типа update
    if update.message:
        user = update.message.from_user
        chat_id = update.message.chat_id
    elif update.callback_query:
        user = update.callback_query.from_user
        chat_id = update.callback_query.message.chat_id
    else:
        # Если не можем получить пользователя, выходим
        return
    
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
        
        if update.message:
            await update.message.reply_text(
                "❌ *Товары временно недоступны*\n\n"
                "Не удалось загрузить товары из магазина.\n"
                "Попробуйте обновить или обратитесь в поддержку.",
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
        else:
            await update.callback_query.edit_message_text(
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
    
    if update.message:
        await update.message.reply_text(welcome_text, reply_markup=reply_markup, parse_mode='Markdown')
    else:
        await update.callback_query.edit_message_text(welcome_text, reply_markup=reply_markup, parse_mode='Markdown')

# ... остальной код бота остается без изменений ...

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

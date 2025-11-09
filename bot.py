import os
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
import asyncio

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
        """Получает товары с реальными ценами и названиями через v3/product/list + v4/product/info/prices"""
        print("🔄 Получение товаров через комбинированный метод...")
        
        try:
            # Получаем список товаров через v3/product/list
            products_response = requests.post(
                "https://api-seller.ozon.ru/v3/product/list",
                headers=self.headers,
                json={
                    "filter": {
                        "visibility": "ALL"
                    },
                    "limit": limit,
                    "sort_dir": "ASC"
                },
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
            
            # Получаем информацию о ценах и остатках через v4/product/info/prices
            product_ids = [item['product_id'] for item in items if 'product_id' in item]
            print(f"🔍 Запрашиваем цены для {len(product_ids)} товаров...")
            
            prices_response = requests.post(
                "https://api-seller.ozon.ru/v4/product/info/prices",
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
            
            prices_data = {}
            if prices_response.status_code == 200:
                prices_result = prices_response.json().get('result', {})
                price_items = prices_result.get('items', [])
                print(f"📊 Получены цены для {len(price_items)} товаров")
                
                # Создаем словарь для быстрого доступа к ценам
                for price_item in price_items:
                    product_id = price_item.get('product_id')
                    prices_data[product_id] = price_item
            else:
                print(f"❌ Ошибка получения цен: {prices_response.status_code}")
            
            # Формируем итоговый список товаров
            enhanced_products = []
            for item in items:
                try:
                    product_id = item.get('product_id')
                    offer_id = item.get('offer_id')
                    
                    if not product_id:
                        continue
                    
                    # Получаем название из offer_id или создаем generic
                    name = offer_id or f"Товар {product_id}"
                    
                    # Получаем цену из данных v4
                    price_item = prices_data.get(product_id, {})
                    price = self.extract_price_from_v4(price_item)
                    
                    # Пропускаем товары без цены
                    if price == 0:
                        print(f"⚠️ Пропускаем товар без цены: {name}")
                        continue
                    
                    # Получаем количество (используем данные из v3 или ставим по умолчанию)
                    quantity = self.extract_quantity_from_v3(item)
                    
                    description = f"Артикул: {offer_id}" if offer_id else f"ID: {product_id}"
                    
                    enhanced_product = {
                        'product_id': product_id,
                        'offer_id': offer_id,
                        'name': name,
                        'price': price,
                        'description': description,
                        'quantity': quantity
                    }
                    enhanced_products.append(enhanced_product)
                    print(f"📦 Товар: {name} - {price} ₽ (Остаток: {quantity})")
                    
                except Exception as e:
                    print(f"❌ Ошибка обработки товара {item.get('product_id')}: {e}")
                    continue
            
            print(f"✅ Обработано {len(enhanced_products)} товаров с ценами")
            return enhanced_products
                
        except Exception as e:
            print(f"❌ Ошибка запроса к Ozon API: {e}")
            return None
    
    def extract_price_from_v4(self, price_item):
        """Извлекает цену из структуры v4/product/info/prices"""
        if not price_item:
            return 0
        
        # Пробуем разные поля с ценой в порядке приоритета
        price_info = price_item.get('price', '')
        
        if isinstance(price_info, dict):
            # Если price - это объект
            price = price_info.get('price')
            if price and str(price).replace('.', '').isdigit():
                return int(float(price))
        
        elif isinstance(price_info, str) and price_info.replace('.', '').isdigit():
            # Если price - это строка с числом
            return int(float(price_info))
        
        elif isinstance(price_info, (int, float)):
            # Если price - это число
            return int(price_info)
        
        # Пробуем другие поля
        alternative_prices = [
            price_item.get('old_price'),
            price_item.get('premium_price'),
            price_item.get('recommended_price'),
            price_item.get('min_price'),
            price_item.get('marketing_price'),
        ]
        
        for price in alternative_prices:
            if price and str(price).replace('.', '').isdigit():
                price_value = int(float(price))
                if price_value > 0:
                    return price_value
        
        return 0
    
    def extract_quantity_from_v3(self, item):
        """Извлекает количество из структуры v3/product/list"""
        try:
            # Пробуем получить количество из разных полей
            stocks = item.get('stocks', {})
            
            # Способ 1: из coming
            coming = stocks.get('coming', 0)
            if coming > 0:
                return coming
            
            # Способ 2: из present
            present = stocks.get('present', 0)
            if present > 0:
                return present
            
            # Способ 3: из reserved
            reserved = stocks.get('reserved', 0)
            available = present - reserved
            if available > 0:
                return available
            
            # По умолчанию
            return 10
            
        except Exception as e:
            print(f"⚠️ Ошибка получения количества: {e}")
            return 10

# Инициализация API
ozon_api = OzonSellerAPI()

def create_demo_products():
    """Создает демо-товары для тестирования"""
    return {
        1: {"name": "Смартфон Xiaomi Redmi Note 13", "price": 24999, "image": "📱", "description": "Смартфон с AMOLED дисплеем 120Гц", "quantity": 8},
        2: {"name": "Наушники Sony WH-1000XM4", "price": 27999, "image": "🎧", "description": "Беспроводные наушники с шумоподавлением", "quantity": 12},
        3: {"name": "Футболка хлопковая мужская", "price": 1899, "image": "👕", "description": "100% хлопок, все размеры", "quantity": 25},
        4: {"name": "Кроссовки Nike Air Force 1", "price": 12999, "image": "👟", "description": "Классические белые кроссовки", "quantity": 6},
        5: {"name": "Ноутбук ASUS VivoBook 15", "price": 54999, "image": "💻", "description": "15.6 дюймов, 8GB RAM, 512GB SSD", "quantity": 4},
        6: {"name": "Умные часы Apple Watch Series 9", "price": 41999, "image": "⌚", "description": "GPS, 45mm, алюминиевый корпус", "quantity": 7},
        7: {"name": "Рюкзак городской", "price": 3499, "image": "🎒", "description": "Водонепроницаемый, 30 литров", "quantity": 15},
        8: {"name": "Кофеварка автоматическая", "price": 18999, "image": "☕", "description": "Приготовление капучино и латте", "quantity": 5},
    }

async def load_real_products():
    """Загружает реальные товары с ценами и названиями из Ozon API"""
    global products_cache
    
    print("🔄 Загрузка товаров из Ozon...")
    
    # Проверяем наличие API ключей
    if not OZON_CLIENT_ID or not OZON_API_KEY:
        print("❌ API ключи не настроены!")
        print("⚠️ Создаем демо-товары для тестирования...")
        demo_products = create_demo_products()
        products_cache = demo_products
        return demo_products
    
    # Получаем товары с реальными ценами и названиями
    products_data = ozon_api.get_products_with_prices(limit=15)
    
    if not products_data:
        print("❌ Не удалось получить товары через Ozon API")
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
            name = item.get('name', '')
            price = item.get('price', 0)
            description = item.get('description', '')
            quantity = item.get('quantity', 10)
            
            # Пропускаем товары без цены
            if price == 0:
                print(f"⚠️ Пропускаем товар без цены: {name}")
                continue
            
            # Улучшаем название
            if not name or name == offer_id:
                name = f"Товар {offer_id}" if offer_id else f"Товар {product_id}"
            
            # Формируем описание
            if not description:
                description = f"Артикул: {offer_id}" if offer_id else f"ID: {product_id}"
            elif len(description) > 150:
                description = description[:150] + "..."
            
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
            
            print(f"📦 Товар {product_counter}: {name} - {price} ₽ (Остаток: {quantity})")
            product_counter += 1
            
        except Exception as e:
            print(f"❌ Ошибка обработки товара: {e}")
            continue
    
    print(f"✅ Загружено {len(products)} товаров с реальными ценами и названиями из Ozon")
    products_cache = products
    return products

# ... остальные функции бота остаются без изменений ...

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    user = update.effective_user
    
    # Проверяем, есть ли реальные товары или демо
    product_source = "реальными" if any('ozon_id' in product for product in products_cache.values()) else "демо"
    
    welcome_text = f"""
👋 Привет, {user.first_name}!

Добро пожаловать в Ozon Client Bot! 🛍️

📊 Используются {product_source} товары
📦 Доступно товаров: {len(products_cache)}

Здесь вы можете:
• 📦 Просматривать товары
• 🛒 Добавлять товары в корзину
• 💰 Оформлять заказы

Используйте кнопки ниже для навигации:
    """
    
    keyboard = [
        [InlineKeyboardButton("🛍️ Смотреть товары", callback_data="view_products")],
        [InlineKeyboardButton("🛒 Корзина", callback_data="view_cart"),
         InlineKeyboardButton("📦 Мои заказы", callback_data="view_orders")],
        [InlineKeyboardButton("🔄 Обновить товары", callback_data="refresh_products")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(welcome_text, reply_markup=reply_markup)

async def refresh_products(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /refresh"""
    await update.message.reply_text("🔄 Обновляем список товаров...")
    products_count_before = len(products_cache)
    await load_real_products()
    products_count_after = len(products_cache)
    
    if products_count_after > 0:
        await update.message.reply_text(
            f"✅ Товары обновлены!\n"
            f"📦 Доступно товаров: {products_count_after}\n"
            f"🔄 Было: {products_count_before}, стало: {products_count_after}"
        )
    else:
        await update.message.reply_text("❌ Не удалось обновить товары. Используются демо-данные.")

# ... остальные функции handle_callback, show_products и т.д. остаются без изменений ...

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик callback запросов от кнопок"""
    query = update.callback_query
    await query.answer()
    
    callback_data = query.data
    
    if callback_data == "view_products":
        await show_products(query, context)
    elif callback_data == "view_cart":
        await show_cart(query, context)
    elif callback_data == "view_orders":
        await show_orders(query, context)
    elif callback_data == "refresh_products":
        await refresh_products_callback(query, context)
    elif callback_data.startswith("product_"):
        await handle_product_action(query, context, callback_data)
    elif callback_data.startswith("cart_"):
        await handle_cart_action(query, context, callback_data)

async def show_products(query, context):
    """Показывает список товаров"""
    if not products_cache:
        await load_real_products()
    
    if not products_cache:
        await query.edit_message_text("❌ Товары временно недоступны. Попробуйте позже.")
        return
    
    # Показываем первый товар
    await show_product_detail(query, context, 1)

async def show_product_detail(query, context, product_index):
    """Показывает детали товара"""
    product = products_cache.get(product_index)
    if not product:
        await query.edit_message_text("❌ Товар не найден")
        return
    
    # Определяем источник товара
    source = "🛒 Ozon" if product.get('ozon_id') else "🎮 Демо"
    
    product_text = f"""
{product['image']} *{product['name']}*

💵 *Цена:* {product['price']} ₽
📝 *Описание:* {product['description']}
📦 *В наличии:* {product['quantity']} шт.
🔗 *Источник:* {source}

Выберите действие:
    """
    
    keyboard = [
        [InlineKeyboardButton("🛒 Добавить в корзину", callback_data=f"product_add_{product_index}")],
        [InlineKeyboardButton("⬅️ Предыдущий", callback_data=f"product_prev_{product_index}"),
         InlineKeyboardButton("Следующий ➡️", callback_data=f"product_next_{product_index}")],
        [InlineKeyboardButton("📋 К списку товаров", callback_data="view_products"),
         InlineKeyboardButton("🛒 Корзина", callback_data="view_cart")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(product_text, reply_markup=reply_markup, parse_mode='Markdown')

async def handle_product_action(query, context, callback_data):
    """Обрабатывает действия с товарами"""
    parts = callback_data.split('_')
    action = parts[1]
    product_index = int(parts[2])
    
    if action == "add":
        await add_to_cart(query, context, product_index)
    elif action == "next":
        next_index = product_index + 1
        if next_index > len(products_cache):
            next_index = 1
        await show_product_detail(query, context, next_index)
    elif action == "prev":
        prev_index = product_index - 1
        if prev_index < 1:
            prev_index = len(products_cache)
        await show_product_detail(query, context, prev_index)

async def add_to_cart(query, context, product_index):
    """Добавляет товар в корзину"""
    user_id = query.from_user.id
    product = products_cache.get(product_index)
    
    if not product:
        await query.answer("❌ Товар не найден", show_alert=True)
        return
    
    if user_id not in user_carts:
        user_carts[user_id] = {}
    
    cart = user_carts[user_id]
    
    if product_index in cart:
        cart[product_index] += 1
    else:
        cart[product_index] = 1
    
    await query.answer(f"✅ {product['name']} добавлен в корзину!")
    await show_product_detail(query, context, product_index)

async def show_cart(query, context):
    """Показывает корзину пользователя"""
    user_id = query.from_user.id
    
    if user_id not in user_carts or not user_carts[user_id]:
        await query.edit_message_text("🛒 Ваша корзина пуста")
        return
    
    cart = user_carts[user_id]
    total = 0
    cart_text = "🛒 *Ваша корзина:*\n\n"
    
    for product_index, quantity in cart.items():
        product = products_cache.get(product_index)
        if product:
            item_total = product['price'] * quantity
            total += item_total
            cart_text += f"• {product['name']}\n  {quantity} × {product['price']} ₽ = {item_total} ₽\n"
    
    cart_text += f"\n💵 *Итого:* {total} ₽"
    
    keyboard = [
        [InlineKeyboardButton("💰 Оформить заказ", callback_data="checkout")],
        [InlineKeyboardButton("🛍️ Продолжить покупки", callback_data="view_products"),
         InlineKeyboardButton("🗑️ Очистить корзину", callback_data="clear_cart")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(cart_text, reply_markup=reply_markup, parse_mode='Markdown')

async def show_orders(query, context):
    """Показывает заказы пользователя"""
    user_id = query.from_user.id
    
    if user_id not in user_orders or not user_orders[user_id]:
        await query.edit_message_text("📦 У вас пока нет заказов")
        return
    
    orders = user_orders[user_id]
    orders_text = "📦 *Ваши заказы:*\n\n"
    
    for i, order in enumerate(orders, 1):
        orders_text += f"*Заказ #{i}:*\n"
        orders_text += f"💰 Сумма: {order['total']} ₽\n"
        orders_text += f"📅 Дата: {order['date']}\n"
        orders_text += f"📋 Товаров: {order['items_count']} шт.\n\n"
    
    keyboard = [
        [InlineKeyboardButton("🛍️ К товарам", callback_data="view_products")],
        [InlineKeyboardButton("🛒 Корзина", callback_data="view_cart")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(orders_text, reply_markup=reply_markup, parse_mode='Markdown')

async def refresh_products_callback(query, context):
    """Обновляет товары через callback"""
    await query.edit_message_text("🔄 Обновляем список товаров...")
    products_count_before = len(products_cache)
    await load_real_products()
    products_count_after = len(products_cache)
    
    if products_count_after > 0:
        await query.edit_message_text(
            f"✅ Товары обновлены!\n"
            f"📦 Доступно товаров: {products_count_after}\n"
            f"🔄 Было: {products_count_before}, стало: {products_count_after}"
        )
    else:
        await query.edit_message_text("❌ Не удалось обновить товары. Используются демо-данные.")

async def handle_cart_action(query, context, callback_data):
    """Обрабатывает действия с корзиной"""
    if callback_data == "checkout":
        await checkout(query, context)
    elif callback_data == "clear_cart":
        await clear_cart(query, context)

async def checkout(query, context):
    """Оформляет заказ"""
    user_id = query.from_user.id
    
    if user_id not in user_carts or not user_carts[user_id]:
        await query.answer("❌ Корзина пуста", show_alert=True)
        return
    
    # Создаем заказ
    import datetime
    cart = user_carts[user_id]
    total = 0
    items_count = 0
    
    for product_index, quantity in cart.items():
        product = products_cache.get(product_index)
        if product:
            total += product['price'] * quantity
            items_count += quantity
    
    order = {
        'total': total,
        'items_count': items_count,
        'date': datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
        'products': cart.copy()
    }
    
    if user_id not in user_orders:
        user_orders[user_id] = []
    
    user_orders[user_id].append(order)
    user_carts[user_id] = {}  # Очищаем корзину
    
    await query.edit_message_text(
        f"✅ *Заказ оформлен!*\n\n"
        f"💰 Сумма: {total} ₽\n"
        f"📦 Товаров: {items_count} шт.\n"
        f"📅 Дата: {order['date']}\n\n"
        f"Спасибо за покупку! 🎉",
        parse_mode='Markdown'
    )

async def clear_cart(query, context):
    """Очищает корзину"""
    user_id = query.from_user.id
    user_carts[user_id] = {}
    await query.edit_message_text("🗑️ Корзина очищена")

async def preload_products():
    """Предзагрузка товаров при запуске"""
    print("🔄 Предзагрузка товаров...")
    await load_real_products()
    print("✅ Товары загружены!")

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
    
    # Запускаем предзагрузку асинхронно
    loop = asyncio.get_event_loop()
    loop.run_until_complete(preload_products())
    
    print("🛍️ Ozon Client Bot запущен!")
    application.run_polling()

if __name__ == '__main__':
    main()

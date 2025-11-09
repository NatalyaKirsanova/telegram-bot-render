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
        """Получает товары с реальными ценами и названиями"""
        print("🔄 Получение товаров через v3/product/list...")
        
        try:
            # Получаем список товаров через v3/product/list (более стабильный)
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
            
            # Получаем информацию о товарах и ценах
            enhanced_products = []
            for item in items:
                try:
                    product_id = item.get('product_id')
                    offer_id = item.get('offer_id')
                    
                    if not product_id:
                        continue
                    
                    # Получаем детальную информацию о товаре
                    product_info = self.get_product_info(product_id)
                    if not product_info:
                        continue
                    
                    # Получаем цену товара
                    price_info = self.get_product_price(product_id)
                    if not price_info:
                        continue
                    
                    # Извлекаем данные
                    name = product_info.get('name', offer_id)
                    price = self.extract_price(price_info)
                    description = product_info.get('description', '')
                    
                    if not name or price == 0:
                        continue
                    
                    # Обрезаем длинное описание
                    if description and len(description) > 150:
                        description = description[:150] + "..."
                    elif not description:
                        description = f"Артикул: {offer_id}"
                    
                    enhanced_product = {
                        'product_id': product_id,
                        'offer_id': offer_id,
                        'name': name,
                        'price': price,
                        'description': description,
                        'quantity': 10  # По умолчанию
                    }
                    enhanced_products.append(enhanced_product)
                    print(f"📦 Товар: {name} - {price} ₽")
                    
                except Exception as e:
                    print(f"❌ Ошибка обработки товара {item.get('product_id')}: {e}")
                    continue
            
            print(f"✅ Обработано {len(enhanced_products)} товаров с ценами")
            return enhanced_products
                
        except Exception as e:
            print(f"❌ Ошибка запроса к Ozon API: {e}")
            return None
    
    def get_product_info(self, product_id):
        """Получает информацию о конкретном товаре"""
        try:
            response = requests.post(
                "https://api-seller.ozon.ru/v2/product/info",
                headers=self.headers,
                json={
                    "product_id": product_id
                },
                timeout=10
            )
            
            if response.status_code == 200:
                return response.json().get('result', {})
            else:
                print(f"❌ Ошибка получения информации о товаре {product_id}: {response.status_code}")
                return None
        except Exception as e:
            print(f"❌ Ошибка запроса информации о товаре: {e}")
            return None
    
    def get_product_price(self, product_id):
        """Получает цену товара"""
        try:
            response = requests.post(
                "https://api-seller.ozon.ru/v4/product/info/prices",
                headers=self.headers,
                json={
                    "filter": {
                        "product_id": [product_id],
                        "visibility": "ALL"
                    },
                    "last_id": "",
                    "limit": 100
                },
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                items = data.get('result', {}).get('items', [])
                return items[0] if items else None
            else:
                print(f"❌ Ошибка получения цены товара {product_id}: {response.status_code}")
                return None
        except Exception as e:
            print(f"❌ Ошибка запроса цены товара: {e}")
            return None
    
    def extract_price(self, price_item):
        """Извлекает цену из структуры товара"""
        if not price_item:
            return 0
        
        # Пробуем разные поля с ценой
        price_fields = [
            price_item.get('price'),
            price_item.get('old_price'),
            price_item.get('premium_price'),
            price_item.get('recommended_price'),
        ]
        
        for price in price_fields:
            if price and str(price).isdigit() and int(price) > 0:
                return int(price)
        
        # Пробуем получить из вложенной структуры
        price_info = price_item.get('price', '')
        if isinstance(price_info, str) and price_info.replace('.', '').isdigit():
            return int(float(price_info))
        
        return 0

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
            
            # Пропускаем товары без цены или названия
            if price == 0 or not name:
                print(f"⚠️ Пропускаем товар без цены или названия: {name}")
                continue
            
            # Формируем описание
            if not description or description == f'Артикул: {offer_id}':
                description = f"Артикул: {offer_id}"
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
            
            print(f"📦 Товар {product_counter}: {name} - {price} ₽")
            product_counter += 1
            
        except Exception as e:
            print(f"❌ Ошибка обработки товара: {e}")
            continue
    
    print(f"✅ Загружено {len(products)} товаров с реальными ценами и названиями из Ozon")
    products_cache = products
    return products

# ... остальные функции бота (start, refresh_products, handle_callback и т.д.) остаются без изменений ...

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    user = update.effective_user
    welcome_text = f"""
👋 Привет, {user.first_name}!

Добро пожаловать в Ozon Client Bot! 🛍️

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
    await load_real_products()
    await update.message.reply_text("✅ Товары обновлены!")

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
    
    product_text = f"""
{product['image']} *{product['name']}*

💵 *Цена:* {product['price']} ₽
📝 *Описание:* {product['description']}
📦 *В наличии:* {product['quantity']} шт.

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
    await load_real_products()
    await query.edit_message_text("✅ Товары обновлены!")

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

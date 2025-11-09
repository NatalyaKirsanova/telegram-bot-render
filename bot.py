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
    
    def get_products_with_prices(self, limit=20):
        """Получает товары с реальными ценами и названиями"""
        working_endpoints = self.test_all_endpoints()
        
        if not working_endpoints:
            print("❌ Нет рабочих endpoints Ozon API")
            return None
        
        # Используем endpoint для получения товаров
        endpoint = working_endpoints[0]
        print(f"🔄 Используем endpoint: {endpoint['name']}")
        
        try:
            # Получаем список товаров
            response = requests.post(
                endpoint["url"],
                headers=self.headers,
                json={**endpoint["payload"], "limit": limit},
                timeout=10
            )
            
            if response.status_code == 200:
                products_data = response.json()
                print(f"✅ Получено товаров: {len(products_data.get('result', {}).get('items', []))}")
                
                # Получаем ID товаров для запроса цен
                product_ids = []
                for item in products_data.get('result', {}).get('items', []):
                    product_id = item.get('product_id')
                    if product_id:
                        product_ids.append(product_id)
                
                print(f"🔍 Запрашиваем цены для {len(product_ids)} товаров...")
                
                # Получаем цены товаров
                prices_response = requests.post(
                    "https://api-seller.ozon.ru/v5/product/info/prices",
                    headers=self.headers,
                    json={
                        "product_id": product_ids,
                        "visibility": "ALL"
                    },
                    timeout=10
                )
                
                prices_map = {}
                if prices_response.status_code == 200:
                    prices_data = prices_response.json()
                    for price_item in prices_data.get('result', {}).get('items', []):
                        product_id = price_item.get('product_id')
                        price = price_item.get('price')
                        if product_id and price:
                            prices_map[str(product_id)] = price
                    print(f"✅ Получены цены для {len(prices_map)} товаров")
                else:
                    print(f"❌ Ошибка получения цен: {prices_response.status_code}")
                
                # Объединяем данные товаров и цен
                enhanced_products = []
                for item in products_data.get('result', {}).get('items', []):
                    product_id = item.get('product_id')
                    enhanced_product = {
                        'product_id': product_id,
                        'offer_id': item.get('offer_id'),
                        'name': item.get('name'),
                        'price': prices_map.get(str(product_id), 0),
                        'description': item.get('description', ''),
                        'quantity': item.get('quantity', 0)
                    }
                    enhanced_products.append(enhanced_product)
                
                return enhanced_products
            else:
                print(f"❌ Ошибка {endpoint['name']}: {response.status_code}")
                return None
                
        except Exception as e:
            print(f"❌ Ошибка запроса {endpoint['name']}: {e}")
            return None

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
            if description:
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

async def view_products(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает список товаров"""
    query = update.callback_query
    if query:
        await query.answer()
    
    # Если товаров нет - загружаем
    if not products_cache:
        await load_real_products()
    
    # Проверяем есть ли товары после загрузки
    if not products_cache:
        if query:
            await query.edit_message_text(
                "❌ Товары временно недоступны\nПопробуйте обновить позже.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔄 Обновить", callback_data="refresh_products")]])
            )
        else:
            await update.message.reply_text(
                "❌ Товары временно недоступны\nПопробуйте обновить позже.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔄 Обновить", callback_data="refresh_products")]])
            )
        return
    
    user_id = query.from_user.id if query else update.message.from_user.id
    
    # Начинаем с первого товара
    current_product_index[user_id] = 0
    await show_product(update, context, user_id)

async def show_product(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int = None, force_update: bool = False):
    """Показывает текущий товар с реальными данными"""
    if not user_id:
        if update.callback_query:
            user_id = update.callback_query.from_user.id
        else:
            user_id = update.message.from_user.id
    
    if user_id not in current_product_index:
        current_product_index[user_id] = 0
    
    product_ids = list(products_cache.keys())
    
    if not product_ids:
        # Используем reply_text вместо edit_message_text для нового сообщения
        if update.callback_query:
            await update.callback_query.message.reply_text(
                "❌ Товары временно недоступны",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔄 Обновить", callback_data="refresh_products")]])
            )
        else:
            await update.message.reply_text(
                "❌ Товары временно недоступны",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔄 Обновить", callback_data="refresh_products")]])
            )
        return
    
    current_index = current_product_index[user_id]
    product_id = product_ids[current_index]
    product = products_cache[product_id]
    
    # Кнопки навигации
    keyboard = []
    
    if len(product_ids) > 1:
        nav_buttons = []
        
        if current_index > 0:
            nav_buttons.append(InlineKeyboardButton("⬅️ Назад", callback_data="product_prev"))
        
        nav_buttons.append(InlineKeyboardButton(f"{current_index + 1}/{len(product_ids)}", callback_data="none"))
        
        if current_index < len(product_ids) - 1:
            nav_buttons.append(InlineKeyboardButton("Вперед ➡️", callback_data="product_next"))
        
        keyboard.append(nav_buttons)
    
    # Основные кнопки
    keyboard.extend([
        [InlineKeyboardButton("🛒 Добавить в корзину", callback_data=f"add_{product_id}")],
        [InlineKeyboardButton("🛒 Перейти в корзину", callback_data="cart")],
        [InlineKeyboardButton("🛍️ К списку товаров", callback_data="view_products")],
        [InlineKeyboardButton("↩️ Главное меню", callback_data="back_main")]
    ])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Формируем сообщение с реальными данными
    message_text = (
        f"{product['image']} *{product['name']}*\n\n"
        f"💵 *Цена:* {product['price']} ₽\n"
        f"📝 *Описание:* {product['description']}\n"
        f"📦 *В наличии:* {product['quantity']} шт.\n\n"
        f"✅ *Готов к заказу*\n"
        f"🚚 *Доставка:* Ozon FBS (1-3 дня)\n\n"
        f"🛒 Нажмите 'Добавить в корзину' чтобы заказать!"
    )
    
    if update.callback_query:
        try:
            # Пытаемся изменить сообщение
            await update.callback_query.edit_message_text(
                message_text, 
                reply_markup=reply_markup, 
                parse_mode='Markdown'
            )
        except Exception as e:
            # Если ошибка "сообщение не изменено", просто отвечаем на callback
            if "message is not modified" in str(e):
                await update.callback_query.answer()
            else:
                # Другие ошибки - создаем новое сообщение
                await update.callback_query.message.reply_text(
                    message_text,
                    reply_markup=reply_markup,
                    parse_mode='Markdown'
                )
    else:
        await update.message.reply_text(
            message_text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )

async def handle_product_navigation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка навигации по товарам"""
    query = update.callback_query
    await query.answer()  # Всегда отвечаем на callback
    
    user_id = query.from_user.id
    action = query.data
    
    product_ids = list(products_cache.keys())
    
    if action == "product_prev" and current_product_index[user_id] > 0:
        current_product_index[user_id] -= 1
    elif action == "product_next" and current_product_index[user_id] < len(product_ids) - 1:
        current_product_index[user_id] += 1
    
    await show_product(update, context, user_id, force_update=True)

async def add_to_cart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Добавляет товар в корзину"""
    query = update.callback_query
    await query.answer()
    
    product_id = int(query.data.split("_")[1])
    user_id = query.from_user.id
    
    if user_id not in user_carts:
        user_carts[user_id] = {}
    
    if product_id in user_carts[user_id]:
        user_carts[user_id][product_id] += 1
    else:
        user_carts[user_id][product_id] = 1
    
    product = products_cache[product_id]
    await query.answer(f"✅ {product['name']} добавлен в корзину!")

async def show_cart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает корзину"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    if user_id not in user_carts or not user_carts[user_id]:
        keyboard = [
            [InlineKeyboardButton("🛍️ Смотреть товары", callback_data="view_products")],
            [InlineKeyboardButton("↩️ Главное меню", callback_data="back_main")]
        ]
        await query.edit_message_text(
            "🛒 *Ваша корзина пуста*\n\n"
            "Добавьте товары из каталога!",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
        return
    
    # Формируем содержимое корзины
    cart_text = "🛒 *Ваша корзина:*\n\n"
    total = 0
    
    for product_id, quantity in user_carts[user_id].items():
        product = products_cache[product_id]
        item_total = product['price'] * quantity
        total += item_total
        cart_text += f"{product['image']} *{product['name']}*\n"
        cart_text += f"   {quantity} шт. × {product['price']} ₽ = *{item_total} ₽*\n\n"
    
    cart_text += f"💵 *Итого: {total} ₽*"
    
    keyboard = [
        [InlineKeyboardButton("📦 Оформить заказ", callback_data="checkout")],
        [InlineKeyboardButton("🛍️ Продолжить покупки", callback_data="view_products")],
        [InlineKeyboardButton("🗑️ Очистить корзину", callback_data="clear_cart")],
        [InlineKeyboardButton("↩️ Главное меню", callback_data="back_main")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(cart_text, reply_markup=reply_markup, parse_mode='Markdown')

async def checkout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Оформление заказа"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    user = query.from_user
    
    if user_id not in user_carts or not user_carts[user_id]:
        await query.answer("❌ Корзина пуста!")
        return
    
    # Подсчет итоговой суммы
    total = sum(products_cache[pid]['price'] * qty for pid, qty in user_carts[user_id].items())
    
    # Сохраняем заказ
    if user_id not in user_orders:
        user_orders[user_id] = []
    
    order_id = len(user_orders[user_id]) + 1
    user_orders[user_id].append({
        "order_id": order_id,
        "items": user_carts[user_id].copy(),
        "total": total,
        "status": "Обрабатывается"
    })
    
    # Очищаем корзину
    user_carts[user_id] = {}
    
    # Формируем сообщение о заказе
    order_text = (
        "🎉 *Заказ успешно оформлен!*\n\n"
        f"📋 *Номер заказа:* #{order_id}\n"
        f"💵 *Сумма заказа:* {total} ₽\n"
        f"👤 *Получатель:* {user.first_name}\n"
        f"📞 *Статус:* Обрабатывается\n\n"
        f"🚚 *Доставка:* Ozon FBS\n"
        f"📦 Свяжемся с вами для уточнения деталей доставки\n\n"
        f"Спасибо за покупку! 💝"
    )
    
    keyboard = [
        [InlineKeyboardButton("📦 Мои заказы", callback_data="my_orders")],
        [InlineKeyboardButton("🛍️ Новый заказ", callback_data="view_products")],
        [InlineKeyboardButton("📞 Поддержка", callback_data="support")]
    ]
    
    await query.edit_message_text(
        order_text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def show_my_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает заказы пользователя"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    if user_id not in user_orders or not user_orders[user_id]:
        keyboard = [
            [InlineKeyboardButton("🛍️ Сделать заказ", callback_data="view_products")],
            [InlineKeyboardButton("↩️ Главное меню", callback_data="back_main")]
        ]
        await query.edit_message_text(
            "📦 *У вас пока нет заказов*\n\n"
            "Сделайте ваш первый заказ в нашем магазине!",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
        return
    
    orders_text = "📦 *Ваши заказы:*\n\n"
    
    for order in user_orders[user_id][-5:]:
        orders_text += f"🆔 *Заказ #{order['order_id']}*\n"
        orders_text += f"💵 Сумма: {order['total']} ₽\n"
        orders_text += f"📊 Статус: {order['status']}\n"
        orders_text += f"📦 Товаров: {len(order['items'])}\n\n"
    
    keyboard = [
        [InlineKeyboardButton("🛍️ Новый заказ", callback_data="view_products")],
        [InlineKeyboardButton("📞 Поддержка", callback_data="support")],
        [InlineKeyboardButton("↩️ Главное меню", callback_data="back_main")]
    ]
    
    await query.edit_message_text(
        orders_text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

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
    
    if not query:
        return
    
    data = query.data
    
    try:
        if data == "view_products":
            await view_products(update, context)
        elif data in ["product_prev", "product_next"]:
            await handle_product_navigation(update, context)
        elif data == "none":
            # Просто отвечаем на callback без изменений
            await query.answer()
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
    except Exception as e:
        print(f"❌ Ошибка в обработчике callback: {e}")
        await query.answer("❌ Произошла ошибка, попробуйте снова")

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

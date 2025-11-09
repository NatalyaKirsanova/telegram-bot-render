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
            
            # Получаем ID товаров для запроса полной информации
            product_ids = []
            for item in items:
                product_id = item.get('product_id')
                if product_id:
                    product_ids.append(product_id)
            
            print(f"🔍 Запрашиваем полную информацию для {len(product_ids)} товаров через v3/product/info/list...")
            
            # Получаем полную информацию о товарах через v3 endpoint
            products_info = self.get_products_info_v3(product_ids)
            
            print(f"🔍 Запрашиваем цены для {len(product_ids)} товаров через v5/product/info/prices...")
            
            # Получаем цены товаров через v5 endpoint
            prices_map = self.get_prices_v5(product_ids)
            
            # Объединяем данные товаров и цен
            enhanced_products = []
            for product_info in products_info:
                product_id = product_info.get('id')
                offer_id = product_info.get('offer_id')
                name = product_info.get('name')
                
                # Проверяем наличие названия и offer_id
                if not name:
                    print(f"⚠️ Пропускаем товар без названия: ID={product_id}, Offer={offer_id}")
                    continue
                
                if not offer_id:
                    print(f"⚠️ Пропускаем товар без offer_id: ID={product_id}, Name='{name}'")
                    continue
                
                price_value = prices_map.get(str(product_id), 0)
                
                # Пропускаем товары без цены
                if price_value == 0:
                    print(f"⚠️ Пропускаем товар без цены: {name} (ID: {product_id})")
                    continue
                
                description = product_info.get('description', f'Артикул: {offer_id}')
                if description and len(description) > 150:
                    description = description[:150] + "..."
                
                # Получаем количество из stocks
                quantity = 0
                stocks = product_info.get('stocks', {}).get('stocks', [])
                if stocks:
                    quantity = sum(stock.get('present', 0) for stock in stocks)
                
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
    
    def get_products_info_v3(self, product_ids):
        """Получает полную информацию о товарах через v3/product/info/list"""
        print("🔍 Используем v3/product/info/list...")
        try:
            info_response = requests.post(
                "https://api-seller.ozon.ru/v3/product/info/list",
                headers=self.headers,
                json={
                    "product_id": product_ids
                },
                timeout=10
            )
            
            if info_response.status_code == 200:
                info_data = info_response.json()
                info_items = info_data.get('result', {}).get('items', [])
                print(f"📊 v3/info: Получена информация для {len(info_items)} товаров")
                
                # Детальная информация о каждом товаре
                print("🔍 Детальная информация о товарах из v3:")
                for i, item in enumerate(info_items):
                    product_id = item.get('id')
                    offer_id = item.get('offer_id')
                    name = item.get('name')
                    print(f"  Товар {i+1}: ID={product_id}, Offer={offer_id}, Name='{name}'")
                
                return info_items
            else:
                print(f"❌ v3/info endpoint ошибка: {info_response.status_code}")
                print(f"Текст ошибки: {info_response.text}")
                return []
                
        except Exception as e:
            print(f"❌ Ошибка v3/info endpoint: {e}")
            return []
    
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

# ... остальной код бота (view_products, show_product, handle_product_navigation, add_to_cart, show_cart, checkout, show_my_orders, refresh_products, support, handle_callback, main) ...

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
    if query:
        await query.answer()
    
    await load_real_products()
    
    if not products_cache:
        keyboard = [[InlineKeyboardButton("📞 Поддержка", callback_data="support")]]
        if query:
            await query.edit_message_text(
                "❌ Не удалось загрузить товары\n"
                "Попробуйте позже или обратитесь в поддержку",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        else:
            await update.message.reply_text(
                "❌ Не удалось загрузить товары\n"
                "Попробуйте позже или обратитесь в поддержку",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        return
    
    keyboard = [[InlineKeyboardButton("🛍️ Смотреть товары", callback_data="view_products")]]
    
    if query:
        await query.edit_message_text(
            f"✅ Товары обновлены!\n"
            f"📦 Загружено товаров: {len(products_cache)}",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    else:
        await update.message.reply_text(
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

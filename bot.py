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
            
            print(f"🔍 Запрашиваем полную информацию для {len(product_ids)} товаров...")
            
            # Получаем полную информацию о товарах
            products_info = self.get_products_info(product_ids)
            
            print(f"🔍 Запрашиваем цены для {len(product_ids)} товаров через v5/product/info/prices...")
            
            # Получаем цены товаров через v5 endpoint
            prices_data = self.get_prices_v5(product_ids)
            
            # Объединяем данные товаров и цен
            enhanced_products = []
            for product_info in products_info:
                product_id = product_info.get('id')
                offer_id = product_info.get('offer_id')
                name = product_info.get('name')
                
                # Пропускаем товары без названия
                if not name:
                    print(f"⚠️ Пропускаем товар без названия: ID={product_id}")
                    continue
                
                # Получаем цену из данных v5
                price_item = self.find_price_item(prices_data, product_id)
                if not price_item:
                    print(f"⚠️ Не найдена цена для товара: {name} (ID={product_id})")
                    continue
                
                # Получаем цену из структуры
                price_info = price_item.get('price', {})
                price_value = self.extract_price_from_structure(price_info)
                
                # Пропускаем товары без цены
                if price_value == 0:
                    print(f"⚠️ Пропускаем товар без цены: {name} (ID={product_id})")
                    continue
                
                description = product_info.get('description', f'Артикул: {offer_id}')
                if description and len(description) > 150:
                    description = description[:150] + "..."
                
                # Получаем количество
                quantity = self.get_product_quantity(product_info)
                
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
    
    def get_products_info(self, product_ids):
        """Получает полную информацию о товарах"""
        # Пробуем разные endpoints для получения информации о товарах
        endpoints = [
            self.get_products_info_v2,
            self.get_products_info_v3,
            self.get_products_info_v4
        ]
        
        for endpoint in endpoints:
            print(f"🔍 Пробуем {endpoint.__name__}...")
            products_info = endpoint(product_ids)
            if products_info:
                print(f"✅ {endpoint.__name__}: Получена информация для {len(products_info)} товаров")
                return products_info
            else:
                print(f"❌ {endpoint.__name__}: Не удалось получить информацию")
        
        print("❌ Все endpoints для получения информации о товарах не сработали")
        return []
    
    def get_products_info_v2(self, product_ids):
        """Получает информацию о товарах через v2/product/info/list"""
        try:
            info_response = requests.post(
                "https://api-seller.ozon.ru/v2/product/info/list",
                headers=self.headers,
                json={
                    "product_id": product_ids
                },
                timeout=10
            )
            
            if info_response.status_code == 200:
                info_data = info_response.json()
                return info_data.get('result', {}).get('items', [])
            else:
                print(f"❌ v2/info ошибка: {info_response.status_code}")
                return []
        except Exception as e:
            print(f"❌ Ошибка v2/info: {e}")
            return []
    
    def get_products_info_v3(self, product_ids):
        """Получает информацию о товарах через v3/product/info/list"""
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
                return info_data.get('result', {}).get('items', [])
            else:
                print(f"❌ v3/info ошибка: {info_response.status_code}")
                return []
        except Exception as e:
            print(f"❌ Ошибка v3/info: {e}")
            return []
    
    def get_products_info_v4(self, product_ids):
        """Получает информацию о товарах через v4/product/info/prices (может содержать названия)"""
        try:
            info_response = requests.post(
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
            
            if info_response.status_code == 200:
                info_data = info_response.json()
                items = info_data.get('result', {}).get('items', [])
                
                # Преобразуем структуру v4 в структуру похожую на v2/v3
                transformed_items = []
                for item in items:
                    transformed_items.append({
                        'id': item.get('product_id'),
                        'offer_id': item.get('offer_id'),
                        'name': item.get('offer_id'),  # В v4 может не быть названия, используем offer_id
                        'description': f'Артикул: {item.get("offer_id")}'
                    })
                return transformed_items
            else:
                print(f"❌ v4/info ошибка: {info_response.status_code}")
                return []
        except Exception as e:
            print(f"❌ Ошибка v4/info: {e}")
            return []
    
    def find_price_item(self, prices_data, product_id):
        """Находит элемент с ценой по product_id"""
        if not prices_data or 'items' not in prices_data:
            return None
        
        for item in prices_data['items']:
            if item.get('product_id') == product_id:
                return item
        return None
    
    def get_product_quantity(self, product_info):
        """Получает количество товара в наличии"""
        try:
            # Пробуем разные способы получения количества
            stocks = product_info.get('stocks', {})
            
            # Способ 1: из stocks -> stocks array
            if 'stocks' in stocks:
                total_quantity = 0
                for stock in stocks['stocks']:
                    present = stock.get('present', 0)
                    reserved = stock.get('reserved', 0)
                    available = present - reserved
                    if available > 0:
                        total_quantity += available
                
                if total_quantity > 0:
                    return total_quantity
            
            # Способ 2: из discounted_fbo_stocks
            fbo_stocks = product_info.get('discounted_fbo_stocks', 0)
            if fbo_stocks > 0:
                return fbo_stocks
            
            # Способ 3: проверяем has_stock
            has_stock = stocks.get('has_stock', False)
            if has_stock:
                return 10  # Если есть stock но нет количества, ставим 10
                
            return 10  # По умолчанию 10 шт.
        except Exception as e:
            print(f"❌ Ошибка получения количества: {e}")
            return 10
    
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
                return prices_data
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
            name = item.get('name', '')
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

# ДОБАВЛЕННЫЕ ФУНКЦИИ-ОБРАБОТЧИКИ:

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

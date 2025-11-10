import os
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
import asyncio
import datetime

# Токены
BOT_TOKEN = os.environ.get('BOT_TOKEN')
OZON_API_KEY = os.environ.get('OZON_API_KEY')
OZON_CLIENT_ID = os.environ.get('OZON_CLIENT_ID')

# Кэш товаров
products_cache = {}

current_product_index = {}

class OzonSellerAPI:
    def __init__(self):
        self.headers = {
            "Client-Id": OZON_CLIENT_ID,
            "Api-Key": OZON_API_KEY,
            "Content-Type": "application/json"
        }
    
    def get_products_with_prices(self, limit=50):
        """Получает реальные товары с реальными ценами из Ozon"""
        print("🔄 Получение реальных товаров из Ozon API...")
        
        try:
            # 1. Получаем список товаров через v3/product/list
            print("🔍 Получаем список товаров через v3/product/list...")
            list_response = requests.post(
                "https://api-seller.ozon.ru/v3/product/list",
                headers=self.headers,
                json={
                    "filter": {"visibility": "ALL"},
                    "limit": limit
                },
                timeout=10
            )
        
            if list_response.status_code != 200:
                print(f"❌ Ошибка v3/product/list: {list_response.status_code}")
                print(f"Текст ошибки: {list_response.text}")
                return None
        
            list_data = list_response.json()
            items = list_data.get('result', {}).get('items', [])
            print(f"✅ Получено товаров: {len(items)}")
        
            if not items:
                print("❌ Нет товаров в ответе")
                return None
            
            # Получаем product_id для запроса описаний
            product_ids = [item['product_id'] for item in items if 'product_id' in item]
            print(f"🔍 Получено {len(product_ids)} product_id")
        
            # 2. Получаем описания товаров через v1/product/info/description
            print("🔍 Получаем описания товаров через v1/product/info/description...")
            descriptions_data = self._get_products_descriptions(product_ids)
        
            # 3. Получаем цены через v5/product/info/prices
            print("🔍 Получаем цены через v5/product/info/prices...")
            prices_data = self._get_products_prices_v5(product_ids)
        
            # 4. Получаем остатки через v2/product/info/list
            print("🔍 Получаем остатки через v2/product/info/list...")
            stocks_data = self._get_products_stocks_simple(product_ids)
        
            # Формируем итоговый список товаров
            products = []
            for item in items:
                try:
                    product_id = item.get('product_id')
                    offer_id = item.get('offer_id')
                
                    if not product_id:
                        continue
                
                    # Получаем описание из v1/product/info/description
                    description_info = descriptions_data.get(product_id, {})
                    name = description_info.get('name', offer_id or f"Товар {product_id}")
                    description = description_info.get('description', '')
                
                    # Если нет описания из v1, используем базовое
                    if not description:
                        description = f"Артикул: {offer_id}" if offer_id else f"ID: {product_id}"
                
                    # Получаем цену из v5
                    price = self._extract_price_from_v5(prices_data.get(product_id, {}))
                    if price == 0:
                        print(f"⚠️ Пропускаем товар без цены: {name}")
                        continue
                
                    # Получаем количество
                    quantity = self._extract_quantity(stocks_data.get(product_id, {}))
                    print(f"📦 Итоговое количество для {name}: {quantity}")
                
                    # Очищаем описание от HTML тегов и обрезаем
                    description = self._clean_description(description)
                    if len(description) > 150:
                        description = description[:150] + "..."
                
                    products.append({
                        'product_id': product_id,
                        'offer_id': offer_id,
                        'name': name,
                        'price': price,
                        'description': description,
                        'quantity': quantity
                    })
                    
                    print(f"📦 {name} - {price} ₽ (Остаток: {quantity})")
                
                except Exception as e:
                    print(f"❌ Ошибка обработки товара: {e}")
                    continue
        
            print(f"✅ Обработано {len(products)} товаров с реальными ценами")
            return products
            
        except Exception as e:
            print(f"❌ Ошибка запроса к Ozon API: {e}")
            return None
    
    def _get_products_descriptions(self, product_ids):
        """Получает описания товаров через v1/product/info/description"""
        descriptions_data = {}
        try:
            # Обрабатываем каждый product_id отдельно
            for product_id in product_ids:
                description_response = requests.post(
                    "https://api-seller.ozon.ru/v1/product/info/description",
                    headers=self.headers,
                    json={"product_id": product_id},
                    timeout=10
                )
                
                if description_response.status_code == 200:
                    description_result = description_response.json().get('result', {})
                    if description_result:
                        descriptions_data[product_id] = {
                            'name': description_result.get('name', ''),
                            'description': description_result.get('description', '')
                        }
                        print(f"📝 Получено описание для товара {product_id}")
                else:
                    print(f"⚠️ Ошибка получения описания для {product_id}: {description_response.status_code}")
            
            print(f"📝 Всего получено описаний: {len(descriptions_data)}")
            return descriptions_data
            
        except Exception as e:
            print(f"❌ Ошибка получения описаний: {e}")
            return {}
    
    def _get_products_prices_v5(self, product_ids):
        """Получает цены товаров через v5/product/info/prices"""
        prices_data = {}
        try:
            # Разбиваем на группы по 50 product_id
            for i in range(0, len(product_ids), 50):
                batch_ids = product_ids[i:i+50]
            
                prices_response = requests.post(
                    "https://api-seller.ozon.ru/v5/product/info/prices",
                    headers=self.headers,
                    json={
                        "filter": {
                            "product_id": batch_ids,
                            "visibility": "ALL"
                        },
                        "last_id": "",
                        "limit": 1000
                    },
                    timeout=10
                )
            
                if prices_response.status_code == 200:
                    prices_result = prices_response.json()
                    # В v5 items находится в корне ответа
                    price_items = prices_result.get('items', [])
                    print(f"💰 Получены цены для {len(price_items)} товаров")
                
                    for price_item in price_items:
                        product_id = price_item.get('product_id')
                        prices_data[product_id] = price_item
                        
                else:
                    print(f"❌ Ошибка получения цен v5: {prices_response.status_code}")
                    print(f"Текст ошибки: {prices_response.text}")
        
            return prices_data
        
        except Exception as e:
            print(f"❌ Ошибка получения цен v5: {e}")
            return {}
    
    def _extract_price_from_v5(self, price_item):
        """Извлекает цену из структуры Ozon v5"""
        if not price_item:
            return 0
    
        try:
            # Прямой доступ к цене по структуре из вашего примера
            price_info = price_item.get('price', {})
        
            # Основная цена
            main_price = price_info.get('price')
            if main_price:
                price_int = int(float(main_price))
                if price_int > 0:
                    print(f"✅ Найдена цена: {price_int} ₽")
                    return price_int
        
            # Старая цена как запасной вариант
            old_price = price_info.get('old_price')
            if old_price:
                price_int = int(float(old_price))
                if price_int > 0:
                    print(f"✅ Найдена старая цена: {price_int} ₽")
                    return price_int
        
            return 0
        
        except Exception as e:
            print(f"❌ Ошибка извлечения цены: {e}")
            return 0

    def _get_products_stocks_simple(self, product_ids):
        """Упрощенный метод получения остатков через v2/product/info/list"""
        stocks_data = {}
        try:
            # Разбиваем на группы по 50 product_id
            for i in range(0, len(product_ids), 50):
                batch_ids = product_ids[i:i+50]
            
                # Используем v2/product/info/list который возвращает основную информацию включая stock
                info_response = requests.post(
                    "https://api-seller.ozon.ru/v2/product/info/list",
                    headers=self.headers,
                    json={
                        "product_id": batch_ids
                    },
                    timeout=10
                )
            
                if info_response.status_code == 200:
                    info_result = info_response.json()
                    print(f"📦 Получен ответ от v2/product/info/list")
                
                    items = info_result.get('result', {}).get('items', [])
                    print(f"📦 Получена информация для {len(items)} товаров")
                
                    for item in items:
                        product_id = item.get('product_id')
                        if product_id:
                            # Получаем все возможные поля с остатками
                            stock = item.get('stock', 0)
                            fbo_stock = item.get('fbo_stock', 0)
                            fbs_stock = item.get('fbs_stock', 0)
                            
                            # Логируем все значения
                            print(f"📊 Товар {product_id}: stock={stock}, fbo_stock={fbo_stock}, fbs_stock={fbs_stock}")
                            
                            # Выбираем наибольшее доступное количество
                            available_stock = max(stock, fbo_stock, fbs_stock)
                            
                            stocks_data[product_id] = {
                                'stock': stock,
                                'fbo_stock': fbo_stock,
                                'fbs_stock': fbs_stock,
                                'available_stock': available_stock
                            }
                            
                            print(f"✅ Доступный остаток для {product_id}: {available_stock}")
                        
                else:
                    print(f"⚠️ Ошибка получения информации v2: {info_response.status_code}")
                    print(f"Текст ошибки: {info_response.text}")
        
            return stocks_data
        
        except Exception as e:
            print(f"❌ Ошибка получения простых остатков: {e}")
            return {}

    def _extract_quantity(self, stock_item):
        """Извлекает количество из структуры остатков"""
        try:
            if not stock_item:
                print("⚠️ Нет данных об остатках, используем значение по умолчанию: 10")
                return 10  # По умолчанию
        
            print(f"🔍 Анализируем структуру остатков: {stock_item}")
        
            # Способ 1: available_stock - наш расчетный показатель
            if 'available_stock' in stock_item:
                available_stock = stock_item['available_stock']
                if available_stock is not None:
                    try:
                        available_int = int(available_stock)
                        print(f"📊 available_stock: {available_int}")
                        if available_int >= 0:
                            print(f"✅ Количество из поля 'available_stock': {available_int}")
                            return available_int
                    except (ValueError, TypeError) as e:
                        print(f"⚠️ Ошибка преобразования available_stock: {e}")
        
            # Способ 2: stock
            if 'stock' in stock_item:
                stock = stock_item['stock']
                if stock is not None:
                    try:
                        stock_int = int(stock)
                        print(f"📊 stock: {stock_int}")
                        if stock_int >= 0:
                            print(f"✅ Количество из поля 'stock': {stock_int}")
                            return stock_int
                    except (ValueError, TypeError) as e:
                        print(f"⚠️ Ошибка преобразования stock: {e}")
        
            # Способ 3: fbo_stock
            if 'fbo_stock' in stock_item:
                fbo_stock = stock_item['fbo_stock']
                if fbo_stock is not None:
                    try:
                        fbo_int = int(fbo_stock)
                        print(f"📊 fbo_stock: {fbo_int}")
                        if fbo_int >= 0:
                            print(f"✅ Количество из поля 'fbo_stock': {fbo_int}")
                            return fbo_int
                    except (ValueError, TypeError) as e:
                        print(f"⚠️ Ошибка преобразования fbo_stock: {e}")
        
            # Способ 4: fbs_stock
            if 'fbs_stock' in stock_item:
                fbs_stock = stock_item['fbs_stock']
                if fbs_stock is not None:
                    try:
                        fbs_int = int(fbs_stock)
                        print(f"📊 fbs_stock: {fbs_int}")
                        if fbs_int >= 0:
                            print(f"✅ Количество из поля 'fbs_stock': {fbs_int}")
                            return fbs_int
                    except (ValueError, TypeError) as e:
                        print(f"⚠️ Ошибка преобразования fbs_stock: {e}")
        
            print("⚠️ Не удалось определить количество, используем значение по умолчанию: 10")
            return 10  # По умолчанию
        
        except Exception as e:
            print(f"❌ Ошибка извлечения количества: {e}")
            print(f"📋 Структура stock_item: {stock_item}")
            return 10
    
    def _clean_description(self, description):
        """Очищает описание от HTML тегов"""
        if not description:
            return ""
        
        # Удаляем основные HTML теги
        import re
        clean_text = re.sub(r'<br\s*/?>', '\n', description)  # Заменяем <br> на переносы
        clean_text = re.sub(r'<[^>]+>', '', clean_text)  # Удаляем все остальные теги
        clean_text = re.sub(r'\n\s*\n', '\n', clean_text)  # Удаляем лишние переносы
        clean_text = clean_text.strip()
        
        return clean_text


# Инициализация API
ozon_api = OzonSellerAPI()

async def load_real_products():
    """Загружает только реальные товары из Ozon API"""
    global products_cache
    
    print("🔄 Загрузка реальных товаров из Ozon...")
    
    # Проверяем наличие API ключей
    if not OZON_CLIENT_ID or not OZON_API_KEY:
        print("❌ API ключи не настроены!")
        products_cache = {}
        return {}
    
    # Получаем реальные товары с реальными ценами
    products_data = ozon_api.get_products_with_prices(limit=50)
    
    if not products_data:
        print("❌ Не удалось получить реальные товары через Ozon API")
        products_cache = {}
        return {}
    
    products = {}
    product_counter = 1
    
    # Обрабатываем только реальные товары
    for item in products_data:
        try:
            product_id = item.get('product_id', '')
            offer_id = item.get('offer_id', '')
            name = item.get('name', '')
            price = item.get('price', 0)
            description = item.get('description', '')
            quantity = item.get('quantity', 0)
            
            # Пропускаем товары без цены
            if price == 0:
                continue
            
            # Формируем описание
            if not description:
                description = f"Артикул: {offer_id}" if offer_id else f"ID: {product_id}"
            
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
            
            print(f"✅ Товар {product_counter}: {name} - {price} ₽ (Остаток: {quantity})")
            product_counter += 1
            
        except Exception as e:
            print(f"❌ Ошибка обработки товара: {e}")
            continue
    
    print(f"🎯 Загружено {len(products)} реальных товаров с реальными ценами из Ozon")
    products_cache = products
    return products

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    user = update.effective_user
    
    welcome_text = f"""
👋 Привет, {user.first_name}!

Добро пожаловать в Ozon Client Bot! 🛍️

📊 Реальные товары из вашего Ozon магазина
📦 Доступно товаров: {len(products_cache)}

Здесь вы можете:
• 📦 Просматривать реальные товары
• 🛒 Добавлять товары в корзину
• 💰 Оформлять заказы
• 📱 Перейти в личный кабинет Ozon

Используйте кнопки ниже для навигации:
    """
    
    keyboard = [
        [InlineKeyboardButton("🛍️ Смотреть товары", callback_data="view_products")],
        [InlineKeyboardButton("🛒 Корзина", callback_data="view_cart"),
         InlineKeyboardButton("📦 Мои заказы", callback_data="view_orders")],
        [InlineKeyboardButton("🔄 Обновить товары", callback_data="refresh_products")],
        [InlineKeyboardButton("📱 Личный кабинет Ozon", url="https://www.ozon.ru/my/orderlist/")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(welcome_text, reply_markup=reply_markup)

async def refresh_products(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /refresh"""
    await update.message.reply_text("🔄 Обновляем список реальных товаров...")
    products_count_before = len(products_cache)
    await load_real_products()
    products_count_after = len(products_cache)
    
    if products_count_after > 0:
        await update.message.reply_text(
            f"✅ Реальные товары обновлены!\n"
            f"📦 Доступно товаров: {products_count_after}"
        )
    else:
        await update.message.reply_text(
            "❌ Не удалось загрузить реальные товары.\n"
            "Проверьте настройки API ключей Ozon."
        )

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
    elif callback_data == "checkout":
        await checkout(query, context)
    elif callback_data == "clear_cart":
        await clear_cart(query, context)    
    elif callback_data.startswith("product_"):
        await handle_product_action(query, context, callback_data)
    elif callback_data.startswith("cart_"):
        await handle_cart_action(query, context, callback_data)



async def show_products(query, context):
    """Показывает список реальных товаров"""
    if not products_cache:
        await query.edit_message_text(
            "❌ Нет доступных товаров.\n"
            "Используйте /refresh для загрузки товаров из Ozon."
        )
        return
    
    # Показываем первый товар
    await show_product_detail(query, context, 1)

async def show_product_detail(query, context, product_index):
    """Показывает детали реального товара"""
    product = products_cache.get(product_index)
    if not product:
        await query.edit_message_text("❌ Товар не найден")
        return
    
    product_text = f"""
📦 *{product['name']}*

💵 *Цена:* {product['price']} ₽
📝 *Описание:* {product['description']}
📦 *В наличии:* {product['quantity']} шт.
🔗 *Артикул:* {product['offer_id']}

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
    
    try:
        await query.edit_message_text(product_text, reply_markup=reply_markup, parse_mode='Markdown')
    except Exception as e:
        # Игнорируем ошибку "Message is not modified"
        if "Message is not modified" not in str(e):
            raise e

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
    # Инициализируем корзину в user_data
    if 'cart' not in context.user_data:
        context.user_data['cart'] = {}
    
    cart = context.user_data['cart']
    product = products_cache.get(product_index)
    
    if not product:
        await query.answer("❌ Товар не найден", show_alert=True)
        return
    
    if str(product_index) in cart:
        cart[str(product_index)] += 1
    else:
        cart[str(product_index)] = 1
    
    product_name = product['name']
    if len(product_name) > 100:
        product_name = product_name[:97] + "..."
    
    await query.answer(f"✅ {product_name} добавлен в корзину!", show_alert=True)

async def show_cart(query, context):
    """Показывает корзину пользователя"""
    # Получаем корзину из user_data
    cart = context.user_data.get('cart', {})
    
    if not cart:
        cart_text = "🛒 *Ваша корзина пуста*"
        
        keyboard = [
            [InlineKeyboardButton("🛍️ Начать покупки", callback_data="view_products")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(cart_text, reply_markup=reply_markup, parse_mode='Markdown')
        return
    
    total = 0
    cart_text = "🛒 *Ваша корзина:*\n\n"
    
    for product_index, quantity in cart.items():
        product = products_cache.get(int(product_index))
        if product:
            item_total = product['price'] * quantity
            total += item_total
            product_name = product['name']
            if len(product_name) > 50:
                product_name = product_name[:47] + "..."
            cart_text += f"• {product_name}\n  {quantity} × {product['price']} ₽ = {item_total} ₽\n"
    
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
    # Получаем заказы из user_data
    orders = context.user_data.get('orders', [])
    
    if not orders:
        orders_text = "📦 *У вас пока нет заказов*"
        
        keyboard = [
            [InlineKeyboardButton("🛍️ Начать покупки", callback_data="view_products")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(orders_text, reply_markup=reply_markup, parse_mode='Markdown')
        return
    
    orders_text = "📦 *История ваших заказов:*\n\n"
    
    for i, order in enumerate(orders, 1):
        orders_text += f"*Заказ #{i}:*\n"
        orders_text += f"💰 Сумма: {order['total']} ₽\n"
        orders_text += f"📅 Дата: {order['created_at']}\n"
        orders_text += f"📦 Товаров: {order['items_count']} шт.\n"
        orders_text += f"👤 Получатель: {order['customer_name']}\n"
        
        if order.get('ozon_posting_number'):
            orders_text += f"🔗 Номер в Ozon: {order['ozon_posting_number']}\n"
        
        orders_text += f"📊 Статус: {order.get('status', 'создан')}\n"
        orders_text += "━━━━━━━━━━━━━━━━━━━━\n\n"
    
    keyboard = [
        [InlineKeyboardButton("🛒 Корзина", callback_data="view_cart")],
        [InlineKeyboardButton("🛍️ К товарам", callback_data="view_products")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(orders_text, reply_markup=reply_markup, parse_mode='Markdown')



async def preload_products():
    """Предзагрузка товаров при запуске"""
    print("🔄 Предзагрузка реальных товаров...")
    await load_real_products()
    if products_cache:
        print(f"✅ Загружено {len(products_cache)} реальных товаров")
    else:
        print("❌ Не удалось загрузить реальные товары")

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
    
    # Добавляем обработчик текстовых сообщений для контактов
    from telegram.ext import MessageHandler, filters
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_contacts))
    
    # Предзагрузка реальных товаров
    print("🔄 Загрузка реальных товаров из Ozon...")
    
    # Запускаем предзагрузку асинхронно
    loop = asyncio.get_event_loop()
    loop.run_until_complete(preload_products())
    
    print("🛍️ Ozon Client Bot запущен!")
    application.run_polling()

if __name__ == '__main__':
    main()

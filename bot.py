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
current_product_index = {}  # Текущий индекс товара для каждого пользователя

class OzonSellerAPI:
    def __init__(self):
        self.headers = {
            "Client-Id": OZON_CLIENT_ID,
            "Api-Key": OZON_API_KEY,
            "Content-Type": "application/json"
        }
    
    def get_products_list(self, limit=50):
        """Получает реальные товары из Ozon магазина"""
        try:
            response = requests.post(
                "https://api-seller.ozon.ru/v3/product/list",
                headers=self.headers,
                json={
                    "filter": {"visibility": "ALL"},
                    "limit": limit
                },
                timeout=10
            )
            if response.status_code == 200:
                return response.json()
            else:
                print(f"❌ Ошибка получения товаров: {response.status_code}")
                return None
        except Exception as e:
            print(f"❌ Ошибка запроса товаров: {e}")
            return None

# Инициализация API
ozon_api = OzonSellerAPI()

async def load_real_products():
    """Загружает реальные товары из Ozon API"""
    global products_cache
    
    print("🔄 Загрузка товаров из Ozon...")
    
    products_data = ozon_api.get_products_list(limit=30)
    
    if not products_data or 'result' not in products_data:
        print("❌ Не удалось загрузить товары из Ozon")
        return get_demo_products()
    
    products = {}
    product_counter = 1
    
    for item in products_data['result']['items']:
        try:
            product_id = item['product_id']
            offer_id = item['offer_id']
            name = item.get('name', f'Товар {offer_id}')
            
            # Используем offer_id как ключ для уникальности
            product_key = product_counter
            
            products[product_key] = {
                'ozon_id': product_id,
                'offer_id': offer_id,
                'name': name,
                'price': 1999,  # Заглушка - в реальности нужно получать цену из API
                'image': "📦",  # Базовая иконка
                'description': f"Артикул: {offer_id}",
                'quantity': 10  # Заглушка
            }
            
            product_counter += 1
            
        except Exception as e:
            print(f"❌ Ошибка обработки товара: {e}")
            continue
    
    print(f"✅ Загружено {len(products)} товаров из Ozon")
    products_cache = products
    return products

def get_demo_products():
    """Демо-товары на случай если API не работает"""
    print("⚠️ Использую демо-товары")
    demo_products = {
        1: {"name": "Смартфон Xiaomi Redmi Note 12", "price": 19999, "image": "📱", "description": "Смартфон с отличной камерой", "quantity": 10},
        2: {"name": "Наушники Sony WH-CH720N", "price": 12999, "image": "🎧", "description": "Беспроводные наушники с шумоподавлением", "quantity": 15},
        3: {"name": "Футболка хлопковая", "price": 1499, "image": "👕", "description": "Мужская футболка из 100% хлопка", "quantity": 25},
        4: {"name": "Кроссовки Nike Revolution 7", "price": 8999, "image": "👟", "description": "Спортивные кроссовки для бега", "quantity": 8},
        5: {"name": "Часы Casio G-Shock", "price": 15999, "image": "⌚", "description": "Прочные спортивные часы", "quantity": 5},
        6: {"name": "Рюкзак городской", "price": 3999, "image": "🎒", "description": "Вместительный рюкзак для города", "quantity": 12},
    }
    products_cache.update(demo_products)
    return demo_products

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Приветствие и главное меню"""
    user = update.message.from_user
    
    # Загружаем товары при старте
    if not products_cache:
        await load_real_products()
    
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

async def view_products(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает список товаров"""
    query = update.callback_query
    if query:
        await query.answer()
    
    # Если товаров нет - загружаем
    if not products_cache:
        await load_real_products()
    
    user_id = query.from_user.id if query else update.message.from_user.id
    
    # Начинаем с первого товара
    current_product_index[user_id] = 0
    
    # Показываем первый товар
    await show_product(update, context, user_id)

async def show_product(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int = None):
    """Показывает текущий товар"""
    if not user_id:
        if update.callback_query:
            user_id = update.callback_query.from_user.id
        else:
            user_id = update.message.from_user.id
    
    if user_id not in current_product_index:
        current_product_index[user_id] = 0
    
    product_ids = list(products_cache.keys())
    
    if not product_ids:
        await update.callback_query.edit_message_text(
            "❌ Товары временно недоступны\nПопробуйте позже или напишите в поддержку.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📞 Поддержка", callback_data="support")]])
        )
        return
    
    current_index = current_product_index[user_id]
    product_id = product_ids[current_index]
    product = products_cache[product_id]
    
    # Кнопки навигации
    keyboard = []
    
    if len(product_ids) > 1:
        nav_buttons = []
        
        # Кнопка "Назад" если не первый товар
        if current_index > 0:
            nav_buttons.append(InlineKeyboardButton("⬅️ Назад", callback_data="product_prev"))
        
        # Номер текущего товара
        nav_buttons.append(InlineKeyboardButton(f"{current_index + 1}/{len(product_ids)}", callback_data="none"))
        
        # Кнопка "Вперед" если не последний товар
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
    
    message_text = (
        f"{product['image']} *{product['name']}*\n\n"
        f"💵 *Цена:* {product['price']} ₽\n"
        f"📝 *Описание:* {product.get('description', 'Описание товара')}\n"
        f"📦 *В наличии:* {product.get('quantity', 1)} шт.\n\n"
        f"✅ *Готов к заказу*\n"
        f"🚚 *Доставка:* Ozon FBS (1-3 дня)\n\n"
        f"🛒 Нажмите 'Добавить в корзину' чтобы заказать!"
    )
    
    if update.callback_query:
        await update.callback_query.edit_message_text(message_text, reply_markup=reply_markup, parse_mode='Markdown')
    else:
        await update.message.reply_text(message_text, reply_markup=reply_markup, parse_mode='Markdown')

async def handle_product_navigation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка навигации по товарам"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    action = query.data
    
    product_ids = list(products_cache.keys())
    
    if action == "product_prev" and current_product_index[user_id] > 0:
        current_product_index[user_id] -= 1
    elif action == "product_next" and current_product_index[user_id] < len(product_ids) - 1:
        current_product_index[user_id] += 1
    
    await show_product(update, context, user_id)

async def add_to_cart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Добавляет товар в корзину"""
    query = update.callback_query
    await query.answer()
    
    product_id = int(query.data.split("_")[1])
    user_id = query.from_user.id
    
    # Инициализируем корзину пользователя
    if user_id not in user_carts:
        user_carts[user_id] = {}
    
    # Добавляем товар в корзину
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
    
    for order in user_orders[user_id][-5:]:  # Показываем последние 5 заказов
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
    
    print("🛍️ Ozon Client Bot запущен!")
    application.run_polling()

if __name__ == '__main__':
    main()

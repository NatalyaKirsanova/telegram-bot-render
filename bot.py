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
    
    def get_products_with_prices(self, limit=50):
        """Получает реальные товары с реальными ценами из Ozon"""
        print("🔄 Получение реальных товаров из Ozon API...")
        
        try:
            # 1. Получаем список товаров через v2/product/list
            print("🔍 Получаем список товаров через v2/product/list...")
            list_response = requests.post(
                "https://api-seller.ozon.ru/v2/product/list",
                headers=self.headers,
                json={
                    "filter": {"visibility": "ALL"},
                    "limit": limit
                },
                timeout=10
            )
            
            if list_response.status_code != 200:
                print(f"❌ Ошибка v2/product/list: {list_response.status_code}")
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
            
            # 3. Получаем цены через v4/product/info/prices
            print("🔍 Получаем цены через v4/product/info/prices...")
            prices_data = self._get_products_prices(product_ids)
            
            # 4. Получаем остатки через v3/product/info/stocks
            print("🔍 Получаем остатки через v3/product/info/stocks...")
            stocks_data = self._get_products_stocks(product_ids)
            
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
                    
                    # Получаем цену
                    price = self._extract_price(prices_data.get(product_id, {}))
                    if price == 0:
                        print(f"⚠️ Пропускаем товар без цены: {name}")
                        continue
                    
                    # Получаем количество
                    quantity = self._extract_quantity(stocks_data.get(product_id, {}))
                    
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
                    json={"product_id": product_id},  # Отправляем один product_id
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
    
    def _get_products_prices(self, product_ids):
        """Получает цены товаров через v4/product/info/prices"""
        prices_data = {}
        try:
            # Разбиваем на группы по 50 product_id
            for i in range(0, len(product_ids), 50):
                batch_ids = product_ids[i:i+50]
                
                prices_response = requests.post(
                    "https://api-seller.ozon.ru/v4/product/info/prices",
                    headers=self.headers,
                    json={
                        "filter": {
                            "product_id": batch_ids,
                            "visibility": "ALL"
                        },
                        "limit": 1000
                    },
                    timeout=10
                )
                
                if prices_response.status_code == 200:
                    prices_result = prices_response.json().get('result', {})
                    price_items = prices_result.get('items', [])
                    print(f"💰 Получены цены для {len(price_items)} товаров")
                    
                    for price_item in price_items:
                        product_id = price_item.get('product_id')
                        prices_data[product_id] = price_item
                else:
                    print(f"⚠️ Ошибка получения цен: {prices_response.status_code}")
            
            return prices_data
            
        except Exception as e:
            print(f"❌ Ошибка получения цен: {e}")
            return {}
    
    def _get_products_stocks(self, product_ids):
        """Получает остатки товаров через v3/product/info/stocks"""
        stocks_data = {}
        try:
            # Разбиваем на группы по 50 product_id
            for i in range(0, len(product_ids), 50):
                batch_ids = product_ids[i:i+50]
                
                stocks_response = requests.post(
                    "https://api-seller.ozon.ru/v3/product/info/stocks",
                    headers=self.headers,
                    json={
                        "filter": {
                            "product_id": batch_ids,
                            "visibility": "ALL"
                        },
                        "limit": 1000
                    },
                    timeout=10
                )
                
                if stocks_response.status_code == 200:
                    stocks_result = stocks_response.json().get('result', {})
                    stock_items = stocks_result.get('items', [])
                    print(f"📦 Получены остатки для {len(stock_items)} товаров")
                    
                    for stock_item in stock_items:
                        product_id = stock_item.get('product_id')
                        stocks_data[product_id] = stock_item
                else:
                    print(f"⚠️ Ошибка получения остатков: {stocks_response.status_code}")
            
            return stocks_data
            
        except Exception as e:
            print(f"❌ Ошибка получения остатков: {e}")
            return {}
    
    def _extract_price(self, price_item):
        """Извлекает цену из структуры цены"""
        if not price_item:
            return 0
        
        # Основная цена
        price_info = price_item.get('price', '')
        if isinstance(price_info, dict):
            # Если цена вложенная структура
            for key in ['price', 'value', 'amount']:
                price = price_info.get(key)
                if price and str(price).replace('.', '').isdigit():
                    price_value = int(float(price))
                    if price_value > 0:
                        return price_value
        elif price_info and str(price_info).replace('.', '').isdigit():
            # Если цена прямое значение
            price_value = int(float(price_info))
            if price_value > 0:
                return price_value
        
        # Альтернативные поля с ценой
        alternative_prices = [
            price_item.get('old_price'),
            price_item.get('marketing_price'),
            price_item.get('min_price'),
        ]
        
        for price in alternative_prices:
            if price and str(price).replace('.', '').isdigit():
                price_value = int(float(price))
                if price_value > 0:
                    return price_value
        
        return 0
    
    def _extract_quantity(self, stock_item):
        """Извлекает количество из структуры остатков"""
        try:
            if not stock_item:
                return 10  # По умолчанию
            
            # Пробуем разные поля с количеством
            stocks = stock_item.get('stocks', [])
            if stocks:
                total = 0
                for stock in stocks:
                    present = stock.get('present', 0)
                    reserved = stock.get('reserved', 0)
                    total += max(0, present - reserved)
                if total > 0:
                    return total
            
            # Прямые поля
            quantity_fields = [
                stock_item.get('stock'),
                stock_item.get('fbo_stock'),
                stock_item.get('fbs_stock'),
            ]
            
            for quantity in quantity_fields:
                if quantity and str(quantity).isdigit():
                    quantity_value = int(quantity)
                    if quantity_value > 0:
                        return quantity_value
            
            return 10  # По умолчанию
            
        except Exception as e:
            print(f"⚠️ Ошибка извлечения количества: {e}")
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

# ... остальные функции бота остаются без изменений ...

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

# ... остальные функции handle_callback, show_products и т.д. остаются без изменений ...

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
    
    # Предзагрузка реальных товаров
    print("🔄 Загрузка реальных товаров из Ozon...")
    
    # Запускаем предзагрузку асинхронно
    loop = asyncio.get_event_loop()
    loop.run_until_complete(preload_products())
    
    print("🛍️ Ozon Client Bot запущен!")
    application.run_polling()

if __name__ == '__main__':
    main()

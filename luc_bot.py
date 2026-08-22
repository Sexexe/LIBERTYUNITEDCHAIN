import asyncio
import sqlite3
from datetime import datetime
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, FSInputFile

# ===== НАСТРОЙКИ =====
BOT_TOKEN = "ВСТАВЬ_СЮДА_ТОКЕН"
ADMIN_ID = 123456789

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# ===== ПЕРЕВОДЫ =====
TRANSLATIONS = {
    'en': {
        'welcome': 'Welcome to LIBERTY UNITED CHAIN',
        'choose_role': 'Choose your role:',
        'provider': '💻 I have GPU (Earn)',
        'buyer': ' I need GPU (Buy)',
        'connect': '🔗 CONNECT',
        'disconnect': '⏸ DISCONNECT',
        'earning': '💰 Earning: {} Stars/hour',
        'total_earned': '📊 Total earned: {} Stars',
        'connected': '✅ Connected! You are earning.',
        'disconnected': ' Disconnected. Earning paused.',
        'buy_compute': '🛒 BUY COMPUTE',
        'enter_hours': 'How many hours do you need?',
        'confirm_buy': '✅ Buy {} hours for {} Stars?',
        'yes': '✅ YES',
        'no': ' NO',
        'order_paid': '✅ Order paid! GPU is working.',
        'balance': '💰 Balance: {} Stars',
        'back': '← Back',
        'status_online': '🟢 Online',
        'status_offline': '⚫ Offline',
    },
    'ru': {
        'welcome': 'Добро пожаловать в LIBERTY UNITED CHAIN',
        'choose_role': 'Выберите роль:',
        'provider': '💻 У меня есть GPU (Заработок)',
        'buyer': '🚀 Мне нужен GPU (Купить)',
        'connect': '🔗 ПОДКЛЮЧИТЬ',
        'disconnect': '⏸ ОТКЛЮЧИТЬ',
        'earning': '💰 Заработок: {} Stars/час',
        'total_earned': '📊 Всего заработано: {} Stars',
        'connected': '✅ Подключено! Вы зарабатываете.',
        'disconnected': '⏸ Отключено. Заработок остановлен.',
        'buy_compute': '🛒 КУПИТЬ МОЩНОСТИ',
        'enter_hours': 'Сколько часов нужно?',
        'confirm_buy': '✅ Купить {} часов за {} Stars?',
        'yes': '✅ ДА',
        'no': '❌ НЕТ',
        'order_paid': '✅ Оплачено! GPU работает.',
        'balance': '💰 Баланс: {} Stars',
        'back': '← Назад',
        'status_online': '🟢 Онлайн',
        'status_offline': '⚫ Оффлайн',
    }
}

def get_lang(user):
    """Определяем язык пользователя"""
    if user.language_code and user.language_code.startswith('ru'):
        return 'ru'
    return 'en'

def t(key, user):
    """Получить перевод"""
    lang = get_lang(user)
    return TRANSLATIONS[lang][key]

# ===== БАЗА ДАННЫХ =====
def init_db():
    conn = sqlite3.connect('luc.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (user_id INTEGER PRIMARY KEY, username TEXT, role TEXT DEFAULT 'buyer',
                  balance INTEGER DEFAULT 0, is_connected INTEGER DEFAULT 0,
                  hourly_rate INTEGER DEFAULT 50, total_earned INTEGER DEFAULT 0,
                  connected_since TIMESTAMP)''')
    c.execute('''CREATE TABLE IF NOT EXISTS orders
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, buyer_id INTEGER, hours INTEGER,
                  total_cost INTEGER, status TEXT DEFAULT 'pending',
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    conn.commit()
    conn.close()

def get_user(user_id, username):
    conn = sqlite3.connect('luc.db')
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    user = c.fetchone()
    if not user:
        c.execute("INSERT INTO users (user_id, username) VALUES (?, ?)", (user_id, username))
        conn.commit()
        c.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        user = c.fetchone()
    conn.close()
    return user

def update_user(user_id, **kwargs):
    conn = sqlite3.connect('luc.db')
    c = conn.cursor()
    for key, value in kwargs.items():
        c.execute(f"UPDATE users SET {key} = ? WHERE user_id = ?", (value, user_id))
    conn.commit()
    conn.close()

# ===== ГЛАВНОЕ МЕНЮ =====
async def send_logo(message):
    """Отправляем логотип"""
    try:
        photo = FSInputFile('luc.png')
        await message.answer_photo(photo=photo)
    except:
        pass

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    user = get_user(message.from_user.id, message.from_user.username)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t('provider', message.from_user), callback_data="role_provider")],
        [InlineKeyboardButton(text=t('buyer', message.from_user), callback_data="role_buyer")]
    ])
    
    await send_logo(message)
    await message.answer(
        f"{t('welcome', message.from_user)}\n\n{t('choose_role', message.from_user)}",
        reply_markup=keyboard
    )

# ===== ВЫБОР РОЛИ =====
@dp.callback_query(F.data == "role_provider")
async def role_provider(callback: types.CallbackQuery):
    update_user(callback.from_user.id, role='provider')
    await show_provider_screen(callback)
    await callback.answer()

@dp.callback_query(F.data == "role_buyer")
async def role_buyer(callback: types.CallbackQuery):
    update_user(callback.from_user.id, role='buyer')
    await show_buyer_screen(callback)
    await callback.answer()

# ===== ЭКРАН ПОСТАВЩИКА =====
async def show_provider_screen(callback):
    user = get_user(callback.from_user.id, callback.from_user.username)
    is_connected = user[4]  # is_connected
    hourly_rate = user[5]   # hourly_rate
    total_earned = user[6]  # total_earned
    
    # Считаем сколько заработано пока подключен
    current_session = 0
    if is_connected and user[7]:  # connected_since
        try:
            since = datetime.fromisoformat(user[7])
            hours = (datetime.now() - since).total_seconds() / 3600
            current_session = int(hours * hourly_rate)
        except:
            pass
    
    total_with_session = total_earned + current_session
    
    if is_connected:
        btn_text = t('disconnect', callback.from_user)
        btn_data = "disconnect"
        status = t('status_online', callback.from_user)
    else:
        btn_text = t('connect', callback.from_user)
        btn_data = "connect"
        status = t('status_offline', callback.from_user)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=btn_text, callback_data=btn_data)],
        [InlineKeyboardButton(text=t('back', callback.from_user), callback_data="back_to_menu")]
    ])
    
    text = (
        f"{status}\n\n"
        f"{t('earning', callback.from_user).format(hourly_rate)}\n"
        f"{t('total_earned', callback.from_user).format(total_with_session)}"
    )
    
    await callback.message.edit_text(text, reply_markup=keyboard)

@dp.callback_query(F.data == "connect")
async def connect_node(callback: types.CallbackQuery):
    update_user(
        callback.from_user.id,
        is_connected=1,
        connected_since=datetime.now().isoformat()
    )
    await callback.answer(t('connected', callback.from_user), show_alert=True)
    await show_provider_screen(callback)

@dp.callback_query(F.data == "disconnect")
async def disconnect_node(callback: types.CallbackQuery):
    user = get_user(callback.from_user.id, callback.from_user.username)
    
    # Добавляем заработанное за сессию
    current_session = 0
    if user[7]:  # connected_since
        try:
            since = datetime.fromisoformat(user[7])
            hours = (datetime.now() - since).total_seconds() / 3600
            current_session = int(hours * user[5])  # hourly_rate
        except:
            pass
    
    new_total = user[6] + current_session  # total_earned + current_session
    new_balance = user[3] + current_session  # balance + current_session
    
    update_user(
        callback.from_user.id,
        is_connected=0,
        total_earned=new_total,
        balance=new_balance,
        connected_since=None
    )
    
    await callback.answer(t('disconnected', callback.from_user), show_alert=True)
    await show_provider_screen(callback)

# ===== ЭКРАН ПОКУПАТЕЛЯ =====
async def show_buyer_screen(callback):
    user = get_user(callback.from_user.id, callback.from_user.username)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t('buy_compute', callback.from_user), callback_data="buy_compute")],
        [InlineKeyboardButton(text=t('back', callback.from_user), callback_data="back_to_menu")]
    ])
    
    text = t('balance', callback.from_user).format(user[3])
    
    await callback.message.edit_text(text, reply_markup=keyboard)

@dp.callback_query(F.data == "buy_compute")
async def buy_compute(callback: types.CallbackQuery):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="1 hour", callback_data="hours_1")],
        [InlineKeyboardButton(text="5 hours", callback_data="hours_5")],
        [InlineKeyboardButton(text="10 hours", callback_data="hours_10")],
        [InlineKeyboardButton(text=t('back', callback.from_user), callback_data="back_to_buyer")]
    ])
    
    await callback.message.edit_text(
        t('enter_hours', callback.from_user),
        reply_markup=keyboard
    )

@dp.callback_query(F.data.startswith("hours_"))
async def select_hours(callback: types.CallbackQuery):
    hours = int(callback.data.split("_")[1])
    cost = hours * 50  # 50 Stars per hour
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t('yes', callback.from_user), callback_data=f"confirm_{hours}_{cost}")],
        [InlineKeyboardButton(text=t('no', callback.from_user), callback_data="back_to_buyer")]
    ])
    
    await callback.message.edit_text(
        t('confirm_buy', callback.from_user).format(hours, cost),
        reply_markup=keyboard
    )

@dp.callback_query(F.data.startswith("confirm_"))
async def confirm_buy(callback: types.CallbackQuery):
    parts = callback.data.split("_")
    hours = int(parts[1])
    cost = int(parts[2])
    
    user = get_user(callback.from_user.id, callback.from_user.username)
    
    if user[3] < cost:  # balance < cost
        await callback.answer("❌ Not enough Stars!", show_alert=True)
        return
    
    # Создаем заказ
    conn = sqlite3.connect('luc.db')
    c = conn.cursor()
    c.execute("INSERT INTO orders (buyer_id, hours, total_cost, status) VALUES (?, ?, ?, 'paid')",
              (callback.from_user.id, hours, cost))
    c.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?",
              (cost, callback.from_user.id))
    conn.commit()
    conn.close()
    
    await callback.answer(t('order_paid', callback.from_user), show_alert=True)
    await show_buyer_screen(callback)

# ===== НАЗАД =====
@dp.callback_query(F.data == "back_to_menu")
async def back_to_menu(callback: types.CallbackQuery):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t('provider', callback.from_user), callback_data="role_provider")],
        [InlineKeyboardButton(text=t('buyer', callback.from_user), callback_data="role_buyer")]
    ])
    
    await callback.message.edit_text(
        f"{t('welcome', callback.from_user)}\n\n{t('choose_role', callback.from_user)}",
        reply_markup=keyboard
    )

@dp.callback_query(F.data == "back_to_buyer")
async def back_to_buyer(callback: types.CallbackQuery):
    await show_buyer_screen(callback)

# ===== БАЛАНС =====
@dp.message(Command("balance"))
async def cmd_balance(message: types.Message):
    user = get_user(message.from_user.id, message.from_user.username)
    await message.answer(t('balance', message.from_user).format(user[3]))

# ===== ЗАПУСК =====
async def main():
    init_db()
    print(" LIBERTY UNITED CHAIN Bot started!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
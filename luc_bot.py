import asyncio
import logging
import sqlite3
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from tonconnect import TonConnect  # Для работы с TON

# ===== НАСТРОЙКИ =====
BOT_TOKEN = "ТВОЙ_ТОКЕН"
ADMIN_ID = 123456789
MIN_WITHDRAW = 1.0  # Минимум для авто-вывода (TON)
HOURLY_RATE = 0.05  # 0.05 TON/час (~$0.1)
COMMISSION = 0.15   # 15% комиссия платформы

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
logging.basicConfig(level=logging.INFO)

# ===== TON CONNECT =====
ton = TonConnect('https://toncenter.com/v2/jsonRPC')

# ===== СОСТОЯНИЯ =====
class WalletState(StatesGroup):
    waiting_for_address = State()

class OrderState(StatesGroup):
    waiting_for_hours = State()

# ===== БАЗА ДАННЫХ =====
def init_db():
    conn = sqlite3.connect('liberty_v2.db')
    c = conn.cursor()
    
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (user_id INTEGER PRIMARY KEY, username TEXT, role TEXT DEFAULT 'buyer',
                  ton_address TEXT, balance REAL DEFAULT 0, is_connected INTEGER DEFAULT 0,
                  hourly_rate REAL DEFAULT 0.05, total_earned REAL DEFAULT 0,
                  connected_since TIMESTAMP, last_withdraw TIMESTAMP,
                  auto_withdraw INTEGER DEFAULT 1)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS nodes
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, owner_id INTEGER, name TEXT,
                  specs TEXT, status TEXT DEFAULT 'offline', gpu_model TEXT,
                  hourly_rate REAL, registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS orders
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, buyer_id INTEGER, node_id INTEGER,
                  task_description TEXT, hours INTEGER, total_cost REAL,
                  status TEXT DEFAULT 'pending', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS transactions
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, amount REAL,
                  type TEXT, tx_hash TEXT, description TEXT, 
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS withdrawals
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, amount REAL,
                  ton_address TEXT, tx_hash TEXT, status TEXT DEFAULT 'pending',
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    
    conn.commit()
    conn.close()

def get_user(user_id, username):
    conn = sqlite3.connect('liberty_v2.db')
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
    conn = sqlite3.connect('liberty_v2.db')
    c = conn.cursor()
    for key, value in kwargs.items():
        c.execute(f"UPDATE users SET {key} = ? WHERE user_id = ?", (value, user_id))
    conn.commit()
    conn.close()

# ===== ПЕРЕВОДЫ =====
def t(key, user):
    translations = {
        'en': {
            'welcome': ' LIBERTY UNITED CHAIN',
            'subtitle': 'Connected Earnings on TON',
            'choose_role': 'Choose your role:',
            'provider': '💻 I have GPU (Earn TON)',
            'buyer': '🚀 I need GPU (Buy)',
            'wallet': '💰 Wallet: {}',
            'connect_wallet': ' Connect TON Wallet',
            'balance': '💵 Balance: {} TON',
            'connect': '🔗 CONNECT',
            'disconnect': '⏸ DISCONNECT',
            'earning': '💰 Earning: {} TON/hour',
            'total_earned': '📊 Total earned: {} TON',
            'connected': '✅ Connected! You are earning.',
            'disconnected': '⏸ Disconnected. Earning paused.',
            'auto_withdraw': '🔄 Auto-withdraw: {}',
            'enabled': 'ON',
            'disabled': 'OFF',
            'buy_compute': '🛒 BUY COMPUTE',
            'enter_hours': 'How many hours do you need?',
            'confirm_buy': '✅ Buy {} hours for {} TON?',
            'yes': '✅ YES',
            'no': ' NO',
            'order_paid': '✅ Order paid! GPU is working.',
            'back': '← Back',
            'status_online': '🟢 Online',
            'status_offline': '⚫ Offline',
            'withdraw_success': '✅ Withdrawn {} TON to {}',
            'min_withdraw': ' Minimum withdraw: {} TON',
        },
        'ru': {
            'welcome': '🔗 LIBERTY UNITED CHAIN',
            'subtitle': 'Заработок на TON',
            'choose_role': 'Выберите роль:',
            'provider': '💻 У меня есть GPU (Заработок)',
            'buyer': '🚀 Мне нужен GPU (Купить)',
            'wallet': '💰 Кошелек: {}',
            'connect_wallet': '🔐 Подключить TON Wallet',
            'balance': '💵 Баланс: {} TON',
            'connect': ' ПОДКЛЮЧИТЬ',
            'disconnect': '⏸ ОТКЛЮЧИТЬ',
            'earning': '💰 Заработок: {} TON/час',
            'total_earned': '📊 Всего заработано: {} TON',
            'connected': '✅ Подключено! Вы зарабатываете.',
            'disconnected': '⏸ Отключено. Заработок остановлен.',
            'auto_withdraw': '🔄 Авто-вывод: {}',
            'enabled': 'ВКЛ',
            'disabled': 'ВЫКЛ',
            'buy_compute': ' КУПИТЬ МОЩНОСТИ',
            'enter_hours': 'Сколько часов нужно?',
            'confirm_buy': '✅ Купить {} часов за {} TON?',
            'yes': '✅ ДА',
            'no': '❌ НЕТ',
            'order_paid': '✅ Оплачено! GPU работает.',
            'back': '← Назад',
            'status_online': '🟢 Онлайн',
            'status_offline': '⚫ Оффлайн',
            'withdraw_success': '✅ Выведено {} TON на {}',
            'min_withdraw': '❌ Минимум для вывода: {} TON',
        }
    }
    lang = 'ru' if user.language_code and user.language_code.startswith('ru') else 'en'
    return translations[lang][key]

# ===== КЛАВИАТУРЫ =====
def main_keyboard(user, role=None):
    if role == 'provider':
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=t('connect', user), callback_data="connect"),
             InlineKeyboardButton(text=t('disconnect', user), callback_data="disconnect")],
            [InlineKeyboardButton(text=t('auto_withdraw', user).format(
                t('enabled', user) if get_user(user.id, user.username)[10] else t('disabled', user)
            ), callback_data="toggle_withdraw")],
            [InlineKeyboardButton(text=t('back', user), callback_data="back_to_menu")]
        ])
    else:
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=t('buy_compute', user), callback_data="buy_compute")],
            [InlineKeyboardButton(text=t('back', user), callback_data="back_to_menu")]
        ])

# ===== КОМАНДЫ =====
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    user = get_user(message.from_user.id, message.from_user.username)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t('provider', message.from_user), callback_data="role_provider")],
        [InlineKeyboardButton(text=t('buyer', message.from_user), callback_data="role_buyer")],
        [InlineKeyboardButton(text=t('connect_wallet', message.from_user), callback_data="connect_wallet")]
    ])
    
    await message.answer(
        f"{t('welcome', message.from_user)}\n"
        f"<i>{t('subtitle', message.from_user)}</i>\n\n"
        f"{t('choose_role', message.from_user)}",
        reply_markup=keyboard,
        parse_mode="HTML"
    )

@dp.callback_query(F.data == "connect_wallet")
async def connect_wallet(callback: types.CallbackQuery):
    await callback.message.answer(
        " <b>Подключение TON Wallet</b>\n\n"
        "Отправьте адрес вашего TON кошелька:\n"
        "<i>(начинается с UQ или EQ)</i>",
        parse_mode="HTML"
    )
    await WalletState.waiting_for_address.set()

@dp.message(WalletState.waiting_for_address)
async def save_wallet(message: types.Message, state: FSMContext):
    address = message.text.strip()
    
    if not (address.startswith('UQ') or address.startswith('EQ')) or len(address) != 48:
        await message.answer("❌ Неверный формат адреса TON!")
        return
    
    update_user(message.from_user.id, ton_address=address)
    await state.clear()
    
    await message.answer(
        f"✅ <b>Кошелек подключен!</b>\n\n"
        f"Адрес: <code>{address}</code>\n"
        f"Авто-вывод при достижении {MIN_WITHDRAW} TON"
    )

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

async def show_provider_screen(callback):
    user = get_user(callback.from_user.id, callback.from_user.username)
    is_connected = user[6]
    hourly_rate = user[7]
    total_earned = user[8]
    auto_withdraw = user[10]
    
    current_session = 0
    if is_connected and user[9]:
        try:
            since = datetime.fromisoformat(user[9])
            hours = (datetime.now() - since).total_seconds() / 3600
            current_session = hours * hourly_rate
        except:
            pass
    
    total_with_session = total_earned + current_session
    
    keyboard = main_keyboard(callback.from_user, role='provider')
    
    text = (
        f"{t('status_online' if is_connected else 'status_offline', callback.from_user)}\n\n"
        f"{t('earning', callback.from_user).format(hourly_rate or HOURLY_RATE)}\n"
        f"{t('total_earned', callback.from_user).format(f'{total_with_session:.4f}')}\n"
        f"{t('balance', callback.from_user).format(f'{user[5]:.4f}')}\n\n"
        f"<i>Авто-вывод каждые 24ч при балансе > {MIN_WITHDRAW} TON</i>"
    )
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")

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
    
    current_session = 0
    if user[9]:
        try:
            since = datetime.fromisoformat(user[9])
            hours = (datetime.now() - since).total_seconds() / 3600
            current_session = hours * user[7]
        except:
            pass
    
    new_total = user[8] + current_session
    new_balance = user[5] + current_session
    
    update_user(
        callback.from_user.id,
        is_connected=0,
        total_earned=new_total,
        balance=new_balance,
        connected_since=None
    )
    
    await callback.answer(t('disconnected', callback.from_user), show_alert=True)
    await show_provider_screen(callback)

@dp.callback_query(F.data == "toggle_withdraw")
async def toggle_withdraw(callback: types.CallbackQuery):
    user = get_user(callback.from_user.id, callback.from_user.username)
    new_state = 0 if user[10] else 1
    update_user(callback.from_user.id, auto_withdraw=new_state)
    await show_provider_screen(callback)
    await callback.answer()

async def show_buyer_screen(callback):
    user = get_user(callback.from_user.id, callback.from_user.username)
    keyboard = main_keyboard(callback.from_user)
    
    text = (
        f"{t('balance', callback.from_user).format(f'{user[5]:.4f}')}\n"
        f"<i>1 TON ≈ $2-3</i>"
    )
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")

@dp.callback_query(F.data == "buy_compute")
async def buy_compute(callback: types.CallbackQuery):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="1 hour (0.05 TON)", callback_data="hours_1")],
        [InlineKeyboardButton(text="5 hours (0.25 TON)", callback_data="hours_5")],
        [InlineKeyboardButton(text="10 hours (0.5 TON)", callback_data="hours_10")],
        [InlineKeyboardButton(text=t('back', callback.from_user), callback_data="back_to_buyer")]
    ])
    
    await callback.message.edit_text(t('enter_hours', callback.from_user), reply_markup=keyboard)

@dp.callback_query(F.data.startswith("hours_"))
async def select_hours(callback: types.CallbackQuery):
    hours = int(callback.data.split("_")[1])
    cost = hours * 0.05  # 0.05 TON/hour
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t('yes', callback.from_user), callback_data=f"confirm_{hours}_{cost}")],
        [InlineKeyboardButton(text=t('no', callback.from_user), callback_data="back_to_buyer")]
    ])
    
    await callback.message.edit_text(
        t('confirm_buy', callback.from_user).format(hours, f'{cost:.2f}'),
        reply_markup=keyboard
    )

@dp.callback_query(F.data.startswith("confirm_"))
async def confirm_buy(callback: types.CallbackQuery):
    parts = callback.data.split("_")
    hours = int(parts[1])
    cost = float(parts[2])
    
    user = get_user(callback.from_user.id, callback.from_user.username)
    
    if user[5] < cost:
        await callback.answer("❌ Недостаточно TON!", show_alert=True)
        return
    
    conn = sqlite3.connect('liberty_v2.db')
    c = conn.cursor()
    c.execute("INSERT INTO orders (buyer_id, hours, total_cost, status) VALUES (?, ?, ?, 'paid')",
              (callback.from_user.id, hours, cost))
    c.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (cost, callback.from_user.id))
    conn.commit()
    conn.close()
    
    await callback.answer(t('order_paid', callback.from_user), show_alert=True)
    await show_buyer_screen(callback)

@dp.callback_query(F.data == "back_to_menu")
async def back_to_menu(callback: types.CallbackQuery):
    await cmd_start(callback.message)

@dp.callback_query(F.data == "back_to_buyer")
async def back_to_buyer(callback: types.CallbackQuery):
    await show_buyer_screen(callback)

# ===== АВТО-ВЫВОД =====
async def auto_withdraw():
    """Фоновая задача для авто-вывода"""
    while True:
        try:
            conn = sqlite3.connect('liberty_v2.db')
            c = conn.cursor()
            
            # Найти пользователей с балансом > MIN_WITHDRAW и включенным авто-выводом
            c.execute("""SELECT user_id, ton_address, balance, username 
                        FROM users 
                        WHERE balance >= ? AND auto_withdraw = 1 AND ton_address IS NOT NULL""",
                     (MIN_WITHDRAW,))
            
            users = c.fetchall()
            
            for user_id, address, balance, username in users:
                # Здесь должна быть реальная отправка TON
                # Пока просто имитация
                tx_hash = f"fake_tx_{datetime.now().timestamp()}"
                
                c.execute("""INSERT INTO withdrawals (user_id, amount, ton_address, tx_hash, status) 
                            VALUES (?, ?, ?, ?, 'completed')""",
                         (user_id, balance, address, tx_hash))
                
                c.execute("UPDATE users SET balance = 0, last_withdraw = ? WHERE user_id = ?",
                         (datetime.now().isoformat(), user_id))
                
                try:
                    await bot.send_message(
                        user_id,
                        f"✅ <b>Авто-вывод выполнен!</b>\n\n"
                        f"Выведено: {balance:.4f} TON\n"
                        f"На кошелек: <code>{address}</code>\n"
                        f"TX: <code>{tx_hash}</code>",
                        parse_mode="HTML"
                    )
                except:
                    pass
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logging.error(f"Auto-withdraw error: {e}")
        
        await asyncio.sleep(3600)  # Проверка каждый час

# ===== ЗАПУСК =====
async def main():
    init_db()
    
    # Запустить фоновую задачу авто-вывода
    asyncio.create_task(auto_withdraw())
    
    print("🔗 LIBERTY UNITED CHAIN v2.0 запущен!")
    print(f"💰 Оплата в TON | Авто-вывод: {MIN_WITHDRAW} TON")
    
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
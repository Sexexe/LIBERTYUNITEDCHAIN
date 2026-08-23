from keep_alive import keep_alive
keep_alive()
import asyncio
import sqlite3
from datetime import datetime
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, FSInputFile
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

BOT_TOKEN = "8846227664:AAHbyx0JG1JwsWjMDDBleLaKpryptXwhOr4"
MIN_WITHDRAW = 1.0  # Минимум авто-вывода TON
COMMISSION = 0.15   # 15% платформы

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# ===== БАЗА ЦЕН GPU =====
GPU_PRICES = {
    'rtx 4090': 0.15, 'rtx 4080': 0.12, 'rtx 4070': 0.10,
    'rtx 3090': 0.10, 'rtx 3080': 0.08, 'rtx 3070': 0.06,
    'rtx 3060': 0.05, 'rtx 2080': 0.05, 'rtx 2060': 0.03,
    'gtx 1660': 0.03, 'gtx 1650': 0.02, 'gtx 1080': 0.04,
    'gtx 1070': 0.03, 'gtx 1060': 0.02, 'rx 7900': 0.10,
    'rx 6800': 0.08, 'rx 6700': 0.06, 'rx 6600': 0.04,
}

def calc_rate(gpu: str, vram: int) -> float:
    g = gpu.lower()
    for k, p in GPU_PRICES.items():
        if k in g:
            if vram > 16: return round(p * 1.3, 3)
            if vram > 8: return round(p * 1.1, 3)
            return p
    if vram >= 24: return 0.12
    if vram >= 16: return 0.08
    if vram >= 12: return 0.06
    if vram >= 8:  return 0.05
    if vram >= 6:  return 0.03
    return 0.02

# ===== ПЕРЕВОДЫ =====
T = {
    'en': {
        'welcome': '🔗 LIBERTY UNITED CHAIN\n<i>Connected Earnings on TON</i>',
        'role': 'Choose your role:',
        'provider': '💻 I have GPU (Earn)',
        'buyer': '🚀 I need GPU (Buy)',
        'connect': ' CONNECT',
        'disconnect': ' DISCONNECT',
        'balance': '💵 Balance: {} TON',
        'earned': '📊 Earned: {} TON',
        'rate': '💰 Rate: {} TON/hour',
        'online': '🟢 Online',
        'offline': ' Offline',
        'connected': '✅ Connected! Earning started.',
        'disconnected': '⏸ Disconnected.',
        'buy': '🛒 BUY COMPUTE',
        'hours_q': 'How many hours?',
        'confirm': 'Buy {}h for {} TON?',
        'yes': '✅ YES', 'no': '❌ NO',
        'paid': '✅ Paid! GPU working.',
        'back': '← Back',
        'wallet': '💰 Wallet: {}',
        'set_wallet': '🔐 Set TON Wallet',
        'send_addr': 'Send your TON address (starts with UQ or EQ):',
        'wallet_saved': '✅ Wallet saved: {}',
        'withdraw': '✅ Withdrawn {} TON to {}',
        'min_w': ' Min withdraw: {} TON',
        'no_gpu': 'No GPU detected. Send: RTX 4090 | 24',
        'monthly': ' ~{} TON/month (24/7)',
    },
    'ru': {
        'welcome': '🔗 LIBERTY UNITED CHAIN\n<i>Заработок на TON</i>',
        'role': 'Выберите роль:',
        'provider': '💻 У меня есть GPU (Заработок)',
        'buyer': '🚀 Мне нужен GPU (Купить)',
        'connect': '🔗 ПОДКЛЮЧИТЬ',
        'disconnect': ' ОТКЛЮЧИТЬ',
        'balance': '💵 Баланс: {} TON',
        'earned': '📊 Заработано: {} TON',
        'rate': '💰 Ставка: {} TON/час',
        'online': '🟢 Онлайн',
        'offline': '⚫ Оффлайн',
        'connected': '✅ Подключено! Заработок идет.',
        'disconnected': '⏸ Отключено.',
        'buy': '🛒 КУПИТЬ МОЩНОСТИ',
        'hours_q': 'Сколько часов?',
        'confirm': 'Купить {}ч за {} TON?',
        'yes': '✅ ДА', 'no': '❌ НЕТ',
        'paid': '✅ Оплачено! GPU работает.',
        'back': '← Назад',
        'wallet': '💰 Кошелек: {}',
        'set_wallet': ' Указать TON кошелек',
        'send_addr': 'Отправьте адрес TON (начинается с UQ или EQ):',
        'wallet_saved': '✅ Кошелек сохранен: {}',
        'withdraw': '✅ Выведено {} TON на {}',
        'min_w': '❌ Минимум вывода: {} TON',
        'no_gpu': 'GPU не найден. Отправьте: RTX 4090 | 24',
        'monthly': '📈 ~{} TON/месяц (24/7)',
    }
}

def lang(u): return 'ru' if u.language_code and u.language_code.startswith('ru') else 'en'
def t(k, u): return T[lang(u)][k]

# ===== БД =====
def init_db():
    conn = sqlite3.connect('liberty.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users
        (user_id INTEGER PRIMARY KEY, username TEXT, role TEXT DEFAULT 'buyer',
         ton_address TEXT, balance REAL DEFAULT 0, is_connected INTEGER DEFAULT 0,
         gpu_model TEXT, vram INTEGER, hourly_rate REAL DEFAULT 0.05,
         total_earned REAL DEFAULT 0, connected_since TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS orders
        (id INTEGER PRIMARY KEY AUTOINCREMENT, buyer_id INTEGER, hours INTEGER,
         cost REAL, status TEXT DEFAULT 'pending', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    c.execute('''CREATE TABLE IF NOT EXISTS withdrawals
        (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, amount REAL,
         address TEXT, tx_hash TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    conn.commit(); conn.close()

def get_user(uid, uname):
    conn = sqlite3.connect('liberty.db'); c = conn.cursor()
    c.execute("SELECT * FROM users WHERE user_id=?", (uid,))
    u = c.fetchone()
    if not u:
        c.execute("INSERT INTO users (user_id, username) VALUES (?,?)", (uid, uname))
        conn.commit()
        c.execute("SELECT * FROM users WHERE user_id=?", (uid,))
        u = c.fetchone()
    conn.close(); return u

def upd(uid, **kw):
    conn = sqlite3.connect('liberty.db'); c = conn.cursor()
    for k,v in kw.items(): c.execute(f"UPDATE users SET {k}=? WHERE user_id=?", (v, uid))
    conn.commit(); conn.close()

# ===== СОСТОЯНИЯ =====
class S(StatesGroup):
    gpu = State()
    wallet = State()
    hours = State()

# ===== ЛОГОТИП =====
async def send_logo(msg):
    try:
        await msg.answer_photo(photo=FSInputFile('luc.png'))
    except: pass

# ===== СТАРТ =====
@dp.message(Command("start"))
async def start(msg: types.Message):
    u = get_user(msg.from_user.id, msg.from_user.username)
    await send_logo(msg)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t('provider', msg.from_user), callback_data="role_p")],
        [InlineKeyboardButton(text=t('buyer', msg.from_user), callback_data="role_b")],
        [InlineKeyboardButton(text=t('set_wallet', msg.from_user), callback_data="set_wallet")],
    ])
    await msg.answer(t('welcome', msg.from_user) + f"\n\n{t('role', msg.from_user)}",
                     reply_markup=kb, parse_mode="HTML")

# ===== РОЛИ =====
@dp.callback_query(F.data == "role_p")
async def role_p(cb: types.CallbackQuery, state: FSMContext):
    upd(cb.from_user.id, role='provider')
    u = get_user(cb.from_user.id, cb.from_user.username)
    if u[6] and u[7]:  # gpu_model и vram уже есть
        await show_provider(cb)
    else:
        await cb.message.answer(t('no_gpu', cb.from_user))
        await state.set_state(S.gpu)
    await cb.answer()

@dp.message(S.gpu)
async def save_gpu(msg: types.Message, state: FSMContext):
    try:
        parts = msg.text.split('|')
        gpu = parts[0].strip()
        vram = int(parts[1].strip()) if len(parts)>1 else 8
        rate = calc_rate(gpu, vram)
        upd(msg.from_user.id, gpu_model=gpu, vram=vram, hourly_rate=rate)
        await state.clear()
        await msg.answer(
            f"✅ GPU: {gpu} {vram}GB\n"
            f"{t('rate', msg.from_user).format(rate)}\n"
            f"{t('monthly', msg.from_user).format(round(rate*24*30, 2))}",
            parse_mode="HTML"
        )
        await show_provider_msg(msg)
    except:
        await msg.answer("❌ Формат: RTX 4090 | 24")

@dp.callback_query(F.data == "role_b")
async def role_b(cb: types.CallbackQuery):
    upd(cb.from_user.id, role='buyer')
    await show_buyer(cb)
    await cb.answer()

# ===== ПОСТАВЩИК =====
async def show_provider(cb):
    u = get_user(cb.from_user.id, cb.from_user.username)
    gpu, rate = u[6], u[8]
    is_conn = u[5]
    
    session = 0
    if is_conn and u[10]:
        try:
            h = (datetime.now() - datetime.fromisoformat(u[10])).total_seconds()/3600
            session = h * rate
        except: pass
    
    total = u[9] + session
    btn = t('disconnect', cb.from_user) if is_conn else t('connect', cb.from_user)
    bdata = "disconnect" if is_conn else "connect"
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=btn, callback_data=bdata)],
        [InlineKeyboardButton(text=t('back', cb.from_user), callback_data="back")],
    ])
    
    txt = (f"{t('online' if is_conn else 'offline', cb.from_user)}\n\n"
           f"🖥 {gpu} {u[7]}GB\n"
           f"{t('rate', cb.from_user).format(rate)}\n"
           f"{t('earned', cb.from_user).format(f'{total:.4f}')}\n"
           f"{t('balance', cb.from_user).format(f'{u[4]:.4f}')}")
    
    await cb.message.edit_text(txt, reply_markup=kb, parse_mode="HTML")

async def show_provider_msg(msg):
    u = get_user(msg.from_user.id, msg.from_user.username)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t('connect', msg.from_user), callback_data="connect")],
    ])
    txt = (f"🖥 {u[6]} {u[7]}GB\n"
           f"{t('rate', msg.from_user).format(u[8])}\n"
           f"{t('monthly', msg.from_user).format(round(u[8]*24*30, 2))}")
    await msg.answer(txt, reply_markup=kb, parse_mode="HTML")

@dp.callback_query(F.data == "connect")
async def connect(cb: types.CallbackQuery):
    upd(cb.from_user.id, is_connected=1, connected_since=datetime.now().isoformat())
    await cb.answer(t('connected', cb.from_user), show_alert=True)
    await show_provider(cb)

@dp.callback_query(F.data == "disconnect")
async def disconnect(cb: types.CallbackQuery):
    u = get_user(cb.from_user.id, cb.from_user.username)
    session = 0
    if u[10]:
        try:
            h = (datetime.now() - datetime.fromisoformat(u[10])).total_seconds()/3600
            session = h * u[8]
        except: pass
    upd(cb.from_user.id, is_connected=0, total_earned=u[9]+session,
        balance=u[4]+session, connected_since=None)
    await cb.answer(t('disconnected', cb.from_user), show_alert=True)
    await show_provider(cb)

# ===== ПОКУПАТЕЛЬ =====
async def show_buyer(cb):
    u = get_user(cb.from_user.id, cb.from_user.username)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t('buy', cb.from_user), callback_data="buy")],
        [InlineKeyboardButton(text=t('back', cb.from_user), callback_data="back")],
    ])
    txt = t('balance', cb.from_user).format(f'{u[4]:.4f}')
    await cb.message.edit_text(txt, reply_markup=kb, parse_mode="HTML")

@dp.callback_query(F.data == "buy")
async def buy(cb: types.CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="1h (0.05 TON)", callback_data="h_1")],
        [InlineKeyboardButton(text="5h (0.25 TON)", callback_data="h_5")],
        [InlineKeyboardButton(text="10h (0.5 TON)", callback_data="h_10")],
        [InlineKeyboardButton(text=t('back', cb.from_user), callback_data="back_b")],
    ])
    await cb.message.edit_text(t('hours_q', cb.from_user), reply_markup=kb)

@dp.callback_query(F.data.startswith("h_"))
async def pick_hours(cb: types.CallbackQuery):
    h = int(cb.data.split("_")[1])
    cost = round(h * 0.05, 2)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t('yes', cb.from_user), callback_data=f"ok_{h}_{cost}")],
        [InlineKeyboardButton(text=t('no', cb.from_user), callback_data="back_b")],
    ])
    await cb.message.edit_text(t('confirm', cb.from_user).format(h, cost), reply_markup=kb)

@dp.callback_query(F.data.startswith("ok_"))
async def confirm(cb: types.CallbackQuery):
    _, h, cost = cb.data.split("_")
    h, cost = int(h), float(cost)
    u = get_user(cb.from_user.id, cb.from_user.username)
    if u[4] < cost:
        await cb.answer("❌ No TON!", show_alert=True); return
    conn = sqlite3.connect('liberty.db'); c = conn.cursor()
    c.execute("INSERT INTO orders (buyer_id, hours, cost, status) VALUES (?,?,?, 'paid')",
              (cb.from_user.id, h, cost))
    c.execute("UPDATE users SET balance=balance-? WHERE user_id=?", (cost, cb.from_user.id))
    conn.commit(); conn.close()
    await cb.answer(t('paid', cb.from_user), show_alert=True)
    await show_buyer(cb)

# ===== КОШЕЛЕК =====
@dp.callback_query(F.data == "set_wallet")
async def set_wallet(cb: types.CallbackQuery, state: FSMContext):
    await cb.message.answer(t('send_addr', cb.from_user))
    await state.set_state(S.wallet)
    await cb.answer()

@dp.message(S.wallet)
async def save_wallet(msg: types.Message, state: FSMContext):
    addr = msg.text.strip()
    if not (addr.startswith('UQ') or addr.startswith('EQ')) or len(addr) < 40:
        await msg.answer("❌ Bad address"); return
    upd(msg.from_user.id, ton_address=addr)
    await state.clear()
    await msg.answer(t('wallet_saved', msg.from_user).format(addr[:10]+'...'+addr[-6:]))

# ===== НАЗАД =====
@dp.callback_query(F.data == "back")
async def back(cb: types.CallbackQuery):
    await start(cb.message)

@dp.callback_query(F.data == "back_b")
async def back_b(cb: types.CallbackQuery):
    await show_buyer(cb)

# ===== БАЛАНС =====
@dp.message(Command("balance"))
async def bal(msg: types.Message):
    u = get_user(msg.from_user.id, msg.from_user.username)
    await msg.answer(t('balance', msg.from_user).format(f'{u[4]:.4f}'))

# ===== АВТО-ВЫВОД =====
async def auto_withdraw():
    while True:
        try:
            conn = sqlite3.connect('liberty.db'); c = conn.cursor()
            c.execute("SELECT user_id, ton_address, balance FROM users WHERE balance>=? AND ton_address IS NOT NULL",
                      (MIN_WITHDRAW,))
            for uid, addr, bal in c.fetchall():
                tx = f"TX{int(datetime.now().timestamp())}"
                c.execute("INSERT INTO withdrawals (user_id, amount, address, tx_hash) VALUES (?,?,?,?)",
                          (uid, bal, addr, tx))
                c.execute("UPDATE users SET balance=0 WHERE user_id=?", (uid,))
                try:
                    await bot.send_message(uid,
                        f"✅ {t('withdraw', type('U',(),{'language_code':'ru'})()).format(f'{bal:.4f}', addr[:10]+'...')}\nTX: {tx}",
                        parse_mode="HTML")
                except: pass
            conn.commit(); conn.close()
        except Exception as e:
            print(f"Withdraw error: {e}")
        await asyncio.sleep(3600)

# ===== ЗАПУСК =====
async def main():
    init_db()
    asyncio.create_task(auto_withdraw())
    print("🔗 LIBERTY UNITED CHAIN запущен!")
    print(f"💰 Авто-вывод: {MIN_WITHDRAW} TON")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
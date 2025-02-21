import os
import requests
import logging
import sqlite3
from dotenv import load_dotenv
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext

#Используем .env
load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
HELIUS_API_KEY = os.getenv("HELIUS_API_KEY")
COLLECTION_ID = os.getenv("COLLECTION_ID")

# Настройка логов
logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)

# 🔹 Настройка пути к базе данных
DB_FOLDER = ".data"
DB_PATH = os.path.join(DB_FOLDER, "wallets.db")

# 🔹 Создаём папку для базы, если её нет
if not os.path.exists(DB_FOLDER):
    os.makedirs(DB_FOLDER, exist_ok=True)

# 🔹 Инициализация базы данных
def init_db():
    """Создаёт таблицу в базе данных, если её нет."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS wallets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            wallet_address TEXT UNIQUE,
            has_nft INTEGER
        )
    """)
    conn.commit()
    conn.close()
    logging.info("✅ База данных инициализирована.")

def save_wallet(wallet_address: str, has_nft: bool):
    """Сохраняет кошелёк и наличие NFT в базе данных."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO wallets (wallet_address, has_nft)
            VALUES (?, ?)
            ON CONFLICT(wallet_address) DO UPDATE SET has_nft = ?
        """, (wallet_address, int(has_nft), int(has_nft)))
        conn.commit()
    except sqlite3.Error as e:
        logging.error(f"Ошибка при сохранении кошелька: {e}")
    finally:
        conn.close()

# 🔹 Клавиатура
keyboard = ReplyKeyboardMarkup(
    [[KeyboardButton("🔍 Проверить NFT")], [KeyboardButton("ℹ️ О боте")]],
    resize_keyboard=True,
    one_time_keyboard=False,
)


async def check_nft(wallet_address: str) -> bool:
    """Проверяет наличие NFT из коллекции по ID у кошелька."""
    url = f"https://mainnet.helius-rpc.com/?api-key={HELIUS_API_KEY}"
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "getAssetsByOwner",
        "params": {
            "ownerAddress": wallet_address,
            "page": 1,
            "limit": 1000
        }
    }

    response = requests.post(url, json=payload)
    
    if response.status_code == 200:
        data = response.json()
        if "result" in data and "items" in data["result"]:
            nfts = data["result"]["items"]
            logging.info(f"Получено {len(nfts)} NFT от кошелька {wallet_address}")
            
            for nft in nfts:
                if "grouping" in nft:
                    for group in nft["grouping"]:
                        if group["group_key"] == "collection" and group["group_value"] == COLLECTION_ID:
                            logging.info(f"✅ Найден NFT из коллекции {COLLECTION_ID}")
                            return True
    return False  # Нет NFT из нужной коллекции


async def start(update: Update, context: CallbackContext) -> None:
    """Обработчик команды /start."""
    await update.message.reply_text(
        "👋 Привет! Я бот для проверки NFT на Solana.\n\nВыбери действие ниже:",
        reply_markup=keyboard,
    )


async def about_bot(update: Update, context: CallbackContext) -> None:
    """Обработчик кнопки 'О боте'."""
    await update.message.reply_text("🤖 Этот бот проверяет наличие NFT на Solana-кошельке.")


async def request_wallet(update: Update, context: CallbackContext) -> None:
    """Обработчик кнопки 'Проверить NFT'."""
    await update.message.reply_text("🔹 Введите адрес Solana-кошелька для проверки.")


async def check_wallet(update: Update, context: CallbackContext) -> None:
    """Обработчик введённого кошелька."""
    wallet_address = update.message.text.strip()
    
    if len(wallet_address) < 32 or len(wallet_address) > 44:
        await update.message.reply_text("⚠️ Введите корректный Solana-адрес!")
        return
    
    await update.message.reply_text(f"🔍 Проверяем NFT у {wallet_address}...")

    has_nft = await check_nft(wallet_address)
    save_wallet(wallet_address, has_nft)

    if has_nft:
        await update.message.reply_text("✅ У кошелька есть NFT из коллекции Trinity!")
    else:
        await update.message.reply_text("❌ У кошелька нет NFT из коллекции Trinity.")


def main():
    """Запуск бота."""
    init_db()
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Обработчики команд с автодополнением
    app.add_handler(CommandHandler("start", start, block=False))
    app.add_handler(CommandHandler("check", request_wallet, block=False))
    
    # Обработчики текстовых сообщений
    app.add_handler(MessageHandler(filters.Text("🔍 Проверить NFT"), request_wallet))
    app.add_handler(MessageHandler(filters.Text("ℹ️ О боте"), about_bot))

    # Обработчик любого введенного текста (считаем его за адрес кошелька)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, check_wallet))

    print("🤖 Бот запущен!")
    app.run_polling()


if __name__ == "__main__":
    main()
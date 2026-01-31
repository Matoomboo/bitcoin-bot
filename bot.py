import os
import requests
import pandas as pd
import pandas_ta as ta
import mplfinance as mpf
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes

# === Настройки ===
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OWNER_ID = int(os.getenv("OWNER_ID"))

# === Меню с кнопками ===
keyboard = [
    ["/price", "/chart"],
    ["/help"]
]
reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# === Получение данных с Binance (24 свечи, 1h) ===
def get_ohlcv():
    url = "https://api.binance.com/api/v3/klines"
    params = {"symbol": "BTCUSDT", "interval": "1h", "limit": 24}  # 24 свечи по 1 часу
    try:
        response = requests.get(url, params=params)
        data = response.json()
        df = pd.DataFrame(data, columns=[
            "timestamp", "open", "high", "low", "close", "volume",
            "close_time", "quote_asset_volume", "trades",
            "taker_buy_base", "taker_buy_quote", "ignore"
        ])
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
        df["open"] = df["open"].astype(float)
        df["high"] = df["high"].astype(float)
        df["low"] = df["low"].astype(float)
        df["close"] = df["close"].astype(float)
        df["volume"] = df["volume"].astype(float)
        df.set_index("timestamp", inplace=True)
        return df
    except Exception as e:
        print(f"Ошибка загрузки данных: {e}")
        return None

# === Добавление индикаторов ===
def add_indicators(df):
    # Bollinger Bands (20, 2σ)
    df.ta.bbands(close="close", length=20, std=2, append=True)
    # SMA 20
    df.ta.sma(length=20, append=True)
    # RSI 14
    df.ta.rsi(length=14, append=True)
    return df

# === Команда /start ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != OWNER_ID:
        await update.message.reply_text("❌ Доступ запрещён.")
        return
    await update.message.reply_text(
        "🚀 Bitcoin Pulse активирован!\n"
        "Выберите команду:",
        reply_markup=reply_markup
    )

# === Команда /price ===
async def price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != OWNER_ID:
        await update.message.reply_text("❌ Доступ запрещён.")
        return
    df = get_ohlcv()
    if df is not None and not df.empty:
        price = df["close"].iloc[-1]
        await update.message.reply_text(f"📊 Текущая цена BTC: ${price:,.2f}")
    else:
        await update.message.reply_text("❌ Не удалось получить цену.")

# === Команда /chart — свечи + индикаторы ===
async def chart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != OWNER_ID:
        await update.message.reply_text("❌ Доступ запрещён.")
        return
    await update.message.reply_text("⏳ Строю график... (24 свечи, 1h)")

    df = get_ohlcv()
    if df is None or df.empty:
        await update.message.reply_text("❌ Не удалось загрузить данные.")
        return

    df = add_indicators(df)

    # Подготовка индикаторов
    apds = [
        # Bollinger Bands
        mpf.make_addplot(df["BBL_20_2.0"], color="lightblue", width=1),
        mpf.make_addplot(df["BBM_20_2.0"], color="gray", width=0.8, alpha=0.7),
        mpf.make_addplot(df["BBU_20_2.0"], color="lightblue", width=1),
        # SMA 20
        mpf.make_addplot(df["SMA_20"], color="blue", width=1.2),
        # RSI (в отдельной панели)
        mpf.make_addplot(df["RSI_14"], panel=1, color="purple", ylabel="RSI")
    ]

    # Построение графика
    fig, axes = mpf.plot(
        df,
        type="candle",
        style="charles",
        volume=True,  # объёмы под свечами
        addplot=apds,
        title="BTC/USDT — 24h (1h) | Bollinger + SMA + RSI + Volume",
        ylabel="Цена, $",
        ylabel_lower="Объём",
        figsize=(12, 8),
        returnfig=True
    )

    fig.savefig("btc_analysis.png", dpi=150, bbox_inches="tight")
    plt.close(fig)

    await update.message.reply_photo(photo=open("btc_analysis.png", "rb"))
    os.remove("btc_analysis.png")

# === Команда /help ===
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "📚 Команды:\n"
        "/price — текущая цена BTC\n"
        "/chart — график: свечи, Bollinger, SMA, RSI, объёмы\n"
        "/help — это меню"
    )
    await update.message.reply_text(text)

# === Запуск бота ===
def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("price", price))
    app.add_handler(CommandHandler("chart", chart))
    app.add_handler(CommandHandler("help", help_command))
    app.run_polling()

if __name__ == "__main__":
    main()

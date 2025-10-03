import re
import asyncio
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

# 👉 Сіздің токен (нақты өзіңіздікі қойылды)
BOT_TOKEN = "8035442387:AAFnszuT3AbictfnyA2xrHVD6IFxX5Tw1zA"

# Әр чатқа жеке-жеке күй сақтаймыз
states = {}

def split_text(text, size=4):
    words = [w for w in re.split(r"\s+", text.strip()) if w]
    return [" ".join(words[i:i+size]) for i in range(0, len(words), size)]

def keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("▶️ Start", callback_data="start"),
         InlineKeyboardButton("⏸ Stop", callback_data="stop")],
        [InlineKeyboardButton("🔍 Preview", callback_data="preview")]
    ])

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Сәлем! Маған ұзын мәтін жібер.\n"
        "Мен оны бөліп-бөліп жіберемін.\n",
        reply_markup=keyboard()
    )

async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    text = update.message.text
    chunks = split_text(text, 4)
    states[chat_id] = {"chunks": chunks, "index": 0, "task": None}
    await update.message.reply_text(
        f"Мәтін қабылданды. {len(chunks)} бөлікке бөлінді.",
        reply_markup=keyboard()
    )

async def preview(chat_id, context):
    st = states.get(chat_id)
    if not st or not st["chunks"]:
        await context.bot.send_message(chat_id, "Алдымен мәтін жіберіңіз.")
        return
    preview = "\n".join(st["chunks"][:10])
    await context.bot.send_message(chat_id, "Алдын ала көру:\n" + preview)

async def sender(chat_id, context):
    st = states[chat_id]
    while st["index"] < len(st["chunks"]):
        chunk = st["chunks"][st["index"]]
        await context.bot.send_message(chat_id, chunk)
        st["index"] += 1
        await asyncio.sleep(8)  # ⏱ әр 8 секунд сайын

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    chat_id = query.message.chat.id
    st = states.get(chat_id)

    if query.data == "start":
        if not st or not st["chunks"]:
            await query.answer("Алдымен мәтін жібер.")
            return
        if st["task"] and not st["task"].done():
            await query.answer("Қазірдің өзінде жіберіліп жатыр.")
            return
        st["index"] = 0
        st["task"] = asyncio.create_task(sender(chat_id, context))
        await query.answer("Жіберу басталды ▶️")

    elif query.data == "stop":
        if st and st["task"]:
            st["task"].cancel()
            await query.answer("Тоқтатылды ⏸")
        else:
            await query.answer("Ештеңе жүрмей тұр.")

    elif query.data == "preview":
        await preview(chat_id, context)
        await query.answer()

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    app.add_handler(CallbackQueryHandler(button))
    app.run_polling()

if __name__ == "__main__":
    main()

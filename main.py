import os
import base64
import httpx
import asyncio
import json
import random
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters

# --------------------- ТОКЕНЫ ---------------------
BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

# --------------------- ПРЕДМЕТЫ ---------------------
subjects = {
    "math": "📐 Математика",
    "russian": "📖 Русский язык",
    "physics": "⚛️ Физика",
    "chemistry": "🧪 Химия",
    "biology": "🧬 Биология",
    "history": "📜 История",
    "social": "⚖️ Обществознание",
    "english": "🌍 Английский",
    "informatics": "💻 Информатика",
    "geography": "🌏 География",
    "literature": "📚 Литература"
}

subject_keyboard = InlineKeyboardMarkup([
    [InlineKeyboardButton("📐 Математика", callback_data="subject_math"),
     InlineKeyboardButton("📖 Русский язык", callback_data="subject_russian")],
    [InlineKeyboardButton("⚛️ Физика", callback_data="subject_physics"),
     InlineKeyboardButton("🧪 Химия", callback_data="subject_chemistry")],
    [InlineKeyboardButton("🧬 Биология", callback_data="subject_biology"),
     InlineKeyboardButton("📜 История", callback_data="subject_history")],
    [InlineKeyboardButton("⚖️ Обществознание", callback_data="subject_social"),
     InlineKeyboardButton("🌍 Английский", callback_data="subject_english")],
    [InlineKeyboardButton("💻 Информатика", callback_data="subject_informatics"),
     InlineKeyboardButton("🌏 География", callback_data="subject_geography")],
    [InlineKeyboardButton("📚 Литература", callback_data="subject_literature")]
])

fipi_bank = {
    "math": {
        "oge": [
            {"question": "Решите уравнение: 2x² - 8x = 0", "answer": "x₁ = 0, x₂ = 4"},
            {"question": "Решите неравенство: 3x - 5 > 7", "answer": "x > 4"},
        ],
        "ege": [
            {"question": "Решите уравнение: 3x² - 5x + 2 = 0", "answer": "x₁ = 1, x₂ = 2/3"},
            {"question": "Найдите производную: f(x) = 3x² - 2x + 5", "answer": "f'(x) = 6x - 2"},
        ]
    },
    "russian": {
        "oge": [
            {"question": "В каком слове пишется 'Е'?\nА) пр_вет\nБ) пр_красный\nВ) пр_шёл", "answer": "А"},
            {"question": "Какое слово заимствованное?\nА) дерево\nБ) компьютер\nВ) солнце", "answer": "Б"},
        ],
        "ege": [
            {"question": "Укажите ошибку в форме слова:\nА) лягте\nБ) ихние\nВ) более сильный", "answer": "Б"},
            {"question": "В каком ряду чередующаяся гласная?\nА) заг_рать\nБ) заг_реть\nВ) заг_р", "answer": "А"},
        ]
    }
}

user_data = {}

# --------------------- AGNES AI (ВМЕСТО GROQ) ---------------------
async def ask_ai(question: str, subject: str = "Математика", exam: str = "ОГЭ") -> str:
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "agnesis/agnes-2.0-flash",
                    "messages": [{
                        "role": "system",
                        "content": f"Ты — AI Tutor Pro, репетитор по {subject}. Уровень: {exam}. Отвечай с эмодзи, по шагам. В конце совет."
                    }, {"role": "user", "content": question}],
                    "temperature": 0.7,
                    "max_tokens": 500,
                }
            )
            return response.json()["choices"][0]["message"]["content"]
    except Exception as e:
        return f"⚠️ Ошибка: {e}"

# --------------------- ФОТО ---------------------
async def handle_photo(update: Update, context):
    await update.message.reply_text("📸 Принял фото! Сейчас разберу...")
    try:
        photo_file = await update.message.photo[-1].get_file()
        image_bytes = await photo_file.download_as_bytearray()
        image_base64 = base64.b64encode(image_bytes).decode("utf-8")
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}", "Content-Type": "application/json"},
                json={
                    "model": "google/gemini-1.5-flash",
                    "messages": [{"role": "user", "content": [{"type": "text", "text": "Реши задачу с фото."}, {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_base64}"}}]}],
                    "max_tokens": 500,
                }
            )
            await update.message.reply_text(f"🧠 Решение:\n\n{response.json()['choices'][0]['message']['content']}")
    except Exception as e:
        await update.message.reply_text(f"⚠️ Ошибка: {e}")

# --------------------- КОМАНДЫ /FIPI, /STATS, /TASK ---------------------
async def start(update: Update, context):
    user_id = update.message.from_user.id
    if user_id not in user_data:
        user_data[user_id] = {
            "name": update.message.from_user.first_name or "друг",
            "exam": "ОГЭ",
            "subject": "Математика",
            "xp": 0,
            "streak": 0,
            "subjects_stats": {}
        }
    await show_main_menu(update, context)

async def show_main_menu(update: Update, context):
    user_id = update.message.from_user.id
    data = user_data.get(user_id, {})
    name = data.get("name", "друг")
    exam = data.get("exam", "ОГЭ")
    
    menu_keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📚 Предметы", callback_data="menu_subjects")],
        [InlineKeyboardButton("🎯 ОГЭ (9 класс)", callback_data="exam_oge")],
        [InlineKeyboardButton("🎯 ЕГЭ (11 класс)", callback_data="exam_ege")],
        [InlineKeyboardButton("📂 Банк ФИПИ", callback_data="menu_fipi")],
        [InlineKeyboardButton("📊 Моя статистика", callback_data="menu_stats")],
        [InlineKeyboardButton("🧠 Случайное задание", callback_data="menu_task")],
        [InlineKeyboardButton("❓ Помощь", callback_data="menu_help")],
    ])
    await update.message.reply_text(
        f"🤖 *AI Tutor Pro*\n\n"
        f"Привет, {name}! 👋\n"
        f"Я — твой репетитор для подготовки к ОГЭ, ЕГЭ и ВПР.\n\n"
        f"📚 *Что я умею:*\n"
        f"- 11 предметов\n"
        f"- Объясняю по шагам\n"
        f"- Даю задания из ФИПИ\n"
        f"- Показываю статистику\n\n"
        f"Твой экзамен: *{exam}*\n"
        f"Выбери действие:",
        reply_markup=menu_keyboard,
        parse_mode="Markdown"
    )

async def menu_callback(update: Update, context):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = user_data.get(user_id, {})

    if query.data == "menu_subjects":
        await query.edit_message_text("📚 Выбери предмет:", reply_markup=subject_keyboard, parse_mode="Markdown")
    elif query.data == "exam_oge":
        data["exam"] = "ОГЭ"
        user_data[user_id] = data
        await query.edit_message_text("✅ Выбран ОГЭ (9 класс)", parse_mode="Markdown")
        await show_main_menu_from_callback(query)
    elif query.data == "exam_ege":
        data["exam"] = "ЕГЭ"
        user_data[user_id] = data
        await query.edit_message_text("✅ Выбран ЕГЭ (11 класс)", parse_mode="Markdown")
        await show_main_menu_from_callback(query)
    elif query.data == "menu_fipi":
        fipi_keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📐 Математика", callback_data="fipi_math")],
            [InlineKeyboardButton("📖 Русский язык", callback_data="fipi_russian")],
        ])
        await query.edit_message_text("📂 Банк ФИПИ:\nВыбери предмет:", reply_markup=fipi_keyboard, parse_mode="Markdown")
    elif query.data == "menu_stats":
        await show_stats(query, user_id)
    elif query.data == "menu_task":
        await query.edit_message_text("🧠 Генерирую задание... ⏳")
        subject = data.get("subject", "Математика")
        exam = data.get("exam", "ОГЭ")
        reply = await ask_ai(f"Дай случайное задание по {subject} для {exam}.", subject, exam)
        await query.message.reply_text(f"📝 {reply}")
    elif query.data == "menu_help":
        await query.edit_message_text(
            "📖 Команды:\n/start — меню\n/stats — статистика\n/fipi — банк ФИПИ\n/task — задание",
            parse_mode="Markdown"
        )
    elif query.data.startswith("fipi_"):
        subject_key = query.data.replace("fipi_", "")
        subject_name = subjects.get(subject_key, "Математика")
        exam = data.get("exam", "ОГЭ")
        tasks = fipi_bank.get(subject_key, {}).get(exam.lower(), [])
        if not tasks:
            await query.edit_message_text(f"⚠️ Заданий по {subject_name} для {exam} пока нет.", parse_mode="Markdown")
            return
        task = random.choice(tasks)
        await query.edit_message_text(
            f"📂 *Банк ФИПИ — {subject_name} ({exam})*\n\n{task['question']}",
            parse_mode="Markdown"
        )

async def show_main_menu_from_callback(query):
    user_id = query.from_user.id
    data = user_data.get(user_id, {})
    name = data.get("name", "друг")
    exam = data.get("exam", "ОГЭ")
    
    menu_keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📚 Предметы", callback_data="menu_subjects")],
        [InlineKeyboardButton("🎯 ОГЭ (9 класс)", callback_data="exam_oge")],
        [InlineKeyboardButton("🎯 ЕГЭ (11 класс)", callback_data="exam_ege")],
        [InlineKeyboardButton("📂 Банк ФИПИ", callback_data="menu_fipi")],
        [InlineKeyboardButton("📊 Моя статистика", callback_data="menu_stats")],
        [InlineKeyboardButton("🧠 Случайное задание", callback_data="menu_task")],
        [InlineKeyboardButton("❓ Помощь", callback_data="menu_help")],
    ])
    await query.message.reply_text(
        f"🤖 *AI Tutor Pro*\n\nПривет, {name}! 👋\nТвой экзамен: *{exam}*\nВыбери действие:",
        reply_markup=menu_keyboard,
        parse_mode="Markdown"
    )

async def show_stats(query, user_id):
    data = user_data.get(user_id, {})
    name = data.get("name", "друг")
    exam = data.get("exam", "ОГЭ")
    xp = data.get("xp", 0)
    streak = data.get("streak", 0)
    level = xp // 100 + 1
    subjects_stats = data.get("subjects_stats", {})
    
    text = f"📊 *Твой прогресс, {name}*\n\n"
    text += f"🎯 Экзамен: {exam}\n"
    text += f"⭐ Опыт: {xp} XP\n"
    text += f"📈 Уровень: {level}\n"
    text += f"🔥 Серия: {streak} дней\n\n"
    text += "📚 *По предметам:*\n"
    for subject, stats in subjects_stats.items():
        correct = stats.get("correct", 0)
        total = stats.get("total", 0)
        percent = round(correct / total * 100) if total > 0 else 0
        text += f"✅ {subjects.get(subject, subject)}: {total} задач ({percent}%)\n"
    
    if xp >= 500:
        text += "\n🏆 *Достижения:*\n"
        if xp >= 500:
            text += "🥇 Первые 500 XP\n"
        if xp >= 1000:
            text += "🥇 1000 XP — ты крут!\n"
        if streak >= 7:
            text += "🔥 7 дней подряд — ты машина!\n"
    
    await query.edit_message_text(text, parse_mode="Markdown")

async def subject_callback(update: Update, context):
    query = update.callback_query
    await query.answer()
    subject_key = query.data.replace("subject_", "")
    subject_name = subjects.get(subject_key, "Математика")
    user_id = query.from_user.id
    if user_id not in user_data:
        user_data[user_id] = {"name": "друг", "exam": "ОГЭ", "subject": "Математика", "xp": 0, "streak": 0, "subjects_stats": {}}
    user_data[user_id]["subject"] = subject_name
    await query.edit_message_text(f"✅ *{subject_name}*\n\nЗадавай вопросы!", parse_mode="Markdown")

# --------------------- КОМАНДЫ /STATS, /FIPI, /TASK ---------------------
async def stats_command(update: Update, context):
    user_id = update.message.from_user.id
    data = user_data.get(user_id, {})
    name = data.get("name", "друг")
    exam = data.get("exam", "ОГЭ")
    xp = data.get("xp", 0)
    streak = data.get("streak", 0)
    level = xp // 100 + 1
    subjects_stats = data.get("subjects_stats", {})
    
    text = f"📊 *Твой прогресс, {name}*\n\n"
    text += f"🎯 Экзамен: {exam}\n"
    text += f"⭐ Опыт: {xp} XP\n"
    text += f"📈 Уровень: {level}\n"
    text += f"🔥 Серия: {streak} дней\n\n"
    text += "📚 *По предметам:*\n"
    for subject, stats in subjects_stats.items():
        correct = stats.get("correct", 0)
        total = stats.get("total", 0)
        percent = round(correct / total * 100) if total > 0 else 0
        text += f"✅ {subjects.get(subject, subject)}: {total} задач ({percent}%)\n"
    
    await update.message.reply_text(text, parse_mode="Markdown")

async def fipi_command(update: Update, context):
    fipi_keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📐 Математика", callback_data="fipi_math")],
        [InlineKeyboardButton("📖 Русский язык", callback_data="fipi_russian")],
    ])
    await update.message.reply_text("📂 *Банк ФИПИ*\nВыбери предмет:", reply_markup=fipi_keyboard, parse_mode="Markdown")

async def task_command(update: Update, context):
    user_id = update.message.from_user.id
    data = user_data.get(user_id, {})
    subject = data.get("subject", "Математика")
    exam = data.get("exam", "ОГЭ")
    await update.message.reply_text("🧠 *Генерирую задание...* ⏳")
    reply = await ask_ai(f"Дай случайное задание по {subject} для {exam}.", subject, exam)
    await update.message.reply_text(f"📝 {reply}")

async def help_command(update: Update, context):
    await update.message.reply_text(
        "📖 *Команды:*\n"
        "/start — главное меню\n"
        "/stats — моя статистика\n"
        "/fipi — банк заданий ФИПИ\n"
        "/task — случайное задание\n\n"
        "Просто задавай вопросы, и я помогу! 💪",
        parse_mode="Markdown"
    )

async def handle_text(update: Update, context):
    text = update.message.text
    if text.startswith("/"):
        return
    user_id = update.message.from_user.id
    data = user_data.get(user_id, {})
    subject = data.get("subject", "Математика")
    exam = data.get("exam", "ОГЭ")
    
    await update.message.reply_chat_action(action="typing")
    await asyncio.sleep(0.8)
    
    reply = await ask_ai(text, subject, exam)
    
    if user_id not in user_data:
        user_data[user_id] = {"name": "друг", "exam": "ОГЭ", "subject": "Математика", "xp": 0, "streak": 0, "subjects_stats": {}}
    user_data[user_id]["xp"] = user_data[user_id].get("xp", 0) + 10
    
    await update.message.reply_text(reply, parse_mode="Markdown")

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(CommandHandler("fipi", fipi_command))
    app.add_handler(CommandHandler("task", task_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CallbackQueryHandler(menu_callback, pattern="menu_"))
    app.add_handler(CallbackQueryHandler(menu_callback, pattern="exam_"))
    app.add_handler(CallbackQueryHandler(menu_callback, pattern="fipi_"))
    app.add_handler(CallbackQueryHandler(subject_callback, pattern="subject_"))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    print("✅ AI Tutor Pro запущен")
    app.run_polling()

if __name__ == "__main__":
    main()


import os
import sqlite3
import nest_asyncio
import asyncio
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, ContextTypes, filters

# Location for the persistent DB file
DB_PATH = ""

# Apply for Spyder/Notebook environments
nest_asyncio.apply()

# ====== DB SETUP ======
def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # Users table
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            last_name TEXT,
            name TEXT,
            company TEXT,
            registered INTEGER DEFAULT 0
        )
    ''')
    # Chat log table
    c.execute('''
        CREATE TABLE IF NOT EXISTS chatlog (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            question TEXT,
            answer TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# ====== REGISTRATION & LOGGING UTILS ======
user_states = {}         # Tracks onboarding steps per user
pending_user_data = {}   # Temporarily stores registration data

def get_user(user_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT name, company FROM users WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    conn.close()
    return row  # None if not registered

def register_user(user_id, username, first_name, last_name, name, company):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        INSERT OR REPLACE INTO users (user_id, username, first_name, last_name, name, company, registered)
        VALUES (?, ?, ?, ?, ?, ?, 1)
    ''', (user_id, username, first_name, last_name, name, company))
    conn.commit()
    conn.close()

def log_to_db(user_id, question, answer):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        INSERT INTO chatlog (user_id, question, answer)
        VALUES (?, ?, ?)
    ''', (user_id, question, answer))
    conn.commit()
    conn.close()

# ====== FAKE LLM FUNCTION FOR DEMO ======
def ask_question2_test(question):
    # Replace with your CrewAI logic here!
    return f"🤖 You asked: {question}\n(This is a placeholder answer.)"



# ====== TELEGRAM HANDLER ======
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    user_id = user.id
    message = update.message.text.strip()

    # 1. Registration flow
    registered = get_user(user_id)
    if not registered:
        state = user_states.get(user_id)
        if not state:
            user_states[user_id] = "ask_name"
            await update.message.reply_text("¡Hola! Soy un MVP, genero reportes segun tu consulta regulatoria del BCRA. No estoy diseñado seguir el hilo de la conversiocion, solo respondo despues de tu consulta. Por el momento no estoy perfectamente orientado en el tiempo y mi base de datos se actualizo por ultima vez el 3/6/25. Podes hacer consultas complejas, mis respuestas tipicamente son de 1 a 6 carillas, intenta agregar el contexto adecuado. Comenza tu pregunta con #Full, para preguntas complejas. Para comenzar, por favor dime tu **nombre completo**:")
            return
        elif state == "ask_name":
            pending_user_data[user_id] = {"name": message}
            user_states[user_id] = "ask_company"
            await update.message.reply_text("Gracias. Ahora dime el **nombre de tu empresa**:")
            return
        elif state == "ask_company":
            user_info = pending_user_data.pop(user_id, {})
            name = user_info.get("name", "")
            company = message
            register_user(
                user_id, user.username, user.first_name, user.last_name, name, company
            )
            user_states[user_id] = None
            await update.message.reply_text(
                f"¡Gracias {name} de {company}! Ahora puedes hacerme preguntas."
            )
            return

    # 2. Normal chat flow (user already registered)
    await update.message.reply_text("OK, elaborando la consulta... usualmente demoro 3 minutos")
    if message.lower().startswith("#full"):
        message = message[5:].strip()  # remueve '#full' y espacios
        response = ask_question2_full(message)
    else:
        response = ask_question2(message)
    #response = ask_question2(message)
    log_to_db(user_id, message, response)
    
    #import traceback

    try:
        await update.message.reply_text(response)
    except Exception as e:
        # Print the full traceback to console (and optionally send to user)
        print("Exception in reply_text:", e)
        traceback.print_exc()  # <---- Esto imprime el stack trace real en consola
        # Fallback to PDF...
        pdf_file_path = "/home/reinaldo/Downloads/outputllm.pdf"
        make_pretty_pdf(response, filename=pdf_file_path, font_size=12)
        with open(pdf_file_path, "rb") as pdf_file:
            await update.message.reply_document(pdf_file)
    
    

# ====== MAIN RUNNER ======
async def main():
    # Put your bot token here
    app = ApplicationBuilder().token("").build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("Bot is running...")
    await app.run_polling()

# ====== IF RUNNING IN SPYDER/JUPYTER ======

await main()


ds()


import sqlite3

DB_PATH = "chatlog.db"

def load_users_dict():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT user_id, username, first_name, last_name, name, company, registered FROM users")
    rows = c.fetchall()
    conn.close()
    # Build dict: user_id -> user info dict
    users = {
        row[0]: {
            "username": row[1],
            "first_name": row[2],
            "last_name": row[3],
            "name": row[4],
            "company": row[5],
            "registered": bool(row[6])
        }
        for row in rows
    }
    return users

users = load_users_dict()
print(users)


def load_chatlogs():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT user_id, question, answer, timestamp FROM chatlog ORDER BY timestamp")
    rows = c.fetchall()
    conn.close()
    # Each entry is a dict
    logs = [
        {
            "user_id": row[0],
            "question": row[1],
            "answer": row[2],
            "timestamp": row[3]
        }
        for row in rows
    ]
    return logs

logs = load_chatlogs()
print(logs)


from collections import defaultdict

def load_chatlogs_grouped_by_user():
    logs = load_chatlogs()
    logs_by_user = defaultdict(list)
    for entry in logs:
        logs_by_user[entry["user_id"]].append(entry)
    return dict(logs_by_user)

logs_by_user = load_chatlogs_grouped_by_user()
for user_id, qas in logs_by_user.items():
    print(f"User {user_id}:")
    for qa in qas:
        print(f"  [{qa['timestamp']}] Q: {qa['question']}\n     A: {qa['answer']}\n")



import os
import sqlite3
from datetime import datetime, timedelta
import asyncio
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from dotenv import load_dotenv

load_dotenv()  # load .env if present
TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    raise RuntimeError("BOT_TOKEN environment variable is required. Put it in a .env file or environment variables.")

DB_NAME = "shield_data.db"
MAX_ACCOUNTS_PER_USER = 20

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS shields (
                    user_id TEXT,
                    chat_id TEXT,
                    account_name TEXT,
                    end_time TEXT
                )''')
    conn.commit()
    conn.close()

def add_shield_db(user_id, chat_id, account_name, end_time_iso):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("INSERT INTO shields (user_id, chat_id, account_name, end_time) VALUES (?, ?, ?, ?)",
              (user_id, str(chat_id), account_name, end_time_iso))
    conn.commit()
    conn.close()

def remove_shield_db(user_id, account_name):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("DELETE FROM shields WHERE user_id=? AND account_name=?", (user_id, account_name))
    conn.commit()
    conn.close()

def get_user_shields_db(user_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT account_name, end_time, chat_id FROM shields WHERE user_id=?", (user_id,))
    data = c.fetchall()
    conn.close()
    return data

def get_all_shields_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT user_id, chat_id, account_name, end_time FROM shields")
    data = c.fetchall()
    conn.close()
    return data

def count_user_accounts(user_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM shields WHERE user_id=?", (user_id,))
    n = c.fetchone()[0]
    conn.close()
    return n

scheduler = AsyncIOScheduler()

async def send_message(bot, chat_id, text):
    try:
        await bot.send_message(chat_id=chat_id, text=text, parse_mode='Markdown')
    except Exception as e:
        print("Failed to send message to", chat_id, e)

def schedule_reminders_for(app, user_id, chat_id, account_name, end_time_iso):
    end = datetime.fromisoformat(end_time_iso)
    now = datetime.now()
    # schedule 1 hour before, 5 minutes before, and at end time
    one_hour = end - timedelta(hours=1)
    five_min = end - timedelta(minutes=5)

    if one_hour > now:
        scheduler.add_job(lambda: asyncio.create_task(send_message(app.bot, chat_id, f"⚠️ Shield akun *{account_name}* sisa 1 jam!")),
                          trigger='date', run_date=one_hour, id=f"{user_id}_{account_name}_1h", replace_existing=True)
    if five_min > now:
        scheduler.add_job(lambda: asyncio.create_task(send_message(app.bot, chat_id, f"⏰ Shield akun *{account_name}* sisa 5 menit!")),
                          trigger='date', run_date=five_min, id=f"{user_id}_{account_name}_5m", replace_existing=True)
    if end > now:
        scheduler.add_job(lambda: asyncio.create_task(send_message(app.bot, chat_id, f"💥 Shield akun *{account_name}* sudah HABIS! Segera aktifkan lagi.")),
                          trigger='date', run_date=end, id=f"{user_id}_{account_name}_end", replace_existing=True)

def load_and_schedule_all(app):
    # schedule all future reminders from DB (call at startup)
    all_shields = get_all_shields_db()
    for user_id, chat_id, account_name, end_time in all_shields:
        try:
            schedule_reminders_for(app, user_id, chat_id, account_name, end_time)
        except Exception as e:
            print("Error scheduling for", account_name, e)

async def setshield(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 3:
        await update.message.reply_text("Gunakan: /setshield <nama_akun> <durasi> <jam>\nContoh: /setshield NalaWuxin 7days 02:45")
        return

    user_id = str(update.message.from_user.id)
    chat_id = update.message.chat_id
    account_name = context.args[0]
    try:
        days = int(context.args[1].replace("days", ""))
    except:
        await update.message.reply_text("Format durasi salah. Contoh format yang benar: 7days")
        return
    try:
        hour, minute = map(int, context.args[2].split(":"))
    except:
        await update.message.reply_text("Format jam salah. Contoh: 02:45")
        return

    # check limit
    if count_user_accounts(user_id) >= MAX_ACCOUNTS_PER_USER:
        await update.message.reply_text(f"⚠️ Batas maksimal {MAX_ACCOUNTS_PER_USER} akun tercapai.")
        return

    now = datetime.now()
    shield_end = datetime(now.year, now.month, now.day, hour, minute) + timedelta(days=days)

    add_shield_db(user_id, chat_id, account_name, shield_end.isoformat())
    # schedule reminders
    schedule_reminders_for(context.application, user_id, chat_id, account_name, shield_end.isoformat())

    await update.message.reply_text(f"✅ Shield *{account_name}* diset selama {days} hari. Aku akan ingatkan 1 jam, 5 menit sebelumnya, dan saat habis.", parse_mode='Markdown')

async def listshield(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)
    rows = get_user_shields_db(user_id)
    if not rows:
        await update.message.reply_text("Belum ada shield yang diset.")
        return
    msg = "🛡️ Daftar Shield Akun:\n"
    for account_name, end_time, chat_id in rows:
        end = datetime.fromisoformat(end_time)
        remaining = end - datetime.now()
        days = remaining.days
        hours = remaining.seconds // 3600
        minutes = (remaining.seconds % 3600) // 60
        msg += f"• {account_name}: {days} hari {hours} jam {minutes} menit tersisa\n"
    await update.message.reply_text(msg)

async def removeshield(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 1:
        await update.message.reply_text("Gunakan: /removeshield <nama_akun>")
        return
    user_id = str(update.message.from_user.id)
    account_name = context.args[0]
    remove_shield_db(user_id, account_name)
    # remove scheduled jobs if exist
    for suffix in ['_1h', '_5m', '_end']:
        job_id = f"{user_id}_{account_name}{suffix}"
        try:
            scheduler.remove_job(job_id)
        except:
            pass
    await update.message.reply_text(f"❌ Shield *{account_name}* dihapus dari daftar pengingat.", parse_mode='Markdown')

async def daily_summary_job(app):
    # sends a daily summary to each chat_id with their shields
    all_shields = get_all_shields_db()
    if not all_shields:
        return
    # group by chat_id
    by_chat = {}
    for user_id, chat_id, account_name, end_time in all_shields:
        by_chat.setdefault(chat_id, []).append((account_name, end_time))
    for chat_id, items in by_chat.items():
        msg = "📋 *Ringkasan Shield Hari Ini*\n"
        for account_name, end_time in items:
            end = datetime.fromisoformat(end_time)
            remaining = end - datetime.now()
            days = remaining.days
            hours = remaining.seconds // 3600
            minutes = (remaining.seconds % 3600) // 60
            msg += f"• {account_name}: {days} hari {hours} jam {minutes} menit\n"
        await send_message(app.bot, chat_id, msg)

async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Halo! Saya *Bot_ShieldDuration* - pengingat shield Lords Mobile.\nGunakan /setshield untuk mulai.", parse_mode='Markdown')

def main():
    init_db()
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("setshield", setshield))
    app.add_handler(CommandHandler("listshield", listshield))
    app.add_handler(CommandHandler("removeshield", removeshield))

    # start scheduler and load existing shields
    scheduler.start()
    # schedule daily summary at 08:00 every day
    scheduler.add_job(lambda: asyncio.create_task(daily_summary_job(app)), CronTrigger(hour=8, minute=0), id="daily_summary", replace_existing=True)
    load_and_schedule_all(app)

    print("🤖 Bot_ShieldDuration berjalan 24/7...")
    app.run_polling()

if __name__ == "__main__":
    main()

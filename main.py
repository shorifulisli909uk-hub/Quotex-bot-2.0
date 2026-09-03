import re
import asyncio
import datetime
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, filters, ContextTypes
from quotexapi.stable_api import Quotex

QUOTEX_EMAIL = "raihanusa77uk@gmail.com"
QUOTEX_PASSWORD = "Asdf@1234"
TELEGRAM_BOT_TOKEN = "8659731733:AAGBbQGmUhTd1aDzBAk6cSSseC65cjBV33I"
ADMIN_ID = 7047896730

client = None

async def init_quotex():
    global client
    client = Quotex(email=QUOTEX_EMAIL, password=QUOTEX_PASSWORD)
    check, reason = await client.connect()
    if check:
        print("✅ Quotex connected successfully!")
    else:
        print(f"❌ Quotex Connection Failed: {reason}")

async def get_candle_status(pair: str, time_str: str) -> str:
    clean_pair = re.sub(r'[^A-Z0-9]', '', pair.upper())
    if "OTC" in pair.upper() and not clean_pair.endswith("OTC"):
        clean_pair += "OTC"
    
    formatted_pair = clean_pair.replace("OTC", "_otc")
    
    now = datetime.datetime.now()
    hour, minute = map(int, time_str.split(":"))
    dt = datetime.datetime(now.year, now.month, now.day, hour, minute)
    timestamp = int(dt.timestamp())

    try:
        candles = await client.get_candles(formatted_pair, timestamp, 60, 1)
        if candles and len(candles) > 0:
            candle = candles[0]
            if candle['close'] > candle['open']:
                return "CALL"
            elif candle['close'] < candle['open']:
                return "PUT"
            return "DOJI"
    except Exception as e:
        print(f"Data Fetch Error ({pair} - {time_str}): {e}")
    
    return "UNKNOWN"

def adjust_time(time_str: str, minutes_offset: int) -> str:
    t = datetime.datetime.strptime(time_str, "%H:%M")
    adjusted = t + datetime.timedelta(minutes=minutes_offset)
    return adjusted.strftime("%H:%M")

async def process_sectioned_signals(text: str) -> str:
    lines = text.split('\n')
    
    current_mode = "NORMAL"
    report = "📊 **SIGNAL RESULT REPORT** 📊\n"
    report += "━━━━━━━━━━━━━━━━━━━━━\n"

    sections_found = 0

    for line in lines:
        clean_line = line.strip()
        if not clean_line:
            continue

        upper_line = clean_line.upper()
        if any(keyword in upper_line for keyword in ["NORMAL", "DIRECT", "FUTURE"]):
            current_mode = "NORMAL"
            report += "\n🎯 **[NORMAL STRATEGY]**\n"
            sections_found += 1
            continue
        elif any(keyword in upper_line for keyword in ["SAME CANDLE", "RG AI", "SAME"]):
            current_mode = "SAME"
            report += "\n💸 **[SAME CANDLE STRATEGY]**\n"
            sections_found += 1
            continue
        elif any(keyword in upper_line for keyword in ["BLACKOUT", "OPPOSITE", "REVERSAL"]):
            current_mode = "BLACKOUT"
            report += "\n☣️ **[BLACKOUT STRATEGY]**\n"
            sections_found += 1
            continue

        time_match = re.search(r'\b([01]?\d|2[0-3]):([0-5]\d)\b', clean_line)
        pair_match = re.search(r'\b([A-Z]{6}(?:[-_]?OTC)?|[A-Z]{3}/[A-Z]{3}(?:[-_]?OTC)?)\b', clean_line, re.IGNORECASE)

        if time_match and pair_match:
            time_str = time_match.group(0)
            pair = pair_match.group(0).upper()

            if current_mode == "NORMAL":
                dir_match = re.search(r'\b(CALL|PUT|BUY|SELL)\b', clean_line, re.IGNORECASE)
                if dir_match:
                    raw_dir = dir_match.group(0).upper()
                    target_direction = "CALL" if raw_dir in ["CALL", "BUY"] else "PUT"
                    
                    main_res = await get_candle_status(pair, time_str)
                    if main_res == target_direction:
                        report += f"🔹 `{time_str}` **{pair}** ➔ ✅ WIN ({target_direction})\n"
                    else:
                        mtg_time = adjust_time(time_str, 1)
                        mtg_res = await get_candle_status(pair, mtg_time)
                        if mtg_res == target_direction:
                            report += f"🔹 `{time_str}` **{pair}** ➔ ✅¹ WIN ({target_direction})\n"
                        else:
                            report += f"🔹 `{time_str}` **{pair}** ➔ ❌ LOSS ({target_direction})\n"

            elif current_mode == "SAME":
                prev_time = adjust_time(time_str, -1)
                prev_res = await get_candle_status(pair, prev_time)
                target_direction = prev_res if prev_res in ["CALL", "PUT"] else "CALL"

                main_res = await get_candle_status(pair, time_str)
                if main_res == target_direction:
                    report += f"🔹 `{time_str}` **{pair}** ➔ ✅ WIN ({target_direction})\n"
                else:
                    mtg_time = adjust_time(time_str, 1)
                    mtg_res = await get_candle_status(pair, mtg_time)
                    if mtg_res == target_direction:
                        report += f"🔹 `{time_str}` **{pair}** ➔ ✅¹ WIN ({target_direction})\n"
                    else:
                        report += f"🔹 `{time_str}` **{pair}** ➔ ❌ LOSS ({target_direction})\n"

            elif current_mode == "BLACKOUT":
                prev_time = adjust_time(time_str, -1)
                prev_res = await get_candle_status(pair, prev_time)
                target_direction = "PUT" if prev_res == "CALL" else "CALL"

                main_res = await get_candle_status(pair, time_str)
                if main_res == target_direction:
                    report += f"🔹 `{time_str}` **{pair}** ➔ ✅ WIN ({target_direction})\n"
                else:
                    mtg_time = adjust_time(time_str, 1)
                    mtg_res = await get_candle_status(pair, mtg_time)
                    if mtg_res == target_direction:
                        report += f"🔹 `{time_str}` **{pair}** ➔ ✅¹ WIN ({target_direction})\n"
                    else:
                        report += f"🔹 `{time_str}` **{pair}** ➔ ❌ LOSS ({target_direction})\n"

    if sections_found == 0 and "🔹" not in report:
        return "❌ **কোনো সঠিক সিগন্যাল পাওয়া যায়নি!**"

    return report

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    msg = await update.message.reply_text("⏳ সিগন্যাল চেক করা হচ্ছে...")

    result_report = await process_sectioned_signals(user_text)
    await msg.edit_text(result_report, parse_mode="Markdown")

async def admin_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    
    msg = f"⚙️ **Bot Admin Settings**\n"
    msg += f"━━━━━━━━━━━━━━━━━━━━━\n"
    msg += f"👤 **Admin ID:** `{ADMIN_ID}`\n"
    msg += f"📧 **Quotex Email:** `{QUOTEX_EMAIL}`\n"
    msg += f"🔑 **Quotex Pass:** `{QUOTEX_PASSWORD}`\n\n"
    msg += "⚙️ **Commands to Change:**\n"
    msg += "` /setemail <new_email>`\n"
    msg += "` /setpass <new_password>`"
    
    await update.message.reply_text(msg, parse_mode="Markdown")

async def set_email(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global QUOTEX_EMAIL
    if update.effective_user.id != ADMIN_ID:
        return

    if context.args:
        QUOTEX_EMAIL = context.args[0]
        await init_quotex()
        await update.message.reply_text(f"✅ Quotex Email updated to: `{QUOTEX_EMAIL}`", parse_mode="Markdown")

async def set_pass(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global QUOTEX_PASSWORD
    if update.effective_user.id != ADMIN_ID:
        return

    if context.args:
        QUOTEX_PASSWORD = context.args[0]
        await init_quotex()
        await update.message.reply_text("✅ Quotex Password updated successfully!")

async def main():
    await init_quotex()
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("settings", admin_settings))
    app.add_handler(CommandHandler("setemail", set_email))
    app.add_handler(CommandHandler("setpass", set_pass))
    
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    
    print("🤖 Public Result Bot Active...")
    await app.run_polling()

if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())

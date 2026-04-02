import asyncio
import logging
import os
from typing import Iterable

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters

import web_scraper_updated as web_scraper


MAX_MESSAGE_LEN = 4096
MULTI_MODE_CHATS: set[int] = set()
LOGGER = logging.getLogger(__name__)


# ---------------- UTIL ---------------- #

def is_valid_url(url: str) -> bool:
    return url.startswith("http://") or url.startswith("https://")


def scrape_single_with_existing_logic(url: str):
    output = []
    web_scraper.extract_products_info(url, output)
    product_info = output[0] if output else {}
    LOGGER.info("Full product_info from extractor for %s: %s", url, product_info)
    return product_info


def safe_message(text: str) -> str:
    if len(text) <= MAX_MESSAGE_LEN:
        return text
    return text[: MAX_MESSAGE_LEN - 16] + "\n\n...truncated"


def split_message_chunks(text: str) -> list[str]:
    if len(text) <= MAX_MESSAGE_LEN:
        return [text]

    chunks: list[str] = []
    remaining = text

    while len(remaining) > MAX_MESSAGE_LEN:
        split_at = remaining.rfind("\n\n---\n\n", 0, MAX_MESSAGE_LEN)
        if split_at == -1:
            split_at = remaining.rfind("\n", 0, MAX_MESSAGE_LEN)
        if split_at == -1:
            split_at = MAX_MESSAGE_LEN

        chunk = remaining[:split_at].strip()
        if chunk:
            chunks.append(chunk)
        remaining = remaining[split_at:].lstrip()

    if remaining:
        chunks.append(remaining)

    return chunks


async def reply_text_chunked(update: Update, text: str) -> None:
    if not update.message:
        return

    for chunk in split_message_chunks(text):
        await update.message.reply_text(safe_message(chunk))


def format_product_result(url: str, product_info: dict) -> str:
    priority_fields = ["Title", "Price", "Rating"]
    other_fields = [key for key in product_info.keys() if key not in priority_fields]
    ordered_fields = priority_fields + other_fields

    lines = [f"URL: {url}"]
    for key in ordered_fields:
        value = product_info.get(key)

        if isinstance(value, str):
            value = value.strip()

        if value in (None, "", [], {}, ()):
            continue

        lines.append(f"{key}: {value}")

    if len(lines) == 1:
        lines.append("No non-empty product fields found")

    return "\n".join(lines)


def parse_urls_from_lines(lines: Iterable[str]) -> list[str]:
    return [line.strip() for line in lines if line.strip()]


# ---------------- CORE ---------------- #

async def process_urls_sequentially(urls: list[str]) -> list[str]:
    results: list[str] = []

    for url in urls:
        if not is_valid_url(url):
            results.append(f"URL: {url}\nError: Invalid URL")
            continue

        try:
            product_info = await asyncio.to_thread(scrape_single_with_existing_logic, url)

            if not product_info:
                results.append(f"URL: {url}\nError: Failed to scrape URL")
                continue

            results.append(format_product_result(url, product_info))

        except Exception as exc:
            results.append(f"URL: {url}\nError: {exc}")

    return results


# ---------------- COMMANDS ---------------- #

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message:
        await update.message.reply_text(
            "🤖 Amazon Scraper Bot\n\n"
            "Commands:\n"
            "/scrape <url>\n"
            "/multi → send multiple URLs\n"
            "Upload .txt file → multiple URLs\n"
        )


async def scrape_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return

    if not context.args:
        await update.message.reply_text("Usage: /scrape <url>")
        return

    url = " ".join(context.args).strip()

    if not is_valid_url(url):
        await update.message.reply_text("Invalid URL")
        return

    await update.message.reply_text("Scraping... ⏳")

    try:
        product_info = await asyncio.to_thread(scrape_single_with_existing_logic, url)
    except Exception as exc:
        await update.message.reply_text(safe_message(f"Error: {exc}"))
        return

    if not product_info:
        await update.message.reply_text("Failed to scrape URL")
        return

    await reply_text_chunked(update, format_product_result(url, product_info))


async def multi_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.effective_chat:
        return

    MULTI_MODE_CHATS.add(update.effective_chat.id)

    await update.message.reply_text(
        "Send URLs like this:\n\n"
        "https://...\nhttps://...\nhttps://..."
    )


async def multi_input_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.effective_chat:
        return

    chat_id = update.effective_chat.id

    urls = parse_urls_from_lines(update.message.text.splitlines()) if update.message.text else []

    if not urls:
        if chat_id in MULTI_MODE_CHATS:
            MULTI_MODE_CHATS.discard(chat_id)
            await update.message.reply_text("No URLs found. Use /multi again.")
        return

    # If user did not start /multi, treat plain message with one URL as a single scrape.
    if chat_id not in MULTI_MODE_CHATS:
        if len(urls) != 1:
            await update.message.reply_text(
                "Send one URL directly, or use /multi for multiple URLs."
            )
            return

        url = urls[0]

        if not is_valid_url(url):
            await update.message.reply_text("Invalid URL")
            return

        await update.message.reply_text("Scraping... ⏳")

        try:
            product_info = await asyncio.to_thread(scrape_single_with_existing_logic, url)
        except Exception as exc:
            await update.message.reply_text(safe_message(f"Error: {exc}"))
            return

        if not product_info:
            await update.message.reply_text("Failed to scrape URL")
            return

        await reply_text_chunked(update, format_product_result(url, product_info))
        return

    MULTI_MODE_CHATS.discard(chat_id)

    await update.message.reply_text(f"Processing {len(urls)} URLs...")

    results = await process_urls_sequentially(urls)

    await reply_text_chunked(update, "\n\n---\n\n".join(results))


async def file_upload_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.message.document:
        return

    document = update.message.document

    if not document.file_name or not document.file_name.lower().endswith(".txt"):
        await update.message.reply_text("Only .txt files are supported")
        return

    try:
        telegram_file = await document.get_file()
        file_bytes = await telegram_file.download_as_bytearray()

        text = bytes(file_bytes).decode("utf-8", errors="replace")
        urls = parse_urls_from_lines(text.splitlines())

        if not urls:
            await update.message.reply_text("No URLs found in file")
            return

        await update.message.reply_text(f"Processing {len(urls)} URLs from file...")

        results = await process_urls_sequentially(urls)

        await reply_text_chunked(update, "\n\n---\n\n".join(results))

    except Exception as exc:
        await update.message.reply_text(safe_message(f"Error: {exc}"))


# ---------------- APP ---------------- #

def main():
    load_dotenv()

    token = os.getenv("TELEGRAM_BOT_TOKEN")

    if not token:
        raise RuntimeError(
            "❌ TELEGRAM_BOT_TOKEN missing.\n"
            "Create .env file and add:\n"
            "TELEGRAM_BOT_TOKEN=your_token"
        )

    logging.basicConfig(level=logging.INFO)
    print("🚀 Bot starting...")

    app = ApplicationBuilder().token(token).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("scrape", scrape_command))
    app.add_handler(CommandHandler("multi", multi_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, multi_input_handler))
    app.add_handler(MessageHandler(filters.Document.ALL, file_upload_handler))

    print("✅ Bot running...")

    # ✅ FINAL FIX (IMPORTANT)

    # 🔥 IMPORTANT FIX (event loop create)
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    app.run_polling()


if __name__ == "__main__":
    main()
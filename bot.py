import asyncio
import os
from typing import Iterable

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

import web_scraper


MAX_MESSAGE_LEN = 4096
MULTI_MODE_CHATS: set[int] = set()


# ---------------- UTIL ---------------- #

def is_valid_url(url: str) -> bool:
    return url.startswith("http://") or url.startswith("https://")


def scrape_single_with_existing_logic(url: str):
    output = []
    web_scraper.extract_products_info(url, output)
    return output[0] if output else {}


def safe_message(text: str) -> str:
    if len(text) <= MAX_MESSAGE_LEN:
        return text
    return text[:4000] + "\n\n...truncated"


def format_product_result(url: str, product_info: dict) -> str:
    return (
        f"URL: {url}\n"
        f"Title: {product_info.get('Title')}\n"
        f"Price: {product_info.get('Price')}\n"
        f"Rating: {product_info.get('Rating')}"
    )


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

    await update.message.reply_text(
        safe_message(format_product_result(url, product_info))
    )


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

    if chat_id not in MULTI_MODE_CHATS:
        return

    MULTI_MODE_CHATS.discard(chat_id)

    urls = parse_urls_from_lines(update.message.text.splitlines()) if update.message.text else []

    if not urls:
        await update.message.reply_text("No URLs found. Use /multi again.")
        return

    await update.message.reply_text(f"Processing {len(urls)} URLs...")

    results = await process_urls_sequentially(urls)

    await update.message.reply_text(
        safe_message("\n\n---\n\n".join(results))
    )


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

        await update.message.reply_text(
            safe_message("\n\n---\n\n".join(results))
        )

    except Exception as exc:
        await update.message.reply_text(safe_message(f"Error: {exc}"))


# ---------------- APP ---------------- #

def build_app() -> Application:
    load_dotenv()

    token = os.getenv("TELEGRAM_BOT_TOKEN")

    if not token:
        raise RuntimeError(
            "❌ TELEGRAM_BOT_TOKEN missing.\n"
            "Create .env file and add:\n"
            "TELEGRAM_BOT_TOKEN=your_token"
        )

    app = Application.builder().token(token).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("scrape", scrape_command))
    app.add_handler(CommandHandler("multi", multi_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, multi_input_handler))
    app.add_handler(MessageHandler(filters.Document.ALL, file_upload_handler))

    return app


def main() -> None:
    try:
        print("🚀 Bot starting...")
        app = build_app()
        print("✅ Bot running...")
        app.run_polling()
    except RuntimeError as exc:
        print(exc)


if __name__ == "__main__":
    main()
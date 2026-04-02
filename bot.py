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
    app.run_polling()


if __name__ == "__main__":
    main()
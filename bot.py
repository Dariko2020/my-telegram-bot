# УДАЛЕНО: TOKEN больше не определяется здесь. Он будет браться внутри main()
# TOKEN = os.environ.get("BOT_TOKEN") # Эту строку убираем отсюда
# ...
def main() -> None:
    # ...
    token = os.environ.get("BOT_TOKEN") # <--- ВОТ ЭТОТ СТРОКА ВАЖНА
    if not token:
        logger.error("BOT_TOKEN не найден в переменных окружения. Убедитесь, что вы его установили на Render!")
        exit(1)

    app = ApplicationBuilder().token(token).build()
    # ...
    PORT = int(os.environ.get("PORT", "8080"))
    WEBHOOK_URL_BASE = os.environ.get("RENDER_EXTERNAL_URL") # <--- И ЭТА

    if WEBHOOK_URL_BASE:
        full_webhook_url = f"{WEBHOOK_URL_BASE}/{token}"
        print(f"🌐 Устанавливаю вебхук в Telegram: {full_webhook_url}")
        asyncio.run(app.bot.set_webhook(url=full_webhook_url)) # <--- И ЭТА
        app.run_webhook(
            listen="0.0.0.0",
            port=PORT,
            url_path=token,
            webhook_url=full_webhook_url
        )
        print(f"✅ ULX Ukraine Bot запущен с вебхуком на {full_webhook_url}")
    else:
        print("✅ ULX Ukraine Bot запущен локально (polling)! Для Render установите RENDER_EXTERNAL_URL.")
        app.run_polling(allowed_updates=Update.ALL_TYPES)

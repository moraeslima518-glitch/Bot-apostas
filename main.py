app = Flask(__name__)


@app.route("/")
def home():
    return "Bot Sniper Pro rodando."


def rodar_telegram():
    log.info("Iniciando bot no Telegram...")
    while True:
        try:
            bot.infinity_polling(none_stop=True, interval=0, timeout=20)
        except Exception as e:
            log.error(f"Polling caiu, reiniciando em 5s: {e}")
            time.sleep(5)


if __name__ == "__main__":
    carregar_chats()

    t1 = threading.Thread(target=monitoramento_ao_vivo, daemon=True)
    t1.start()

    t2 = threading.Thread(target=rodar_telegram, daemon=True)
    t2.start()
    
    app.run(host="0.0.0.0", port=5000)

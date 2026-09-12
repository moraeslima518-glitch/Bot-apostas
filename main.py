import os
import time
import threading
import requests
from flask import Flask
from datetime import datetime, timedelta

# Cria o servidor web para o Render detectar a porta aberta
app = Flask(__name__)

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")
RAPIDAPI_KEY = os.environ.get("RAPIDAPI_KEY")

@app.route('/')
def home():
    return "Bot de Apostas Online!", 200

def enviar_mensagem_telegram(texto):
    if not TELEGRAM_TOKEN or not CHAT_ID:
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": texto, "parse_mode": "Markdown"}
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"Erro Telegram: {e}")

def enviar_resumo_jogos_dia():
    if not RAPIDAPI_KEY:
        return
    hoje = datetime.now().strftime("%Y-%m-%d")
    headers = {
        'x-rapidapi-host': "v3.football.api-sports.io",
        'x-rapidapi-key': RAPIDAPI_KEY
    }
    url = f"https://v3.football.api-sports.io/fixtures?date={hoje}"
    try:
        response = requests.get(url, headers=headers, timeout=15)
        partidas = response.json().get('response', [])
        jogos = []
        for p in partidas:
            data_utc = datetime.strptime(p['fixture']['date'], "%Y-%m-%dT%H:%M:%S%z")
            hora_br = data_utc - timedelta(hours=3)
            if hora_br.hour >= 7:
                jogos.append(f"⚽ *{hora_br.strftime('%H:%M')}* - {p['teams']['home']['name']} x {p['teams']['away']['name']} _({p['league']['name']})_")
        
        msg = "📋 *RESUMO DE JOGOS DO DIA (A partir das 07:00)* 📋\n\n" + "\n".join(jogos[:30]) if jogos else "⚠️ Nenhum jogo hoje a partir das 07:00."
        enviar_mensagem_telegram(msg)
    except Exception as e:
        print(f"Erro API: {e}")

def loop_bot():
    time.sleep(5)
    enviar_resumo_jogos_dia()
    while True:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Checando partidas...")
        time.sleep(300)

if __name__ == "__main__":
    # Inicia a busca dos jogos em segundo plano
    threading.Thread(target=loop_bot, daemon=True).start()
    
    # Abre a porta web para o Render ficar satisfeito
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

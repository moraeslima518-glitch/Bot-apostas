import os
import time
import threading
import requests
from flask import Flask
from datetime import datetime, timedelta

# Inicializa a aplicação Flask para escutar na porta do Render
app = Flask(__name__)

# Configurações das Variáveis de Ambiente no Render
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")
RAPIDAPI_KEY = os.environ.get("RAPIDAPI_KEY")

@app.route('/')
def home():
    """Rota para o UptimeRobot pingar e manter o serviço ativo."""
    return "Bot de Apostas Online!", 200

def enviar_mensagem_telegram(texto):
    if not TELEGRAM_TOKEN or not CHAT_ID:
        print("Erro: TELEGRAM_TOKEN ou CHAT_ID ausente.")
        return
        
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": texto,
        "parse_mode": "Markdown"
    }
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"Erro ao enviar Telegram: {e}")

def enviar_resumo_jogos_dia():
    if not RAPIDAPI_KEY:
        print("Erro: RAPIDAPI_KEY ausente.")
        return

    hoje = datetime.now().strftime("%Y-%m-%d")
    headers = {
        'x-rapidapi-host': "v3.football.api-sports.io",
        'x-rapidapi-key': RAPIDAPI_KEY
    }
    url = f"https://v3.football.api-sports.io/fixtures?date={hoje}"
    
    try:
        response = requests.get(url, headers=headers, timeout=15)
        dados = response.json()
        partidas = dados.get('response', [])
        
        jogos_filtrados = []

        for partida in partidas:
            data_str = partida['fixture']['date']
            data_utc = datetime.strptime(data_str, "%Y-%m-%dT%H:%M:%S%z")
            hora_br = data_utc - timedelta(hours=3)
            
            if hora_br.hour >= 7:
                time_casa = partida['teams']['home']['name']
                time_fora = partida['teams']['away']['name']
                nome_liga = partida['league']['name']
                horario_formatado = hora_br.strftime("%H:%M")
                
                jogos_filtrados.append(f"⚽ *{horario_formatado}* - {time_casa} x {time_fora} _({nome_liga})_")

        if jogos_filtrados:
            mensagem = "📋 *RESUMO DE JOGOS DO DIA (A partir das 07:00)* 📋\n\n" + "\n".join(jogos_filtrados[:30])
        else:
            mensagem = "⚠️ Nenhum jogo encontrado para hoje a partir das 07:00."

        enviar_mensagem_telegram(mensagem)
        print("Resumo enviado para o Telegram.")

    except Exception as e:
        print(f"Erro na requisição: {e}")

def loop_bot():
    """Loop contínuo executado em segundo plano."""
    time.sleep(5)  # Aguarda 5 segundos após o boot
    enviar_resumo_jogos_dia()
    
    while True:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Checando alertas pré-jogo e ao vivo...")
        # Adicione aqui sua função principal de monitoramento
        time.sleep(300)

if __name__ == "__main__":
    # Inicia a thread do bot em segundo plano
    t = threading.Thread(target=loop_bot, daemon=True)
    t.start()
    
    # Inicia o servidor Web Flask na porta do Render
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

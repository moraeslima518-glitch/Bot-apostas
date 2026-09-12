import os
import time
import threading
import requests
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime, timedelta

# Configurações das Variáveis de Ambiente no Render
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")
RAPIDAPI_KEY = os.environ.get("RAPIDAPI_KEY")

# Servidor HTTP simples nativo do Python para responder ao Render e UptimeRobot
class SimpleHTTPRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        self.wfile.write(b"Bot de Apostas Online!")

    def log_message(self, format, *args):
        return  # Desativa logs HTTP para nao poluir o console

def rodar_servidor_web():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(('0.0.0.0', port), SimpleHTTPRequestHandler)
    print(f"Servidor Web ativo na porta {port}")
    server.serve_forever()

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
        print("Resumo enviado com sucesso para o Telegram!")

    except Exception as e:
        print(f"Erro na requisição da API: {e}")

def loop_bot():
    time.sleep(3)  # Aguarda 3 segundos
    enviar_resumo_jogos_dia()
    
    while True:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Checando alertas pré-jogo e ao vivo...")
        time.sleep(300)

if __name__ == "__main__":
    # 1. Inicia o servidor HTTP nativo em uma thread separada
    t_web = threading.Thread(target=rodar_servidor_web, daemon=True)
    t_web.start()
    
    # 2. Inicia o loop do bot
    loop_bot()

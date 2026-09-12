import os
import time
import requests
import schedule
import pytz
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY")

FUSO_BR = pytz.timezone("America/Sao_Paulo")

class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Bot de Apostas Ativo!")
        
    def do_HEAD(self):
        self.send_response(200)
        self.end_headers()

def iniciar_servidor_web():
    port = int(os.getenv("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
    server.serve_forever()

def enviar_mensagem_telegram(texto):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": texto, "parse_mode": "Markdown"}
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"Erro Telegram: {e}")

def obter_jogos():
    url = "https://api-football-v1.p.rapidapi.com/v3/fixtures"
    headers = {
        "X-RapidAPI-Key": RAPIDAPI_KEY,
        "X-RapidAPI-Host": "api-football-v1.p.rapidapi.com"
    }
    
    # 1. Busca TODAS as partidas ao vivo do mundo nesse exato instante
    try:
        res = requests.get(url, headers=headers, params={"live": "all"}, timeout=15)
        dados = res.json()
        
        if "errors" in dados and dados["errors"]:
            enviar_mensagem_telegram(f"⚠️ *Erro na API:* `{dados['errors']}`")
            return []
            
        jogos = dados.get("response", [])
        if jogos:
            return jogos
    except Exception as e:
        print(f"Erro busca ao vivo: {e}")

    # 2. Se não houver jogos ao vivo, busca os jogos da data de hoje
    hoje = datetime.now(FUSO_BR).strftime("%Y-%m-%d")
    try:
        res = requests.get(url, headers=headers, params={"date": hoje}, timeout=15)
        dados = res.json()
        
        if "errors" in dados and dados["errors"]:
            enviar_mensagem_telegram(f"⚠️ *Erro na API:* `{dados['errors']}`")
            return []
            
        return dados.get("response", [])
    except Exception as e:
        print(f"Erro busca por data: {e}")
        return []

def enviar_resumo():
    jogos = obter_jogos()
    
    if not jogos:
        enviar_mensagem_telegram("⚽ *Central de Jogos*\n\nNenhuma partida ao vivo ou agendada encontrada no momento.")
        return

    mensagem = f"⚽ *Partidas Encontradas ({datetime.now(FUSO_BR).strftime('%H:%M')})*\n\n"
    
    for item in jogos[:15]:
        liga = item["league"]["name"]
        pais = item["league"]["country"]
        time_casa = item["teams"]["home"]["name"]
        time_fora = item["teams"]["away"]["name"]
        
        gols_casa = item["goals"]["home"] if item["goals"]["home"] is not None else 0
        gols_fora = item["goals"]["away"] if item["goals"]["away"] is not None else 0
        status = item["fixture"]["status"]["short"]
        
        mensagem += f"🌎 *{pais} - {liga}*\n"
        mensagem += f"⚽ {time_casa} {gols_casa} x {gols_fora} {time_fora} [{status}]\n\n"

    if len(jogos) > 15:
        mensagem += f"_... e mais {len(jogos) - 15} partidas rodando no mundo._"

    enviar_mensagem_telegram(mensagem)

# Iniciar thread do servidor HTTP
thread_web = threading.Thread(target=iniciar_servidor_web, daemon=True)
thread_web.start()

# Teste imediato
enviar_resumo()

# Loop do bot
while True:
    time.sleep(60)

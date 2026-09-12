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
    print(f"Servidor HTTP rodando na porta {port}...")
    server.serve_forever()

def enviar_mensagem_telegram(texto):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": texto, "parse_mode": "Markdown"}
    try:
        response = requests.post(url, json=payload, timeout=10)
        return response.status_code == 200
    except Exception as e:
        print(f"Erro ao enviar Telegram: {e}")
        return False

def obter_jogos_do_dia():
    hoje = datetime.now(FUSO_BR).strftime("%Y-%m-%d")
    print(f"--- INICIANDO BUSCA DE JOGOS PARA A DATA: {hoje} ---")
    
    url = "https://api-football-v1.p.rapidapi.com/v3/fixtures"
    headers = {
        "X-RapidAPI-Key": RAPIDAPI_KEY,
        "X-RapidAPI-Host": "api-football-v1.p.rapidapi.com"
    }
    params = {"date": hoje, "timezone": "America/Sao_Paulo"}

    try:
        res = requests.get(url, headers=headers, params=params, timeout=15)
        print(f"Status da API: {res.status_code}")
        dados = res.json()
        
        # Imprime no log exatamente o que a API respondeu
        if "errors" in dados and dados["errors"]:
            print(f"ERRO DA API: {dados['errors']}")
            enviar_mensagem_telegram(f"⚠️ *Erro na API-Football:* `{dados['errors']}`")
            return []
            
        jogos = dados.get("response", [])
        print(f"Quantidade de jogos retornados: {len(jogos)}")
        
        # Se vier zerado por data, tenta puxar os jogos ao vivo (live)
        if not jogos:
            print("Tentando buscar jogos ao vivo (live)...")
            res_live = requests.get(url, headers=headers, params={"live": "all"}, timeout=15)
            if res_live.status_code == 200:
                jogos = res_live.json().get("response", [])
                print(f"Quantidade de jogos ao vivo encontrados: {len(jogos)}")

        return jogos

    except Exception as e:
        print(f"Exceção no código: {e}")
        return []

def enviar_resumo_diario():
    jogos = obter_jogos_do_dia()
    
    if not jogos:
        enviar_mensagem_telegram("⚽ *Resumo do Dia*\n\nNenhum jogo encontrado para hoje.")
        return

    mensagem = f"⚽ *Jogos do Dia ({datetime.now(FUSO_BR).strftime('%d/%m/%Y')})*\n\n"
    for item in jogos[:20]:
        liga = item["league"]["name"]
        time_casa = item["teams"]["home"]["name"]
        time_fora = item["teams"]["away"]["name"]
        data_jogo = item["fixture"]["date"]
        hora = datetime.fromisoformat(data_jogo).astimezone(FUSO_BR).strftime("%H:%M")
        status = item["fixture"]["status"]["short"]
        
        mensagem += f"🏆 *{liga}*\n⏰ {hora} | {time_casa} x {time_fora} ({status})\n\n"

    if len(jogos) > 20:
        mensagem += f"_... e mais {len(jogos) - 20} partidas agendadas._"

    enviar_mensagem_telegram(mensagem)

# Inicia Servidor Web
thread_web = threading.Thread(target=iniciar_servidor_web, daemon=True)
thread_web.start()

# Executa imediatamente ao ligar
enviar_resumo_diario()

# Agendamento diário às 07:00
schedule.every().day.at("07:00").do(enviar_resumo_diario)

while True:
    schedule.run_pending()
    time.sleep(60)

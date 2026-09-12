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

# IDs das Principais Ligas no API-Football:
# 71: Brasileirão Série A | 72: Brasileirão Série B | 39: Premier League | 140: La Liga | 135: Serie A Italia
LIGAS_PRINCIPAIS = [71, 72, 39, 140, 135]

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
        print(f"Erro Telegram: {e}")
        return False

def obter_jogos_do_dia():
    hoje = datetime.now(FUSO_BR).strftime("%Y-%m-%d")
    url = "https://api-football-v1.p.rapidapi.com/v3/fixtures"
    
    headers = {
        "X-RapidAPI-Key": RAPIDAPI_KEY,
        "X-RapidAPI-Host": "api-football-v1.p.rapidapi.com"
    }

    todos_jogos = []

    # 1. Tenta buscar partidas ao vivo primeiro (Garante retorno a qualquer hora do dia)
    try:
        res_live = requests.get(url, headers=headers, params={"live": "all"}, timeout=15)
        if res_live.status_code == 200:
            dados_live = res_live.json()
            if "errors" in dados_live and dados_live["errors"]:
                print(f"Erro na API: {dados_live['errors']}")
            else:
                todos_jogos.extend(dados_live.get("response", []))
    except Exception as e:
        print(f"Exceção Live: {e}")

    # 2. Se não houver jogos ao vivo, busca por data nas principais ligas
    if not todos_jogos:
        for liga_id in LIGAS_PRINCIPAIS:
            params = {
                "date": hoje,
                "league": liga_id,
                "season": datetime.now(FUSO_BR).year,
                "timezone": "America/Sao_Paulo"
            }
            try:
                res = requests.get(url, headers=headers, params=params, timeout=15)
                if res.status_code == 200:
                    dados = res.json()
                    jogos_liga = dados.get("response", [])
                    todos_jogos.extend(jogos_liga)
            except Exception as e:
                print(f"Exceção Liga {liga_id}: {e}")

    return todos_jogos

def enviar_resumo_diario():
    jogos = obter_jogos_do_dia()
    
    if not jogos:
        enviar_mensagem_telegram("⚽ *Resumo de Partidas*\n\nNenhuma partida ao vivo ou agendada para as principais ligas no momento.")
        return

    mensagem = f"⚽ *Jogos Encontrados ({datetime.now(FUSO_BR).strftime('%d/%m/%Y %H:%M')})*\n\n"
    
    for item in jogos[:20]:
        liga = item["league"]["name"]
        time_casa = item["teams"]["home"]["name"]
        time_fora = item["teams"]["away"]["name"]
        data_jogo = item["fixture"]["date"]
        
        try:
            hora = datetime.fromisoformat(data_jogo).astimezone(FUSO_BR).strftime("%H:%M")
        except:
            hora = "--:--"
            
        status = item["fixture"]["status"]["short"]
        
        # Placar se o jogo estiver acontecendo
        gols_casa = item["goals"]["home"]
        gols_fora = item["goals"]["away"]
        placar = f"({gols_casa} x {gols_fora})" if gols_casa is not None else ""

        mensagem += f"🏆 *{liga}*\n⏰ {hora} | {time_casa} {placar} x {time_fora} [Status: {status}]\n\n"

    if len(jogos) > 20:
        mensagem += f"_... e mais {len(jogos) - 20} partidas disponíveis._"

    enviar_mensagem_telegram(mensagem)

# Iniciar thread do servidor web HTTP
thread_web = threading.Thread(target=iniciar_servidor_web, daemon=True)
thread_web.start()

# Envia o teste imediatamente ao iniciar
enviar_resumo_diario()

# Agendamento diário
schedule.every().day.at("07:00").do(enviar_resumo_diario)

while True:
    schedule.run_pending()
    time.sleep(60)

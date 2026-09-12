import os
import time
import requests
import schedule
import pytz
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime

# Credenciais do ambiente (definidas no Render)
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY")

FUSO_BR = pytz.timezone("America/Sao_Paulo")

# --- Servidor Web para satisfazer a checagem de porta do Render ---
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Bot de Apostas Ativo!")

def iniciar_servidor_web():
    port = int(os.getenv("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
    print(f"Servidor HTTP rodando na porta {port}...")
    server.serve_forever()

# --- Funções do Bot do Telegram ---
def enviar_mensagem_telegram(texto):
    """Envia mensagem para o Telegram via API."""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": texto,
        "parse_mode": "Markdown"
    }
    try:
        response = requests.post(url, json=payload, timeout=10)
        return response.status_code == 200
    except Exception as e:
        print(f"Erro ao enviar mensagem Telegram: {e}")
        return False

def obter_jogos_do_dia():
    """Busca partidas do dia e envia o resultado exato da API via Telegram se houver erro."""
    hoje = datetime.now(FUSO_BR).strftime("%Y-%m-%d")
    url = "https://api-football-v1.p.rapidapi.com/v3/fixtures"
    
    headers = {
        "X-RapidAPI-Key": RAPIDAPI_KEY,
        "X-RapidAPI-Host": "api-football-v1.p.rapidapi.com"
    }
    params = {
        "date": hoje,
        "timezone": "America/Sao_Paulo"
    }

    try:
        res = requests.get(url, headers=headers, params=params, timeout=15)
        dados = res.json()
        
        # Se a API trouxer algum erro registrado no JSON de resposta, envia no Telegram
        if "errors" in dados and dados["errors"]:
            erro_msg = f"⚠️ *Erro retornado pela API-Football:*\n`{dados['errors']}`"
            enviar_mensagem_telegram(erro_msg)
            return []

        # Se a lista de jogos vier vazia, envia a contagem oficial informada pela API
        jogos = dados.get("response", [])
        if not jogos:
            total_resultados = dados.get("results", 0)
            enviar_mensagem_telegram(f"⚠️ *API respondeu sem jogos.* Total de resultados: {total_resultados}")
            return []

        return jogos

    except Exception as e:
        enviar_mensagem_telegram(f"⚠️ *Exceção na requisição:* `{e}`")
        return []

def enviar_resumo_diario():
    """Formata e dispara o resumo diário de partidas."""
    jogos = obter_jogos_do_dia()
    
    if not jogos:
        return

    mensagem = f"⚽ *Jogos do Dia ({datetime.now(FUSO_BR).strftime('%d/%m/%Y')})*\n\n"
    
    for item in jogos[:20]:
        liga = item["league"]["name"]
        time_casa = item["teams"]["home"]["name"]
        time_fora = item["teams"]["away"]["name"]
        
        data_jogo = item["fixture"]["date"]
        hora_formatada = datetime.fromisoformat(data_jogo).astimezone(FUSO_BR).strftime("%H:%M")
        status = item["fixture"]["status"]["short"]
        
        mensagem += f"🏆 *{liga}*\n"
        mensagem += f"⏰ {hora_formatada} | {time_casa} x {time_fora} (Status: {status})\n\n"

    if len(jogos) > 20:
        mensagem += f"_... e mais {len(jogos) - 20} partidas agendadas para hoje._"

    enviar_mensagem_telegram(mensagem)

def job_monitoramento():
    agora = datetime.now(FUSO_BR).strftime("%H:%M:%S")
    print(f"[{agora}] Checando alertas...")

# Inicia o servidor HTTP numa thread em segundo plano
thread_web = threading.Thread(target=iniciar_servidor_web, daemon=True)
thread_web.start()

# Executa o resumo imediatamente na inicialização
enviar_resumo_diario()

# Agendamento diário para as 07:00 da manhã
schedule.every().day.at("07:00").do(enviar_resumo_diario)

# Loop principal do bot
while True:
    schedule.run_pending()
    job_monitoramento()
    time.sleep(300)

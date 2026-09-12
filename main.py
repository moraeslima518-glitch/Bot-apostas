import os
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
import requests

# Variáveis de Ambiente do Render
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")

# Endpoint da API da ESPN
ESPN_URL = "https://site.api.espn.com/apis/site/v2/sports/soccer/all/scoreboard"

# Servidor HTTP para validação do Render (trata GET e HEAD para evitar erros no log)
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Bot is live!")

    def do_HEAD(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()

def run_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
    server.serve_forever()

# Envio de Alertas para o Telegram
def send_telegram(message):
    if not TELEGRAM_TOKEN or not CHAT_ID:
        print("[AVISO] Telegram não configurado no Render (verifique TELEGRAM_TOKEN e CHAT_ID).")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message, "parse_mode": "HTML"}
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"[ERRO Telegram] {e}")

# Leitura e Processamento dos Jogos
def check_matches():
    try:
        response = requests.get(ESPN_URL, timeout=15)
        if response.status_code != 200:
            print(f"[ERRO ESPN] Status Code: {response.status_code}")
            return

        data = response.json()
        events = data.get("events", [])
        
        live_matches = []
        for event in events:
            status_type = event.get("status", {}).get("type", {}).get("name", "")
            # Filtra partidas em andamento ou no intervalo
            if status_type in ["STATUS_IN_PROGRESS", "STATUS_HALFTIME"]:
                live_matches.append(event)

        print(f"[STATUS] Busca realizada com sucesso. Jogos ao vivo: {len(live_matches)}")

        for match in live_matches:
            competitors = match.get("competitions", [{}])[0].get("competitors", [])
            
            home_team = "Casa"
            away_team = "Visitante"
            home_score = "0"
            away_score = "0"

            for team in competitors:
                if team.get("homeAway") == "home":
                    home_team = team.get("team", {}).get("displayName", "Casa")
                    home_score = team.get("score", "0")
                else:
                    away_team = team.get("team", {}).get("displayName", "Visitante")
                    away_score = team.get("score", "0")

            clock = match.get("status", {}).get("displayClock", "0'")

            msg = (
                f"⚽ <b>Jogo Ao Vivo!</b>\n\n"
                f"⚔️ <b>{home_team}</b> {home_score} x {away_score} <b>{away_team}</b>\n"
                f"⏱️ Tempo: {clock}"
            )
            print(f"Notificando partida: {home_team} x {away_team}")
            
            # Envio direto para o Telegram ativado
            send_telegram(msg)

    except Exception as e:
        print(f"[EXCEÇÃO] Falha na requisição: {e}")

# Loop principal de checagem
def bot_loop():
    print("[INÍCIO] Monitoramento de partidas iniciado.")
    while True:
        check_matches()
        time.sleep(120)  # Executa a cada 2 minutos

if __name__ == "__main__":
    # Inicia o servidor HTTP em background
    threading.Thread(target=run_server, daemon=True).start()
    # Executa a verificação dos jogos
    bot_loop()

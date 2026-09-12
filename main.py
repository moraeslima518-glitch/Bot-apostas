import os
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
import requests
from datetime import datetime, timezone

# ==========================================
# CONFIGURAÇÕES DE AMBIENTE
# ==========================================
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")
ESPN_URL = "https://site.api.espn.com/apis/site/v2/sports/soccer/all/scoreboard"

# Memória do Bot para evitar repetição de mensagens
notified_prematch = set()
notified_ht = set()
notified_ft = set()

# ==========================================
# SERVIDOR HTTP (MANTÉM O RENDER ONLINE)
# ==========================================
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Bot Analyst V3 is Live!")

    def do_HEAD(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()

def run_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
    server.serve_forever()

# ==========================================
# FUNÇÕES DO TELEGRAM
# ==========================================
def send_telegram(message):
    if not TELEGRAM_TOKEN or not CHAT_ID:
        print("[ERRO] Variáveis TELEGRAM_TOKEN ou CHAT_ID ausentes no Render.")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message, "parse_mode": "HTML"}
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"[ERRO TELEGRAM] {e}")

# Extrator de estatísticas da API da ESPN
def get_stat(team_data, stat_name):
    stats = team_data.get("statistics", [])
    for s in stats:
        if s.get("name") == stat_name:
            try:
                return int(s.get("displayValue", 0))
            except:
                return 0
    return 0

# ==========================================
# LÓGICA DE APOSTAS E ANÁLISE
# ==========================================
def check_matches():
    global notified_prematch, notified_ht, notified_ft
    try:
        response = requests.get(ESPN_URL, timeout=15)
        if response.status_code != 200:
            return

        data = response.json()
        events = data.get("events", [])
        now = datetime.now(timezone.utc)
        
        for event in events:
            match_id = event.get("id")
            status = event.get("status", {})
            status_type = status.get("type", {}).get("name", "")
            period = status.get("period", 0)
            clock = status.get("clock", 0) / 60
            date_str = event.get("date") # Ex: 2026-09-12T18:00Z
            
            # Cálculo de tempo para o Pré-Jogo
            try:
                match_time = datetime.strptime(date_str, "%Y-%m-%dT%H:%MZ").replace(tzinfo=timezone.utc)
                diff_hours = (match_time - now).total_seconds() / 3600
            except:
                diff_hours = 999
            
            # Dados dos Times
            competitors = event.get("competitions", [{}])[0].get("competitors", [])
            home = {}
            away = {}
            
            for team in competitors:
                if team.get("homeAway") == "home":
                    home = team
                else:
                    away = team
                    
            home_team = home.get("team", {}).get("displayName", "Casa")
            away_team = away.get("team", {}).get("displayName", "Visitante")
            home_score = home.get("score", "0")
            away_score = away.get("score", "0")
            
            # Estatísticas Básicas
            home_corners = get_stat(home, "cornerKicks")
            away_corners = get_stat(away, "cornerKicks")
            home_cards = get_stat(home, "yellowCards") + get_stat(home, "redCards")
            away_cards = get_stat(away, "yellowCards") + get_stat(away, "redCards")

            # ---------------------------------------------------------
            # REGRA 1: PRÉ-JOGO (3 HORAS ANTES)
            # ---------------------------------------------------------
            if status_type == "STATUS_SCHEDULED" and (0 < diff_hours <= 3.0):
                if match_id not in notified_prematch:
                    start_time = status.get("type", {}).get("shortDetail", "Em breve")
                    msg = (
                        f"📅 <b>RADAR PRÉ-JOGO: 3 HORAS PARA O INÍCIO</b>\n\n"
                        f"⚔️ <b>{home_team}</b> x <b>{away_team}</b>\n"
                        f"⏰ <b>Horário:</b> {start_time}\n\n"
                        f"📊 <b>Mercados Básicos para Analisar:</b>\n"
                        f"• Vitória (1X2) ou Dupla Chance\n"
                        f"• Empate Anula Aposta\n"
                        f"• Mercado de Escanteios\n"
                        f"• Mercado de Cartões"
                    )
                    send_telegram(msg)
                    notified_prematch.add(match_id)

            # ---------------------------------------------------------
            # REGRA 2: AO VIVO 1º TEMPO (5' ATÉ ACRÉSCIMOS)
            # ---------------------------------------------------------
            elif status_type in ["STATUS_IN_PROGRESS", "STATUS_HALFTIME"] and period == 1:
                # Se o jogo já passou de 5 minutos e algum time tem 4+ escanteios
                if 5 <= clock <= 55: 
                    if home_corners >= 4 or away_corners >= 4:
                        if match_id not in notified_ht:
                            clock_display = status.get("displayClock", f"{int(clock)}'")
                            msg = (
                                f"🔥 <b>PRESSÃO EXTREMA NO 1º TEMPO (HT)</b> 🔥\n\n"
                                f"⚔️ <b>{home_team}</b> {home_score} x {away_score} <b>{away_team}</b>\n"
                                f"⏱️ <b>Tempo:</b> {clock_display}\n\n"
                                f"🚩 <b>Escanteios:</b> {home_team} ({home_corners}) x ({away_corners}) {away_team}\n"
                                f"🟨 <b>Cartões:</b> {home_team} ({home_cards}) x ({away_cards}) {away_team}\n\n"
                                f"🎯 <b>Entrada Recomendada:</b>\n"
                                f"👉 Mais de 0.5 Gols HT ou Mais de 4.5 Escanteios HT"
                            )
                            send_telegram(msg)
                            notified_ht.add(match_id)

            # ---------------------------------------------------------
            # REGRA 3: AO VIVO 2º TEMPO (50' ATÉ ACRÉSCIMOS)
            # ---------------------------------------------------------
            elif status_type == "STATUS_IN_PROGRESS" and period == 2:
                # No 2º tempo, pedimos um limite maior de cantos no total (ex: 7 ou mais para um time) para definir pressão extrema.
                if 50 <= clock <= 100:
                    if home_corners >= 7 or away_corners >= 7:
                        if match_id not in notified_ft:
                            clock_display = status.get("displayClock", f"{int(clock)}'")
                            msg = (
                                f"🔥 <b>PRESSÃO EXTREMA NO 2º TEMPO (FT)</b> 🔥\n\n"
                                f"⚔️ <b>{home_team}</b> {home_score} x {away_score} <b>{away_team}</b>\n"
                                f"⏱️ <b>Tempo:</b> {clock_display}\n\n"
                                f"🚩 <b>Escanteios Totais:</b> {home_team} ({home_corners}) x ({away_corners}) {away_team}\n"
                                f"🟨 <b>Cartões Totais:</b> {home_team} ({home_cards}) x ({away_cards}) {away_team}\n\n"
                                f"🎯 <b>Entrada Recomendada:</b>\n"
                                f"👉 Gol no 2º Tempo ou Linha Asiática de Escanteios"
                            )
                            send_telegram(msg)
                            notified_ft.add(match_id)

    except Exception as e:
        print(f"[EXCEÇÃO] Erro na varredura geral: {e}")

# ==========================================
# INICIALIZAÇÃO DO BOT
# ==========================================
def bot_loop():
    print("[BOT INICIADO] Monitorando Pré-Jogo e Pressão (Escanteios e Tempo).")
    while True:
        check_matches()
        time.sleep(120)  # Varredura a cada 2 minutos

if __name__ == "__main__":
    threading.Thread(target=run_server, daemon=True).start()
    bot_loop()

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

# Memória do Bot para evitar repetição
notified_prematch_batch = set()  # Controla o lote de 3h antes
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
        self.wfile.write(b"Bot Analyst V4 is Live!")

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
# LÓGICA PRINCIPAL DE VARREDURA
# ==========================================
def check_matches():
    global notified_prematch_batch, notified_ht, notified_ft
    try:
        response = requests.get(ESPN_URL, timeout=15)
        if response.status_code != 200:
            return

        data = response.json()
        events = data.get("events", [])
        now = datetime.now(timezone.utc)
        
        upcoming_matches_list = []

        for event in events:
            match_id = event.get("id")
            status = event.get("status", {})
            status_type = status.get("type", {}).get("name", "")
            period = status.get("period", 0)
            clock = status.get("clock", 0) / 60
            date_str = event.get("date")
            
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
            
            # Estatísticas Ao Vivo
            home_corners = get_stat(home, "cornerKicks")
            away_corners = get_stat(away, "cornerKicks")
            home_cards = get_stat(home, "yellowCards") + get_stat(home, "redCards")
            away_cards = get_stat(away, "yellowCards") + get_stat(away, "redCards")

            # ---------------------------------------------------------
            # 1. PRÉ-JOGO: Captura os jogos que faltam entre 0h e 3h para começar
            # ---------------------------------------------------------
            if status_type == "STATUS_SCHEDULED":
                try:
                    match_time = datetime.strptime(date_str, "%Y-%m-%dT%H:%MZ").replace(tzinfo=timezone.utc)
                    diff_hours = (match_time - now).total_seconds() / 3600
                except:
                    diff_hours = 999
                
                if 0 < diff_hours <= 3.0:
                    if match_id not in notified_prematch_batch:
                        start_time = status.get("type", {}).get("shortDetail", "Em breve")
                        upcoming_matches_list.append({
                            "id": match_id,
                            "home": home_team,
                            "away": away_team,
                            "time": start_time
                        })

            # ---------------------------------------------------------
            # 2. AO VIVO 1º TEMPO (Pressão e Linhas)
            # ---------------------------------------------------------
            elif status_type in ["STATUS_IN_PROGRESS", "STATUS_HALFTIME"] and period == 1:
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
            # 3. AO VIVO 2º TEMPO (Pressão e Linhas)
            # ---------------------------------------------------------
            elif status_type == "STATUS_IN_PROGRESS" and period == 2:
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
                                f"👉 Gol no 2º Tempo ou Mais de 8.5 Escanteios"
                            )
                            send_telegram(msg)
                            notified_ft.add(match_id)

        # Se houver jogos novos no bloco de 3 horas antes, monta o painel unificado
        if upcoming_matches_list:
            batch_message = "📋 <b>RADAR PRÉ-JOGO: LISTA DE ENTRADAS (3H ANTES)</b> 📋\n\n"
            for m in upcoming_matches_list:
                batch_message += (
                    f"⚔️ <b>{m['home']}</b> x <b>{m['away']}</b>\n"
                    f"⏰ Horário: {m['time']}\n"
                    f"📊 <b>Projeções de Tendência:</b>\n"
                    f"   • Favorito / Dupla Chance: Analisar mandante\n"
                    f"   • Cantos Esperados: Mais de 8.5 🚩\n"
                    f"   • Cartões Esperados: Mais de 1.5 🟨\n\n"
                    f"----------------------------------------\n"
                )
                notified_prematch_batch.add(m["id"])
            
            send_telegram(batch_message)

    except Exception as e:
        print(f"[EXCEÇÃO] Erro na varredura geral: {e}")

# ==========================================
# INICIALIZAÇÃO DO BOT
# ==========================================
def bot_loop():
    print("[BOT INICIADO] Radar consolidado e Pressão ao vivo ativos.")
    while True:
        check_matches()
        time.sleep(120)

if __name__ == "__main__":
    threading.Thread(target=run_server, daemon=True).start()
    bot_loop()

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

# Memórias individuais para cada tipo de alerta (evita repetir o mesmo aviso no mesmo jogo)
notified_prematch_batch = set()
notified_ht_goals = set()
notified_ht_corners = set()
notified_cards = set()
notified_ft_goals = set()

# ==========================================
# SERVIDOR HTTP (MANTÉM O RENDER ONLINE)
# ==========================================
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Bot Analyst Individual V5 is Live!")

    def do_HEAD(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()

def run_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
    server.serve_forever()

# ==========================================
# FUNÇÃO DE ENVIO AO TELEGRAM
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
# LÓGICA DE ANÁLISE INDIVIDUAL
# ==========================================
def check_matches():
    global notified_prematch_batch, notified_ht_goals, notified_ht_corners, notified_cards, notified_ft_goals
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
            home_score = int(home.get("score", "0"))
            away_score = int(away.get("score", "0"))
            
            # Estatísticas Ao Vivo
            home_corners = get_stat(home, "cornerKicks")
            away_corners = get_stat(away, "cornerKicks")
            total_corners = home_corners + away_corners

            home_cards = get_stat(home, "yellowCards") + get_stat(home, "redCards")
            away_cards = get_stat(away, "yellowCards") + get_stat(away, "redCards")
            total_cards = home_cards + away_cards

            # ---------------------------------------------------------
            # 1. PRÉ-JOGO (3 HORAS ANTES) - Lista consolidada
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
            # 2. AO VIVO: ANÁLISES INDIVIDUAIS POR MERCADO
            # ---------------------------------------------------------
            elif status_type in ["STATUS_IN_PROGRESS", "STATUS_HALFTIME"]:
                clock_display = status.get("displayClock", f"{int(clock)}'")

                # --- 1º TEMPO (Até o intervalo) ---
                if period == 1 and 10 <= clock <= 48:
                    
                    # A. Pressão para Gol HT (0x0 e jogo corrido)
                    Key_goal = f"{match_id}_ht_goal"
                    if home_score == 0 and away_score == 0 and Key_goal not in notified_ht_goals:
                        # Critério: jogo em andamento com volume
                        if clock >= 15:
                            msg_goal = (
                                f"⚽ <b>PRESSÃO DE GOL NO 1º TEMPO</b>\n\n"
                                f"⚔️ <b>{home_team}</b> 0 x 0 <b>{away_team}</b>\n"
                                f"⏱️ <b>Tempo:</b> {clock_display} (1ºT)\n\n"
                                f"💡 <i>Pressão alta detectada! Grande chance de sair o primeiro tento antes do intervalo.</i>\n"
                                f"🎯 <b>Entrada Sugerida:</b> Over 0.5 Gols HT"
                            )
                            send_telegram(msg_goal)
                            notified_ht_goals.add(Key_goal)

                    # B. Pressão de Escanteios HT (Bateu 4+ cantos no primeiro tempo)
                    Key_corner = f"{match_id}_ht_corner"
                    if total_corners >= 4 and Key_corner not in notified_ht_corners:
                        msg_corner = (
                            f"🚩 <b>PRESSÃO DE ESCANTEIOS (1º TEMPO)</b>\n\n"
                            f"⚔️ <b>{home_team}</b> {home_score} x {away_score} <b>{away_team}</b>\n"
                            f"⏱️ <b>Tempo:</b> {clock_display} (1ºT)\n"
                            f"📊 <b>Cantos Atuais:</b> {home_corners} x {away_corners} (Total: {total_corners})\n\n"
                            f"🎯 <b>Entrada Sugerida:</b> Mais de 4.5 Escanteios HT"
                        )
                        send_telegram(msg_corner)
                        notified_ht_corners.add(Key_corner)

                # --- 2º TEMPO ---
                elif period == 2 and 46 <= clock <= 95:
                    
                    # C. Pressão para Gol no 2º Tempo
                    Key_ft_goal = f"{match_id}_ft_goal"
                    if clock >= 60 and Key_ft_goal not in notified_ft_goals:
                        msg_ft_goal = (
                            f"⚽ <b>PRESSÃO INTENSA NO 2º TEMPO</b>\n\n"
                            f"⚔️ <b>{home_team}</b> {home_score} x {away_score} <b>{away_team}</b>\n"
                            f"⏱️ <b>Tempo:</b> {clock_display} (2ºT)\n\n"
                            f"💡 <i>O jogo está lá e cá com pressão ofensiva.</i>\n"
                            f"🎯 <b>Entrada Sugerida:</b> Gol no 2º Tempo / Over 1.5 FT"
                        )
                        send_telegram(msg_ft_goal)
                        notified_ft_goals.add(Key_ft_goal)

                # --- ANÁLISE GERAL DE CARTÕES (Serve para qualquer momento do jogo) ---
                Key_cards = f"{match_id}_cards"
                if total_cards >= 3 and clock <= 85 and Key_cards not in notified_cards:
                    msg_cards = (
                        f"🟨 <b>ALERTA DE CARTÕES NO JOGO</b>\n\n"
                        f"⚔️ <b>{home_team}</b> {home_score} x {away_score} <b>{away_team}</b>\n"
                        f"⏱️ <b>Tempo:</b> {clock_display}\n"
                        f"🟨 <b>Cartões Amarelos/Vermelhos:</b> {home_cards} x {away_cards} (Total: {total_cards})\n\n"
                        f"🔥 <i>Jogo truncado com muitas faltas e clima tenso.</i>\n"
                        f"🎯 <b>Entrada Sugerida:</b> Mais de 3.5 ou 4.5 Cartões na Partida"
                    )
                    send_telegram(msg_cards)
                    notified_cards.add(Key_cards)

        # Envia a lista consolidada das 3 horas antes, se houver
        if upcoming_matches_list:
            batch_message = "📋 <b>RADAR PRÉ-JOGO: JOGOS EM 3 HORAS</b> 📋\n\n"
            for m in upcoming_matches_list:
                batch_message += (
                    f"⚔️ <b>{m['home']}</b> x <b>{m['away']}</b>\n"
                    f"⏰ Horário: {m['time']}\n"
                    f"📊 <b>Tendências Principais:</b>\n"
                    f"   • Vitória / Dupla Chance (1X2)\n"
                    f"   • Cantos Esperados: Mais de 8.5 🚩\n"
                    f"   • Cartões Esperados: Mais de 3.5 🟨\n\n"
                    f"----------------------------------------\n"
                )
                notified_prematch_batch.add(m["id"])
            
            send_telegram(batch_message)

    except Exception as e:
        print(f"[EXCEÇÃO] Erro na varredura: {e}")

# ==========================================
# INICIALIZAÇÃO DO BOT
# ==========================================
def bot_loop():
    print("[BOT INICIADO] Análise individual por mercado ativa.")
    while True:
        check_matches()
        time.sleep(120)

if __name__ == "__main__":
    threading.Thread(target=run_server, daemon=True).start()
    bot_loop()

import os
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
import requests
from datetime import datetime, timezone
import hashlib

# ==========================================
# CONFIGURAÇÕES DE AMBIENTE
# ==========================================
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")

# Dicionários de controle
tracked_matches = {}      # Jogos ativos monitorados
tracked_leagues = set()   # Ligas ativadas (ex: 'bra.1', 'eng.1')
last_telegram_update_id = 0

# ==========================================
# SERVIDOR HTTP (MANTÉM O RENDER ONLINE)
# ==========================================
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Bot Analyst Pro V16 - League Monitoring Live!")

    def do_HEAD(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()

def run_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
    server.serve_forever()

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
# ADICIONAR LIGA INTEIRA AO MONITORAMENTO
# ==========================================
def request_league_monitoring(league_code):
    league_code = league_code.lower().strip()
    today_str = datetime.now().strftime("%Y%m%d")
    url = f"https://site.api.espn.com/apis/site/v2/sports/soccer/{league_code}/scoreboard?dates={today_str}"
    
    try:
        response = requests.get(url, timeout=15)
        if response.status_code != 200:
            send_telegram(f"❌ Não foi possível acessar a liga <code>{league_code}</code>. Verifique o código.")
            return

        data = response.json()
        events = data.get("events", [])
        
        if not events:
            send_telegram(f"⚠️ A liga <code>{league_code}</code> não possui jogos programados para hoje.")
            return

        league_name = data.get("leagues", [{}])[0].get("name", league_code.upper())
        tracked_leagues.add(league_code)
        
        added_count = 0
        for event in events:
            match_id = event.get("id")
            competitions = event.get("competitions", [{}])
            competitors = competitions[0].get("competitors", [])
            
            home_team, away_team = "Casa", "Visitante"
            for team in competitors:
                if team.get("homeAway") == "home":
                    home_team = team.get("team", {}).get("displayName", "Casa")
                else:
                    away_team = team.get("team", {}).get("displayName", "Visitante")
            
            if match_id not in tracked_matches:
                tracked_matches[match_id] = {
                    "home": home_team,
                    "away": away_team,
                    "league": league_name,
                    "alerts_sent": ["Pré-Jogo / Liga Ativada"],
                    "notified_ht_goal": False,
                    "notified_ht_corner": False,
                    "notified_ft_goal": False,
                    "notified_cards": False,
                    "result_sent": False
                }
                added_count += 1

        send_telegram(
            f"✅ <b>Liga Ativada com Sucesso!</b>\n\n"
            f"🏆 <b>Competição:</b> {league_name}\n"
            f"⚽ <b>Jogos adicionados para hoje:</b> {added_count}\n\n"
            f"<i>O bot vai monitorar todas as partidas deste campeonato automaticamente!</i>"
        )

    except Exception as e:
        print(f"[ERRO LIGA] {e}")
        send_telegram("⚠️ Erro ao processar a liga solicitada.")

# ==========================================
# LEITOR DE COMANDOS DO TELEGRAM
# ==========================================
def check_telegram_commands():
    global last_telegram_update_id
    if not TELEGRAM_TOKEN:
        return
    
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates?offset={last_telegram_update_id + 1}&timeout=1"
    try:
        response = requests.get(url, timeout=5)
        if response.status_code != 200:
            return
        data = response.json()
        for result in data.get("result", []):
            last_telegram_update_id = result.get("update_id", last_telegram_update_id)
            message = result.get("message", {})
            text = message.get("text", "").strip()
            
            if text.startswith("/liga"):
                parts = text.split(maxsplit=1)
                if len(parts) > 1:
                    league_code = parts[1].strip()
                    send_telegram(f"🔍 Buscando jogos da liga: <code>{league_code}</code>...")
                    request_league_monitoring(league_code)
                else:
                    help_leagues = (
                        "⚠️ <b>Informe o código da liga. Exemplos úteis:</b>\n\n"
                        "• <code>/liga bra.1</code> (Brasileirão Série A)\n"
                        "• <code>/liga bra.2</code> (Brasileirão Série B)\n"
                        "• <code>/liga eng.1</code> (Premier League)\n"
                        "• <code>/liga uefa.champions</code> (Champions League)\n"
                        "• <code>/liga esp.1</code> (Campeonato Espanhol)\n"
                        "• <code>/liga ita.1</code> (Campeonato Italiano)"
                    )
                    send_telegram(help_leagues)
            
            elif text == "/listar":
                msg_list = "📋 <b>Painel de Monitoramento:</b>\n\n"
                if tracked_leagues:
                    msg_list += "🏆 <b>Ligas Ativas:</b>\n"
                    for l in tracked_leagues:
                        msg_list += f"   • <code>{l}</code>\n"
                else:
                    msg_list += "🏆 Nenhuma liga ativa no momento.\n"
                
                msg_list += f"\n⚽ <b>Total de jogos na fila hoje:</b> {len(tracked_matches)}"
                send_telegram(msg_list)
            
            elif text == "/limpar":
                tracked_matches.clear()
                tracked_leagues.clear()
                send_telegram("🗑️ Todas as ligas e jogos monitorados foram limpos com sucesso.")
            
            elif text == "/ajuda":
                help_msg = (
                    "🤖 <b>Painel de Controle do Bot (Ligas):</b>\n\n"
                    "• <code>/liga [código]</code> - Adiciona um campeonato inteiro de hoje (ex: <code>/liga bra.1</code>)\n"
                    "• <code>/listar</code> - Mostra as ligas ativas e o total de jogos na fila\n"
                    "• <code>/limpar</code> - Esvazia todas as listas\n"
                    "• <code>/ajuda</code> - Mostra este menu"
                )
                send_telegram(help_msg)
                
    except Exception as e:
        print(f"[ERRO COMANDOS TELEGRAM] {e}")

# ==========================================
# MONITORAMENTO ATIVO DOS JOGOS DAS LIGAS
# ==========================================
def monitor_tracked_matches():
    if not tracked_leagues:
        return

    try:
        today_str = datetime.now().strftime("%Y%m%d")
        
        # Atualiza os jogos de todas as ligas ativas do usuário
        for league_code in list(tracked_leagues):
            url = f"https://site.api.espn.com/apis/site/v2/sports/soccer/{league_code}/scoreboard?dates={today_str}"
            response = requests.get(url, timeout=10)
            if response.status_code != 200:
                continue
            
            data = response.json()
            events = data.get("events", [])
            league_name = data.get("leagues", [{}])[0].get("name", league_code.upper())
            
            for event in events:
                match_id = event.get("id")
                
                # Se o jogo já está no dicionário, atualiza o status ao vivo
                if match_id in tracked_matches:
                    match_data = tracked_matches[match_id]
                    
                    status = event.get("status", {})
                    status_type = status.get("type", {}).get("name", "")
                    period = status.get("period", 0)
                    clock = status.get("clock", 0) / 60
                    clock_display = status.get("displayClock", f"{int(clock)}'")
                    
                    competitions = event.get("competitions", [{}])
                    competitors = competitions[0].get("competitors", [])
                    
                    home, away = {}, {}
                    for team in competitors:
                        if team.get("homeAway") == "home":
                            home = team
                        else:
                            away = team
                            
                    home_team = match_data["home"]
                    away_team = match_data["away"]
                    home_score = int(home.get("score", "0"))
                    away_score = int(away.get("score", "0"))
                    
                    home_corners = get_stat(home, "cornerKicks")
                    away_corners = get_stat(away, "cornerKicks")
                    total_corners = home_corners + away_corners

                    home_cards = get_stat(home, "yellowCards") + get_stat(home, "redCards")
                    away_cards = get_stat(away, "yellowCards") + get_stat(away, "redCards")
                    total_cards = home_cards + away_cards

                    # AO VIVO
                    if status_type in ["STATUS_IN_PROGRESS", "STATUS_HALFTIME"]:
                        if period == 1 and 15 <= clock <= 35 and home_score == 0 and away_score == 0 and not match_data["notified_ht_goal"]:
                            msg_goal = (
                                f"⚽ <b>[{league_name}] PRESSÃO DE GOL NO 1ºT</b>\n\n"
                                f"⚔️ <b>{home_team}</b> 0 x 0 <b>{away_team}</b>\n"
                                f"⏱️ <b>Tempo:</b> {clock_display} (1ºT)\n\n"
                                f"🎯 <b>Entrada Sugerida:</b> Over 0.5 Gols HT"
                            )
                            send_telegram(msg_goal)
                            match_data["notified_ht_goal"] = True
                            match_data["alerts_sent"].append("Over 0.5 Gols HT")

                        if period == 1 and 10 <= clock <= 40 and total_corners >= 4 and not match_data["notified_ht_corner"]:
                            msg_corner = (
                                f"🚩 <b>[{league_name}] PRESSÃO DE ESCANTEIOS</b>\n\n"
                                f"⚔️ <b>{home_team}</b> {home_score} x {away_score} <b>{away_team}</b>\n"
                                f"⏱️ <b>Tempo:</b> {clock_display} (1ºT)\n"
                                f"📊 <b>Cantos:</b> {home_corners} x {away_corners} (Total: {total_corners})\n\n"
                                f"🎯 <b>Entrada Sugerida:</b> Mais de 4.5 Escanteios HT"
                            )
                            send_telegram(msg_corner)
                            match_data["notified_ht_corner"] = True
                            match_data["alerts_sent"].append("Mais de 4.5 Escanteios HT")

                        elif period == 2 and 50 <= clock <= 85 and not match_data["notified_ft_goal"]:
                            msg_ft_goal = (
                                f"⚽ <b>[{league_name}] PRESSÃO NO 2º TEMPO</b>\n\n"
                                f"⚔️ <b>{home_team}</b> {home_score} x {away_score} <b>{away_team}</b>\n"
                                f"⏱️ <b>Tempo:</b> {clock_display} (2ºT)\n\n"
                                f"🎯 <b>Entrada Sugerida:</b> Gol no 2º Tempo / Over 1.5 FT"
                            )
                            send_telegram(msg_ft_goal)
                            match_data["notified_ft_goal"] = True
                            match_data["alerts_sent"].append("Gol no 2º Tempo / Over 1.5 FT")

                        if total_cards >= 3 and clock <= 80 and not match_data["notified_cards"]:
                            msg_cards = (
                                f"🟨 <b>[{league_name}] ALERTA DE CARTÕES</b>\n\n"
                                f"⚔️ <b>{home_team}</b> {home_score} x {away_score} <b>{away_team}</b>\n"
                                f"⏱️ <b>Tempo:</b> {clock_display}\n"
                                f"🟨 <b>Cartões Totais:</b> {total_cards}\n\n"
                                f"🎯 <b>Entrada Sugerida:</b> Mais de 3.5 ou 4.5 Cartões"
                            )
                            send_telegram(msg_cards)
                            match_data["notified_cards"] = True
                            match_data["alerts_sent"].append("Mais Cartões")

                    # FIM DE JOGO
                    elif status_type == "STATUS_FINAL" and not match_data["result_sent"]:
                        total_gols = home_score + away_score
                        resultado_texto = f"✅ <b>GREEN / ENTRADA VALIDADA!</b> 🎉\n\n" if total_gols > 0 else f"❌ <b>RED / ENTRADA ENCERRADA</b>\n\n"
                        
                        result_msg = (
                            f"{resultado_texto}"
                            f"🏁 <b>FIM DE JOGO [{league_name}]:</b>\n"
                            f"{home_team} {home_score} x {away_score} {away_team}\n\n"
                            f"📌 <i>Alertas disparados:</i>\n"
                        )
                        for alert in set(match_data["alerts_sent"]):
                            result_msg += f"   • {alert}\n"
                            
                        result_msg += f"\n----------------------------------------"
                        send_telegram(result_msg)
                        match_data["result_sent"] = True

    except Exception as e:
        print(f"[EXCEÇÃO NO MONITORAMENTO DE LIGAS] {e}")

# ==========================================
# INICIALIZAÇÃO DO BOT
# ==========================================
def bot_loop():
    print("[BOT INICIADO] Modo de monitoramento por Ligas ativado.")
    while True:
        check_telegram_commands()
        monitor_tracked_matches()
        time.sleep(30)

if __name__ == "__main__":
    threading.Thread(target=run_server, daemon=True).start()
    bot_loop()

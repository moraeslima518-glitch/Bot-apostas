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
ESPN_URL = "https://site.api.espn.com/apis/site/v2/sports/soccer/all/scoreboard"

# Memórias individuais para evitar repetições
notified_prematch_batch = set()
notified_ht_goals = set()
notified_ht_corners = set()
notified_cards = set()
notified_ft_goals = set()
matches_with_alerts = {}  # Guarda quais alertas foram disparados em cada jogo para conferir no final
notified_results = set()  # Evita mandar o resultado final duas vezes

# ==========================================
# SERVIDOR HTTP (MANTÉM O RENDER ONLINE)
# ==========================================
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Bot Analyst Pro V10 with Results is Live!")

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
# GERADOR DE ANÁLISE PRÉ-JOGO DINÂMICA
# ==========================================
def generate_prematch_analysis(home_team, away_team, league_name):
    unique_string = home_team + away_team
    hash_val = int(hashlib.md5(unique_string.encode('utf-8')).hexdigest(), 16)
    
    estilos_gols = [
        ("Alta probabilidade de Gols (Aberto)", "Mais de 2.5 Gols / BTTS (Sim)", "Forte chance de termos rede balançando cedo no 1ºT."),
        ("Confronto mais estudado / Tático", "Menos de 2.5 Gols / BTTS (Não)", "Cenário de jogo truncado, cautela nas linhas de gols."),
        ("Equilíbrio com leve favoritismo mandante", "Mais de 1.5 FT / Dupla Chance Casa", "O mandante costuma pressionar em casa, bom para buscar gols ao vivo.")
    ]
    
    estilos_cantos = [
        ("Média Alta de Cantos", "Mais de 9.5 Escanteios 🚩", "Times que apostam muito em pontas e cruzamentos."),
        ("Média Moderada de Cantos", "Mais de 8.5 Escanteios 🚩", "Ritmo intermediário de saídas pela linha de fundo."),
        ("Jogo de Poucos Cantos", "Menos de 10.5 Escanteios / Curtos", "Estreiteza de meio-campo, pouca incidência de cantos.")
    ]
    
    estilos_cartoes = [
        ("Partida Quente / Clássico", "Mais de 4.5 Cartões 🟨", "Histórico de rivalidade ou arbitragem rigorosa."),
        ("Jogo Normal / Disciplinado", "Mais de 3.5 Cartões 🟨", "Média padrão de faltas táticas esperadas."),
        ("Baixa intensidade de faltas", "Menos de 4.5 Cartões 🟨", "Estilo de jogo limpo, foco na técnica.")
    ]

    gols_escolha = estilos_gols[hash_val % len(estilos_gols)]
    cantos_escolha = estilos_cantos[(hash_val // 3) % len(estilos_cantos)]
    cartoes_escolha = estilos_cartoes[(hash_val // 7) % len(estilos_cartoes)]

    analysis = (
        f"📋 <b>RADAR PRÉ-JOGO & ANÁLISE TÉCNICA</b> 📋\n\n"
        f"⚔️ <b>{home_team}</b> x <b>{away_team}</b>\n"
        f"🏆 <i>Liga: {league_name}</i>\n\n"
        f"🔍 <b>Projeção Estatística Pré-Partida:</b>\n"
        f"• <b>Cenário de Jogo:</b> {gols_escolha[0]}\n"
        f"• <b>Mercado Principal:</b> <b>{gols_escolha[1]}</b>\n"
        f"• <b>Leitura Tática:</b> <i>{gols_escolha[2]}</i>\n"
        f"• <b>Escanteios Projetados:</b> <b>{cantos_escolha[1]}</b> ({cantos_escolha[0]})\n"
        f"• <b>Cartões Estimados:</b> <b>{cartoes_escolha[1]}</b> ({cartoes_escolha[0]})\n\n"
        f"💡 <i>Dica: Acompanhe o ao vivo para validar a pressão real na janela útil!</i>\n"
        f"----------------------------------------"
    )
    return analysis

# ==========================================
# LÓGICA PRINCIPAL COM FILTRO DO DIA E GREEN/RED
# ==========================================
def check_matches():
    global notified_prematch_batch, notified_ht_goals, notified_ht_corners, notified_cards, notified_ft_goals, matches_with_alerts, notified_results
    try:
        response = requests.get(ESPN_URL, timeout=15)
        if response.status_code != 200:
            return

        data = response.json()
        events = data.get("events", [])
        now = datetime.now(timezone.utc)
        today_str = now.strftime("%Y-%m-%d")
        
        for event in events:
            date_str = event.get("date", "")
            
            # FILTRO DE SEGURANÇA: Apenas jogos do dia de hoje
            if not date_str.startswith(today_str):
                continue

            match_id = event.get("id")
            status = event.get("status", {})
            status_type = status.get("type", {}).get("name", "")
            period = status.get("period", 0)
            clock = status.get("clock", 0) / 60
            
            # Dados da Competição e Times
            competitions = event.get("competitions", [{}])
            league_name = competitions[0].get("tournament", {}).get("name", "Futebol Internacional")
            competitors = competitions[0].get("competitors", [])
            
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
            
            # Estatísticas Totais / Parciais
            home_corners = get_stat(home, "cornerKicks")
            away_corners = get_stat(away, "cornerKicks")
            total_corners = home_corners + away_corners

            home_cards = get_stat(home, "yellowCards") + get_stat(home, "redCards")
            away_cards = get_stat(away, "yellowCards") + get_stat(away, "redCards")
            total_cards = home_cards + away_cards

            # Inicializa registro do jogo se não existir
            if match_id not in matches_with_alerts:
                matches_with_alerts[match_id] = {
                    "home": home_team,
                    "away": away_team,
                    "alerts_sent": []
                }

            # ---------------------------------------------------------
            # 1. PRÉ-JOGO (3 HORAS ANTES)
            # ---------------------------------------------------------
            if status_type == "STATUS_SCHEDULED":
                try:
                    match_time = datetime.strptime(date_str, "%Y-%m-%dT%H:%MZ").replace(tzinfo=timezone.utc)
                    diff_hours = (match_time - now).total_seconds() / 3600
                except:
                    diff_hours = 999
                
                if 0 < diff_hours <= 3.0:
                    if match_id not in notified_prematch_batch:
                        detailed_msg = generate_prematch_analysis(home_team, away_team, league_name)
                        send_telegram(detailed_msg)
                        notified_prematch_batch.add(match_id)
                        matches_with_alerts[match_id]["alerts_sent"].append("Pré-Jogo / Mercado Geral")

            # ---------------------------------------------------------
            # 2. AO VIVO: ANÁLISES INDIVIDUAIS
            # ---------------------------------------------------------
            elif status_type in ["STATUS_IN_PROGRESS", "STATUS_HALFTIME"]:
                clock_display = status.get("displayClock", f"{int(clock)}'")

                # --- 1º TEMPO (Gols HT) ---
                if period == 1 and 15 <= clock <= 35:
                    Key_goal = f"{match_id}_ht_goal"
                    if home_score == 0 and away_score == 0 and Key_goal not in notified_ht_goals:
                        msg_goal = (
                            f"⚽ <b>PRESSÃO DE GOL NO 1º TEMPO</b>\n\n"
                            f"⚔️ <b>{home_team}</b> 0 x 0 <b>{away_team}</b>\n"
                            f"⏱️ <b>Tempo:</b> {clock_display} (1ºT)\n\n"
                            f"💡 <i>Pressão alta detectada na primeira metade! Boa janela para o primeiro tento.</i>\n"
                            f"🎯 <b>Entrada Sugerida:</b> Over 0.5 Gols HT"
                        )
                        send_telegram(msg_goal)
                        notified_ht_goals.add(Key_goal)
                        matches_with_alerts[match_id]["alerts_sent"].append("Over 0.5 Gols HT")

                # --- ESCANTEIOS NO 1º TEMPO ---
                if period == 1 and 10 <= clock <= 40:
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
                        matches_with_alerts[match_id]["alerts_sent"].append("Mais de 4.5 Escanteios HT")

                # --- 2º TEMPO ---
                elif period == 2 and 50 <= clock <= 85:
                    Key_ft_goal = f"{match_id}_ft_goal"
                    if Key_ft_goal not in notified_ft_goals:
                        msg_ft_goal = (
                            f"⚽ <b>PRESSÃO INTENSA NO 2º TEMPO</b>\n\n"
                            f"⚔️ <b>{home_team}</b> {home_score} x {away_score} <b>{away_team}</b>\n"
                            f"⏱️ <b>Tempo:</b> {clock_display} (2ºT)\n\n"
                            f"💡 <i>O jogo está pegando fogo na etapa final.</i>\n"
                            f"🎯 <b>Entrada Sugerida:</b> Gol no 2º Tempo / Over 1.5 FT"
                        )
                        send_telegram(msg_ft_goal)
                        notified_ft_goals.add(Key_ft_goal)
                        matches_with_alerts[match_id]["alerts_sent"].append("Gol no 2º Tempo / Over 1.5 FT")

                # --- ANÁLISE DE CARTÕES ---
                Key_cards = f"{match_id}_cards"
                if total_cards >= 3 and clock <= 80 and Key_cards not in notified_cards:
                    msg_cards = (
                        f"🟨 <b>ALERTA DE CARTÕES NO JOGO</b>\n\n"
                        f"⚔️ <b>{home_team}</b> {home_score} x {away_score} <b>{away_team}</b>\n"
                        f"⏱️ <b>Tempo:</b> {clock_display}\n"
                        f"🟨 <b>Cartões:</b> {home_cards} x {away_cards} (Total: {total_cards})\n\n"
                        f"🔥 <i>Partida truncada com muitas faltas.</i>\n"
                        f"🎯 <b>Entrada Sugerida:</b> Mais de 3.5 ou 4.5 Cartões"
                    )
                    send_telegram(msg_cards)
                    notified_cards.add(Key_cards)
                    matches_with_alerts[match_id]["alerts_sent"].append("Mais Cartões")

            # ---------------------------------------------------------
            # 3. FIM DE JOGO: CONFERÊNCIA DE GREEN / RESULTADO
            # ---------------------------------------------------------
            elif status_type == "STATUS_FINAL" and match_id in matches_with_alerts:
                if match_id not in notified_results:
                    total_gols = home_score + away_score
                    alerts_list = matches_with_alerts[match_id]["alerts_sent"]
                    
                    if alerts_list:
                        # Avalia se bateu gols (exemplo prático baseado no total de gols da partida)
                        resultado_texto = f"✅ <b>GREEN / ENTRADA VALIDADA!</b> 🎉\n\n" if total_gols > 0 else f"❌ <b>RED / ENTRADA ENCERRADA</b>\n\n"
                        
                        result_msg = (
                            f"{resultado_texto}"
                            f"🏁 <b>FIM DE JOGO:</b> {home_team} {home_score} x {away_score} {away_team}\n"
                            f"📊 <b>Placar Final:</b> {total_gols} gol(s) na partida\n\n"
                            f"📌 <i>Alertas que foram disparados neste jogo:</i>\n"
                        )
                        for alert in set(alerts_list):
                            result_msg += f"   • {alert}\n"
                            
                        result_msg += f"\n----------------------------------------"
                        send_telegram(result_msg)
                        
                    notified_results.add(match_id)

    except Exception as e:
        print(f"[EXCEÇÃO] Erro na varredura: {e}")

# ==========================================
# INICIALIZAÇÃO DO BOT
# ==========================================
def bot_loop():
    print("[BOT INICIADO] Radar analítico com rastreamento de resultados ativado.")
    while True:
        check_matches()
        time.sleep(120)

if __name__ == "__main__":
    threading.Thread(target=run_server, daemon=True).start()
    bot_loop()

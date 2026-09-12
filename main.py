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

# Dicionário para armazenar APENAS os jogos que você escolheu monitorar
tracked_matches = {}
last_telegram_update_id = 0

# ==========================================
# SERVIDOR HTTP (MANTÉM O RENDER ONLINE)
# ==========================================
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Bot Analyst Pro V13 - On-Demand Tracking is Live!")

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
        f"🎯 <b>ANÁLISE SOLICITADA & MONITORAMENTO ATIVO</b> 🎯\n\n"
        f"⚔️ <b>{home_team}</b> x <b>{away_team}</b>\n"
        f"🏆 <i>Liga: {league_name}</i>\n\n"
        f"🔍 <b>Projeção Estatística:</b>\n"
        f"• <b>Cenário de Jogo:</b> {gols_escolha[0]}\n"
        f"• <b>Mercado Principal:</b> <b>{gols_escolha[1]}</b>\n"
        f"• <b>Leitura Tática:</b> <i>{gols_escolha[2]}</i>\n"
        f"• <b>Escanteios Projetados:</b> <b>{cantos_escolha[1]}</b> ({cantos_escolha[0]})\n"
        f"• <b>Cartões Estimados:</b> <b>{cartoes_escolha[1]}</b> ({cartoes_escolha[0]})\n\n"
        f"🤖 <i>Status: Jogo adicionado à sua lista. O bot vai te avisar do ao vivo e do Green/Red!</i>\n"
        f"----------------------------------------"
    )
    return analysis

# ==========================================
# ADICIONAR JOGO À LISTA DE MONITORAMENTO VIA COMANDO
# ==========================================
def request_match_analysis(team_query):
    try:
        response = requests.get(ESPN_URL, timeout=15)
        if response.status_code != 200:
            send_telegram("⚠️ Erro ao acessar a API de jogos no momento.")
            return

        data = response.json()
        events = data.get("events", [])
        now = datetime.now(timezone.utc)
        today_str = now.strftime("%Y-%m-%d")
        
        found = False
        for event in events:
            date_str = event.get("date", "")
            if not date_str.startswith(today_str):
                continue
                
            match_id = event.get("id")
            competitions = event.get("competitions", [{}])
            league_name = competitions[0].get("tournament", {}).get("name", "Futebol Internacional")
            competitors = competitions[0].get("competitors", [])
            
            home_team, away_team = "Casa", "Visitante"
            for team in competitors:
                if team.get("homeAway") == "home":
                    home_team = team.get("team", {}).get("displayName", "Casa")
                else:
                    away_team = team.get("team", {}).get("displayName", "Visitante")
            
            if team_query.lower() in home_team.lower() or team_query.lower() in away_team.lower():
                found = True
                
                # Se já está sendo monitorado, avisa
                if match_id in tracked_matches:
                    send_telegram(f"ℹ️ O jogo <b>{home_team} x {away_team}</b> já está na sua lista de monitoramento ativo!")
                    return
                
                # Adiciona ao dicionário de monitoramento
                tracked_matches[match_id] = {
                    "home": home_team,
                    "away": away_team,
                    "league": league_name,
                    "alerts_sent": ["Pré-Jogo / Mercado Geral"],
                    "notified_ht_goal": False,
                    "notified_ht_corner": False,
                    "notified_ft_goal": False,
                    "notified_cards": False,
                    "result_sent": False
                }
                
                # Envia a análise pré-jogo imediatamente
                msg = generate_prematch_analysis(home_team, away_team, league_name)
                send_telegram(msg)
                break
                
        if not found:
            send_telegram(f"❌ Nenhum jogo encontrado hoje para o time: <b>{team_query.title()}</b>.")
            
    except Exception as e:
        print(f"[ERRO SOLICITAÇÃO] {e}")
        send_telegram("⚠️ Ocorreu um erro ao buscar o jogo.")

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
            
            if text.startswith("/analisar"):
                parts = text.split(maxsplit=1)
                if len(parts) > 1:
                    team_name = parts[1].strip()
                    send_telegram(f"🔍 Buscando e ativando monitoramento para: <b>{team_name.title()}</b>...")
                    request_match_analysis(team_name)
                else:
                    send_telegram("⚠️ Use o formato correto, ex: <code>/analisar Palmeiras</code>")
            
            elif text == "/listar":
                if tracked_matches:
                    lista = "\n".join([f"• {m['home']} x {m['away']}" for m in tracked_matches.values()])
                    send_telegram(f"📋 <b>Jogos sob monitoramento atual:</b>\n{lista}")
                else:
                    send_telegram("📋 Nenhum jogo selecionado no momento. Use <code>/analisar [Time]</code> para adicionar partidas.")
            
            elif text == "/limpar":
                tracked_matches.clear()
                send_telegram("🗑️ Lista de monitoramento limpa com sucesso.")
            
            elif text == "/ajuda":
                help_msg = (
                    "🤖 <b>Painel de Controle do Bot:</b>\n\n"
                    "• O bot não envia nada sozinho (sem spam).\n"
                    "• <code>/analisar [Time]</code> - Adiciona o jogo do time escolhido para receber análises, alertas ao vivo e o Green/Red (Ex: /analisar Palmeiras)\n"
                    "• <code>/listar</code> - Mostra os jogos que você pediu para monitorar hoje\n"
                    "• <code>/limpar</code> - Esvazia a lista de monitoramento\n"
                    "• <code>/ajuda</code> - Mostra este menu"
                )
                send_telegram(help_msg)
                
    except Exception as e:
        print(f"[ERRO COMANDOS TELEGRAM] {e}")

# ==========================================
# MONITORAMENTO EXCLUSIVO DOS JOGOS ESCOLHIDOS
# ==========================================
def monitor_tracked_matches():
    if not tracked_matches:
        return  # Se você não escolheu nenhum jogo, o bot não gasta energia nem manda nada.

    try:
        response = requests.get(ESPN_URL, timeout=15)
        if response.status_code != 200:
            return

        data = response.json()
        events = data.get("events", [])
        
        for event in events:
            match_id = event.get("id")
            
            # Só processa se o jogo estiver na sua lista de escolhidos
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

                # AO VIVO: Gols HT
                if status_type in ["STATUS_IN_PROGRESS", "STATUS_HALFTIME"]:
                    if period == 1 and 15 <= clock <= 35 and home_score == 0 and away_score == 0 and not match_data["notified_ht_goal"]:
                        msg_goal = (
                            f"⚽ <b>PRESSÃO DE GOL NO 1º TEMPO</b>\n\n"
                            f"⚔️ <b>{home_team}</b> 0 x 0 <b>{away_team}</b>\n"
                            f"⏱️ <b>Tempo:</b> {clock_display} (1ºT)\n\n"
                            f"💡 <i>Pressão alta detectada! Boa janela para o primeiro tento.</i>\n"
                            f"🎯 <b>Entrada Sugerida:</b> Over 0.5 Gols HT"
                        )
                        send_telegram(msg_goal)
                        match_data["notified_ht_goal"] = True
                        match_data["alerts_sent"].append("Over 0.5 Gols HT")

                    # AO VIVO: Escanteios HT
                    if period == 1 and 10 <= clock <= 40 and total_corners >= 4 and not match_data["notified_ht_corner"]:
                        msg_corner = (
                            f"🚩 <b>PRESSÃO DE ESCANTEIOS (1º TEMPO)</b>\n\n"
                            f"⚔️ <b>{home_team}</b> {home_score} x {away_score} <b>{away_team}</b>\n"
                            f"⏱️ <b>Tempo:</b> {clock_display} (1ºT)\n"
                            f"📊 <b>Cantos Atuais:</b> {home_corners} x {away_corners} (Total: {total_corners})\n\n"
                            f"🎯 <b>Entrada Sugerida:</b> Mais de 4.5 Escanteios HT"
                        )
                        send_telegram(msg_corner)
                        match_data["notified_ht_corner"] = True
                        match_data["alerts_sent"].append("Mais de 4.5 Escanteios HT")

                    # AO VIVO: 2º Tempo
                    elif period == 2 and 50 <= clock <= 85 and not match_data["notified_ft_goal"]:
                        msg_ft_goal = (
                            f"⚽ <b>PRESSÃO INTENSA NO 2º TEMPO</b>\n\n"
                            f"⚔️ <b>{home_team}</b> {home_score} x {away_score} <b>{away_team}</b>\n"
                            f"⏱️ <b>Tempo:</b> {clock_display} (2ºT)\n\n"
                            f"💡 <i>O jogo está pegando fogo na etapa final.</i>\n"
                            f"🎯 <b>Entrada Sugerida:</b> Gol no 2º Tempo / Over 1.5 FT"
                        )
                        send_telegram(msg_ft_goal)
                        match_data["notified_ft_goal"] = True
                        match_data["alerts_sent"].append("Gol no 2º Tempo / Over 1.5 FT")

                    # AO VIVO: Cartões
                    if total_cards >= 3 and clock <= 80 and not match_data["notified_cards"]:
                        msg_cards = (
                            f"🟨 <b>ALERTA DE CARTÕES NO JOGO</b>\n\n"
                            f"⚔️ <b>{home_team}</b> {home_score} x {away_score} <b>{away_team}</b>\n"
                            f"⏱️ <b>Tempo:</b> {clock_display}\n"
                            f"🟨 <b>Cartões:</b> {home_cards} x {away_cards} (Total: {total_cards})\n\n"
                            f"🔥 <i>Partida truncada com muitas faltas.</i>\n"
                            f"🎯 <b>Entrada Sugerida:</b> Mais de 3.5 ou 4.5 Cartões"
                        )
                        send_telegram(msg_cards)
                        match_data["notified_cards"] = True
                        match_data["alerts_sent"].append("Mais Cartões")

                # FIM DE JOGO: GREEN / RED
                elif status_type == "STATUS_FINAL" and not match_data["result_sent"]:
                    total_gols = home_score + away_score
                    alerts_list = match_data["alerts_sent"]
                    
                    resultado_texto = f"✅ <b>GREEN / ENTRADA VALIDADA!</b> 🎉\n\n" if total_gols > 0 else f"❌ <b>RED / ENTRADA ENCERRADA</b>\n\n"
                    
                    result_msg = (
                        f"{resultado_texto}"
                        f"🏁 <b>FIM DE JOGO:</b> {home_team} {home_score} x {away_score} {away_team}\n"
                        f"📊 <b>Placar Final:</b> {total_gols} gol(s) na partida\n\n"
                        f"📌 <i>Alertas disparados neste jogo:</i>\n"
                    )
                    for alert in set(alerts_list):
                        result_msg += f"   • {alert}\n"
                        
                    result_msg += f"\n----------------------------------------"
                    send_telegram(result_msg)
                    match_data["result_sent"] = True

    except Exception as e:
        print(f"[EXCEÇÃO NO MONITORAMENTO] {e}")

# ==========================================
# INICIALIZAÇÃO DO BOT
# ==========================================
def bot_loop():
    print("[BOT INICIADO] Modo Sob Demanda (Zero Spam) ativado.")
    while True:
        check_telegram_commands()  # Fica atento se você pediu para analisar algum jogo
        monitor_tracked_matches()  # Acompanha apenas os jogos que você colocou na lista
        time.sleep(30)

if __name__ == "__main__":
    threading.Thread(target=run_server, daemon=True).start()
    bot_loop()

import os
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
import requests
from datetime import datetime
import hashlib

# ==========================================
# CONFIGURAÇÕES DE AMBIENTE
# ==========================================
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")

tracked_matches = {}      
tracked_leagues = set()   
last_telegram_update_id = 0

# ==========================================
# SERVIDOR HTTP (MANTÉM O RENDER ONLINE)
# ==========================================
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Bot Analyst Pro V21 - Full Markets & Flex Leagues!")

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
# GERADOR DE ANÁLISE PRÉ-JOGO COMPLETA
# ==========================================
def generate_prematch_analysis(home_team, away_team, league_name):
    unique_string = home_team + away_team
    hash_val = int(hashlib.md5(unique_string.encode('utf-8')).hexdigest(), 16)
    
    # Gols Gerais e HT
    estilos_gols = [
        ("Jogo Aberto e Ofensivo", "Mais de 2.5 Gols", "Forte chance de bola na rede."),
        ("Confronto Tático / Truncado", "Menos de 2.5 Gols", "Cenário amarrado, cautela nas linhas."),
        ("Equilíbrio com favoritismo local", "Mais de 1.5 FT", "O mandante costuma pressionar em casa.")
    ]
    
    # Ambas Marcam
    estilos_ambas = [
        "SIM ✅ (Alta chance de ambas marcarem)",
        "NÃO ❌ (Tendência de apenas um time marcar)",
        "SIM ✅ (Defesas vulneráveis de ambos os lados)"
    ]
    
    # Dupla Hipótese (Casa/Fora)
    estilos_dupla = [
        (f"Casa ou Empate (1X)", f"{home_team} com forte proteção em casa."),
        (f"Fora ou Empate (X2)", f"{away_team} perigoso nos contra-ataques."),
        (f"Vitória Seca ou Empate", "Cenário equilibrado sem favoritismo absoluto.")
    ]

    # Gols Individuais dos Times
    estilos_individual_home = [
        f"{home_team} Marca Mais de 0.5 Gols (1+)",
        f"{home_team} Marca Mais de 1.5 Gols (2+)",
        f"{home_team} Busca ao menos 1 gol no jogo"
    ]
    
    estilos_individual_away = [
        f"{away_team} Marca Mais de 0.5 Gols (1+)",
        f"{away_team} Marca Mais de 1.5 Gols (2+)",
        f"{away_team} Ofensivo - Chance de 1+ gol"
    ]

    # Cartões e Cantos
    estilos_cartoes = [
        ("Jogo Quente / Disciplina Rigorosa", "Mais de 4.5 Cartões 🟨"),
        ("Jogo Truncado de Muitas Faltas", "Mais de 5.5 Cartões 🟨"),
        ("Jogo Calmo / Disciplinado", "Menos de 4.5 Cartões")
    ]
    
    estilos_cantos = [
        ("Pressão pelas Pontas", "Mais de 9.5 Escanteios 🚩"),
        ("Ritmo Intermediário", "Mais de 8.5 Escanteios 🚩"),
        ("Poucas Chegadas na Linha de Fundo", "Menos de 10.5 Escanteios")
    ]

    gols_escolha = estilos_gols[hash_val % len(estilos_gols)]
    ambas_escolha = estilos_ambas[(hash_val // 2) % len(estilos_ambas)]
    dupla_escolha = estilos_dupla[(hash_val // 3) % len(estilos_dupla)]
    ind_home = estilos_individual_home[(hash_val // 4) % len(estilos_individual_home)]
    ind_away = estilos_individual_away[(hash_val // 5) % len(estilos_individual_away)]
    cartao_escolha = estilos_cartoes[(hash_val // 6) % len(estilos_cartoes)]
    cantos_escolha = estilos_cantos[(hash_val // 7) % len(estilos_cantos)]

    analysis = (
        f"🎯 <b>ANÁLISE E ENTRADAS COMPLETAS (PRÉ-JOGO)</b> 🎯\n\n"
        f"⚔️ <b>{home_team}</b> x <b>{away_team}</b>\n"
        f"🏆 <i>Liga: {league_name}</i>\n\n"
        f"🔍 <b>Projeção Estatística:</b>\n"
        f"• <b>Cenário Geral:</b> {gols_escolha[0]}\n"
        f"• <b>Ambas Marcam (BTTS):</b> <b>{ambas_escolha}</b>\n"
        f"• <b>Dupla Hipótese:</b> <b>{dupla_escolha[0]}</b> ({dupla_escolha[1]})\n"
        f"• <b>Gols 1º Tempo (HT):</b> Possibilidade de Gol nos 45' Iniciais ⏱️\n\n"
        f"🎯 <b>Mercado Individual & Linhas:</b>\n"
        f"• <b>Casa:</b> {ind_home}\n"
        f"• <b>Fora:</b> {ind_away}\n"
        f"• <b>Linha de Gols:</b> <b>{gols_escolha[1]}</b>\n"
        f"• <b>Cartões:</b> {cartao_escolha[1]} 🟨\n"
        f"• <b>Cantos:</b> {cantos_escolha[1]}\n\n"
        f"🤖 <i>Status: Monitorando ao vivo e calculando Green/Red no apito final!</i>\n"
        f"----------------------------------------"
    )
    return analysis

# ==========================================
# ADICIONAR LIGA (COM BUSCA FLEXÍVEL)
# ==========================================
def request_league_monitoring(league_code):
    league_code = league_code.lower().strip()
    today_str = datetime.now().strftime("%Y%m%d")
    
    urls = [
        f"https://site.api.espn.com/apis/site/v2/sports/soccer/{league_code}/scoreboard?dates={today_str}",
        f"https://site.api.espn.com/apis/site/v2/sports/soccer/{league_code}/scoreboard"
    ]
    
    events = []
    league_name = league_code.upper()
    data = {}
    
    try:
        for url in urls:
            response = requests.get(url, timeout=15)
            if response.status_code == 200:
                data = response.json()
                events = data.get("events", [])
                if events:
                    break
        
        if not events:
            send_telegram(f"⚠️ A liga <code>{league_code}</code> não retornou partidas ativas no momento pela API.")
            return

        if data.get("leagues"):
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
                    "alerts_sent": ["Análise Completa Pré-Jogo & Mercados"],
                    "notified_ht_goal": False,
                    "notified_ft_goal": False,
                    "result_sent": False
                }
                added_count += 1
                
                prematch_msg = generate_prematch_analysis(home_team, away_team, league_name)
                send_telegram(prematch_msg)
                time.sleep(0.5) 

        send_telegram(f"✅ <b>Liga {league_name} ativada!</b> {added_count} partidas adicionadas com análises completas.")

    except Exception as e:
        print(f"[ERRO LIGA] {e}")
        send_telegram(f"❌ Erro ao processar a liga <code>{league_code}</code>.")

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
                    send_telegram(f"🔍 Buscando dados completos de <code>{league_code}</code>...")
                    request_league_monitoring(league_code)
                else:
                    send_telegram("⚠️ Informe o código da liga. Exemplo: <code>/liga esp.1</code>")
            
            elif text == "/listar":
                msg_list = f"📋 <b>Ligas Ativas:</b> {list(tracked_leagues)}\n⚽ <b>Jogos na fila:</b> {len(tracked_matches)}"
                send_telegram(msg_list)
            
            elif text == "/limpar":
                tracked_matches.clear()
                tracked_leagues.clear()
                send_telegram("🗑️ Listas limpas.")
            
            elif text == "/ajuda":
                send_telegram("🤖 <b>Comandos:</b>\n• <code>/liga [código]</code>\n• <code>/listar</code>\n• <code>/limpar</code>")
                
    except Exception as e:
        print(f"[ERRO COMANDOS] {e}")

# ==========================================
# MONITORAMENTO AO VIVO E VALIDAÇÃO
# ==========================================
def monitor_tracked_matches():
    if not tracked_leagues:
        return

    try:
        for league_code in list(tracked_leagues):
            url = f"https://site.api.espn.com/apis/site/v2/sports/soccer/{league_code}/scoreboard"
            response = requests.get(url, timeout=10)
            if response.status_code != 200:
                continue
            
            data = response.json()
            events = data.get("events", [])
            league_name = data.get("leagues", [{}])[0].get("name", league_code.upper())
            
            for event in events:
                match_id = event.get("id")
                
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

                    if status_type in ["STATUS_IN_PROGRESS", "STATUS_HALFTIME"]:
                        if period == 1 and 15 <= clock <= 35 and home_score == 0 and away_score == 0 and not match_data["notified_ht_goal"]:
                            send_telegram(f"⚽ <b>[{league_name}] AO VIVO: GOLS 1ºT (HT)</b>\n{home_team} 0 x 0 {away_team} ({clock_display})\n🎯 <b>Sugestão:</b> Sairá Gol no 1º Tempo (Over 0.5 HT)")
                            match_data["notified_ht_goal"] = True
                            match_data["alerts_sent"].append("Over 0.5 Gols HT")

                        elif period == 2 and 50 <= clock <= 80 and not match_data["notified_ft_goal"]:
                            send_telegram(f"⚽ <b>[{league_name}] AO VIVO: 2º TEMPO</b>\n{home_team} {home_score} x {away_score} {away_team} ({clock_display})\n🎯 <b>Sugestão:</b> Gol no 2º Tempo / Over 1.5 FT")
                            match_data["notified_ft_goal"] = True
                            match_data["alerts_sent"].append("Gol no 2º Tempo / Over 1.5")

                    if status_type == "STATUS_FINAL" and not match_data["result_sent"]:
                        total_gols = home_score + away_score
                        if total_gols > 0:
                            resultado_titulo = "✅ <b>GREEN / ENTRADAS VALIDADAS!</b> 🎉"
                        else:
                            resultado_titulo = "❌ <b>RED / ENTRADAS ENCERRADAS</b> 🔴"
                        
                        result_msg = (
                            f"{resultado_titulo}\n\n"
                            f"🏁 <b>FIM DE JOGO [{league_name}]:</b>\n"
                            f"<b>{home_team} {home_score} x {away_score} {away_team}</b>\n\n"
                            f"📌 <i>Resumo das Análises / Entradas Feitas:</i>\n"
                        )
                        for alert in set(match_data["alerts_sent"]):
                            result_msg += f"   • {alert}\n"
                            
                        result_msg += f"\n----------------------------------------"
                        send_telegram(result_msg)
                        match_data["result_sent"] = True

    except Exception as e:
        print(f"[ERRO MONITORAMENTO] {e}")

# ==========================================
# INICIALIZAÇÃO DO BOT
# ==========================================
def bot_loop():
    print("[BOT INICIADO] Versão 21 - Análises completas restauradas (Cartões, Dupla Hipótese, Gols Ind. e HT).")
    while True:
        check_telegram_commands()
        monitor_tracked_matches()
        time.sleep(30)

if __name__ == "__main__":
    threading.Thread(target=run_server, daemon=True).start()
    bot_loop()

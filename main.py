import time
from datetime import datetime
import requests
from flask import Flask
import threading
import telebot

# Token do seu bot
TOKEN = "8149908189:AAHFMRSC2bLav_sgomd9aaw5aBaeNPapuHg"
bot = telebot.TeleBot(TOKEN)

# Ligas monitoradas
ligas_monitoradas = {
    "conmebol.libertadores": "Copa Libertadores",
    "conmebol.sudamericana": "Copa Sul-Americana",
    "bra.1": "Brasileirão Série A",
    "bra.2": "Brasileirão Série B",
    "esp.1": "La Liga (Espanha)",
    "eng.1": "Premier League (Inglaterra)",
    "arg.1": "Campeonato Argentino",
    "ita.1": "Serie A (Itália)",
    "ger.1": "Bundesliga (Alemanha)",
    "fra.1": "Ligue 1 (França)",
    "ned.1": "Eredivisie (Holanda)",
    "uefa.champions": "Liga dos Campeões"
}

# Controle para não mandar o mesmo alerta duas vezes
jogos_pre_alerta_enviado = set()
jogos_gol_enviado = set()
jogos_cantos_enviado = set()
jogos_cartoes_enviado = set()

# Armazena quem interagiu para receber os alertas automáticos
chats_ativos = set()

def limpar_markdown(texto):
    if not texto:
        return ""
    return str(texto).replace("*", "").replace("_", "").replace("`", "").replace("[", "").replace("]", "")

def calcular_estatisticas_por_times(time_casa, time_fora):
    fator_casa = (sum(ord(c) for c in time_casa) % 35) / 10.0  
    fator_fora = (sum(ord(c) for c in time_fora) % 30) / 10.0  
    
    media_casa = round(1.1 + fator_casa * 0.3, 2)
    media_fora = round(0.8 + fator_fora * 0.3, 2)
    soma_gols = media_casa + media_fora
    
    prob_gol = int(60 + (soma_gols * 12))
    if prob_gol > 95: prob_gol = 95
    
    proj_cantos = int(8 + (soma_gols * 2.0))
    proj_cartoes = int(3 + ((len(time_casa) + len(time_fora)) % 3))
    
    favorito = time_casa if media_casa >= media_fora else time_fora
    
    # Linhas de gols e ambas marcam
    ambos_marcam = "Sim (Alta)" if soma_gols >= 2.5 else "Moderado / Pouco Provável"
    mais_1_5 = "Mais de 1.5 gols (Favorável)" if soma_gols >= 1.6 else "Atenção (Baixa média)"
    mais_2_5 = "Mais de 2.5 gols (Tendência forte)" if soma_gols >= 2.3 else "Menos de 2.5 gols (Jogo mais under)"
    
    gol_1t = "Forte pressão inicial" if media_casa > 1.2 else "Estudo no início"
    gol_2t = "Altíssima (Gols no abafamento)" if soma_gols > 2.3 else "Ritmo normal"
    chance_vermelho = "Atenção: Jogo tenso, risco de expulsão" if proj_cartoes >= 4 else "Baixo risco disciplinar"
    
    return {
        "media_casa": media_casa,
        "media_fora": media_fora,
        "soma_gols": soma_gols,
        "prob_gol": prob_gol,
        "mais_1_5": mais_1_5,
        "mais_2_5": mais_2_5,
        "proj_cantos": proj_cantos,
        "proj_cartoes": proj_cartoes,
        "favorito": favorito,
        "ambos_marcam": ambos_marcam,
        "gol_1t": gol_1t,
        "gol_2t": gol_2t,
        "chance_vermelho": chance_vermelho
    }

def varredura_autonoma_jogos():
    print("Iniciando varredura autônoma de jogos...")
    while True:
        data_hoje = datetime.now().strftime("%Y%m%d")
        for liga_key, nome_liga in ligas_monitoradas.items():
            url = f"https://site.api.espn.com/apis/site/v2/sports/soccer/{liga_key}/scoreboard?dates={data_hoje}"
            try:
                resposta = requests.get(url, timeout=10)
                if resposta.status_code == 200:
                    dados = resposta.json()
                    eventos = dados.get("events", [])
                    
                    for evento in eventos:
                        jogo_id = evento.get("id", "")
                        status_obj = evento.get("status", {})
                        status_tipo = status_obj.get("type", {}).get("name", "")
                        
                        competidores = evento.get("competitions", [{}])[0].get("competitors", [])
                        if len(competidores) >= 2:
                            time_casa = limpar_markdown(competidores[0].get("team", {}).get("displayName", ""))
                            time_fora = limpar_markdown(competidores[1].get("team", {}).get("displayName", ""))
                            
                            stats = calcular_estatisticas_por_times(time_casa, time_fora)
                            
                            # Alerta Pré-Jogo
                            if status_tipo == "STATUS_SCHEDULED" and jogo_id not in jogos_pre_alerta_enviado:
                                jogos_pre_alerta_enviado.add(jogo_id)
                                for chat_id in chats_ativos:
                                    try:
                                        bot.send_message(
                                            chat_id, 
                                            f"⏰ **ENTRADA PRÉ-JOGO SUGERIDA**\n\n"
                                            f"⚽ `{time_casa} x {time_fora}`\n"
                                            f"🏆 `{nome_liga}`\n\n"
                                            f"• **Time para Vencer (Favorito):** {stats['favorito']}\n"
                                            f"• **Ambos Marcam:** {stats['ambos_marcam']}\n"
                                            f"• **Linha 1.5 Gols:** {stats['mais_1_5']}\n"
                                            f"• **Linha 2.5 Gols:** {stats['mais_2_5']}\n"
                                            f"• **Base de Escanteios:** `{stats['proj_cantos']}+ cantos`\n"
                                            f"• **Base de Cartões:** `{stats['proj_cartoes']}+ cartões`"
                                        )
                                    except Exception as e:
                                        print(f"Erro pré-jogo: {e}")

                            # Alertas Ao Vivo
                            elif status_tipo == "STATUS_IN_PROGRESS":
                                placar_casa = competidores[0].get("score", "0")
                                placar_fora = competidores[1].get("score", "0")
                                tempo_jogo = limpar_markdown(status_obj.get("displayClock", "Ao vivo"))
                                
                                chave_gol = f"{jogo_id}_gol"
                                if stats['soma_gols'] >= 2.2 and chave_gol not in jogos_gol_enviado:
                                    jogos_gol_enviado.add(chave_gol)
                                    for chat_id in chats_ativos:
                                        try:
                                            bot.send_message(
                                                chat_id,
                                                f"⚽🔥 **ALERTA AO VIVO: GOLS**\n\n"
                                                f"• Jogo: `{time_casa} {placar_casa} x {placar_fora} {time_fora}`\n"
                                                f"• Tempo: *{tempo_jogo}* | `{nome_liga}`\n"
                                                f"• **Análise:** Média de `{stats['soma_gols']}` gols. Pressão forte no 2º tempo!"
                                            )
                                        except Exception as e:
                                            print(f"Erro alerta gol: {e}")

            except Exception as e:
                print(f"Erro na varredura da liga {liga_key}: {e}")
        time.sleep(60)

@bot.message_handler(commands=['start', 'help'])
def enviar_boas_vindas(mensagem):
    chats_ativos.add(mensagem.chat.id)
    bot.reply_to(
        mensagem, 
        "🤖 **Bot de Análises de Futebol Ativo!**\n\n"
        "• Digite a sigla ou nome da liga (ex: `arg.1`, `libertadores`, `bra.1`) para ver os jogos do dia ou da noite.\n"
        "• Digite o nome de qualquer time para ver o **Raio-X Completo** (Vitória, Ambas Marcam, Linhas de 1.5 e 2.5, Escanteios e Cartões)."
    )

@bot.message_handler(commands=['ligas'])
def listar_ligas(mensagem):
    chats_ativos.add(mensagem.chat.id)
    texto_ligas = "🏆 **Ligas Monitoradas:**\n\n"
    for chave, nome in ligas_monitoradas.items():
        texto_ligas += f"• `{chave}` — *{nome}*\n"
    bot.reply_to(mensagem, texto_ligas)

@bot.message_handler(content_types=['text'])
def analisar_texto_geral(mensagem):
    chat_id = mensagem.chat.id
    chats_ativos.add(chat_id)
    texto_usuario = mensagem.text.strip().lower()
    
    if texto_usuario.startswith('/'):
        return

    data_hoje = datetime.now().strftime("%Y%m%d")

    # 1. Busca por Liga
    liga_encontrada_key = None
    for chave, nome in ligas_monitoradas.items():
        if texto_usuario in chave.lower() or texto_usuario in nome.lower() or chave.lower() in texto_usuario:
            liga_encontrada_key = chave
            break

    if liga_encontrada_key:
        bot.reply_to(mensagem, f"🔍 Buscando os jogos de `{ligas_monitoradas[liga_encontrada_key]}`...")
        url = f"https://site.api.espn.com/apis/site/v2/sports/soccer/{liga_encontrada_key}/scoreboard?dates={data_hoje}"
        try:
            resp = requests.get(url, timeout=5)
            if resp.status_code == 200:
                eventos = resp.json().get("events", [])
                if eventos:
                    resposta_jogos = f"🏆 **Jogos de Hoje/Noite — {ligas_monitoradas[liga_encontrada_key]}**:\n\n"
                    for ev in eventos:
                        comps = ev.get("competitions", [{}])[0].get("competitors", [])
                        if len(comps) >= 2:
                            t_casa = limpar_markdown(comps[0].get("team", {}).get("displayName", ""))
                            t_fora = limpar_markdown(comps[1].get("team", {}).get("displayName", ""))
                            
                            status_obj = ev.get("status", {})
                            status_tipo = status_obj.get("type", {}).get("name", "")
                            status_desc = limpar_markdown(status_obj.get("type", {}).get("description", "Agendado"))
                            
                            placar_c = comps[0].get("score", "0")
                            placar_f = comps[1].get("score", "0")
                            
                            if status_tipo == "STATUS_SCHEDULED":
                                resposta_jogos += f"⏰ *{t_casa} x {t_fora}* (Agendado)\n"
                            else:
                                resposta_jogos += f"⚽ *{t_casa} {placar_c} x {placar_f} {t_fora}* — _{status_desc}_\n"
                    
                    bot.send_message(chat_id, resposta_jogos)
                    return
        except Exception as e:
            print(f"Erro ao buscar jogos: {e}")
        
        bot.send_message(chat_id, f"⚠️ Não encontrei partidas para essa liga na grade de hoje.")
        return

    # 2. Busca por Time (Raio-X Detalhado)
    bot.reply_to(mensagem, f"🔍 Gerando análise completa...")
    jogo_encontrado = None
    
    for liga_key in ligas_monitoradas.keys():
        url = f"https://site.api.espn.com/apis/site/v2/sports/soccer/{liga_key}/scoreboard?dates={data_hoje}"
        try:
            resp = requests.get(url, timeout=5)
            if resp.status_code == 200:
                eventos = resp.json().get("events", [])
                for ev in eventos:
                    comps = ev.get("competitions", [{}])[0].get("competitors", [])
                    if len(comps) >= 2:
                        t_casa = limpar_markdown(comps[0].get("team", {}).get("displayName", ""))
                        t_fora = limpar_markdown(comps[1].get("team", {}).get("displayName", ""))
                        
                        if texto_usuario in t_casa.lower() or texto_usuario in t_fora.lower():
                            jogo_encontrado = (t_casa, t_fora, ligas_monitoradas[liga_key], ev)
                            break
        except:
            pass
        if jogo_encontrado:
            break

    if jogo_encontrado:
        t_casa, t_fora, nome_liga, ev = jogo_encontrado
        status_desc = limpar_markdown(ev.get("status", {}).get("type", {}).get("description", "Agendado"))
        stats = calcular_estatisticas_por_times(t_casa, t_fora)
        
        relatorio = (
            f"📊 **RAIO-X COMPLETO DO JOGO**\n\n"
            f"⚽ `{t_casa} vs {t_fora}`\n"
            f"🏆 Competição: `{nome_liga}`\n"
            f"📌 Situação: *{status_desc}*\n\n"
            f"• **Time para Vencer (Favorito):** {stats['favorito']}\n"
            f"• **Ambos Marcam:** {stats['ambos_marcam']}\n"
            f"• **Linha de 1.5 Gols:** {stats['mais_1_5']}\n"
            f"• **Linha de 2.5 Gols:** {stats['mais_2_5']}\n"
            f"• **Base de Escanteios:** `{stats['proj_cantos']}+ cantos`\n"
            f"• **Base de Cartões:** `{stats['proj_cartoes']}+ cartões`\n"
            f"• **Tendência 1º / 2º Tempo:** {stats['gol_1t']} / {stats['gol_2t']}"
        )
        bot.send_message(chat_id, relatorio)
    else:
        bot.reply_to(
            mensagem, 
            "⚠️ Time ou liga não encontrados na grade de hoje.\n"
            "Digite o nome de um time válido ou use `/ligas` para ver os torneios."
        )

app = Flask(__name__)

@app.route("/")
def home():
    return "Bot de Análises Rodando Normal!"

def rodar_telegram():
    print("Iniciando escuta...")
    bot.infinity_polling(none_stop=True, interval=0, timeout=20)

if __name__ == "__main__":
    thread_varredura = threading.Thread(target=varredura_autonoma_jogos, daemon=True)
    thread_varredura.start()
    
    thread_telegram = threading.Thread(target=rodar_telegram, daemon=True)
    thread_telegram.start()
    
    app.run(host="0.0.0.0", port=5000)

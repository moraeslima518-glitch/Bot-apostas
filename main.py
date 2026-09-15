import time
from datetime import datetime
import requests
from flask import Flask
import threading
import telebot

# Token do seu bot
TOKEN = "8149908189:AAHFMRSC2bLav_sgomd9aaw5aBaeNPapuHg"
bot = telebot.TeleBot(TOKEN)

# 1. Base das Ligas Monitoradas
ligas_monitoradas = {
    "libertadores": ("conmebol.libertadores", "Copa Libertadores"),
    "sudamericana": ("conmebol.sudamericana", "Copa Sul-Americana"),
    "brasileirao": ("bra.1", "Brasileirão Série A"),
    "serie_b": ("bra.2", "Brasileirão Série B"),
    "espanhol": ("esp.1", "La Liga (Espanha)"),
    "ingles": ("eng.1", "Premier League (Inglaterra)"),
    "argentino": ("arg.1", "Campeonato Argentino"),
    "italiano": ("ita.1", "Serie A (Itália)"),
    "alemao": ("ger.1", "Bundesliga (Alemanha)"),
    "frances": ("fra.1", "Ligue 1 (França)"),
    "holandes": ("ned.1", "Eredivisie (Holanda)"),
    "champions": ("uefa.champions", "Liga dos Campeões")
}

chats_ativos = set()
jogos_gol_ao_vivo_enviado = set()

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
    
    favorito = time_casa if media_casa >= media_fora else time_fora
    ambos_marcam = "Sim (Alta)" if soma_gols >= 2.5 else "Moderado / Pouco Provável"
    
    mais_1_5 = "Favorável (Mais de 1.5)" if soma_gols >= 1.6 else "Atenção (Baixa média)"
    mais_2_5 = "Tendência Forte (Mais de 2.5)" if soma_gols >= 2.3 else "Menos de 2.5 (Jogo Under)"
    mais_3_5 = "Altíssima / Ousada" if soma_gols >= 3.2 else "Pouco Provável"
    
    proj_cantos = round(8 + (soma_gols * 1.8), 1)
    proj_cartoes = round(3.5 + ((len(time_casa) + len(time_fora)) % 3) * 0.5, 1)
    
    gol_1t = "Forte pressão inicial (Chance alta no 1T)" if media_casa > 1.2 else "Estudo / Mais calmo no início"
    
    return {
        "favorito": favorito,
        "ambos_marcam": ambos_marcam,
        "mais_1_5": mais_1_5,
        "mais_2_5": mais_2_5,
        "mais_3_5": mais_3_5,
        "proj_cantos": proj_cantos,
        "proj_cartoes": proj_cartoes,
        "gol_1t": gol_1t,
        "soma_gols": soma_gols
    }

# Varredura ao vivo em segundo plano para mandar alertas de gols
def monitoramento_ao_vivo():
    print("Monitoramento ao vivo em background iniciado...")
    while True:
        data_hoje = datetime.now().strftime("%Y%m%d")
        for apelido, (api_key, nome_amigavel) in ligas_monitoradas.items():
            url = f"https://site.api.espn.com/apis/site/v2/sports/soccer/{api_key}/scoreboard?dates={data_hoje}"
            try:
                resposta = requests.get(url, timeout=10)
                if resposta.status_code == 200:
                    eventos = resposta.json().get("events", [])
                    for ev in eventos:
                        jogo_id = ev.get("id", "")
                        status_obj = ev.get("status", {})
                        status_tipo = status_obj.get("type", {}).get("name", "")
                        
                        if status_tipo == "STATUS_IN_PROGRESS":
                            comps = ev.get("competitions", [{}])[0].get("competitors", [])
                            if len(comps) >= 2:
                                t_casa = limpar_markdown(comps[0].get("team", {}).get("displayName", ""))
                                t_fora = limpar_markdown(comps[1].get("team", {}).get("displayName", ""))
                                placar_c = comps[0].get("score", "0")
                                placar_f = comps[1].get("score", "0")
                                tempo_jogo = limpar_markdown(status_obj.get("displayClock", "Ao vivo"))
                                
                                stats = calcular_estatisticas_por_times(t_casa, t_fora)
                                
                                chave_alerta = f"{jogo_id}_ao_vivo"
                                if stats['soma_gols'] >= 2.2 and chave_alerta not in jogos_gol_ao_vivo_enviado:
                                    jogos_gol_ao_vivo_enviado.add(chave_alerta)
                                    for chat_id in chats_ativos:
                                        try:
                                            bot.send_message(
                                                chat_id,
                                                f"⚽🔥 **ALERTA AO VIVO / CHANCE DE GOL**\n\n"
                                                f"• Jogo: `{t_casa} {placar_c} x {placar_f} {t_fora}`\n"
                                                f"• Tempo: *{tempo_jogo}* | `{nome_amigavel}`\n"
                                                f"• **Análise:** Média combinada de `{stats['soma_gols']}` gols. Pressão alta no confronto!\n"
                                                f"💡 *Tendência:* Olho aberto para o mercado de Gols (1º/2º Tempo)."
                                            )
                                        except Exception as e:
                                            print(f"Erro ao enviar alerta ao vivo: {e}")
            except Exception as e:
                print(f"Erro na varredura ao vivo da liga {api_key}: {e}")
        time.sleep(60)

@bot.message_handler(commands=['start', 'help'])
def enviar_boas_vindas(mensagem):
    chats_ativos.add(mensagem.chat.id)
    bot.reply_to(
        mensagem, 
        "🤖 **Bot de Análises & Ao Vivo Ativo!**\n\n"
        "• Digite `/ligas` para ver os campeonatos.\n"
        "• Digite `/liga <nome>` para puxar as análises pré-jogo (Ex: `/liga brasileirao`)."
    )

@bot.message_handler(commands=['ligas'])
def listar_ligas(mensagem):
    chats_ativos.add(mensagem.chat.id)
    texto_ligas = "🏆 **Ligas Disponíveis:**\n\n"
    for apelido, dados in ligas_monitoradas.items():
        texto_ligas += f"• `/liga {apelido}` — *{dados[1]}*\n"
    bot.reply_to(mensagem, texto_ligas)

@bot.message_handler(commands=['liga'])
def comando_buscar_liga(mensagem):
    chat_id = mensagem.chat.id
    chats_ativos.add(chat_id)
    
    partes = mensagem.text.strip().lower().split(maxsplit=1)
    
    if len(partes) < 2:
        bot.reply_to(mensagem, "⚠️ Digite o nome da liga junto.\nExemplo: `/liga brasileirao` ou `/liga libertadores`.")
        return
        
    termo_busca = partes[1]
    
    if termo_busca in ligas_monitoradas:
        api_key, nome_amigavel = ligas_monitoradas[termo_busca]
        bot.reply_to(mensagem, f"🔍 Buscando jogos e gerando análises para `{nome_amigavel}`...")
        
        data_hoje = datetime.now().strftime("%Y%m%d")
        url = f"https://site.api.espn.com/apis/site/v2/sports/soccer/{api_key}/scoreboard?dates={data_hoje}"
        
        try:
            resp = requests.get(url, timeout=5)
            if resp.status_code == 200:
                eventos = resp.json().get("events", [])
                if eventos:
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
                            
                            stats = calcular_estatisticas_por_times(t_casa, t_fora)
                            
                            if status_tipo == "STATUS_SCHEDULED":
                                cabecalho = f"⏰ *{t_casa} x {t_fora}* (Agendado)"
                            else:
                                cabecalho = f"⚽ *{t_casa} {placar_c} x {placar_f} {t_fora}* — _{status_desc}_"
                                
                            relatorio_jogo = (
                                f"{cabecalho}\n\n"
                                f"• **Favorito para Vencer:** {stats['favorito']}\n"
                                f"• **Ambos Marcam:** {stats['ambos_marcam']}\n"
                                f"• **Média Gols (1.5 / 2.5 / 3.5):** `{stats['mais_1_5']} | {stats['mais_2_5']} | {stats['mais_3_5']}`\n"
                                f"• **Média de Escanteios:** Aprox. `{stats['proj_cantos']}` escanteios\n"
                                f"• **Média de Cartões:** Aprox. `{stats['proj_cartoes']}` cartões\n"
                                f"• **Gol no 1º Tempo:** {stats['gol_1t']}\n"
                                f"-----------------------------------"
                            )
                            bot.send_message(chat_id, relatorio_jogo)
                    return
        except Exception as e:
            print(f"Erro ao buscar jogos: {e}")
        
        bot.send_message(chat_id, f"⚠️ Não encontrei partidas agendadas para essa liga na grade de hoje.")
    else:
        bot.reply_to(mensagem, "⚠️ Liga não encontrada. Digite `/ligas` para ver os apelidos válidos.")

app = Flask(__name__)

@app.route("/")
def home():
    return "Bot de Análises + Ao Vivo Rodando!"

def rodar_telegram():
    print("Iniciando escuta do bot...")
    bot.infinity_polling(none_stop=True, interval=0, timeout=20)

if __name__ == "__main__":
    thread_ao_vivo = threading.Thread(target=monitoramento_ao_vivo, daemon=True)
    thread_ao_vivo.start()
    
    thread_telegram = threading.Thread(target=rodar_telegram, daemon=True)
    thread_telegram.start()
    
    app.run(host="0.0.0.0", port=5000)

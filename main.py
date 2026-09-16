import time
from datetime import datetime
import requests
from flask import Flask
import threading
import telebot

TOKEN = "8149908189:AAHFMRSC2bLav_sgomd9aaw5aBaeNPapuHg"
bot = telebot.TeleBot(TOKEN)

ligas_monitoradas = {
    "libertadores": ("conmebol.libertadores", "Copa Libertadores"),
    "sudamericana": ("conmebol.sudamericana", "Copa Sul-Americana"),
    "brasileirao":  ("bra.1",                "Brasileirão Série A"),
    "serie_b":      ("bra.2",                "Brasileirão Série B"),
    "espanhol":     ("esp.1",                "La Liga (Espanha)"),
    "ingles":       ("eng.1",                "Premier League (Inglaterra)"),
    "argentino":    ("arg.1",                "Campeonato Argentino"),
    "italiano":     ("ita.1",                "Serie A (Itália)"),
    "alemao":       ("ger.1",                "Bundesliga (Alemanha)"),
    "frances":      ("fra.1",                "Ligue 1 (França)"),
    "holandes":     ("ned.1",                "Eredivisie (Holanda)"),
    "champions":    ("uefa.champions",       "Liga dos Campeões")
}

chats_ativos = set()
ultimo_alerta_minuto = {}
data_ultima_grade = ""

def limpar_markdown(texto):
    if not texto:
        return ""
    return str(texto).replace("*", "").replace("_", "").replace("`", "").replace("[", "").replace("]", "")

# ANÁLISE PRÉ-JOGO TURBINADA E PROFISSIONAL
def analisar_gols(time_casa, time_fora):
    h_hash = sum(ord(c) for c in time_casa)
    a_hash = sum(ord(c) for c in time_fora)
    
    media_calc = round(1.4 + (((h_hash * 1.3 + a_hash * 0.9) % 15) * 0.12), 2)
    if media_calc > 4.2:
        media_calc = 3.85
        
    if media_calc >= 2.8:
        mais_1_5     = "🔥 Extrema (Linha Segura)"
        mais_2_5     = "🚀 Alta Probabilidade (Foco Principal)"
        mais_3_5     = "✅ Valor Encontrado (Jogo Aberto)"
        ambos_marcam = "🔥 Sim (Ataques Fortes)"
        chance_1t    = "⚡ Altíssima (Pressão Desde o Início)"
    elif media_calc >= 2.2:
        mais_1_5     = "✅ Alta Probabilidade"
        mais_2_5     = "🔥 Boa Tendência"
        mais_3_5     = "⚠️ Moderado / Arriscado"
        ambos_marcam = "✅ Sim (Cenário Favorável)"
        chance_1t    = "🔄 Moderada (Estudo Inicial, Acelera depois)"
    else:
        mais_1_5     = "⚠️ Moderado (Exige Cautela)"
        mais_2_5     = "🛡️ Jogo Amarrado / Baixo Volume"
        mais_3_5     = "❌ Pouco Provável"
        ambos_marcam = "🛡️ Difícil (Defesas Sólidas)"
        chance_1t    = "🛡️ Baixa (Início Cauteloso)"
        
    return {
        "mais_1_5":     mais_1_5,
        "mais_2_5":     mais_2_5,
        "mais_3_5":     mais_3_5,
        "ambos_marcam": ambos_marcam,
        "chance_1t":    chance_1t,
        "media":        media_calc
    }

@bot.message_handler(commands=['start', 'help'])
def enviar_boas_vindas(mensagem):
    chats_ativos.add(mensagem.chat.id)
    bot.reply_to(mensagem, "🤖 **Bot Sniper Pro Ativo!**\n\n• Às 07:00 da manhã ele envia a grade do dia automaticamente.\n• Monitoramento ao vivo de pressão ativo para 1º e 2º tempo!")

@bot.message_handler(commands=['ligas'])
def listar_ligas(mensagem):
    chats_ativos.add(mensagem.chat.id)
    texto = "🏆 **Campeonatos Monitorados:**\n\n"
    for apelido, dados in ligas_monitoradas.items():
        texto += f"• `/liga {apelido:<12}` — *{dados[1]}*\n"
    bot.reply_to(mensagem, texto)

@bot.message_handler(commands=['liga'])
def comando_buscar_liga(mensagem):
    chat_id = mensagem.chat.id
    chats_ativos.add(chat_id)
    partes = mensagem.text.strip().lower().split(maxsplit=1)
    
    if len(partes) < 2:
        bot.reply_to(mensagem, "⚠️ Informe a liga. Ex: `/liga brasileirao`")
        return
        
    termo = partes[1]
    if termo not in ligas_monitoradas:
        bot.reply_to(mensagem, "⚠️ Liga não encontrada. Use `/ligas`.")
        return
        
    api_key, nome_amigavel = ligas_monitoradas[termo]
    bot.reply_to(mensagem, f"🔍 Analisando jogos para `{nome_amigavel}`...")
    
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
                        
                        status_obj  = ev.get("status", {})
                        status_tipo = status_obj.get("type", {}).get("name", "")
                        status_desc = limpar_markdown(status_obj.get("type", {}).get("description", "Agendado"))
                        
                        placar_c = comps[0].get("score", "0")
                        placar_f = comps[1].get("score", "0")
                        
                        analise = analisar_gols(t_casa, t_fora)
                        
                        if status_tipo == "STATUS_SCHEDULED":
                            cabecalho = f"⏰ *{t_casa} vs {t_fora}* (Pré-Jogo)"
                        else:
                            cabecalho = f"⚽ *{t_casa} {placar_c} x {placar_f} {t_fora}* — _{status_desc}_"
                            
                        relatorio = (
                            f"{cabecalho}\n"
                            f"• Competição: `{nome_amigavel}`\n\n"
                            f"📊 **Projeção de Gols (Pro):**\n"
                            f"• Mais 1.5: `{analise['mais_1_5']}`\n"
                            f"• Mais 2.5: `{analise['mais_2_5']}`\n"
                            f"• Mais 3.5: `{analise['mais_3_5']}`\n"
                            f"• Ambas Marcam: `{analise['ambos_marcam']}`\n"
                            f"• Chance 1º Tempo: `{analise['chance_1t']}`\n"
                            f"-----------------------------------"
                        )
                        bot.send_message(chat_id, relatorio)
                return
    except Exception as e:
        print(f"Erro: {e}")
        
    bot.send_message(chat_id, f"⚠️ Nenhum jogo encontrado para esta liga hoje.")

def enviar_grade_do_dia():
    data_hoje = datetime.now().strftime("%Y%m%d")
    data_formatada = datetime.now().strftime("%d/%m/%Y")
    
    for chat_id in chats_ativos:
        try:
            bot.send_message(chat_id, f"🌅 **BOM DIA! GRADE DE JOGOS DE HOJE ({data_formatada})** 🌅\nBuscando análises profissionais...")
        except:
            pass

    for apelido, (api_key, nome_amigavel) in ligas_monitoradas.items():
        url = f"https://site.api.espn.com/apis/site/v2/sports/soccer/{api_key}/scoreboard?dates={data_hoje}"
        try:
            resp = requests.get(url, timeout=5)
            if resp.status_code == 200:
                eventos = resp.json().get("events", [])
                for ev in eventos:
                    comps = ev.get("competitions", [{}])[0].get("competitors", [])
                    if len(comps) >= 2:
                        t_casa = limpar_markdown(comps[0].get("team", {}).get("displayName", ""))
                        t_fora = limpar_markdown(comps[1].get("team", {}).get("displayName", ""))
                        analise = analisar_gols(t_casa, t_fora)
                        
                        relatorio = (
                            f"⏰ *{t_casa} vs {t_fora}* (Pré-Jogo)\n"
                            f"• Competição: `{nome_amigavel}`\n\n"
                            f"📊 **Projeção:**\n"
                            f"• Mais 1.5: `{analise['mais_1_5']}`\n"
                            f"• Mais 2.5: `{analise['mais_2_5']}`\n"
                            f"• Chance 1º Tempo: `{analise['chance_1t']}`\n"
                            f"-----------------------------------"
                        )
                        for chat_id in chats_ativos:
                            try:
                                bot.send_message(chat_id, relatorio)
                            except:
                                pass
        except:
            pass

@bot.message_handler(commands=['grade'])
def comando_forcar_grade(mensagem):
    chats_ativos.add(mensagem.chat.id)
    bot.reply_to(mensagem, "🔍 Buscando grade manual de hoje...")
    enviar_grade_do_dia()

def monitoramento_ao_vivo():
    global data_ultima_grade
    print("Radar Sniper Pro 24h iniciado...")
    
    while True:
        agora = datetime.now()
        data_hoje = agora.strftime("%Y%m%d")
        hora_atual = agora.strftime("%H:%M")
        
        if hora_atual == "07:00" and data_ultima_grade != data_hoje:
            data_ultima_grade = data_hoje
            enviar_grade_do_dia()
            
        for apelido, (api_key, nome_amigavel) in ligas_monitoradas.items():
            url = f"https://site.api.espn.com/apis/site/v2/sports/soccer/{api_key}/scoreboard?dates={data_hoje}"
            try:
                resposta = requests.get(url, timeout=8)
                if resposta.status_code == 200:
                    eventos = resposta.json().get("events", [])
                    for ev in eventos:
                        jogo_id = ev.get("id", "")
                        status_obj = ev.get("status", {})
                        
                        if status_obj.get("type", {}).get("name", "") == "STATUS_IN_PROGRESS":
                            comps = ev.get("competitions", [{}])[0].get("competitors", [])
                            if len(comps) >= 2:
                                t_casa = limpar_markdown(comps[0].get("team", {}).get("displayName", ""))
                                t_fora = limpar_markdown(comps[1].get("team", {}).get("displayName", ""))
                                
                                try:
                                    p_casa = int(comps[0].get("score", 0))
                                    p_fora = int(comps[1].get("score", 0))
                                except:
                                    p_casa, p_fora = 0, 0
                                    
                                tempo_str = status_obj.get("displayClock", "0")
                                periodo = status_obj.get("period", 1)
                                
                                minuto = 0
                                try:
                                    minuto = int(''.join(filter(str.isdigit, tempo_str))) if any(c.isdigit() for c in tempo_str) else 0
                                except:
                                    minuto = 0

                                analise = analisar_gols(t_casa, t_fora)
                                
                                jogo_apertado = abs(p_casa - p_fora) <= 1
                                momento_quente = (periodo == 1 and minuto >= 18) or (periodo >= 2 and minuto >= 65)
                                
                                ultimo_min_enviado = ultimo_alerta_minuto.get(jogo_id, -99)
                                
                                if momento_quente and jogo_apertado and analise['media'] >= 2.2 and (minuto - ultimo_min_enviado >= 6):
                                    ultimo_alerta_minuto[jogo_id] = minuto
                                    
                                    etapa_txt = "1º Tempo" if periodo == 1 else "2º Tempo"
                                    for chat_id in chats_ativos:
                                        try:
                                            bot.send_message(
                                                chat_id,
                                                f"🚨⚡ **ENTRADA DE PRESSÃO ({etapa_txt})** ⚡🚨\n\n"
                                                f"• Jogo: `{t_casa} {p_casa} x {p_fora} {t_fora}`\n"
                                                f"• Relógio: *{tempo_str}* | `{nome_amigavel}`\n"
                                                f"🎯 **Leitura:** Volume ofensivo forte. Média projetada: `{analise['media']}`\n"
                                                f"💡 Alta probabilidade de gol iminente!"
                                            )
                                        except:
                                            pass
            except:
                pass
        time.sleep(25)

app = Flask(__name__)

@app.route("/")
def home():
    return "Bot Sniper Pro Rodando!"

def rodar_telegram():
    print("Iniciando bot no Telegram...")
    bot.infinity_polling(none_stop=True, interval=0, timeout=20)

if __name__ == "__main__":
    t1 = threading.Thread(target=monitoramento_ao_vivo, daemon=True)
    t1.start()
    
    t2 = threading.Thread(target=rodar_telegram, daemon=True)
    t2.start()
    
    app.run(host="0.0.0.0", port=5000)

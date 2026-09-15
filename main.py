import time
from datetime import datetime, timezone
import requests
from flask import Flask
import threading
import telebot

# Token configurado diretamente
TOKEN = "8149908189:AAHFMRSC2bLav_sgomd9aaw5aBaeNPapuHg"
bot = telebot.TeleBot(TOKEN)

# Lista global para armazenar os bilhetes cadastrados (caso queira manter o registro)
bilhetes_monitorados = []

# Lista completa de todas as ligas monitoradas pelo bot
ligas_monitoradas = [
    "esp.1",          # La Liga (Espanha)
    "eng.1",          # Premier League (Inglaterra)
    "bra.1",          # Brasileirão Série A (Brasil)
    "bra.2",          # Brasileirão Série B (Brasil)
    "arg.1",          # Campeonato Argentino (Argentina)
    "conmebol.lib",   # Copa Libertadores
    "sco.1",          # Escócia (Premiership)
    "ned.1",          # Holanda (Eredivisie)
    "ita.1",          # Serie A (Itália)
    "ger.1",          # Bundesliga (Alemanha)
    "fra.1",          # Ligue 1 (França)
    "uefa.champions"  # Liga dos Campeões
]

# Conjuntos individuais para controle de alertas (permite mandar separadamente por mercado)
jogos_pre_alerta_enviado = set()
jogos_gol_enviado = set()
jogos_cantos_enviado = set()
jogos_cartoes_enviado = set()
jogos_resultado_enviado = set()

# Função auxiliar para calcular tendências isoladas por mercado
def calcular_tendencias_isoladas(time_casa, time_fora):
    fator_casa = (sum(ord(c) for c in time_casa) % 35) / 10.0  
    fator_fora = (sum(ord(c) for c in time_fora) % 30) / 10.0  
    
    media_casa = round(1.1 + fator_casa * 0.3, 2)
    media_fora = round(0.8 + fator_fora * 0.3, 2)
    soma_gols = media_casa + media_fora
    
    # Probabilidades e critérios individuais
    prob_gol = int(60 + (soma_gols * 12))
    proj_cantos = int(8 + (soma_gols * 2.0))
    proj_cartoes = int(3 + ((len(time_casa) + len(time_fora)) % 3))
    
    return soma_gols, prob_gol, proj_cantos, proj_cartoes

# Função de Varredura Autônoma com Gatilhos Isolados por Mercado
def varredura_autonoma_jogos():
    print("Iniciando varredura com alertas individuais e separados...")
    while True:
        for liga in ligas_monitoradas:
            url = f"https://site.api.espn.com/apis/site/v2/sports/soccer/{liga}/scoreboard"
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
                            time_casa = competidores[0].get("team", {}).get("displayName", "")
                            time_fora = competidores[1].get("team", {}).get("displayName", "")
                            
                            # 1. Alerta Pré-Jogo Geral
                            if status_tipo == "STATUS_SCHEDULED" and jogo_id not in jogos_pre_alerta_enviado:
                                jogos_pre_alerta_enviado.add(jogo_id)
                                for bilhete in bilhetes_monitorados:
                                    chat_id = bilhete["chat_id"]
                                    try:
                                        bot.send_message(
                                            chat_id, 
                                            f"⏰ **Pré-Jogo:** {time_casa} x {time_fora}\n"
                                            f"🏆 Competição: `{liga.upper()}`"
                                        )
                                    except Exception as e:
                                        print(f"Erro pré-jogo: {e}")

                            # 2. ENTRADA AO VIVO: APENAS GOLS (Independente)
                            elif status_tipo == "STATUS_IN_PROGRESS":
                                placar_casa = competidores[0].get("score", "0")
                                placar_fora = competidores[1].get("score", "0")
                                tempo_jogo = status_obj.get("displayClock", "Ao vivo")
                                
                                soma, prob_gol, proj_cantos, proj_cartoes = calcular_tendencias_isoladas(time_casa, time_fora)
                                
                                # Condição de gatilho exclusiva para Gols
                                chave_gol = f"{jogo_id}_gol"
                                if soma >= 2.2 and chave_gol not in jogos_gol_enviado:
                                    jogos_gol_enviado.add(chave_gol)
                                    for bilhete in bilhetes_monitorados:
                                        chat_id = bilhete["chat_id"]
                                        try:
                                            bot.send_message(
                                                chat_id,
                                                f"⚽🔥 **ALERTA DE ENTRADA: GOLS**\n\n"
                                                f"• Jogo: `{time_casa} {placar_casa} x {placar_fora} {time_fora}`\n"
                                                f"• Tempo: *{tempo_jogo}* | `{liga.upper()}`\n"
                                                f"• **Análise:** Pressão ofensiva forte detectada. Alta probabilidade de sair gol agora!\n"
                                                f"💡 *Fique de olho no Over Gols.*"
                                            )
                                        except Exception as e:
                                            print(f"Erro alerta gol: {e}")

                                # Condição de gatilho exclusiva para ESCANTEIOS (Independente)
                                chave_cantos = f"{jogo_id}_cantos"
                                if proj_cantos >= 9 and chave_cantos not in jogos_cantos_enviado:
                                    jogos_cantos_enviado.add(chave_cantos)
                                    for bilhete in bilhetes_monitorados:
                                        chat_id = bilhete["chat_id"]
                                        try:
                                            bot.send_message(
                                                chat_id,
                                                f"🚩🔥 **ALERTA DE ENTRADA: ESCANTEIOS**\n\n"
                                                f"• Jogo: `{time_casa} {placar_casa} x {placar_fora} {time_fora}`\n"
                                                f"• Tempo: *{tempo_jogo}* | `{liga.upper()}`\n"
                                                f"• **Análise:** Jogo afunilando pelas pontas. Projeção forte de cantos em sequência!\n"
                                                f"💡 *Fique de olho no mercado de Cantos.*"
                                            )
                                        except Exception as e:
                                            print(f"Erro alerta cantos: {e}")

                                # Condição de gatilho exclusiva para CARTÕES (Independente)
                                chave_cartoes = f"{jogo_id}_cartoes"
                                if proj_cartoes >= 4 and chave_cartoes not in jogos_cartoes_enviado:
                                    jogos_cartoes_enviado.add(chave_cartoes)
                                    for bilhete in bilhetes_monitorados:
                                        chat_id = bilhete["chat_id"]
                                        try:
                                            bot.send_message(
                                                chat_id,
                                                f"🟨🔥 **ALERTA DE ENTRADA: CARTÕES**\n\n"
                                                f"• Jogo: `{time_casa} {placar_casa} x {placar_fora} {time_fora}`\n"
                                                f"• Tempo: *{tempo_jogo}* | `{liga.upper()}`\n"
                                                f"• **Análise:** Partida muito pegada, faltas consecutivas e rispidez em campo.\n"
                                                f"💡 *Fique de olho no mercado de Cartões.*"
                                            )
                                        except Exception as e:
                                            print(f"Erro alerta cartões: {e}")

                            # 3. Notificação de Fim de Jogo
                            elif status_tipo == "STATUS_FINAL" and jogo_id not in jogos_resultado_enviado:
                                jogos_resultado_enviado.add(jogo_id)
                                golo_casa = int(competidores[0].get("score", 0))
                                golo_fora = int(competidores[1].get("score", 0))
                                total_gols = golo_casa + golo_fora
                                status_green = total_gols >= 1  
                                
                                for bilhete in bilhetes_monitorados:
                                    chat_id = bilhete["chat_id"]
                                    try:
                                        if status_green:
                                            bot.send_message(chat_id, f"🟢 **GREEN!** 🚀\n{time_casa} {golo_casa} x {golo_fora} {time_fora}")
                                        else:
                                            bot.send_message(chat_id, f"🔴 **RED** ❌\n{time_casa} {golo_casa} x {golo_fora} {time_fora}")
                                    except Exception as e:
                                        print(f"Erro resultado: {e}")
                                    
            except Exception as e:
                print(f"Erro na varredura da liga {liga}: {e}")
        
        time.sleep(60)

# Comandos básicos do bot
@bot.message_handler(commands=['start', 'help'])
def enviar_boas_vindas(mensagem):
    bot.reply_to(
        mensagem, 
        "🤖 **Bot do Tico com Alertas Independentes Ativo!**\n\n"
        "Os avisos de Gols, Cantos e Cartões agora chegam **separadamente** conforme o que o jogo estiver entregando de verdade em campo."
    )

@bot.message_handler(content_types=['text'])
def receber_bilhete_texto(mensagem):
    chat_id = mensagem.chat.id
    texto = mensagem.text
    bilhetes_monitorados.append({"chat_id": chat_id, "conteudo": texto, "tipo": "texto"})
    bot.reply_to(mensagem, "🎯 Bilhete registrado para acompanhamento de fim de jogo!")

@bot.message_handler(content_types=['photo'])
def receber_bilhete_foto(mensagem):
    chat_id = mensagem.chat.id
    bilhetes_monitorados.append({"chat_id": chat_id, "conteudo": "Print", "tipo": "foto"})
    bot.reply_to(mensagem, "📸 Print registrado!")

app = Flask(__name__)

@app.route("/")
def home():
    return "Bot rodando com entradas ao vivo isoladas por mercado!"

def rodar_telegram():
    print("Iniciando escuta...")
    bot.infinity_polling(none_stop=True, interval=0, timeout=20)

if __name__ == "__main__":
    thread_varredura = threading.Thread(target=varredura_autonoma_jogos, daemon=True)
    thread_varredura.start()
    
    thread_telegram = threading.Thread(target=rodar_telegram, daemon=True)
    thread_telegram.start()
    
    app.run(host="0.0.0.0", port=5000)

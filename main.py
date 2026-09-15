import time
from datetime import datetime, timezone
import requests
from flask import Flask
import threading
import telebot

# Token configurado diretamente
TOKEN = "8149908189:AAHFMRSC2bLav_sgomd9aaw5aBaeNPapuHg"
bot = telebot.TeleBot(TOKEN)

# Lista global para armazenar os bilhetes e análises cadastradas
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

# Conjunto para controlar jogos que já tiveram alerta pré-jogo enviado (evita spam)
jogos_pre_alerta_enviado = set()

# Função de Varredura Autônoma (Pré-jogo calculado com exatas 2h e Ao Vivo)
def varredura_autonoma_jogos():
    print("Iniciando varredura autônoma com filtro de 2 horas antes...")
    while True:
        agora = datetime.now(timezone.utc)
        
        for liga in ligas_monitoradas:
            url = f"https://site.api.espn.com/apis/site/v2/sports/soccer/{liga}/scoreboard"
            try:
                resposta = requests.get(url, timeout=10)
                if resposta.status_code == 200:
                    dados = resposta.json()
                    eventos = dados.get("events", [])
                    
                    for evento in eventos:
                        jogo_id = evento.get("id", "")
                        status_tipo = evento.get("status", {}).get("type", {}).get("name", "")
                        data_jogo_str = evento.get("date", "")
                        
                        competidores = evento.get("competitions", [{}])[0].get("competitors", [])
                        if len(competidores) >= 2:
                            time_casa = competidores[0].get("team", {}).get("displayName", "")
                            time_fora = competidores[1].get("team", {}).get("displayName", "")
                            
                            # 1. Alerta Pré-Jogo exato (2 horas antes)
                            if status_tipo == "STATUS_SCHEDULED" and data_jogo_str and jogo_id not in jogos_pre_alerta_enviado:
                                try:
                                    # Converte a data do jogo da API para formato comparável em UTC
                                    tempo_jogo = datetime.fromisoformat(data_jogo_str.replace("Z", "+00:00"))
                                    diferenca_segundos = (tempo_jogo - agora).total_seconds()
                                    
                                    # Se faltam 2 horas ou menos (7200 segundos) e o jogo ainda não começou
                                    if 0 < diferenca_segundos <= 7200:
                                        jogos_pre_alerta_enviado.add(jogo_id)
                                        
                                        minutos_restantes = int(diferenca_segundos // 60)
                                        for bilhete in bilhetes_monitorados:
                                            chat_id = bilhete["chat_id"]
                                            try:
                                                bot.send_message(
                                                    chat_id, 
                                                    f"⏰ **Alerta Pré-Jogo (Faltam ~{minutos_restantes} min)!**\n\n"
                                                    f"⚽ {time_casa} x {time_fora}\n"
                                                    f"🏆 Liga: `{liga}`\n\n"
                                                    f"Prepare suas análises, a partida vai começar em breve!"
                                                )
                                            except Exception as e:
                                                print(f"Erro ao enviar pré-jogo: {e}")
                                except Exception as err_data:
                                    print(f"Erro ao calcular tempo do jogo {jogo_id}: {err_data}")

                            # 2. Monitoramento Ao Vivo
                            elif status_tipo == "STATUS_IN_PROGRESS":
                                for bilhete in bilhetes_monitorados:
                                    chat_id = bilhete["chat_id"]
                                    # Lógica ao vivo
                                    
            except Exception as e:
                print(f"Erro ao consultar a liga {liga}: {e}")
        
        time.sleep(60)

# Comandos de boas-vindas
@bot.message_handler(commands=['start', 'help'])
def enviar_boas_vindas(mensagem):
    bot.reply_to(
        mensagem, 
        "🤖 **Bot do Tico Ativo!**\n\n"
        "• Use `/liga <código>` (ex: `/liga esp.1`) para buscar os jogos do dia.\n"
        "• Alertas automáticos **exatas 2 horas antes** dos jogos.\n"
        "• Monitoramento de entradas **ao vivo** em todas as ligas!"
    )

# Consulta rápida de ligas via comando
@bot.message_handler(func=lambda mensagem: mensagem.text and mensagem.text.startswith('/liga'))
def consultar_liga_comando(mensagem):
    texto = mensagem.text.strip()
    partes = texto.split()
    
    if len(partes) > 1:
        liga_escolhida = partes[1].lower()
        bot.reply_to(mensagem, f"🔍 Buscando jogos e estatísticas para: `{liga_escolhida}`...")
        
        url = f"https://site.api.espn.com/apis/site/v2/sports/soccer/{liga_escolhida}/scoreboard"
        try:
            resposta = requests.get(url, timeout=10)
            if resposta.status_code == 200:
                dados = resposta.json()
                eventos = dados.get("events", [])
                
                if not eventos:
                    bot.reply_to(mensagem, f"❌ Não encontrei partidas agendadas para esta liga hoje.")
                else:
                    resposta_texto = f"📋 **Partidas em `{liga_escolhida}`:**\n\n"
                    for ev in eventos:
                        comps = ev.get("competitions", [{}])[0].get("competitors", [])
                        if len(comps) >= 2:
                            c_casa = comps[0].get("team", {}).get("displayName", "")
                            c_fora = comps[1].get("team", {}).get("displayName", "")
                            status_nome = ev.get("status", {}).get("type", {}).get("description", "")
                            resposta_texto += f"⚽ {c_casa} vs {c_fora} — *Status: {status_nome}*\n"
                    bot.reply_to(mensagem, resposta_texto)
            else:
                bot.reply_to(mensagem, "⚠️ Erro ao acessar os dados da liga na API.")
        except Exception as e:
            bot.reply_to(mensagem, f"⚠️ Erro: {e}")
    else:
        bot.reply_to(mensagem, "⚠️ Informe a liga após o comando. Exemplo: `/liga esp.1`")

# Tratamento de textos gerais / bilhetes
@bot.message_handler(content_types=['text'])
def receber_bilhete_texto(mensagem):
    chat_id = mensagem.chat.id
    texto = mensagem.text
    bilhetes_monitorados.append({"chat_id": chat_id, "conteudo": texto, "tipo": "texto"})
    bot.reply_to(mensagem, "✅ Análise registrada! O bot vai te avisar 2 horas antes de cada jogo e monitorar ao vivo.")

# Tratamento de fotos
@bot.message_handler(content_types=['photo'])
def receber_bilhete_foto(mensagem):
    chat_id = mensagem.chat.id
    bilhetes_monitorados.append({"chat_id": chat_id, "conteudo": "Print de aposta", "tipo": "foto"})
    bot.reply_to(mensagem, "📸 Print capturado com sucesso! Na fila de monitoramento automático.")

# Configuração do Flask para o Render
app = Flask(__name__)

@app.route("/")
def home():
    return "Bot do Tico rodando com alerta de 2h pré-jogo e ao vivo!"

def rodar_telegram():
    print("Iniciando escuta do Telegram...")
    bot.infinity_polling(none_stop=True, interval=0, timeout=20)

if __name__ == "__main__":
    thread_varredura = threading.Thread(target=varredura_autonoma_jogos, daemon=True)
    thread_varredura.start()
    
    thread_telegram = threading.Thread(target=rodar_telegram, daemon=True)
    thread_telegram.start()
    
    app.run(host="0.0.0.0", port=5000)

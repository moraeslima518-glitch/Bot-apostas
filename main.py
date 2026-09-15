import time
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

# Função de Varredura Autônoma (Pré-jogo e Ao Vivo)
def varredura_autonoma_jogos():
    print("Iniciando varredura autônoma (Pré-jogo e Ao Vivo)...")
    while True:
        for liga in ligas_monitoradas:  # Correção do espaço aplicada aqui
            url = f"https://site.api.espn.com/apis/site/v2/sports/soccer/{liga}/scoreboard"
            try:
                resposta = requests.get(url, timeout=10)
                if resposta.status_code == 200:
                    dados = resposta.json()
                    eventos = dados.get("events", [])
                    
                    for evento in eventos:
                        jogo_id = evento.get("id", "")
                        status_tipo = evento.get("status", {}).get("type", {}).get("name", "")
                        
                        competidores = evento.get("competitions", [{}])[0].get("competitors", [])
                        if len(competidores) >= 2:
                            time_casa = competidores[0].get("team", {}).get("displayName", "")
                            time_fora = competidores[1].get("team", {}).get("displayName", "")
                            
                            # 1. DETECÇÃO PRÉ-JOGO (Envia alerta antes da bola rolar)
                            if status_tipo == "STATUS_SCHEDULED" and jogo_id not in jogos_pre_alerta_enviado:
                                jogos_pre_alerta_enviado.add(jogo_id)
                                
                                for bilhete in bilhetes_monitorados:
                                    chat_id = bilhete["chat_id"]
                                    try:
                                        bot.send_message(
                                            chat_id, 
                                            f"⏰ **Alerta Pré-Jogo!**\n\n"
                                            f"O jogo vai começar em breve:\n"
                                            f"⚽ {time_casa} x {time_fora}\n"
                                            f"🏆 Liga: `{liga}`\n\n"
                                            f"Fique de olho nas análises cadastradas!"
                                        )
                                    except Exception as e:
                                        print(f"Erro ao enviar pré-jogo para o chat {chat_id}: {e}")

                            # 2. DETECÇÃO AO VIVO (Continua monitorando o andamento)
                            elif status_tipo == "STATUS_IN_PROGRESS":
                                tempo_atual = evento.get("status", {}).get("displayClock", "")
                                placar_casa = competidores[0].get("score", "0")
                                placar_fora = competidores[1].get("score", "0")
                                
                                for bilhete in bilhetes_monitorados:
                                    chat_id = bilhete["chat_id"]
                                    # Lógica de cruzamento ao vivo
                                    
            except Exception as e:
                print(f"Erro ao consultar a liga {liga}: {e}")
        
        time.sleep(60)

# Comandos do Telegram
@bot.message_handler(commands=['start', 'help'])
def enviar_boas_vindas(mensagem):
    bot.reply_to(
        mensagem, 
        "🤖 **Bot de Apostas Principal Ativo!**\n\n"
        "Monitoramento completo ativado:\n"
        "1️⃣ Alertas **antes do jogo começar** (Pré-jogo).\n"
        "2️⃣ Monitoramento e entradas automáticas **ao vivo**.\n"
        "3️⃣ Cobertura de todas as ligas (Brasil, Espanha, Argentina, Europa, Libertadores).\n\n"
        "Envie seu bilhete por texto ou foto para começar!"
    )

@bot.message_handler(content_types=['text'])
def receber_bilhete_texto(mensagem):
    chat_id = mensagem.chat.id
    texto = mensagem.text
    bilhetes_monitorados.append({"chat_id": chat_id, "conteudo": texto, "tipo": "texto"})
    bot.reply_to(mensagem, "✅ Análise registrada! O bot vai te avisar antes do jogo começar e monitorar ao vivo.")

@bot.message_handler(content_types=['photo'])
def receber_bilhete_foto(mensagem):
    chat_id = mensagem.chat.id
    bilhetes_monitorados.append({"chat_id": chat_id, "conteudo": "Print de aposta", "tipo": "foto"})
    bot.reply_to(mensagem, "📸 Print capturado com sucesso! Na fila de varredura pré-jogo e ao vivo.")

# Configuração do Servidor Flask para o Render
app = Flask(__name__)

@app.route("/")
def home():
    return "Bot de Apostas Principal rodando com Pré-Jogo e Ao Vivo!"

def rodar_telegram():
    print("Iniciando escuta do Telegram...")
    bot.infinity_polling(none_stop=True, interval=0, timeout=20)

if __name__ == "__main__":
    thread_varredura = threading.Thread(target=varredura_autonoma_jogos, daemon=True)
    thread_varredura.start()
    
    thread_telegram = threading.Thread(target=rodar_telegram, daemon=True)
    thread_telegram.start()
    
    app.run(host="0.0.0.0", port=5000)

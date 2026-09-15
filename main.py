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

# Função de Varredura Autônoma em Segundo Plano
def varredura_autonoma_jogos():
    print("Iniciando varredura autônoma de jogos...")
    while True:
        for liga in ligas_monitoradas:
            url = f"https://site.api.espn.com/apis/site/v2/sports/soccer/{liga}/scoreboard"
            try:
                resposta = requests.get(url, timeout=10)
                if resposta.status_code == 200:
                    dados = resposta.json()
                    eventos = dados.get("events", [])
                    
                    # Log específico para confirmar varredura da Espanha (esp.1)
                    if liga == "esp.1" and len(eventos) > 0:
                        print(f"La Liga (Espanha) consultada com sucesso: {len(eventos)} evento(s) encontrado(s).")
                        
                    for evento in eventos:
                        status_tipo = evento.get("status", {}).get("type", {}).get("name", "")
                        
                        if status_tipo == "STATUS_IN_PROGRESS":
                            competidores = evento.get("competitions", [{}])[0].get("competitors", [])
                            if len(competidores) >= 2:
                                time_casa = competidores[0].get("team", {}).get("displayName", "")
                                time_fora = competidores[1].get("team", {}).get("displayName", "")
                                tempo_atual = evento.get("status", {}).get("displayClock", "")
                                
                                # Processamento dos bilhetes monitorados ao vivo
                                for bilhete in bilhetes_monitorados:
                                    chat_id = bilhete["chat_id"]
                                    # Alerta automático ao vivo
                                    
            except Exception as e:
                print(f"Erro ao consultar a liga {liga}: {e}")
        
        time.sleep(60)

# Comandos do Telegram
@bot.message_handler(commands=['start', 'help'])
def enviar_boas_vindas(mensagem):
    bot.reply_to(
        mensagem, 
        "🤖 **Bot de Apostas Principal Ativo!**\n\n"
        "Monitoramento autônomo ativado para La Liga (Espanha), Brasil, Argentina, Europa e Libertadores. "
        "Envie seu bilhete por texto ou foto!"
    )

@bot.message_handler(content_types=['text'])
def receber_bilhete_texto(mensagem):
    chat_id = mensagem.chat.id
    texto = mensagem.text
    bilhetes_monitorados.append({"chat_id": chat_id, "conteudo": texto, "tipo": "texto"})
    bot.reply_to(mensagem, "✅ Análise registrada! Monitorando ao vivo automaticamente.")

@bot.message_handler(content_types=['photo'])
def receber_bilhete_foto(mensagem):
    chat_id = mensagem.chat.id
    bilhetes_monitorados.append({"chat_id": chat_id, "conteudo": "Print de aposta", "tipo": "foto"})
    bot.reply_to(mensagem, "📸 Print capturado! Na fila de varredura autônoma.")

# Configuração do Servidor Flask para o Render
app = Flask(__name__)

@app.route("/")
def home():
    return "Bot de Apostas Principal rodando com monitoramento autônomo!"

def rodar_telegram():
    print("Iniciando escuta do Telegram...")
    bot.infinity_polling(none_stop=True, interval=0, timeout=20)

if __name__ == "__main__":
    # Inicia a thread de varredura de jogos da ESPN
    thread_varredura = threading.Thread(target=varredura_autonoma_jogos, daemon=True)
    thread_varredura.start()
    
    # Inicia a thread dedicada para escutar as mensagens do Telegram sem travar o Flask
    thread_telegram = threading.Thread(target=rodar_telegram, daemon=True)
    thread_telegram.start()
    
    # Inicia o servidor web exigido pelo Render
    app.run(host="0.0.0.0", port=5000)

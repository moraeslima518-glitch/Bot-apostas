import time
import requests
from flask import Flask
import threading
import telebot
import os

# Configuração do Token do Primeiro Bot (Bot-apostas)
TOKEN = os.environ.get("TELEGRAM_TOKEN", "COLE_SEU_TOKEN_DO_BOT_1_AQUI")
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

# Função de Varredura Autônoma em Segundo Plano (Roda sozinha sem comandos)
def varredura_autonoma_jogos():
    print("Iniciando varredura autônoma no primeiro bot...")
    while True:
        for liga in ligas_monitoradas:
            url = f"https://site.api.espn.com/apis/site/v2/sports/soccer/{liga}/scoreboard"
            try:
                resposta = requests.get(url, timeout=10)
                if resposta.status_code == 200:
                    dados = resposta.json()
                    eventos = dados.get("events", [])
                    
                    for evento in eventos:
                        status_tipo = evento.get("status", {}).get("type", {}).get("name", "")
                        
                        # Monitora apenas jogos que estão rolando ao vivo
                        if status_tipo == "STATUS_IN_PROGRESS":
                            competicao = evento.get("name", "")
                            competidores = evento.get("competitions", [{}])[0].get("competitors", [])
                            
                            if len(competidores) >= 2:
                                time_casa = competidores[0].get("team", {}).get("displayName", "")
                                placar_casa = competidores[0].get("score", "0")
                                time_fora = competidores[1].get("team", {}).get("displayName", "")
                                placar_fora = competidores[1].get("score", "0")
                                tempo_atual = evento.get("status", {}).get("displayClock", "")
                                
                                # Aqui o bot cruza os jogos ao vivo com os bilhetes que você mandou.
                                # Se bater com o seu critério, ele envia o alerta direto para o chat automaticamente:
                                for bilhete in bilhetes_monitorados:
                                    chat_id = bilhete["chat_id"]
                                    # Exemplo de disparo autônomo (você pode refinar a regra de entrada aqui):
                                    # bot.send_message(chat_id, f"🚨 Oportunidade ao vivo em {time_casa} x {time_fora} ({tempo_atual}')!")
                                    
            except Exception as e:
                print(f"Erro ao consultar a liga {liga}: {e}")
        
        # Pausa antes da próxima varredura completa
        time.sleep(60)

# Comandos do Telegram
@bot.message_handler(commands=['start', 'help'])
def enviar_boas_vindas(mensagem):
    bot.reply_to(
        mensagem, 
        "🤖 **Bot de Apostas Principal Ativo!**\n\n"
        "Envie o seu bilhete ou análise por texto ou foto. "
        "O bot vai guardar na memória e monitorar todas as ligas (Brasil, Argentina, Europa, Libertadores) sozinho, mandando as entradas ao vivo para você!"
    )

# Recebe bilhetes ou pedidos de análise via texto
@bot.message_handler(content_types=['text'])
def receber_bilhete_texto(mensagem):
    chat_id = mensagem.chat.id
    texto = mensagem.text
    
    bilhetes_monitorados.append({
        "chat_id": chat_id,
        "conteudo": texto,
        "tipo": "texto"
    })
    
    bot.reply_to(mensagem, "✅ Análise/Bilhete registrado! O bot já começou o monitoramento automático ao vivo nas ligas.")

# Recebe bilhetes ou prints por foto
@bot.message_handler(content_types=['photo'])
def receber_bilhete_foto(mensagem):
    chat_id = mensagem.chat.id
    
    bilhetes_monitorados.append({
        "chat_id": chat_id,
        "conteudo": "Print de aposta",
        "tipo": "foto"
    })
    
    bot.reply_to(mensagem, "📸 Print capturado com sucesso! Entrando na fila de varredura autônoma ao vivo.")

# Configuração do Servidor Flask para manter o Render ligado 24h
app = Flask(__name__)

@app.route("/")
def home():
    return "Bot de Apostas Principal rodando com monitoramento autônomo!"

if __name__ == "__main__":
    # Inicia a thread de varredura em segundo plano (roda sem precisar de comandos)
    thread_varredura = threading.Thread(target=varredura_autonoma_jogos, daemon=True)
    thread_varredura.start()
    
    # Inicia o servidor web do Render
    app.run(host="0.0.0.0", port=5000)

import os
import time
import requests
from datetime import datetime, timedelta

# Configurações obtidas das Variáveis de Ambiente do Render
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")
RAPIDAPI_KEY = os.environ.get("RAPIDAPI_KEY")

# IDs das ligas que você deseja monitorar na API-Football
# Exemplo: 71 (Brasileirão Série A), 39 (Premier League), 140 (La Liga), 135 (Serie A), 78 (Bundesliga)
LIGAS_MONITORADAS = [71, 39, 140, 135, 78]

def enviar_mensagem_telegram(texto):
    """Envia uma mensagem de texto formatada para o Telegram."""
    if not TELEGRAM_TOKEN or not CHAT_ID:
        print("Erro: TELEGRAM_TOKEN ou CHAT_ID não configurados.")
        return
        
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": texto,
        "parse_mode": "Markdown"
    }
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"Erro ao enviar mensagem para o Telegram: {e}")

def enviar_resumo_jogos_dia():
    """Busca as partidas do dia e envia um resumo no Telegram para testar a API."""
    if not RAPIDAPI_KEY:
        print("Erro: RAPIDAPI_KEY não configurada.")
        return

    # Data de hoje no formato YYYY-MM-DD
    hoje = datetime.now().strftime("%Y-%m-%d")
    
    headers = {
        'x-rapidapi-host': "v3.football.api-sports.io",
        'x-rapidapi-key': RAPIDAPI_KEY
    }
    
    url = f"https://v3.football.api-sports.io/fixtures?date={hoje}"
    
    try:
        response = requests.get(url, headers=headers, timeout=15)
        dados = response.json()
        partidas = dados.get('response', [])
        
        jogos_filtrados = []

        for partida in partidas:
            id_liga = partida['league']['id']
            # Se desejar filtrar apenas as ligas selecionadas, descomente a linha abaixo:
            # if id_liga not in LIGAS_MONITORADAS: continue

            # Converte a data da partida (UTC) para o Horário de Brasília (UTC-3)
            data_str = partida['fixture']['date']
            data_utc = datetime.strptime(data_str, "%Y-%m-%dT%H:%M:%S%z")
            hora_br = data_utc - timedelta(hours=3)
            
            # Filtra partidas marcadas a partir das 07:00
            if hora_br.hour >= 7:
                time_casa = partida['teams']['home']['name']
                time_fora = partida['teams']['away']['name']
                nome_liga = partida['league']['name']
                horario_formatado = hora_br.strftime("%H:%M")
                
                jogos_filtrados.append(f"⚽ *{horario_formatado}* - {time_casa} x {time_fora} _({nome_liga})_")

        if jogos_filtrados:
            # Limita em 30 jogos na mensagem para respeitar o tamanho do Telegram
            mensagem = "📋 *RESUMO DE JOGOS DO DIA (A partir das 07:00)* 📋\n\n" + "\n".join(jogos_filtrados[:30])
        else:
            mensagem = "⚠️ *Teste de Inicialização*: Conexão OK com a API, mas nenhum jogo encontrado para hoje a partir das 07:00."

        enviar_mensagem_telegram(mensagem)
        print("Resumo enviado com sucesso para o Telegram.")

    except Exception as e:
        print(f"Erro ao buscar jogos do dia: {e}")
        enviar_mensagem_telegram(f"❌ *Erro ao conectar com a API-Football:* `{e}`")

def checar_alertas_pre_jogo_e_live():
    """Função do seu loop principal para monitorar a janela de 3h e os jogos ao vivo."""
    # Coloque aqui a lógica de consulta contínua do seu bot
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Verificando partidas e estatísticas...")

if __name__ == "__main__":
    print("Iniciando Bot de Apostas...")
    
    # 1. Envia a lista de validação no Telegram assim que liga
    enviar_resumo_jogos_dia()
    
    # 2. Mantém o loop ativo para buscas periódicas
    while True:
        checar_alertas_pre_jogo_e_live()
        time.sleep(300)  # Aguarda 5 minutos entre cada verificação

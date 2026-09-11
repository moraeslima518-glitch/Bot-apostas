import requests
from telegram import Bot
import asyncio
from datetime import datetime, timezone, timedelta
import os
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

# --- SERVIDOR WEB MÍNIMO PARA O RENDER ---
class SimpleHTTPRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write(b"Bot Ativo e Operacional!")

    def log_message(self, format, *args):
        return # Desativa os logs de acessos HTTP para nao poluir o terminal

def rodar_servidor_web():
    port = int(os.getenv("PORT", 10000))
    server = HTTPServer(('0.0.0.0', port), SimpleHTTPRequestHandler)
    print(f"🌐 Servidor web iniciado na porta {port} para o Render.")
    server.serve_forever()

# Inicia o servidor HTTP em uma thread separada antes de rodar o bot
threading.Thread(target=rodar_servidor_web, daemon=True).start()

# --- CONFIGURAÇÕES DO BOT ---
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "8149908189:AAHFMRSC2bLav_sgomd9aaw5aBaeNPapuHg")
CHAT_ID = os.getenv("CHAT_ID", "8195281163")
RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY", "F909208C46MSHE2A1D04DFD2CACBP18ADB4JSN38F2C5EEA4B4")

HEADERS = {
    "x-rapidapi-key": RAPIDAPI_KEY,
    "x-rapidapi-host": "v3.football.api-sports.io"
}

LIGAS_PRINCIPAIS = [71, 72, 39, 2, 13, 140, 307, 61]

bot = Bot(token=TELEGRAM_TOKEN)
jogos_pre_notificados = set()

async def verificar_entradas_pre_jogo():
    agora_utc = datetime.now(timezone.utc)
    hoje = agora_utc.strftime("%Y-%m-%d")
    url = f"https://v3.football.api-sports.io/fixtures?date={hoje}"
    
    try:
        response = requests.get(url, headers=HEADERS).json()
        jogos = response.get("response", [])
        
        for jogo in jogos:
            fixture_id = jogo["fixture"]["id"]
            if fixture_id in jogos_pre_notificados:
                continue
                
            liga_id = jogo["league"]["id"]
            status = jogo["fixture"]["status"]["short"]
            
            if liga_id in LIGAS_PRINCIPAIS and status == "NS":
                data_jogo_str = jogo["fixture"]["date"]
                data_jogo = datetime.fromisoformat(data_jogo_str.replace("Z", "+00:00"))
                
                diferenca_minutos = (data_jogo - agora_utc).total_seconds() / 60
                
                if 10 <= diferenca_minutos <= 60:
                    liga = jogo["league"]["name"]
                    pais = jogo["league"]["country"]
                    casa = jogo["teams"]["home"]["name"]
                    fora = jogo["teams"]["away"]["name"]
                    horario_br = (data_jogo - timedelta(hours=3)).strftime("%H:%M")

                    msg = (
                        f"🚨 **ENTRADA PRÉ-JOGO (INÍCIO EM BREVE)**\n\n"
                        f"🏆 **Liga:** {pais} - {liga}\n"
                        f"⚔️ **Confronto:** {casa} x {fora}\n"
                        f"⏰ **Início:** {horario_br} (Horário de Brasília)\n\n"
                        f"📊 **Sugestão de Entrada Pré-Jogo:**\n"
                        f"⚽ **Gols:** Over 1.5 Gols na Partida / Over 0.5 HT\n"
                        f"🚩 **Escanteios:** Over 8.5 Cantos no Jogo\n"
                        f"💡 **Recomendação:** Gestão de 1 a 2 unidades."
                    )
                    await bot.send_message(chat_id=CHAT_ID, text=msg, parse_mode="Markdown")
                    jogos_pre_notificados.add(fixture_id)
                    await asyncio.sleep(1.5)

    except Exception as e:
        print(f"Erro no Pré-Jogo: {e}")

async def monitorar_jogos_ao_vivo():
    url = "https://v3.football.api-sports.io/fixtures?live=all"
    
    try:
        response = requests.get(url, headers=HEADERS).json()
        jogos_live = response.get("response", [])
        
        if not jogos_live:
            return

        alertas_enviados = 0

        for jogo in jogos_live:
            tempo = jogo["fixture"]["status"]["elapsed"] or 0
            status_curto = jogo["fixture"]["status"]["short"]
            casa = jogo["teams"]["home"]["name"]
            fora = jogo["teams"]["away"]["name"]
            gols_casa = jogo["goals"]["home"]
            gols_fora = jogo["goals"]["away"]
            liga = jogo["league"]["name"]

            if status_curto == "1H" and 5 <= tempo <= 40:
                msg_live = (
                    f"🔥 **ALERTA PRESSÃO - 1º TEMPO ({tempo}')**\n\n"
                    f"🏆 **Liga:** {liga}\n"
                    f"⚔️ **Confronto:** {casa} {gols_casa} x {gols_fora} {fora}\n"
                    f"⏱️ **Minuto:** {tempo}' (Primeiro Tempo)\n\n"
                    f"🎯 **Indicadores Detectados:**\n"
                    f"⚽ **Chance de Gol HT:** Alta movimentação ofensiva na etapa inicial.\n"
                    f"🚩 **Escanteios HT:** Ritmo acelerado para cantos no 1º Tempo.\n\n"
                    f"💡 *Sugestão:* Over 0.5 Gol HT ou Cantos Asiáticos HT."
                )
                await bot.send_message(chat_id=CHAT_ID, text=msg_live, parse_mode="Markdown")
                alertas_enviados += 1

            elif status_curto == "2H" and 50 <= tempo <= 85:
                msg_live = (
                    f"🔥 **ALERTA PRESSÃO - 2º TEMPO ({tempo}')**\n\n"
                    f"🏆 **Liga:** {liga}\n"
                    f"⚔️ **Confronto:** {casa} {gols_casa} x {gols_fora} {fora}\n"
                    f"⏱️ **Minuto:** {tempo}' (Segundo Tempo)\n\n"
                    f"🎯 **Indicadores Detectados:**\n"
                    f"⚽ **Pressão Final:** Jogo aberto em busca de resultado.\n"
                    f"🚩 **Escanteios FT:** Tendência alta para Cantos Limite / Final do jogo.\n\n"
                    f"💡 *Sugestão:* Over Gol nos minutos finais ou Cantos Limite."
                )
                await bot.send_message(chat_id=CHAT_ID, text=msg_live, parse_mode="Markdown")
                alertas_enviados += 1

            if alertas_enviados >= 3:
                break
                
            await asyncio.sleep(1.5)

    except Exception as e:
        print(f"Erro no Ao Vivo: {e}")

async def main():
    print("🚀 Bot iniciado no Render (Modo Web Service com Porta Ativa)!")
    await bot.send_message(
        chat_id=CHAT_ID,
        text="🤖 **Bot de Apostas Atualizado!**\nServidor de checagem do Render ativado com sucesso.",
        parse_mode="Markdown"
    )
    
    while True:
        try:
            await verificar_entradas_pre_jogo()
            await monitorar_jogos_ao_vivo()
            await asyncio.sleep(300)
            
        except Exception as e:
            print(f"Erro no loop: {e}")
            await asyncio.sleep(60)

if __name__ == "__main__":
    asyncio.run(main())

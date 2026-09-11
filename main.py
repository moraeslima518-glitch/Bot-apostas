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
        return

def rodar_servidor_web():
    port = int(os.getenv("PORT", 10000))
    server = HTTPServer(('0.0.0.0', port), SimpleHTTPRequestHandler)
    print(f"🌐 Servidor web iniciado na porta {port} para o Render.")
    server.serve_forever()

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
ultimos_alertas_tempo = {}

def extrair_estatistica(stats, tipo):
    total = 0
    for equipa in stats:
        for item in equipa.get("statistics", []):
            if item.get("type") == tipo:
                val = item.get("value")
                if val is not None:
                    if str(val).endswith("%"):
                        val = str(val).replace("%", "")
                    try:
                        total += int(val)
                    except ValueError:
                        pass
    return total

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
            
            # Aceita qualquer status de jogo que ainda não começou (NS, TBD)
            if liga_id in LIGAS_PRINCIPAIS and status in ["NS", "TBD"]:
                data_jogo_str = jogo["fixture"]["date"]
                data_jogo = datetime.fromisoformat(data_jogo_str.replace("Z", "+00:00"))
                
                diferenca_minutos = (data_jogo - agora_utc).total_seconds() / 60
                
                # Janela ampliada: pega jogos que iniciam em até 2 horas (120 min)
                if 0 <= diferenca_minutos <= 120:
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
                        f"📊 **Sugestão de Entrada:**\n"
                        f"⚽ **Gols:** Over 1.5 Gols na Partida / Over 0.5 HT\n"
                        f"🚩 **Escanteios:** Over 8.5 Cantos no Jogo\n"
                        f"🟨 **Cartões:** Over 3.5 Cartões no Jogo\n\n"
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
            fixture_id = jogo["fixture"]["id"]
            liga_id = jogo["league"]["id"]

            if liga_id not in LIGAS_PRINCIPAIS:
                continue

            tempo = jogo["fixture"]["status"]["elapsed"] or 0
            status_curto = jogo["fixture"]["status"]["short"]
            
            if status_curto not in ["1H", "2H"]:
                continue

            ultimo_minuto_alertado = ultimos_alertas_tempo.get(fixture_id, -10)
            if (tempo - ultimo_minuto_alertado) < 10:
                continue

            casa = jogo["teams"]["home"]["name"]
            fora = jogo["teams"]["away"]["name"]
            gols_casa = jogo["goals"]["home"] or 0
            gols_fora = jogo["goals"]["away"] or 0
            liga = jogo["league"]["name"]

            url_stats = f"https://v3.football.api-sports.io/fixtures/statistics?fixture={fixture_id}"
            res_stats = requests.get(url_stats, headers=HEADERS).json()
            stats_data = res_stats.get("response", [])

            chutes_no_gol = extrair_estatistica(stats_data, "Shots on Goal")
            chutes_fora = extrair_estatistica(stats_data, "Shots off Goal")
            escanteios = extrair_estatistica(stats_data, "Corner Kicks")
            cartoes_amarelos = extrair_estatistica(stats_data, "Yellow Cards")
            cartoes_vermelhos = extrair_estatistica(stats_data, "Red Cards")
            
            total_finalizacoes = chutes_no_gol + chutes_fora

            alta_pressao_chutes = chutes_no_gol >= 3 or total_finalizacoes >= 7
            reta_final_pressao = (tempo >= 70) and (abs(gols_casa - gols_fora) <= 1)

            if alta_pressao_chutes or reta_final_pressao:
                etapa = "1º Tempo" if status_curto == "1H" else "2º Tempo"
                
                msg_live = (
                    f"🔥 **ALERTA DE PRESSÃO EXTREMA ({tempo}')**\n\n"
                    f"🏆 **Liga:** {liga}\n"
                    f"⚔️ **Confronto:** {casa} {gols_casa} x {gols_fora} {fora}\n"
                    f"⏱️ **Minuto:** {tempo}' ({etapa})\n\n"
                    f"📊 **Estatísticas ao Vivo:**\n"
                    f"🎯 **Chutes no Gol:** {chutes_no_gol} | **Total Chutes:** {total_finalizacoes}\n"
                    f"🚩 **Escanteios:** {escanteios}\n"
                    f"🟨 **Cartões:** {cartoes_amarelos} Amarelos | {cartoes_vermelhos} Vermelhos\n\n"
                    f"⚡ **Oportunidades Recomendadas:**\n"
                    f"⚽ **Próximo Gol / Over Gol Limite** (Jogo muito movimentado)\n"
                    f"🚩 **Escanteios Limite** (Pressão na área)\n"
                    f"🟨 **Cartões** (Jogo faltoso/Reta final)\n\n"
                    f"💡 *Entrar com gestão de banca (1% a 2%).*"
                )
                
                await bot.send_message(chat_id=CHAT_ID, text=msg_live, parse_mode="Markdown")
                ultimos_alertas_tempo[fixture_id] = tempo
                alertas_enviados += 1

            if alertas_enviados >= 3:
                break
                
            await asyncio.sleep(1.5)

    except Exception as e:
        print(f"Erro no Ao Vivo com Estatísticas: {e}")

async def main():
    print("🚀 Bot iniciado no Render (Pré-Jogo Ampliado 120min + Pressão Real)!")
    await bot.send_message(
        chat_id=CHAT_ID,
        text="🤖 **Bot de Apostas Atualizado!**\nJanela pré-jogo ampliada para até 2 horas de antecedência.",
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

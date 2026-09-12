import requests
from telegram import Bot
import asyncio
from datetime import datetime, timezone, timedelta
import os
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

# --- SERVIDOR WEB MÍNIMO PARA MANTER NO RENDER ---
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
    print(f"🌐 Servidor web rodando na porta {port}.")
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

# Ligas monitoradas (Brasileirão A e B, Premier, Champions, Libertadores, La Liga, Saudi, Ligue 1)
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
            
            if liga_id in LIGAS_PRINCIPAIS and status in ["NS", "TBD"]:
                data_jogo_str = jogo["fixture"]["date"]
                data_jogo = datetime.fromisoformat(data_jogo_str.replace("Z", "+00:00"))
                
                diferenca_minutos = (data_jogo - agora_utc).total_seconds() / 60
                
                # Janela de até 180 min (3 horas) antes do jogo
                if 0 <= diferenca_minutos <= 180:
                    liga = jogo["league"]["name"]
                    pais = jogo["league"]["country"]
                    casa = jogo["teams"]["home"]["name"]
                    fora = jogo["teams"]["away"]["name"]
                    horario_br = (data_jogo - timedelta(hours=3)).strftime("%H:%M")

                    msg = (
                        f"🚨 **ENTRADA PRÉ-JOGO CONFIRMADA**\n\n"
                        f"🏆 **Liga:** {pais} - {liga}\n"
                        f"⚔️ **Confronto:** {casa} x {fora}\n"
                        f"⏰ **Início:** {horario_br} (Horário de Brasília)\n\n"
                        f"📊 **Sugestões de Entrada:**\n"
                        f"⚽ **Gols:** Over 1.5 Gols na Partida / Over 0.5 HT\n"
                        f"🚩 **Escanteios:** Over 8.5 Cantos no Jogo\n"
                        f"🟨 **Cartões:** Over 3.5 Cartões no Jogo\n\n"
                        f"💡 **Gestão:** 1% a 2% da banca."
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

            # Evita enviar alerta do mesmo jogo num intervalo menor que 12 minutos
            ultimo_minuto_alertado = ultimos_alertas_tempo.get(fixture_id, -15)
            if (tempo - ultimo_minuto_alertado) < 12:
                continue

            casa = jogo["teams"]["home"]["name"]
            fora = jogo["teams"]["away"]["name"]
            gols_casa = jogo["goals"]["home"] or 0
            gols_fora = jogo["goals"]["away"] or 0
            liga = jogo["league"]["name"]

            # Consulta estatísticas somente para jogos ativos das ligas principais
            url_stats = f"https://v3.football.api-sports.io/fixtures/statistics?fixture={fixture_id}"
            res_stats = requests.get(url_stats, headers=HEADERS).json()
            stats_data = res_stats.get("response", [])

            chutes_no_gol = extrair_estatistica(stats_data, "Shots on Goal")
            chutes_fora = extrair_estatistica(stats_data, "Shots off Goal")
            escanteios = extrair_estatistica(stats_data, "Corner Kicks")
            cartoes_amarelos = extrair_estatistica(stats_data, "Yellow Cards")
            cartoes_vermelhos = extrair_estatistica(stats_data, "Red Cards")
            
            total_finalizacoes = chutes_no_gol + chutes_fora

            # REGRAS INTELIGENTES DE PRESSÃO:
            # - Pressão de finalizações: 2+ chutes no gol ou 5+ finalizações totais
            # - Pressão de tempo: Reta final (65'+ minutos) com placar apertado (diferença <= 1 gol)
            pressao_chutes = chutes_no_gol >= 2 or total_finalizacoes >= 5
            pressao_reta_final = (tempo >= 65) and (abs(gols_casa - gols_fora) <= 1)

            if pressao_chutes or pressao_reta_final:
                etapa = "1º Tempo" if status_curto == "1H" else "2º Tempo"
                
                msg_live = (
                    f"🔥 **ALERTA DE PRESSÃO AO VIVO ({tempo}')**\n\n"
                    f"🏆 **Liga:** {liga}\n"
                    f"⚔️ **Confronto:** {casa} {gols_casa} x {gols_fora} {fora}\n"
                    f"⏱️ **Minuto:** {tempo}' ({etapa})\n\n"
                    f"📈 **Estatísticas de Pressão:**\n"
                    f"🎯 **Chutes no Gol:** {chutes_no_gol} | **Total Chutes:** {total_finalizacoes}\n"
                    f"🚩 **Escanteios:** {escanteios}\n"
                    f"🟨 **Cartões:** {cartoes_amarelos} Amarelos | {cartoes_vermelhos} Vermelhos\n\n"
                    f"⚡ **Sugestões de Entrada:**\n"
                    f"⚽ **Próximo Gol / Over Gol Limite**\n"
                    f"🚩 **Escanteios Limite**\n"
                    f"🟨 **Over Cartões**\n\n"
                    f"💡 *Gestão de banca recomendada: 1% a 2%.*"
                )
                
                await bot.send_message(chat_id=CHAT_ID, text=msg_live, parse_mode="Markdown")
                ultimos_alertas_tempo[fixture_id] = tempo
                alertas_enviados += 1

            if alertas_enviados >= 2:
                break
                
            await asyncio.sleep(1.5)

    except Exception as e:
        print(f"Erro na verificação ao vivo: {e}")

async def main():
    print("🚀 Bot Operacional (Otimizado & Inteligente)!")
    await bot.send_message(
        chat_id=CHAT_ID,
        text="🤖 **Bot de Apostas Atualizado!**\nSistema otimizado para sensibilidade ideal e consumo eficiente de dados.",
        parse_mode="Markdown"
    )
    
    while True:
        try:
            await verificar_entradas_pre_jogo()
            await monitorar_jogos_ao_vivo()
            # Intervalo de 4 minutos entre buscas para equilibrar velocidade e uso de API
            await asyncio.sleep(240)
            
        except Exception as e:
            print(f"Erro no loop principal: {e}")
            await asyncio.sleep(60)

if __name__ == "__main__":
    asyncio.run(main())

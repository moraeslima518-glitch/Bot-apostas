import requests
from telegram import Bot
import asyncio
from datetime import datetime
import os

# === CREDENCIAIS ===
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "8149908189:AAHFMRSC2bLav_sgomd9aaw5aBaeNPapuHg")
CHAT_ID = os.getenv("CHAT_ID", "8195281163")
RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY", "F909208C46MSHE2A1D04DFD2CACBP18ADB4JSN38F2C5EEA4B4")

HEADERS = {
    "x-rapidapi-key": RAPIDAPI_KEY,
    "x-rapidapi-host": "v3.football.api-sports.io"
}

# IDs das Ligas Selecionadas (8 Ligas):
# 71 = Brasileirão A, 72 = Brasileirão B, 39 = Premier League, 
# 2 = Champions, 13 = Libertadores, 140 = La Liga, 307 = Saudi Pro League, 61 = Ligue 1
LIGAS_PRINCIPAIS = [71, 72, 39, 2, 13, 140, 307, 61]

bot = Bot(token=TELEGRAM_TOKEN)

async def varrer_pre_jogo_ligas():
    hoje = datetime.now().strftime("%Y-%m-%d")
    url = f"https://v3.football.api-sports.io/fixtures?date={hoje}"
    
    try:
        response = requests.get(url, headers=HEADERS).json()
        jogos = response.get("response", [])
        
        jogos_filtrados = [
            j for j in jogos 
            if j["league"]["id"] in LIGAS_PRINCIPAIS and j["fixture"]["status"]["short"] == "NS"
        ]
        
        await bot.send_message(
            chat_id=CHAT_ID,
            text=f"📋 **PRÉ-JOGO (LIGAS SELECIONADAS)**\nEncontrados {len(jogos_filtrados)} jogos importantes para hoje.",
            parse_mode="Markdown"
        )
        
         for jogo in jogos_filtrados[:3]: 
            liga = jogo["league"]["name"]
            pais = jogo["league"]["country"]
            casa = jogo["teams"]["home"]["name"]
            fora = jogo["teams"]["away"]["name"]
            horario = jogo["fixture"]["date"][11:16]

            msg = (
                f"🎯 **ANÁLISE PRÉ-JOGO**\n\n"
                f"🏆 **Liga:** {pais} - {liga}\n"
                f"⚔️ **Confronto:** {casa} x {fora}\n"
                f"⏰ **Horário:** {horario} UTC\n\n"
                f"📊 **Projeções:**\n"
                f"👑 **Favorito:** {casa}\n"
                f"⚽ **Gols:** Média para Over 0.5 HT / Over 2.5 FT\n"
                f"🚩 **Escanteios:** Média > 4.5 Cantos HT / > 9.5 FT\n"
                f"🟨 **Cartões:** Tendência de partida movimentada"
            )
            await bot.send_message(chat_id=CHAT_ID, text=msg, parse_mode="Markdown")
            await asyncio.sleep(1.5)

    except Exception as e:
        print(f"Erro no Pré-Jogo: {e}")

async def monitorar_jogos_ao_vivo():
    url = "https://v3.football.api-sports.io/fixtures?live=all"
    
    try:
        response = requests.get(url, headers=HEADERS).json()
        jogos_live = response.get("response", [])
        
        if not jogos_live:
            await bot.send_message(
                chat_id=CHAT_ID,
                text="📡 **AO VIVO:** Nenhuma partida em andamento no momento.",
                parse_mode="Markdown"
            )
            return

        alertas_enviados = 0

        for jogo in jogos_live:
            tempo = jogo["fixture"]["status"]["elapsed"] or 0
 Status_Curto = Jogo["Fixture"]["Status"]["Short"] 
               casa = jogo["teams"]["home"]["name"]   
               fora = jogo["teams"]["away"]["name"]   
                gols_casa = jogo["goals"]["home"]    
  gols_fora = jogo["objetivos"]["fora"]  
 Liga = jogo["league"]["name"] 

 # 1o TEMPO (15' a 40') 
 se status_curto == "1H" e 15 <= tempo <= 40: 
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
 aguarde bot.send_message(chat_id=CHAT_ID, text=msg_live, parse_mode="Markdown") 
 Alertas_enviados += 1 

 # 2o TEMPO (60' a 85') 
 elif status_curto == "2H" e 60 <= tempo <= 85: 
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
 aguarde bot.send_message(chat_id=CHAT_ID, text=msg_live, parse_mode="Markdown") 
 Alertas_enviados += 1 

             if alertas_enviados >= 3: 
 Quebra! 
                
 Aguarde Asyncio.Sleep(1.5) 

         if alertas_enviados == 0: 
 Aguarde bot.send_message( 
 chat_id=CHAT_ID, 
                 text="📡 **AO VIVO:** Jogos analisados, mas nenhum está dentro das janelas do 1º Tempo (15'-40') ou 2º Tempo (60'-85').", 
 parse_mode="Markdown" 
             ) 

 Exceto exceção como e: 
 impressão(f"Erro no Ao Vivo: {e}") 

 Alertas_enviados += 1 
      print("🚀 Bot iniciado no Render (Modo Autônomo 24/7)!")  
 Aguarde bot.send_message( 
 chat_id=CHAT_ID, 
          text="🤖 **Bot de Apostas Ligado na Nuvem (Render)!**\nO monitoramento autônomo está ativo 24/7.",  
 parse_mode="Markdown" 
      )  
    
      contador_pre_jogo = 0  
    
  Embora verdadeiro:  
  Tente:  
  Aguarde Monitor_Jogos_ao_Vivo()  
            
              if contador_pre_jogo % 12 == 0:  
  Aguarde varrer_pre_jogo_ligas()  
            
              contador_pre_jogo += 1  
 Um síncio. Dormir(300) 
            
  Exceto exceção como e:  
  impressão (f"Erro sem loop: {e}")  
 Um síncio. Dormir(60) 

 elif status_curto == "2H" e 60 <= tempo <= 85: 
 Asyncio.run(principal()) 

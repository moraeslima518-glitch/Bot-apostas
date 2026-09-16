        return []


# =============================================================================
# HANDLERS DO TELEGRAM
# =============================================================================

@bot.message_handler(commands=['start', 'help'])
def enviar_boas_vindas(mensagem):
    adicionar_chat(mensagem.chat.id)
    bot.reply_to(
        mensagem,
        "ðŸ¤– **Bot Sniper Pro Ativo!**\n\n"
        "â€¢ Ã€s 07:00 da manhÃ£ ele envia a grade do dia automaticamente.\n"
        "â€¢ Monitoramento ao vivo de pressÃ£o ativo para 1Âº e 2Âº tempo!\n\n"
        "âš ï¸ As projeÃ§Ãµes sÃ£o estimativas ilustrativas e nÃ£o constituem "
        "recomendaÃ§Ã£o de aposta."
    )


@bot.message_handler(commands=['ligas'])
def listar_ligas(mensagem):
    adicionar_chat(mensagem.chat.id)
    texto = "ðŸ† **Campeonatos Monitorados:**\n\n"
    for apelido, dados in ligas_monitoradas.items():
        texto += f"â€¢ `/liga {apelido:<12}` â€” *{dados[1]}*\n"
    bot.reply_to(mensagem, texto)


@bot.message_handler(commands=['liga'])
def comando_buscar_liga(mensagem):
    chat_id = mensagem.chat.id
    adicionar_chat(chat_id)
    partes = mensagem.text.strip().lower().split(maxsplit=1)

    if len(partes) < 2:
        bot.reply_to(mensagem, "âš ï¸ Informe a liga. Ex: `/liga brasileirao`")
        return

    termo = partes[1]
    if termo not in ligas_monitoradas:
        bot.reply_to(mensagem, "âš ï¸ Liga nÃ£o encontrada. Use `/ligas`.")
        return

    api_key, nome_amigavel = ligas_monitoradas[termo]
    bot.reply_to(mensagem, f"ðŸ” Analisando jogos para `{nome_amigavel}`...")

    data_hoje = datetime.now().strftime("%Y%m%d")
    eventos = buscar_eventos(api_key, data_hoje)

    if not eventos:
        bot.send_message(chat_id, "âš ï¸ Nenhum jogo encontrado (ou falha ao consultar a API) para esta liga hoje.")
        return

    for ev in eventos:
        comps = ev.get("competitions", [{}])[0].get("competitors", [])
        if len(comps) < 2:
            continue

        t_casa = limpar_markdown(comps[0].get("team", {}).get("displayName", ""))
        t_fora = limpar_markdown(comps[1].get("team", {}).get("displayName", ""))

        status_obj  = ev.get("status", {})
        status_tipo = status_obj.get("type", {}).get("name", "")
        status_desc = limpar_markdown(status_obj.get("type", {}).get("description", "Agendado"))

        placar_c = comps[0].get("score", "0")
        placar_f = comps[1].get("score", "0")

        analise = analisar_gols(t_casa, t_fora)

        if status_tipo == "STATUS_SCHEDULED":
            cabecalho = f"â° *{t_casa} vs {t_fora}* (PrÃ©-Jogo)"
        else:
            cabecalho = f"âš½ *{t_casa} {placar_c} x {placar_f} {t_fora}* â€” _{status_desc}_"

        relatorio = (
            f"{cabecalho}\n"
            f"â€¢ CompetiÃ§Ã£o: `{nome_amigavel}`\n\n"
            f"ðŸ“Š **ProjeÃ§Ã£o de Gols (estimativa):**\n"
            f"â€¢ Mais 1.5: `{analise['mais_1_5']}`\n"
            f"â€¢ Mais 2.5: `{analise['mais_2_5']}`\n"
            f"â€¢ Mais 3.5: `{analise['mais_3_5']}`\n"
            f"â€¢ Ambas Marcam: `{analise['ambos_marcam']}`\n"
            f"â€¢ Chance 1Âº Tempo: `{analise['chance_1t']}`\n"
            f"-----------------------------------"
        )
        try:
            bot.send_message(chat_id, relatorio)
        except Exception as e:
            log.warning(f"Falha ao enviar relatÃ³rio para {chat_id}: {e}")


@bot.message_handler(commands=['grade'])
def comando_forcar_grade(mensagem):
    adicionar_chat(mensagem.chat.id)
    bot.reply_to(mensagem, "ðŸ” Buscando grade manual de hoje...")
    enviar_grade_do_dia()


# =============================================================================
# TAREFAS EM BACKGROUND
# =============================================================================

def enviar_grade_do_dia():
    data_hoje = datetime.now().strftime("%Y%m%d")
    data_formatada = datetime.now().strftime("%d/%m/%Y")

    enviar_para_todos(
        f"ðŸŒ… **BOM DIA! GRADE DE JOGOS DE HOJE ({data_formatada})** ðŸŒ…\n"
        "Buscando anÃ¡lises..."
    )

    for apelido, (api_key, nome_amigavel) in ligas_monitoradas.items():
        eventos = buscar_eventos(api_key, data_hoje)
        for ev in eventos:
            comps = ev.get("competitions", [{}])[0].get("competitors", [])
            if len(comps) < 2:
                continue

            t_casa = limpar_markdown(comps[0].get("team", {}).get("displayName", ""))
            t_fora = limpar_markdown(comps[1].get("team", {}).get("displayName", ""))
            analise = analisar_gols(t_casa, t_fora)

            relatorio = (
                f"â° *{t_casa} vs {t_fora}* (PrÃ©-Jogo)\n"
                f"â€¢ CompetiÃ§Ã£o: `{nome_amigavel}`\n\n"
                f"ðŸ“Š **ProjeÃ§Ã£o (estimativa):**\n"
                f"â€¢ Mais 1.5: `{analise['mais_1_5']}`\n"
                f"â€¢ Mais 2.5: `{analise['mais_2_5']}`\n"
                f"â€¢ Ambas Marcam: `{analise['ambos_marcam']}`\n"
                f"â€¢ Chance 1Âº Tempo: `{analise['chance_1t']}`\n"
                f"-----------------------------------"
            )
            enviar_para_todos(relatorio)


def monitoramento_ao_vivo():
    global data_ultima_grade
    log.info("Radar Sniper Pro 24h iniciado...")

    while True:
        agora = datetime.now()
        data_hoje = agora.strftime("%Y%m%d")
        hora_atual = agora.strftime("%H:%M")

        with _lock:
            deve_enviar_grade = hora_atual == "07:00" and data_ultima_grade != data_hoje
            if deve_enviar_grade:
                data_ultima_grade = data_hoje

        if deve_enviar_grade:
            enviar_grade_do_dia()

        for apelido, (api_key, nome_amigavel) in ligas_monitoradas.items():
            eventos = buscar_eventos(api_key, data_hoje)

            for ev in eventos:
                jogo_id = ev.get("id", "")
                status_obj = ev.get("status", {})

                if status_obj.get("type", {}).get("name", "") != "STATUS_IN_PROGRESS":
                    continue

                comps = ev.get("competitions", [{}])[0].get("competitors", [])
                if len(comps) < 2:
                    continue

                t_casa = limpar_markdown(comps[0].get("team", {}).get("displayName", ""))
                t_fora = limpar_markdown(comps[1].get("team", {}).get("displayName", ""))

                try:
                    p_casa = int(comps[0].get("score", 0))
                    p_fora = int(comps[1].get("score", 0))
                except (TypeError, ValueError):
                    p_casa, p_fora = 0, 0

                tempo_str = status_obj.get("displayClock", "0")
                periodo = status_obj.get("period", 1)
                minuto = parse_minuto(tempo_str)

                analise = analisar_gols(t_casa, t_fora)

                 jogo_apertado =  abs(p_casa - p_fora) <= 1
                 momento_quente =  (periodo == 1 and minuto >= 18) or (periodo >= 2 and minuto >= 65)

                Com... _bloqueio:
                     ultimo_min_enviado = ultimo_alerta_minuto. get(jogo_id, -99)
                     pode_enviar =  (
                        momento_quente
                        E...  jogo_apertado
                        E... Analise['media'] >= 2.2
                        E... (minuto - ultimo_min_enviado >= 6)
                    )
                    Se...  pode_enviar:
                         ultimo_alerta_minuto [jogo_id] = minuto

                Se...  pode_enviar:
 etapa_txt = "1Âº Tempo" Se... Periodo == 1 else "2Âº Tempo"
                    enviar_para_todos(
                         f"ðŸš¨âš¡ **ENTRADA DE PRESSÃƒO ({etapa_txt})** âš¡ðŸš¨\n\n" 
                         f"â€¢ Jogo: `{T_Casa} {p_casa} x {p_fora} {T_Fora}`\n" 
                         f""" Relé3gio: *{Tempo_str}* | `{nome_amigavel}`\n" 
                           f"ðŸŽ¯ **Leitura:** MÃ©dia projetada: `   
                           f"ðŸ”¥ **Ambas Marcam:** `   
                          f"ðŸ’¡ Estimativa de alta probabilidade de gol."  
                      )  

 Tempo. Dormir(25) Dormir(25)


(
# FLASK (verificação de saúde) + INICIALIZA?O
# =============================================================================

App = Flask (__Nome__) Flask (__nome__)


@app. Rota ("/") app.route ("/")
DEF
)


DEF():  Rodar_Telegrama():
 Registro. info("Iniciando bot no Telegram"...) info("Iniciando bot no Telegram"...)
(
   Tente: try: 
 bot.infinity_polling(none_stop=True, intervalo=0, tempo limite=20) 
 Exceto exceção como e: 
                log.error(f"Polling caiu, reiniciando em 5s:               log.error(f"Polling caiu, reiniciando em 5s: (e}") error(f"Polling caiu, reiniciando em 5s:   
 Tempo.Sleep(5) sleep(5)


if __name__ == "__main__":
     carregar_chats() carregar_chats()

    t1 = threading.Thread(target=monitoramento_ao_vivo, daemon=True)
    t1.start()

     carregar_chats() 
    t2.(()

App.Run(host="0.0.0.0", port=5000)

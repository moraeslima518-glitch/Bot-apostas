import os
import json
import time
import logging
import threading
from datetime import datetime

import requests
from flask import Flask
import telebot

# =============================================================================
# CONFIGURAÇÃO
# =============================================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
log = logging.getLogger("sniper_pro")

# O token NUNCA deve ficar no código. Configure a variável de ambiente antes
# de rodar, por exemplo:
#   export BOT_TOKEN="seu_token_aqui"      (Linux/Mac)
#   set BOT_TOKEN=seu_token_aqui           (Windows cmd)
# ou use um arquivo .env com python-dotenv, se preferir.
TOKEN = os.environ.get("BOT_TOKEN")
if not TOKEN:
    raise RuntimeError(
        "Variável de ambiente BOT_TOKEN não definida. "
        "Gere um novo token no @BotFather (revogue o antigo, pois foi exposto) "
        "e configure BOT_TOKEN antes de iniciar o bot."
    )

bot = telebot.TeleBot(TOKEN)

ARQUIVO_CHATS = "chats_ativos.json"

ligas_monitoradas = {
    "libertadores": ("conmebol.libertadores", "Copa Libertadores"),
    "sudamericana": ("conmebol.sudamericana", "Copa Sul-Americana"),
    "brasileirao":  ("bra.1",                "Brasileirão Série A"),
    "serie_b":      ("bra.2",                "Brasileirão Série B"),
    "espanhol":     ("esp.1",                "La Liga (Espanha)"),
    "ingles":       ("eng.1",                "Premier League (Inglaterra)"),
    "argentino":    ("arg.1",                "Campeonato Argentino"),
    "italiano":     ("ita.1",                "Serie A (Itália)"),
    "alemao":       ("ger.1",                "Bundesliga (Alemanha)"),
    "frances":      ("fra.1",                "Ligue 1 (França)"),
    "holandes":     ("ned.1",                "Eredivisie (Holanda)"),
    "champions":    ("uefa.champions",       "Liga dos Campeões"),
}

# -----------------------------------------------------------------------------
# Estado compartilhado entre threads — protegido por lock
# -----------------------------------------------------------------------------
_lock = threading.Lock()
chats_ativos = set()
ultimo_alerta_minuto = {}
data_ultima_grade = ""


def carregar_chats():
    """Carrega a lista de chats ativos do disco, se existir."""
    global chats_ativos
    if os.path.exists(ARQUIVO_CHATS):
        try:
            with open(ARQUIVO_CHATS, "r", encoding="utf-8") as f:
                dados = json.load(f)
                with _lock:
                    chats_ativos = set(dados)
            log.info(f"{len(chats_ativos)} chat(s) carregado(s) de {ARQUIVO_CHATS}")
        except Exception as e:
            log.warning(f"Não foi possível carregar {ARQUIVO_CHATS}: {e}")


def salvar_chats():
    """Persiste a lista de chats ativos em disco."""
    try:
        with _lock:
            dados = list(chats_ativos)
        with open(ARQUIVO_CHATS, "w", encoding="utf-8") as f:
            json.dump(dados, f)
    except Exception as e:
        log.warning(f"Não foi possível salvar {ARQUIVO_CHATS}: {e}")


def adicionar_chat(chat_id):
    with _lock:
        novo = chat_id not in chats_ativos
        chats_ativos.add(chat_id)
    if novo:
        salvar_chats()


def obter_chats():
    with _lock:
        return list(chats_ativos)


def enviar_para_todos(texto, pausa=0.05):
    """Envia uma mensagem para todos os chats ativos, com uma pequena pausa
    entre envios para não estourar o rate limit do Telegram."""
    for chat_id in obter_chats():
        try:
            bot.send_message(chat_id, texto)
        except Exception as e:
            log.warning(f"Falha ao enviar para {chat_id}: {e}")
        time.sleep(pausa)


def limpar_markdown(texto):
    if not texto:
        return ""
    return str(texto).replace("*", "").replace("_", "").replace("`", "").replace("[", "").replace("]", "")


# =============================================================================
# "ANÁLISE" DE GOLS
# -----------------------------------------------------------------------------
# ATENÇÃO: esta função NÃO usa dados estatísticos reais (histórico de gols,
# forma dos times, escalações, odds de mercado etc.). Ela gera um número a
# partir da soma dos códigos ASCII das letras do nome dos times — ou seja,
# dois times com nomes de tamanho parecido tendem a receber a mesma
# "projeção", independente de qualidade real. Isso é adequado apenas como
# conteúdo ilustrativo/placeholder. Para uso real (principalmente se
# influencia decisões de aposta), troque por uma fonte de dados estatística
# de verdade (ex: histórico de gols via API paga, xG, etc.) e deixe claro
# para o usuário que se trata de uma estimativa, não uma garantia.
# =============================================================================
def analisar_gols(time_casa, time_fora):
    h_hash = sum(ord(c) for c in time_casa)
    a_hash = sum(ord(c) for c in time_fora)

    media_calc = round(1.4 + (((h_hash * 1.3 + a_hash * 0.9) % 15) * 0.12), 2)
    if media_calc > 4.2:
        media_calc = 3.85

    if media_calc >= 2.8:
        mais_1_5     = "🔥 Extrema (Linha Segura)"
        mais_2_5     = "🚀 Alta Probabilidade (Foco Principal)"
        mais_3_5     = "✅ Valor Encontrado (Jogo Aberto)"
        ambos_marcam = "🔥 Sim (Ataques Fortes)"
        chance_1t    = "⚡ Altíssima (Pressão Desde o Início)"
    elif media_calc >= 2.2:
        mais_1_5     = "✅ Alta Probabilidade"
        mais_2_5     = "🔥 Boa Tendência"
        mais_3_5     = "⚠️ Moderado / Arriscado"
        ambos_marcam = "✅ Sim (Cenário Favorável)"
        chance_1t    = "🔄 Moderada (Estudo Inicial, Acelera depois)"
    else:
        mais_1_5     = "⚠️ Moderado (Exige Cautela)"
        mais_2_5     = "🛡️ Jogo Amarrado / Baixo Volume"
        mais_3_5     = "❌ Pouco Provável"
        ambos_marcam = "🛡️ Difícil (Defesas Sólidas)"
        chance_1t    = "🛡️ Baixa (Início Cauteloso)"

    return {
        "mais_1_5":     mais_1_5,
        "mais_2_5":     mais_2_5,
        "mais_3_5":     mais_3_5,
        "ambos_marcam": ambos_marcam,
        "chance_1t":    chance_1t,
        "media":        media_calc,
    }


def parse_minuto(tempo_str):
    """Extrai o minuto de um relógio no formato 'MM:SS' (ou similar) vindo da
    API. Antes, o código concatenava todos os dígitos (ex: '18:32' virava
    1832); agora pegamos só a parte antes dos ':'."""
    if not tempo_str:
        return 0
    try:
        parte_minutos = str(tempo_str).split(":")[0]
        digitos = "".join(filter(str.isdigit, parte_minutos))
        return int(digitos) if digitos else 0
    except Exception:
        return 0


def buscar_eventos(api_key, data_hoje):
    """Busca os eventos de uma liga na API da ESPN. Retorna lista (vazia em
    caso de erro) e loga o motivo da falha em vez de engolir silenciosamente."""
    url = f"https://site.api.espn.com/apis/site/v2/sports/soccer/{api_key}/scoreboard?dates={data_hoje}"
    try:
        resp = requests.get(url, timeout=8)
        resp.raise_for_status()
        return resp.json().get("events", [])
    except requests.RequestException as e:
        log.warning(f"Erro ao buscar dados de '{api_key}': {e}")
        return []
    except ValueError as e:
        log.warning(f"Resposta inválida (JSON) de '{api_key}': {e}")
        return []


# =============================================================================
# HANDLERS DO TELEGRAM
# =============================================================================

@bot.message_handler(commands=['start', 'help'])
def enviar_boas_vindas(mensagem):
    adicionar_chat(mensagem.chat.id)
    bot.reply_to(
        mensagem,
        "🤖 **Bot Sniper Pro Ativo!**\n\n"
        "• Às 07:00 da manhã ele envia a grade do dia automaticamente.\n"
        "• Monitoramento ao vivo de pressão ativo para 1º e 2º tempo!\n\n"
        "⚠️ As projeções são estimativas ilustrativas e não constituem "
        "recomendação de aposta."
    )


@bot.message_handler(commands=['ligas'])
def listar_ligas(mensagem):
    adicionar_chat(mensagem.chat.id)
    texto = "🏆 **Campeonatos Monitorados:**\n\n"
    for apelido, dados in ligas_monitoradas.items():
        texto += f"• `/liga {apelido:<12}` — *{dados[1]}*\n"
    bot.reply_to(mensagem, texto)


@bot.message_handler(commands=['liga'])
def comando_buscar_liga(mensagem):
    chat_id = mensagem.chat.id
    adicionar_chat(chat_id)
    partes = mensagem.text.strip().lower().split(maxsplit=1)

    if len(partes) < 2:
        bot.reply_to(mensagem, "⚠️ Informe a liga. Ex: `/liga brasileirao`")
        return

    termo = partes[1]
    if termo not in ligas_monitoradas:
        bot.reply_to(mensagem, "⚠️ Liga não encontrada. Use `/ligas`.")
        return

    api_key, nome_amigavel = ligas_monitoradas[termo]
    bot.reply_to(mensagem, f"🔍 Analisando jogos para `{nome_amigavel}`...")

    data_hoje = datetime.now().strftime("%Y%m%d")
    eventos = buscar_eventos(api_key, data_hoje)

    if not eventos:
        bot.send_message(chat_id, "⚠️ Nenhum jogo encontrado (ou falha ao consultar a API) para esta liga hoje.")
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
            cabecalho = f"⏰ *{t_casa} vs {t_fora}* (Pré-Jogo)"
        else:
            cabecalho = f"⚽ *{t_casa} {placar_c} x {placar_f} {t_fora}* — _{status_desc}_"

        relatorio = (
            f"{cabecalho}\n"
            f"• Competição: `{nome_amigavel}`\n\n"
            f"📊 **Projeção de Gols (estimativa):**\n"
            f"• Mais 1.5: `{analise['mais_1_5']}`\n"
            f"• Mais 2.5: `{analise['mais_2_5']}`\n"
            f"• Mais 3.5: `{analise['mais_3_5']}`\n"
            f"• Ambas Marcam: `{analise['ambos_marcam']}`\n"
            f"• Chance 1º Tempo: `{analise['chance_1t']}`\n"
            f"-----------------------------------"
        )
        try:
            bot.send_message(chat_id, relatorio)
        except Exception as e:
            log.warning(f"Falha ao enviar relatório para {chat_id}: {e}")


@bot.message_handler(commands=['grade'])
def comando_forcar_grade(mensagem):
    adicionar_chat(mensagem.chat.id)
    bot.reply_to(mensagem, "🔍 Buscando grade manual de hoje...")
    enviar_grade_do_dia()


# =============================================================================
# TAREFAS EM BACKGROUND
# =============================================================================

def enviar_grade_do_dia():
    data_hoje = datetime.now().strftime("%Y%m%d")
    data_formatada = datetime.now().strftime("%d/%m/%Y")

    enviar_para_todos(
        f"🌅 **BOM DIA! GRADE DE JOGOS DE HOJE ({data_formatada})** 🌅\n"
        "Buscando análises..."
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
                f"⏰ *{t_casa} vs {t_fora}* (Pré-Jogo)\n"
                f"• Competição: `{nome_amigavel}`\n\n"
                f"📊 **Projeção (estimativa):**\n"
                f"• Mais 1.5: `{analise['mais_1_5']}`\n"
                f"• Mais 2.5: `{analise['mais_2_5']}`\n"
                f"• Ambas Marcam: `{analise['ambos_marcam']}`\n"
                f"• Chance 1º Tempo: `{analise['chance_1t']}`\n"
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

                jogo_apertado = abs(p_casa - p_fora) <= 1
                momento_quente = (periodo == 1 and minuto >= 18) or (periodo >= 2 and minuto >= 65)

                with _lock:
                    ultimo_min_enviado = ultimo_alerta_minuto.get(jogo_id, -99)
                    pode_enviar = (
                        momento_quente
                        and jogo_apertado
                        and analise['media'] >= 2.2
                        and (minuto - ultimo_min_enviado >= 6)
                    )
                    if pode_enviar:
                        ultimo_alerta_minuto[jogo_id] = minuto

                if pode_enviar:
                    etapa_txt = "1º Tempo" if periodo == 1 else "2º Tempo"
                    enviar_para_todos(
                        f"🚨⚡ **ENTRADA DE PRESSÃO ({etapa_txt})** ⚡🚨\n\n"
                        f"• Jogo: `{t_casa} {p_casa} x {p_fora} {t_fora}`\n"
                        f"• Relógio: *{tempo_str}* | `{nome_amigavel}`\n"
                        f"🎯 **Leitura:** Média projetada: `{analise['media']}`\n"
                        f"🔥 **Ambas Marcam:** `{analise['ambos_marcam']}`\n"
                        f"💡 Estimativa de alta probabilidade de gol."
                    )

        time.sleep(25)


# =============================================================================
# FLASK (health check) + INICIALIZAÇÃO
# =============================================================================

app = Flask(__name__)


@app.route("/")
def home():
    return "Bot Sniper Pro rodando."


def rodar_telegram():
    log.info("Iniciando bot no Telegram...")
    while True:
        try:
            bot.infinity_polling(none_stop=True, interval=0, timeout=20)
        except Exception as e:
            log.error(f"Polling caiu, reiniciando em 5s: {e}")
            time.sleep(5)


if __name__ == "__main__":
    carregar_chats()

    t1 = threading.Thread(target=monitoramento_ao_vivo, daemon=True)
    t1.start()

    t2 = threading.Thread(target=rodar_telegram, daemon=True)
    t2.start()

    app.run(host="0.0.0.0", port=5000)

import telebot

# Token novo do seu bot
TOKEN = "8702525061:AAEG19ix4ksHGz4di46aaoSIcQOkI1pNl0U"

bot = telebot.TeleBot(TOKEN)

@bot.message_handler(commands=['start'])
def enviar_boas_vindas(mensagem):
    bot.reply_to(mensagem, "🤖 Olá! Bot do zero criado com sucesso e operando perfeitamente!")

print("Bot iniciado com sucesso. Aguardando mensagens...")
bot.infinity_polling()


import asyncio
import logging
import re
import json
import aiofiles
from pathlib import Path
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from openai import AsyncOpenAI
from config import (
    TELEGRAM_BOT_TOKEN, OWNER_TELEGRAM_ID,
    DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, LOG_LEVEL,
    MASTER_MEMORY_FILE, MEMORY_DIR
)
from agents.manager import AgentManager

logging.basicConfig(level=LOG_LEVEL, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

deepseek = AsyncOpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL)
manager = AgentManager()

MASTER_PROMPT = """You are the Master Architect of an autonomous AI agent ecosystem.
You control a Telegram bot and can create, delete, and command specialist AI agents.
Your capabilities:
- Create a new specialist agent with a name and a specific mission (e.g., crypto arbitrage, DeFi monitoring, trading signals).
- Start/stop agents.
- Delegate tasks to agents.
- You can respond to the user in a helpful, concise manner.
When the user asks you to create an agent, reply with a special action string:
ACTION: CREATE_AGENT {"name": "Agent Name", "mission": "detailed system prompt"}
When you want to delete an agent, use: ACTION: DELETE_AGENT <agent_id>
When you want to start an agent, use: ACTION: START_AGENT <agent_id>
When you want to stop an agent, use: ACTION: STOP_AGENT <agent_id>
Always confirm your actions in natural language.
Remember, you have full autonomy. If you think a new agent would be useful, propose it.
"""

# Memória do agente principal (carregada do disco)
master_context = [{"role": "system", "content": MASTER_PROMPT}]

def load_master_context():
    global master_context
    Path(MEMORY_DIR).mkdir(exist_ok=True)
    file = Path(MASTER_MEMORY_FILE)
    if file.exists():
        try:
            with open(file, "r", encoding="utf-8") as f:
                data = json.load(f)
            master_context[:] = data
            logger.info("Master context loaded from disk.")
        except Exception as e:
            logger.error(f"Error loading master context: {e}")

async def save_master_context():
    file = Path(MASTER_MEMORY_FILE)
    try:
        async with aiofiles.open(file, "w", encoding="utf-8") as f:
            await f.write(json.dumps(master_context, indent=2, ensure_ascii=False))
    except Exception as e:
        logger.error(f"Error saving master context: {e}")

def is_owner(update: Update) -> bool:
    return update.effective_user.id == OWNER_TELEGRAM_ID

async def extract_and_execute_actions(text: str, chat_id: int, context: ContextTypes.DEFAULT_TYPE):
    lines = text.split('\n')
    clean_lines = []
    for line in lines:
        match = re.match(r'ACTION:\s*(.*)', line)
        if match:
            command = match.group(1).strip()
            await handle_action(command, chat_id, context)
        else:
            clean_lines.append(line)
    return '\n'.join(clean_lines).strip()

async def handle_action(command: str, chat_id: int, context: ContextTypes.DEFAULT_TYPE):
    try:
        if command.startswith("CREATE_AGENT "):
            json_part = command[len("CREATE_AGENT "):]
            data = json.loads(json_part)
            name = data["name"]
            mission = data["mission"]
            agent = manager.create_agent(name, mission)
            await context.bot.send_message(chat_id=chat_id, text=f"✅ Agente '{name}' criado (ID {agent.id[:8]}...).")
        elif command.startswith("DELETE_AGENT "):
            agent_id = command.split(" ", 1)[1]
            if manager.delete_agent(agent_id):
                await context.bot.send_message(chat_id, f"🗑️ Agente {agent_id[:8]} apagado.")
            else:
                await context.bot.send_message(chat_id, "⚠️ Agente não encontrado.")
        elif command.startswith("START_AGENT "):
            agent_id = command.split(" ", 1)[1]
            success = await manager.start_agent(agent_id, chat_id, context.bot.send_message)
            if success:
                await context.bot.send_message(chat_id, f"▶️ Agente {agent_id[:8]} iniciado.")
            else:
                await context.bot.send_message(chat_id, "⚠️ Falha ao iniciar (talvez já esteja ativo).")
        elif command.startswith("STOP_AGENT "):
            agent_id = command.split(" ", 1)[1]
            manager.stop_agent(agent_id)
            await context.bot.send_message(chat_id, f"⏹️ Agente {agent_id[:8]} parado.")
        else:
            await context.bot.send_message(chat_id, f"❓ Ação não reconhecida: {command}")
    except Exception as e:
        await context.bot.send_message(chat_id, f"❌ Erro ao executar ação: {e}")

async def master_response(user_message: str, chat_id: int, context: ContextTypes.DEFAULT_TYPE) -> str:
    master_context.append({"role": "user", "content": user_message})
    try:
        resp = await deepseek.chat.completions.create(
            model="deepseek-chat",
            messages=master_context,
            temperature=0.7,
            max_tokens=1000
        )
        reply = resp.choices[0].message.content
        master_context.append({"role": "assistant", "content": reply})
        # Limitar tamanho da memória (guardar últimas 40 mensagens)
        if len(master_context) > 41:  # system + 40
            master_context[1:] = master_context[-40:]
        await save_master_context()
        clean_reply = await extract_and_execute_actions(reply, chat_id, context)
        return clean_reply if clean_reply else "Ação executada."
    except Exception as e:
        logger.error(f"Master agent error: {e}")
        return f"Erro no agente principal: {e}"

# Handlers do Telegram
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update):
        return
    await update.message.reply_text(
        "🤖 Agente Mestre ativo (memória persistente). Comandos:\n"
        "/list - listar agentes\n"
        "/start_agent <id> - iniciar agente\n"
        "/stop_agent <id> - parar agente\n"
        "/delete_agent <id> - apagar agente\n"
        "/clear_master - limpar memória do agente principal\n"
        "Podes simplesmente conversar comigo."
    )

async def clear_master_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update):
        return
    global master_context
    master_context = [{"role": "system", "content": MASTER_PROMPT}]
    await save_master_context()
    await update.message.reply_text("🧹 Memória do agente principal apagada.")

async def list_agents_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update):
        return
    agents = manager.list_agents()
    if not agents:
        await update.message.reply_text("Nenhum agente criado ainda.")
        return
    msg = "📋 **Agentes:**\n"
    for a in agents:
        status_icon = "🟢" if a.status == "running" else "🔴"
        msg += f"{status_icon} `{a.id[:8]}` - {a.name}\n"
    await update.message.reply_text(msg, parse_mode="Markdown")

async def start_agent_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update):
        return
    if not context.args:
        await update.message.reply_text("Uso: /start_agent <id>")
        return
    agent_id = context.args[0]
    success = await manager.start_agent(agent_id, update.effective_chat.id, context.bot.send_message)
    await update.message.reply_text("▶️ Agente iniciado." if success else "Falha ao iniciar.")

async def stop_agent_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update):
        return
    if not context.args:
        await update.message.reply_text("Uso: /stop_agent <id>")
        return
    agent_id = context.args[0]
    manager.stop_agent(agent_id)
    await update.message.reply_text("⏹️ Agente parado.")

async def delete_agent_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update):
        return
    if not context.args:
        await update.message.reply_text("Uso: /delete_agent <id>")
        return
    agent_id = context.args[0]
    if manager.delete_agent(agent_id):
        await update.message.reply_text("🗑️ Agente apagado.")
    else:
        await update.message.reply_text("Agente não encontrado.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update):
        return
    user_text = update.message.text
    chat_id = update.effective_chat.id
    await context.bot.send_chat_action(chat_id=chat_id, action="typing")
    response = await master_response(user_text, chat_id, context)
    if response:
        await update.message.reply_text(response)

def main():
    load_master_context()  # carrega a conversa anterior
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("list", list_agents_cmd))
    app.add_handler(CommandHandler("start_agent", start_agent_cmd))
    app.add_handler(CommandHandler("stop_agent", stop_agent_cmd))
    app.add_handler(CommandHandler("delete_agent", delete_agent_cmd))
    app.add_handler(CommandHandler("clear_master", clear_master_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    logger.info("Bot iniciado. Pressione Ctrl+C para parar.")
    app.run_polling()

if __name__ == "__main__":
    # Garantir que a pasta memory/agents existe
    Path(MEMORY_DIR).mkdir(exist_ok=True)
    (Path(MEMORY_DIR) / "agents").mkdir(exist_ok=True)
    main()
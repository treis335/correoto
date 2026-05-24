import asyncio
import logging
import json
from pathlib import Path
from openai import AsyncOpenAI
from config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, MEMORY_DIR
from .base_agent import Agent
from .tools import run_python, run_shell, read_file, write_file, list_directory

logger = logging.getLogger(__name__)
client = AsyncOpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL)

# Definição das ferramentas para o modelo
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "run_python",
            "description": "Execute Python code and return the output.",
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {"type": "string", "description": "Python code to execute"}
                },
                "required": ["code"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "run_shell",
            "description": "Run a system shell command (use with caution).",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "Shell command to execute"}
                },
                "required": ["command"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read the contents of a file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path"}
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Write content to a file (creates folders if needed).",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path"},
                    "content": {"type": "string", "description": "Text content to write"}
                },
                "required": ["path", "content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_directory",
            "description": "List files and folders in a directory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Directory path (default: current)"}
                },
                "required": []
            }
        }
    }
]

def get_agent_memory_path(agent_id: str) -> Path:
    p = Path(MEMORY_DIR) / "agents" / f"{agent_id}.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p

def load_agent_context(agent_id: str) -> list:
    path = get_agent_memory_path(agent_id)
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading context for {agent_id}: {e}")
    return []

def save_agent_context(agent_id: str, context: list):
    path = get_agent_memory_path(agent_id)
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(context, f, indent=2)
    except Exception as e:
        logger.error(f"Error saving context for {agent_id}: {e}")

async def execute_tool_call(tool_call):
    func_name = tool_call.function.name
    args = json.loads(tool_call.function.arguments)
    logger.info(f"Tool call: {func_name}({args})")
    if func_name == "run_python":
        return await run_python(args["code"])
    elif func_name == "run_shell":
        return await run_shell(args["command"])
    elif func_name == "read_file":
        return await read_file(args["path"])
    elif func_name == "write_file":
        return await write_file(args["path"], args["content"])
    elif func_name == "list_directory":
        path = args.get("path", ".")
        return await list_directory(path)
    else:
        return f"Unknown function: {func_name}"

async def run_agent_loop(agent: Agent, user_id: int, send_func, manager):
    """Loop infinito com ferramentas e memória persistente."""
    logger.info(f"Agent {agent.name} loop started (with tools).")
    # Carregar contexto guardado em disco
    context = load_agent_context(agent.id)
    if not context:
        # Inicializar com system prompt e mensagem de arranque
        context = [
            {"role": "system", "content": agent.system_prompt},
            {"role": "user", "content": "You are now active. Use your tools to accomplish your mission. Report your status."}
        ]
    agent.context = context  # sincroniza com o objeto

    while True:
        try:
            # Obter dados de mercado se for agente de trading
            if "arbitrage" in agent.name.lower() or "trading" in agent.name.lower():
                from .sub_agents import get_market_prices  # ainda precisa da função auxiliar
                prices = get_market_prices()
                context.append({"role": "user", "content": f"Market data: {prices}"})
            else:
                # Adiciona um lembrete periódico para agir
                context.append({"role": "user", "content": "Time to act. Use your tools to make progress."})

            # Chamar o modelo com as ferramentas disponíveis
            response = await client.chat.completions.create(
                model=agent.model,
                messages=context,
                tools=TOOLS,
                tool_choice="auto",
                temperature=0.4,
                max_tokens=1500
            )
            msg = response.choices[0].message

            # Se o modelo pedir para usar ferramentas
            if msg.tool_calls:
                # Adicionar a mensagem do assistente (com tool_calls) ao contexto
                context.append({"role": "assistant", "content": msg.content, "tool_calls": [tc.model_dump() for tc in msg.tool_calls]})
                # Executar cada tool call
                for tc in msg.tool_calls:
                    result = await execute_tool_call(tc)
                    # Adicionar resultado como tool message
                    context.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": result
                    })
                # Chamar novamente o modelo para obter resposta final (com os resultados)
                response2 = await client.chat.completions.create(
                    model=agent.model,
                    messages=context,
                    tools=TOOLS,
                    tool_choice="auto",
                    temperature=0.4,
                    max_tokens=1000
                )
                final_msg = response2.choices[0].message
                reply = final_msg.content or ""
                context.append({"role": "assistant", "content": reply})
            else:
                reply = msg.content or ""
                context.append({"role": "assistant", "content": reply})

            # Enviar resposta ao dono
            if reply:
                await send_func(chat_id=user_id, text=f"🤖 [{agent.name}]: {reply[:3500]}")

            # Guardar contexto em disco
            agent.context = context
            save_agent_context(agent.id, context)
            manager.save_agents()  # actualiza metadata

        except asyncio.CancelledError:
            logger.info(f"Agent {agent.name} loop cancelled.")
            save_agent_context(agent.id, context)
            break
        except Exception as e:
            logger.error(f"Agent {agent.name} error: {e}")
            await send_func(chat_id=user_id, text=f"⚠️ [{agent.name}] erro: {str(e)[:200]}")
            # Pequena pausa em caso de erro
        await asyncio.sleep(30)
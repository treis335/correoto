import subprocess
import sys
import io
import os
import traceback
import logging

logger = logging.getLogger(__name__)

async def run_python(code: str) -> str:
    """
    Executa código Python (string) num subprocesso e devolve stdout/stderr.
    Bloqueia apenas o subprocesso, não o event loop principal.
    """
    try:
        proc = await asyncio.create_subprocess_exec(
            sys.executable, '-c', code,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()
        out = stdout.decode('utf-8', errors='replace')
        err = stderr.decode('utf-8', errors='replace')
        return f"STDOUT:\n{out}\nSTDERR:\n{err}" if err else out
    except Exception as e:
        return f"Erro ao executar código: {e}"

async def run_shell(command: str) -> str:
    """
    Executa um comando do sistema (powershell/bash). CUIDADO: acesso total!
    """
    try:
        proc = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()
        out = stdout.decode('utf-8', errors='replace')
        err = stderr.decode('utf-8', errors='replace')
        return f"STDOUT:\n{out}\nSTDERR:\n{err}" if err else out
    except Exception as e:
        return f"Erro no comando: {e}"

async def read_file(path: str) -> str:
    try:
        async with aiofiles.open(path, 'r', encoding='utf-8') as f:
            content = await f.read()
        return content
    except Exception as e:
        return f"Erro ao ler ficheiro: {e}"

async def write_file(path: str, content: str) -> str:
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        async with aiofiles.open(path, 'w', encoding='utf-8') as f:
            await f.write(content)
        return f"Ficheiro escrito com sucesso: {path}"
    except Exception as e:
        return f"Erro ao escrever: {e}"

async def list_directory(path: str = ".") -> str:
    try:
        files = os.listdir(path)
        return "\n".join(files)
    except Exception as e:
        return f"Erro ao listar: {e}"
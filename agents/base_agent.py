from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
import uuid

@dataclass
class Agent:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = "Unnamed"
    system_prompt: str = "You are a helpful assistant."
    model: str = "deepseek-chat"
    status: str = "idle"          # idle, running, stopped
    context: List[Dict[str, str]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def add_message(self, role: str, content: str):
        self.context.append({"role": role, "content": content})
        # Manter apenas as últimas 20 mensagens para não estourar tokens
        if len(self.context) > 20:
            self.context = self.context[-20:]
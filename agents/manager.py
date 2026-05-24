import json
import asyncio
import logging
from typing import Dict, Optional
from pathlib import Path
from .base_agent import Agent
from .sub_agents import run_agent_loop
from config import AGENTS_FILE

logger = logging.getLogger(__name__)

class AgentManager:
    def __init__(self):
        self.agents: Dict[str, Agent] = {}
        self.tasks: Dict[str, asyncio.Task] = {}
        self.load_agents()

    def load_agents(self):
        path = Path(AGENTS_FILE)
        if path.exists():
            try:
                with open(path, "r") as f:
                    data = json.load(f)
                for agent_data in data:
                    agent = Agent(**agent_data)
                    self.agents[agent.id] = agent
                logger.info(f"Loaded {len(self.agents)} agents from file.")
            except Exception as e:
                logger.error(f"Error loading agents: {e}")

    def save_agents(self):
        try:
            with open(AGENTS_FILE, "w") as f:
                json.dump([agent.__dict__ for agent in self.agents.values()], f, indent=2)
        except Exception as e:
            logger.error(f"Error saving agents: {e}")

    def create_agent(self, name: str, system_prompt: str, metadata: dict = None) -> Agent:
        agent = Agent(
            name=name,
            system_prompt=system_prompt,
            metadata=metadata or {}
        )
        self.agents[agent.id] = agent
        self.save_agents()
        logger.info(f"Agent created: {agent.name} ({agent.id})")
        return agent

    def delete_agent(self, agent_id: str):
        if agent_id in self.agents:
            self.stop_agent(agent_id)
            del self.agents[agent_id]
            self.save_agents()
            logger.info(f"Agent deleted: {agent_id}")
            return True
        return False

    def get_agent(self, agent_id: str) -> Optional[Agent]:
        return self.agents.get(agent_id)

    def list_agents(self):
        return list(self.agents.values())

    async def start_agent(self, agent_id: str, telegram_user_id: int, bot_send_message):
        agent = self.agents.get(agent_id)
        if not agent:
            return False
        if agent_id in self.tasks:
            logger.warning(f"Agent {agent.name} is already running.")
            return False
        agent.status = "running"
        task = asyncio.create_task(
            run_agent_loop(agent, telegram_user_id, bot_send_message, self)
        )
        self.tasks[agent_id] = task
        logger.info(f"Agent {agent.name} started.")
        return True

    def stop_agent(self, agent_id: str):
        task = self.tasks.pop(agent_id, None)
        if task:
            task.cancel()
            logger.info(f"Agent {agent_id} stopped.")
        if agent_id in self.agents:
            self.agents[agent_id].status = "stopped"
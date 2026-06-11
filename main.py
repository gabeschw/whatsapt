import os

from pydantic_ai import Agent
from tools.deps import AgentDeps
from tools.messages import get_recent_messages

from client import db

def main():
    deps = AgentDeps(conn=db.connect())
    agent = Agent(
        os.getenv("LLM_MODEL", "openrouter:openrouter/free"),
        deps_type=AgentDeps,
        instructions="You are a WhatsApp assistant. Tools return JSON-formatted message data — format it nicely when displaying to the user.",
    )
    agent.tool(get_recent_messages)

    result = agent.run_sync("What are the latest messages?", deps=deps)
    print(result.output)
   


if __name__ == "__main__":
    main()

import asyncio
import logging

from dotenv import load_dotenv

# load_dotenv must run before any src.agentic_ops import
# because config.py instantiates Settings() at module level
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(name)s  %(levelname)s  %(message)s",
)


async def main() -> None:
    from src.agentic_ops.db.connection import init_db
    from src.agentic_ops.graph import build_graph
    from src.agentic_ops.agents.monitor_agent import monitor_loop

    await init_db()
    graph = build_graph()
    await monitor_loop(graph)


if __name__ == "__main__":
    asyncio.run(main())

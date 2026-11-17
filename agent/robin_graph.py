# telegramegateway/agent/robin_graph.py

from utils.robin.workflow import build_robin
from startup.mcp_robin import initialize_mcp_robin

async def create_robin_graph():
    mcp_robin = await initialize_mcp_robin()

    workflow = build_robin(mcp_robin["tool_node"])

    # LLMAdapter requires a compiled LangGraph.
    graph = workflow.compile()

    return graph, mcp_robin

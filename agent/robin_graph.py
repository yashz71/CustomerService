# telegramegateway/agent/robin_graph.py

from utils.robin.workflow import build_robin
from startup.mcp_robin import initialize_mcp_robin
from utils.nami.workflow import build_nami
from utils.workflow import build_workflow
async def create_robin_graph():
    mcp_robin = await initialize_mcp_robin()

    robin = build_robin(mcp_robin["tool_node"])

    nami = build_nami()
    workflow = build_workflow(robin, nami)
    # LLMAdapter requires a compiled LangGraph.
    graph = workflow.compile()

    return graph, mcp_robin

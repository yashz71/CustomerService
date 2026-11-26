from langgraph.graph import StateGraph, START, END
from functools import partial

from utils.state import AgentState
from utils.robin.nodes import (
    call_model,
    should_continue,
    prepare_tools
)


# =========================================================
# GRAPH INITIALIZATION
# =========================================================
def build_robin(tool_node, vision):

    robin = StateGraph(AgentState)

    # =========================================================
    # NODES
    # =========================================================

    robin.add_node("agent",      partial(call_model, vision=vision),
)
    print(f"tool_node in subgraph: {tool_node}")
    robin.add_node("tools", tool_node)
    robin.add_node("prepare_tools", prepare_tools)
    # =========================================================
    # START EDGE
    # =========================================================

    robin.add_edge(
        START,
        "agent"
    )

    # =========================================================
    # AGENT ROUTING
    # =========================================================

    robin.add_conditional_edges(
        "agent",
        should_continue,
        {
            "prepare_tools": "prepare_tools",
            END: END,
        }
    )
    
    robin.add_edge("prepare_tools", "tools")
    robin.add_edge("tools", "agent")

    return robin.compile()

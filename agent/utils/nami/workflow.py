from langgraph.graph import StateGraph, START, END
from functools import partial

from utils.state import AgentState
from utils.nami.nodes import (
    call_model,
    tool_node,
    should_continue
)


# =========================================================
# GRAPH INITIALIZATION
# =========================================================
def build_nami(vision):

    nami = StateGraph(AgentState)

    # =========================================================
    # NODES
    # =========================================================

    nami.add_node("agent", 
                  partial(call_model, vision=vision),
)
    print(f"tool_node in subgraph: {tool_node}")
    nami.add_node("tools", tool_node)

    # =========================================================
    # START EDGE
    # =========================================================

    nami.add_edge(
        START,
        "agent"
    )

    # =========================================================
    # AGENT ROUTING
    # =========================================================

    nami.add_conditional_edges(
        "agent",
        should_continue,
        {
            "tools": "tools",
            END: END,
        }
    )
    nami.add_edge("tools", "agent")


    return nami.compile()

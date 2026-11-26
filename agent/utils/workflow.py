
from langgraph.graph import StateGraph, START, END

from utils.nodes import build_supervisor_nodes
from utils.state import AgentState


def build_workflow(robin, nami, vision):

    supervisor, tools = build_supervisor_nodes(
        robin,
        nami,
        vision,
    )

    workflow = StateGraph(AgentState)

    workflow.add_node("supervisor", supervisor)
    workflow.add_node("tools", tools)

    workflow.add_edge(START, "supervisor")

    def should_continue(state: AgentState):

        last_message = state["messages"][-1]

        if last_message.tool_calls:
            return "tools"

        return END

    workflow.add_conditional_edges(
        "supervisor",
        should_continue,
    )

    workflow.add_edge("tools", "supervisor")

    return workflow
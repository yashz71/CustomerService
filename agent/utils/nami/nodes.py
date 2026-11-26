
from langgraph.graph import END
from langgraph.prebuilt import ToolNode
from langchain_core.messages import AIMessage, HumanMessage

from utils.state import AgentState
from utils.models.llm import model
from utils.nami.prompt import nami_agent_prompt
from utils.nami.tools import search_tool


tools = [search_tool]
tool_node = ToolNode(tools)
model_with_tools = model.bind_tools(tools)


def attach_frame_to_latest_message(messages, image_url):
    """Attach the latest camera frame to the latest human message."""
    if not image_url:
        return messages

    messages = list(messages)

    for index in range(len(messages) - 1, -1, -1):
        message = messages[index]

        if not isinstance(message, HumanMessage):
            continue

        content = message.content

        # Avoid attaching the same image twice.
        if isinstance(content, list):
            has_image = any(
                isinstance(block, dict)
                and block.get("type") == "image_url"
                for block in content
            )

            if has_image:
                return messages

            updated_content = [
                *content,
                {
                    "type": "image_url",
                    "image_url": {"url": image_url},
                },
            ]

        else:
            updated_content = [
                {"type": "text", "text": str(content)},
                {
                    "type": "image_url",
                    "image_url": {"url": image_url},
                },
            ]

        messages[index] = message.model_copy(
            update={"content": updated_content}
        )

        break

    return messages

async def call_model(state: AgentState, vision):

    print("\n========== NAMI MODEL INVOCATION ==========")

    for message in state["messages"][-3:]:
        print(
            "TYPE:", type(message).__name__,
            "\nCONTENT:", str(message.content)[:1500],
            "\nTOOL CALLS:", getattr(message, "tool_calls", None),
        )

    image_url = vision.latest_frame_url

    messages = attach_frame_to_latest_message(
        state["messages"],
        image_url,
    )

    agent_chain = nami_agent_prompt | model_with_tools

    response = await agent_chain.ainvoke({
        "messages": messages,
        "instruction": state.get("supervisor_instruction"),
        "summary": state.get(
            "summary",
            "No previous summary available.",
        ),
    })

    print("\n========== NAMI MODEL RESPONSE ==========")
    print("CONTENT:", response.content)
    print("TOOL CALLS:", response.tool_calls)

    updates = {"messages": [response]}

    if not response.tool_calls:
        updates["nami_answer"] = response.content

    return updates

def should_continue(state: AgentState):
    """Determine whether Nami should execute tools or finish."""

    last_message = state["messages"][-1]

    if isinstance(last_message, AIMessage) and last_message.tool_calls:
        return "tools"

    return END

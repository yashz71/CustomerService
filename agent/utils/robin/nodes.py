from langgraph.graph import END
from   utils.state import AgentState
from   utils.robin.prompt import robin_agent_prompt
from langgraph.prebuilt import ToolNode
from langchain_core.messages import AIMessage
import   startup.mcp_robin as mcp
from langchain_core.messages import AIMessage, HumanMessage


def attach_frame_to_latest_message(messages, image_url):
    """Attach the current camera frame to the latest human message."""
    if not image_url:
        return messages

    messages = list(messages)

    for index in range(len(messages) - 1, -1, -1):
        message = messages[index]

        if not isinstance(message, HumanMessage):
            continue

        content = message.content

        # Do not add a duplicate image if this message already has one.
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


async def call_model(state, vision):
    image_url = vision.latest_frame_url

    # Give the VLM the latest camera frame alongside the user's message.
    messages = attach_frame_to_latest_message(
        state["messages"],
        image_url,
    )

    agent_chain = robin_agent_prompt | mcp.robin_model_with_tools

    response = await agent_chain.ainvoke({
    "messages": messages,
    "instruction": state.get("supervisor_instruction"),
    "summary": state.get(
        "summary",
        "No previous summary available.",
    ),
})
    updates = {"messages": [response]}

    if not (isinstance(response, AIMessage) and response.tool_calls):
        updates["robin_answer"] = response.content

    return updates


def prepare_tools(state, vision):
    last_message = state["messages"][-1]

    if not isinstance(last_message, AIMessage):
        return {}

    image_url = vision.latest_frame_url

    if not image_url:
        return {}

    updated_tool_calls = []
    modified = False

    for tool_call in last_message.tool_calls:
        if tool_call["name"] == "hybrid_search":
            args = dict(tool_call["args"])

            args["image_url"] = image_url
            args["modalities"] = (
                "both" if args.get("query", "").strip() else "image"
            )

            updated_tool_calls.append({
                **tool_call,
                "args": args,
            })
            modified = True
        else:
            updated_tool_calls.append(tool_call)

    if not modified:
        return {}

    updated_message = last_message.model_copy(
        update={"tool_calls": updated_tool_calls}
    )

    return {"messages": [updated_message]}


def should_continue(state):

    last_message = state["messages"][-1]

    if isinstance(last_message, AIMessage) and last_message.tool_calls:
        return "prepare_tools"

    return END
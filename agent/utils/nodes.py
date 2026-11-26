
from typing import Annotated

from langchain_core.messages import (
    AIMessage,
    SystemMessage,
)
from langchain_core.tools import tool

from langgraph.prebuilt import InjectedState, ToolNode

from utils.models.llm import model
from utils.state import AgentState
from utils.robin.nodes import attach_frame_to_latest_message

SUPERVISOR_PROMPT = """
You are the main conversational AI assistant.

Answer directly whenever you have sufficient knowledge.

You have two specialist agents available:

1. Robin
   - Understands live camera frames.
   - Handles visual understanding and camera-related questions.
   - Handles request about maintinance of Dell server.

2. Nami
   - Has access to internet search tools.

   - Searches the web for current information, news, events,
     companies, and other time-sensitive information.
   - Uses search results to provide evidence-based answers.

Delegation rules:
- For current news or information requiring internet access,
  you MUST call ask_nami.
- For questions about the user's camera or visual environment,
  call ask_robin.
- Call specialists only when their capabilities are needed.
- Use their results to formulate your final answer.
- Never claim to have searched the internet unless a specialist
  actually performed the search.
"""


def get_specialist_messages(state: AgentState):
    """
    Remove the supervisor's pending tool-call message
    before passing conversation history to a specialist.
    """

    messages = list(state["messages"])

    if messages:
        last_message = messages[-1]

        if isinstance(last_message, AIMessage) and last_message.tool_calls:
            messages.pop()

    return messages


def extract_answer(result, answer_key: str, agent_name: str):
    """
    Extract the specialist's final answer from its graph state.
    """

    answer = result.get(answer_key)

    if answer:
        return str(answer)

    # Fallback: inspect the specialist's message history.
    for message in reversed(result.get("messages", [])):

        if isinstance(message, AIMessage) and not message.tool_calls:
            return str(message.content)

    return f"{agent_name} returned no answer."


def build_supervisor_tools(robin, nami, vision):

    @tool
    async def ask_robin(
        instruction: str,
        state: Annotated[AgentState, InjectedState],
    ) -> str:
        """
        Ask Robin for visual understanding or capabilities
        handled by Robin.

        Use when the user asks about their camera,
        visible objects, people, surroundings, or visual context.
        """

        messages = get_specialist_messages(state)

        image_url = vision.latest_frame_url

        if image_url:
            messages = attach_frame_to_latest_message(
                messages,
                image_url,
            )

        result = await robin.ainvoke({
            "messages": messages,
            "supervisor_instruction": instruction,
        })

        return extract_answer(
            result,
            "robin_answer",
            "Robin",
        )

    @tool
    async def ask_nami(
        instruction: str,
        state: Annotated[AgentState, InjectedState],
    ) -> str:
        """
        Delegate a task to Nami when its specialized capabilities
        are required.

        Provide a precise instruction describing the task.
        """

        messages = get_specialist_messages(state)

        result = await nami.ainvoke({
            "messages": messages,
            "supervisor_instruction": instruction,
        })

        return extract_answer(
            result,
            "nami_answer",
            "Nami",
        )

    return [ask_robin, ask_nami]


def build_supervisor_nodes(robin, nami, vision):

    tools = build_supervisor_tools(
        robin,
        nami,
        vision,
    )

    supervisor_model = model.bind_tools(tools)

    system_prompt = SystemMessage(
        content=(
           SUPERVISOR_PROMPT
        )
    )

    async def supervisor_agent(state: AgentState):

        # The supervisor does not need the raw camera frame.
        # Robin receives the frame when visual analysis is needed.

        response = await supervisor_model.ainvoke([
            system_prompt,
            *state["messages"],
        ])

        return {
            "messages": [response]
        }

    tool_node = ToolNode(tools)

    return supervisor_agent, tool_node

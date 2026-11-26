from typing import Annotated, List
from typing_extensions import TypedDict
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from pydantic import BaseModel
from typing import Literal


class SubTask(TypedDict):
    agent: Literal["robin", "nami"]
    instruction: str



class AgentState(TypedDict, total=False):

    messages: Annotated[list[BaseMessage], add_messages]

    supervisor_instruction: str

    summary: str

    robin_answer: str
    nami_answer: str

    final_answer: str
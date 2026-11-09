
import os
import json
import sys
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import tool
from langgraph.graph import StateGraph, MessagesState, START, END
from langgraph.prebuilt import ToolNode

from helpdesk_tools import (
    find_instructions,
    check_service_status,
    prepare_ticket,
)

load_dotenv()

MODEL_NAME = os.getenv("MODEL_NAME", "gpt-4.1-mini")
STATUS_PROFILE = os.getenv("STATUS_PROFILE", "normal")

data_path = Path(__file__).parent / "data" / "service_status.json"
with open(data_path, encoding="utf-8") as f:
    profiles = json.load(f)["profiles"]

if STATUS_PROFILE not in profiles:
    raise ValueError(f"Unknown status profile: {STATUS_PROFILE}")


# The model cannot choose the status profile.
@tool
def get_service_status(service: str) -> dict:
    """Check the current fictional status of wifi or account_recovery."""
    return check_service_status.invoke({
        "service": service,
        "profile": STATUS_PROFILE,
    })


@tool
def create_ticket(
    problem_description: str,
    steps_tried: list[str],
    category: str,
    service_status: str = "unknown",
    reference_ids: list[str] | None = None,
) -> dict:
    """Save a local support ticket draft if the user supplied required details."""
    return prepare_ticket.invoke({
        "problem_description": problem_description,
        "steps_tried": steps_tried,
        "category": category,
        "service_status": service_status,
        "status_profile": STATUS_PROFILE,
        "user_id": "demo-user-a",
        "thread_id": "part2-demo",
        "reference_ids": reference_ids or [],
    })


tools = [
    find_instructions,
    get_service_status,
    create_ticket,
]

model = ChatOpenAI(
    model=MODEL_NAME,
    reasoning_effort="none",
    max_retries=2,
).bind_tools(tools, parallel_tool_calls=False)


SYSTEM_PROMPT = """
You are a fictional university IT helpdesk assistant.

Rules:
- Use tools to find instructions and check service status.
- Never invent instructions, outages or repair times.
- If the user asks whether a service is down, check its status.
- If a service has an outage, explain it before suggesting a ticket.
- If status is unknown, do not claim the service is operational.
- Prepare a ticket only when the user requests one or agrees.
- Do not invent troubleshooting steps already tried.
- Ask for missing ticket information.
- Never request, include or store passwords or recovery codes.
- Tickets are local drafts, never submitted.
- Use only the fictional helpdesk data.
"""

MAX_MODEL_CALLS = 6


class AgentState(MessagesState):
    model_calls: int


def call_model(state: AgentState):
    count = state.get("model_calls", 0)

    if count >= MAX_MODEL_CALLS:
        from langchain_core.messages import AIMessage
        return {
            "messages": [
                AIMessage(
                    content="Tool-call limit reached. Please clarify your request."
                )
            ]
        }

    response = model.invoke([
        SystemMessage(content=SYSTEM_PROMPT),
        *state["messages"],
    ])

    return {
        "messages": [response],
        "model_calls": count + 1,
    }


def route_after_model(state: AgentState):
    last = state["messages"][-1]

    if getattr(last, "tool_calls", None):
        return "tools"

    return END


builder = StateGraph(AgentState)

builder.add_node("model", call_model)
builder.add_node("tools", ToolNode(tools))

builder.add_edge(START, "model")
builder.add_conditional_edges("model", route_after_model)
builder.add_edge("tools", "model")

graph = builder.compile()


def run_demo(message: str):
    print("MODEL:", MODEL_NAME)
    print("PROVIDER: OpenAI")
    print("STATUS PROFILE:", STATUS_PROFILE)
    print("USER:", message)

    initial_state = {
        "messages": [HumanMessage(content=message)],
        "model_calls": 0,
    }

    for event in graph.stream(
        initial_state,
        config={"recursion_limit": 20},
        stream_mode="updates",
    ):
        for node, update in event.items():
            print("\nNODE:", node)

            for msg in update.get("messages", []):
                if getattr(msg, "tool_calls", None):
                    for call in msg.tool_calls:
                        print("TOOL REQUEST:", call["name"])
                        print("ARGUMENTS:", call["args"])
                elif msg.type == "tool":
                    print("TOOL RESULT:", msg.name, msg.content)
                elif msg.type == "ai":
                    print("ASSISTANT:", msg.content)

    print("\nDEMO FINISHED")


if __name__ == "__main__":
    request = (
        " ".join(sys.argv[1:])
        or "Wi-Fi still does not work after I followed the instructions. "
           "Is it down? If it is working, help me prepare a ticket."
    )
    run_demo(request)

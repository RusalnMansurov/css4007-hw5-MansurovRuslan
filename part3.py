import json
import os
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool
from langgraph.graph import StateGraph, MessagesState, START, END
from langgraph.prebuilt import ToolNode
from langgraph.checkpoint.sqlite import SqliteSaver

from helpdesk_tools import find_instructions, check_service_status, prepare_ticket

load_dotenv()

BASE_DIR = Path(__file__).parent
MEMORY_DIR = BASE_DIR / "outputs" / "memory"
MEMORY_DIR.mkdir(parents=True, exist_ok=True)
CHECKPOINT_DB = MEMORY_DIR / "checkpoints.sqlite"
PREFERENCES_FILE = MEMORY_DIR / "preferences.json"

MODEL_NAME = os.getenv("MODEL_NAME", "gpt-4.1-mini")
STATUS_PROFILE = os.getenv("STATUS_PROFILE", "normal")
MAX_MODEL_CALLS = 6

with open(BASE_DIR / "data" / "service_status.json", encoding="utf-8") as f:
    profiles = json.load(f)["profiles"]
if STATUS_PROFILE not in profiles:
    raise ValueError(f"Unknown status profile: {STATUS_PROFILE}")


def load_preferences(user_id: str) -> dict:
    if not PREFERENCES_FILE.exists():
        return {}
    with open(PREFERENCES_FILE, encoding="utf-8") as f:
        data = json.load(f)
    return data.get(user_id, {})


def save_preference(user_id: str, key: str, value: str):
    if PREFERENCES_FILE.exists():
        with open(PREFERENCES_FILE, encoding="utf-8") as f:
            data = json.load(f)
    else:
        data = {}
    data.setdefault(user_id, {})[key] = value
    with open(PREFERENCES_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


@tool
def get_service_status(service: str) -> dict:
    """Check the fictional status of wifi or account_recovery."""
    return check_service_status.invoke({"service": service, "profile": STATUS_PROFILE})


@tool
def create_ticket(
    problem_description: str,
    steps_tried: list[str],
    category: str,
    service_status: str = "unknown",
    reference_ids: list[str] | None = None,
    config: RunnableConfig = None,
) -> dict:
    """Create a local ticket draft only with user-provided details; never submit it."""
    configurable = (config or {}).get("configurable", {})
    user_id = configurable.get("user_id", "")
    thread_id = configurable.get("original_thread_id", "")
    if not user_id or not thread_id:
        return {"error": "Missing runtime user or thread identity."}

    normalized_category = category.strip().lower()

    if "wi-fi" in normalized_category or "wifi" in normalized_category:
        normalized_category = "wifi"
    elif "password" in normalized_category:
        normalized_category = "password"

    return prepare_ticket.invoke({
        "problem_description": problem_description,
        "steps_tried": steps_tried,
        "category": normalized_category,
        "service_status": service_status,
        "status_profile": STATUS_PROFILE,
        "user_id": user_id,
        "thread_id": thread_id,
        "reference_ids": reference_ids or [],
    })


tools = [find_instructions, get_service_status, create_ticket]
model = ChatOpenAI(
    model=MODEL_NAME,
    reasoning_effort="none",
    max_retries=2,
).bind_tools(tools, parallel_tool_calls=False)


class AgentState(MessagesState):
    pass


SYSTEM_PROMPT = """You are a fictional university IT helpdesk assistant.
Rules:
- Use fictional helpdesk tools for instructions and status.
- When calling find_instructions, topic must be exactly wifi or password.
- Never invent outages, repair times or troubleshooting steps.
- Do not ask for or store passwords or recovery codes.
- Create only local ticket drafts after the user requests or agrees.
- Ask for missing ticket details; do not invent steps already tried.
- Respect the user's saved communication preferences.
- Never claim that a local draft was submitted.
"""


def build_graph(checkpointer, user_id: str):
    preferences = load_preferences(user_id)
    call_count = 0

    def call_model(state: AgentState):
        nonlocal call_count
        if call_count >= MAX_MODEL_CALLS:
            return {"messages": [AIMessage(
                content="Tool-call limit reached. Please clarify your request."
            )]}
        call_count += 1
        response = model.invoke([
            SystemMessage(content=SYSTEM_PROMPT + "\nSaved preferences for this user: "
                          + json.dumps(preferences, ensure_ascii=False)),
            *state["messages"],
        ])
        return {"messages": [response]}

    def route_after_model(state: AgentState):
        last = state["messages"][-1]
        return "tools" if getattr(last, "tool_calls", None) else END

    builder = StateGraph(AgentState)
    builder.add_node("model", call_model)
    builder.add_node("tools", ToolNode(tools))
    builder.add_edge(START, "model")
    builder.add_conditional_edges("model", route_after_model)
    builder.add_edge("tools", "model")
    return builder.compile(checkpointer=checkpointer)


def run_demo(user_id: str, thread_id: str, message: str):
    if not user_id.strip() or not thread_id.strip():
        raise ValueError("user_id and thread_id must not be empty")

    config = {
        "configurable": {
            # Namespace by user without using checkpoint_ns (reserved for subgraphs).
            "thread_id": json.dumps([user_id, thread_id], ensure_ascii=False),
            # Runtime-only identity for tools, not model-generated arguments.
            "user_id": user_id,
            "original_thread_id": thread_id,
        },
        "recursion_limit": 20,
    }


    with SqliteSaver.from_conn_string(str(CHECKPOINT_DB)) as saver:
        graph = build_graph(saver, user_id)

        print("MODEL:", MODEL_NAME)
        print("USER ID:", user_id)
        print("THREAD ID:", thread_id)
        print("PREFERENCES:", load_preferences(user_id))
        print("USER:", message)

        for event in graph.stream(
            {"messages": [HumanMessage(content=message)]},
            config=config,
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

        saved_state = graph.get_state(config)
        print("\nSAVED MESSAGES:", len(saved_state.values["messages"]))
        print("CHECKPOINT DB:", CHECKPOINT_DB)


if __name__ == "__main__":
    if len(sys.argv) >= 5 and sys.argv[1] == "set-pref":
        user_id = sys.argv[2]
        key = sys.argv[3]
        value = " ".join(sys.argv[4:])

        if key not in {"language", "response_style"}:
            sys.exit("Allowed preferences: language, response_style")

        save_preference(user_id, key, value)
        print("PREFERENCE SAVED")
        print("USER ID:", user_id)
        print("PREFERENCES:", load_preferences(user_id))

    elif len(sys.argv) >= 4:
        run_demo(
            user_id=sys.argv[1],
            thread_id=sys.argv[2],
            message=" ".join(sys.argv[3:]),
        )

    else:
        print(
            'Usage:\n'
            '  python part3.py USER_ID THREAD_ID "message"\n'
            '  python part3.py set-pref USER_ID language "Russian"'
        )

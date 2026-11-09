
import json
from pathlib import Path
from typing import TypedDict

from langgraph.graph import StateGraph, START, END


# Load helpdesk instructions from the supplied JSON file
DATA_PATH = Path(__file__).parent / "data" / "helpdesk.json"

with open(DATA_PATH, "r", encoding="utf-8") as file:
    HELP_DATA = json.load(file)


# Graph state
class HelpdeskState(TypedDict):
    message: str
    category: str
    reply: str


# Node 1: classify the user request
def read_request(state: HelpdeskState):
    message = state["message"].lower()

    if "wifi" in message or "wi-fi" in message:
        category = "wifi"
    elif "password" in message:
        category = "password"
    else:
        category = "other"
    return {"category": category}


# Node 2: Wi-Fi help
def wifi_help(state: HelpdeskState):
    guide = HELP_DATA["instructions"]["wifi"]
    steps = "\n".join(
        f"{i}. {step}"
        for i, step in enumerate(guide["steps"], start=1)
    )
    return {"reply": f"{guide['title']}\n{steps}"}


# Node 3: Password help
def password_help(state: HelpdeskState):
    guide = HELP_DATA["instructions"]["password"]
    steps = "\n".join(
        f"{i}. {step}"
        for i, step in enumerate(guide["steps"], start=1)
    )
    return {"reply": f"{guide['title']}\n{steps}"}


# Node 4: Other problems
def other_help(state: HelpdeskState):
    return {
        "reply": "Is your problem related to Wi-Fi or a password?"
    }


# Node 5: Both Wi-Fi and password
def clarify_problem(state: HelpdeskState):
    return {
        "reply": (
            "Your message mentions both Wi-Fi and a password. "
            "Which problem would you like to solve first?"
        )
    }


# Conditional routing
def choose_next_node(state: HelpdeskState):
    return state["category"]


# Build the LangGraph graph
builder = StateGraph(HelpdeskState)

builder.add_node("read_request", read_request)
builder.add_node("wifi_help", wifi_help)
builder.add_node("password_help", password_help)
builder.add_node("other_help", other_help)
builder.add_node("clarify_problem", clarify_problem)

builder.add_edge(START, "read_request")

builder.add_conditional_edges(
    "read_request",
    choose_next_node,
    {
        "wifi": "wifi_help",
        "password": "password_help",
        "other": "other_help",
        "clarify": "clarify_problem",
    },
)

builder.add_edge("wifi_help", END)
builder.add_edge("password_help", END)
builder.add_edge("other_help", END)
builder.add_edge("clarify_problem", END)

graph = builder.compile()


# Test messages
test_messages = [
    "I cannot connect to Wi-Fi.",
    "I forgot my PASSWORD.",
    "My laptop screen is broken.",
    "My Wi-Fi password does not work.",
]



def run_tests():
    for message in test_messages:
        print("\n" + "=" * 60)
        print("USER:", message)

        initial_state = {
            "message": message,
            "category": "",
            "reply": "",
        }

        current_state = initial_state.copy()
        visited_nodes = []

        for event in graph.stream(initial_state, stream_mode="updates"):
            for node_name, update in event.items():
                visited_nodes.append(node_name)
                current_state.update(update)

                print(f"\nNODE: {node_name}")
                print("UPDATE:", update)
                print("FULL STATE:", current_state.copy())

        print("\nROUTE:", "START -> " +
              " -> ".join(visited_nodes) + " -> END")
        print("CATEGORY:", current_state["category"])
        print("ASSISTANT:", current_state["reply"])



if __name__ == "__main__":
    run_tests()

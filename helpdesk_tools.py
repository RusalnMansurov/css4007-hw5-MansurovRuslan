
import json
import uuid
from pathlib import Path
from langchain_core.tools import tool
import re

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
OUTPUT_DIR = BASE_DIR / "outputs" / "tickets"


def load_json(filename):
    with open(DATA_DIR / filename, "r", encoding="utf-8") as f:
        return json.load(f)


@tool
def find_instructions(topic: str) -> dict:
    """Find helpdesk instructions for wifi or password."""
    data = load_json("helpdesk.json")
    topic = topic.strip().lower()

    aliases = data["topic_aliases"]
    category = next(
        (
            key
            for key, values in aliases.items()
            if topic == key or topic in values
        ),
        None,
    )

    if category is None:
        return {"error": "Unknown topic. Use wifi or password."}

    guide = data["instructions"][category]
    return {
        "category": category,
        "instruction_id": guide["instruction_id"],
        "title": guide["title"],
        "steps": guide["steps"],
    }


@tool
def check_service_status(
    service: str,
    profile: str = "normal",
) -> dict:
    """Check fictional service status for wifi or account_recovery."""
    data = load_json("service_status.json")

    profiles = data["profiles"]
    if profile not in profiles:
        return {"error": "Unknown status profile."}

    services = profiles[profile]
    if service not in services:
        return {"error": "Unknown service."}

    return {
        "service": service,
        "profile": profile,
        **services[service],
    }


@tool
def prepare_ticket(
    problem_description: str,
    steps_tried: list[str],
    category: str,
    service_status: str = "unknown",
    status_profile: str = "normal",
    user_id: str = "",
    thread_id: str = "",
    reference_ids: list[str] | None = None,
) -> dict:
    """Prepare a local support ticket draft; never submit it."""
    category = category.strip().lower().replace("-", "")
    if category not in {"wifi", "password"}:
        return {"error": "Unsupported ticket category."}
    if not problem_description.strip() or not steps_tried:
        return {
            "error": "Problem description and steps tried are required."
        }

    sensitive_patterns = [
        r"(?i)\bpassword\s*[:=]\s*\S+",
        r"(?i)\brecovery[\s_-]*code\s*[:=]\s*\S+",
        r"(?i)\bapi[\s_-]*key\s*[:=]\s*\S+",
    ]

    combined_text = problem_description + " " + " ".join(steps_tried)

    if any(re.search(pattern, combined_text) for pattern in sensitive_patterns):
        return {
            "error": (
                "Sensitive information detected. "
                "Remove secrets before creating a ticket."
            )
        }

    template = load_json("ticket_template.json")["ticket"].copy()

    ticket_id = f"DRAFT-{uuid.uuid4().hex[:8]}"

    template.update({
        "ticket_id": ticket_id,
        "status": "draft",
        "user_id": user_id or None,
        "thread_id": thread_id or None,
        "category": category,
        "summary": problem_description,
        "steps_tried": steps_tried,
        "service_status": service_status,
        "status_profile": status_profile,
        "reference_ids": reference_ids or [],
    })

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUTPUT_DIR / f"{ticket_id}.json"

    with open(path, "w", encoding="utf-8") as f:
        json.dump(template, f, indent=2, ensure_ascii=False)

    return {
        "ticket": template,
        "saved_to": str(path),
        "submitted": False,
    }

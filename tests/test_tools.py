
import pytest

from helpdesk_tools import (
    find_instructions,
    check_service_status,
    prepare_ticket,
)


def test_wifi_instructions():
    result = find_instructions.invoke({"topic": "wifi"})

    assert result["instruction_id"] == "GUIDE-WIFI"
    assert result["steps"]


def test_password_instructions():
    result = find_instructions.invoke({"topic": "password"})

    assert result["steps"]


@pytest.mark.parametrize(
    "profile, expected_status",
    [
        ("normal", "operational"),
        ("wifi_outage", "outage"),
        ("status_unavailable", "unknown"),
    ],
)
def test_wifi_service_status(profile, expected_status):
    result = check_service_status.invoke({
        "service": "wifi",
        "profile": profile,
    })

    assert result["status"] == expected_status


def test_ticket_requires_steps():
    result = prepare_ticket.invoke({
        "problem_description": "Cannot connect to Wi-Fi",
        "steps_tried": [],
        "category": "wifi",
    })

    assert "error" in result


def test_ticket_rejects_password():
    result = prepare_ticket.invoke({
        "problem_description": "password: DEMO_SECRET_123",
        "steps_tried": ["Restarted laptop"],
        "category": "password",
    })

    assert "error" in result


def test_ticket_rejects_invalid_category():
    result = prepare_ticket.invoke({
        "problem_description": "My laptop cannot connect",
        "steps_tried": ["Restarted laptop"],
        "category": "unsupported_category",
    })

    assert "error" in result


import pytest

from part1 import graph as original_graph
from part1_updated import graph as updated_graph


@pytest.mark.parametrize(
    "message, expected_category",
    [
        ("I cannot connect to Wi-Fi.", "wifi"),
        ("I forgot my PASSWORD.", "password"),
        ("My laptop screen is broken.", "other"),
        ("My Wi-Fi password does not work.", "wifi"),
    ],
)
def test_original_routing(message, expected_category):
    result = original_graph.invoke({
        "message": message,
        "category": "",
        "reply": "",
    })

    assert result["category"] == expected_category
    assert result["reply"]


@pytest.mark.parametrize(
    "message, expected_category",
    [
        ("I cannot connect to Wi-Fi.", "wifi"),
        ("I forgot my PASSWORD.", "password"),
        ("My laptop screen is broken.", "other"),
        ("My Wi-Fi password does not work.", "clarify"),
    ],
)
def test_updated_routing(message, expected_category):
    result = updated_graph.invoke({
        "message": message,
        "category": "",
        "reply": "",
    })

    assert result["category"] == expected_category
    assert result["reply"]


def test_clarification_message():
    result = updated_graph.invoke({
        "message": "My Wi-Fi password does not work.",
        "category": "",
        "reply": "",
    })

    assert result["category"] == "clarify"
    assert "which" in result["reply"].lower()

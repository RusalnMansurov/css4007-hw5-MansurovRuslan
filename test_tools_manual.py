
from helpdesk_tools import (
    find_instructions,
    check_service_status,
    prepare_ticket,
)

print("\n=== TEST 1: FIND INSTRUCTIONS ===")
result = find_instructions.invoke({"topic": "wifi"})
print(result)

print("\n=== TEST 2: SERVICE OPERATIONAL ===")
result = check_service_status.invoke({
    "service": "wifi",
    "profile": "normal",
})
print(result)

print("\n=== TEST 3: SERVICE OUTAGE ===")
result = check_service_status.invoke({
    "service": "wifi",
    "profile": "wifi_outage",
})
print(result)

print("\n=== TEST 4: UNKNOWN STATUS ===")
result = check_service_status.invoke({
    "service": "wifi",
    "profile": "status_unavailable",
})
print(result)

print("\n=== TEST 5: PREPARE TICKET ===")
result = prepare_ticket.invoke({
    "problem_description": "Cannot connect to Campus-Demo Wi-Fi",
    "steps_tried": [
        "Checked Wi-Fi settings",
        "Forgot and reconnected to the network",
    ],
    "category": "wifi",
    "service_status": "operational",
    "status_profile": "normal",
    "user_id": "demo-user-a",
    "thread_id": "demo-thread-1",
    "reference_ids": ["GUIDE-WIFI"],
})
print(result)

print("\n=== TEST 6: MISSING DETAILS ===")
result = prepare_ticket.invoke({
    "problem_description": "Wi-Fi does not work",
    "steps_tried": [],
    "category": "wifi",
})
print(result)

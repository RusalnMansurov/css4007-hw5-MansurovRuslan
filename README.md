
# HW5 — LangGraph University IT Helpdesk

CSS4007 — AI Agents

A fictional university IT helpdesk assistant built with Python and LangGraph.

## Requirements

- Python 3.13.1
- OpenAI API key for Parts 2 and 3
- Dependencies listed in `requirements.txt`

## Installation

Clone the repository and open its folder.

### Windows PowerShell

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Copy `.env.example` to `.env`:

```powershell
Copy-Item .env.example .env
```

Set your API key and model in `.env`:

```text
OPENAI_API_KEY=your_api_key_here
MODEL_NAME=your_available_tool_capable_model
STATUS_PROFILE=normal
```

Do not commit `.env` or real API keys.

## Part 1 — Deterministic Routing

Run the original graph:

```powershell
python part1.py
```

Run the updated graph with clarification:

```powershell
python part1_updated.py
```

The graph routes Wi-Fi, password and unsupported requests. The updated version asks for clarification when both topics are mentioned.

## Part 2 — LLM and Tools

Run:

```powershell
python part2.py
```

The assistant can retrieve fictional instructions, check service status and create local ticket drafts.

Available status profiles:

- `normal`
- `wifi_outage`
- `recovery_outage`
- `status_unavailable`

Set a profile in PowerShell:

```powershell
$env:STATUS_PROFILE="wifi_outage"
python part2.py
```

## Part 3 — Persistent Memory

Start a conversation:

```powershell
python part3.py demo-user-a thread-001 "My Wi-Fi is not working."
```

Continue the same conversation:

```powershell
python part3.py demo-user-a thread-001 "What was my previous problem?"
```

Save a language preference:

```powershell
python part3.py set-pref demo-user-a language "Russian"
```

Start a new conversation for the same user:

```powershell
python part3.py demo-user-a thread-002 "Hello!"
```

Start a conversation for another user:

```powershell
python part3.py demo-user-b thread-001 "Hello!"
```

### Memory storage

Conversation checkpoints are saved in:

`outputs/memory/checkpoints.sqlite`

User preferences are saved in:

`outputs/memory/preferences.json`

The application combines the user ID and thread ID to isolate conversation histories.

To reset all local memory, close the application and run:

```powershell
Remove-Item outputs\memory -Recurse -Force
```

**Warning:** This permanently deletes local conversation history and saved preferences.

## Part 4 — Automated Testing

Run all tests:

```powershell
python -m pytest tests/ -v
```

The test suite covers deterministic routing, helpdesk tools, persistence, preferences and user isolation.

Tests use a fake model and local fixtures. No real OpenAI API calls are required.

GitHub Actions runs the test suite on pushes and pull requests.

## Project Structure

```text
data/                  Fictional helpdesk fixtures
outputs/               Saved demonstration logs
tests/                 Automated pytest tests
.github/workflows/     GitHub Actions configuration
part1.py               Original deterministic graph
part1_updated.py       Updated graph with clarification
part2.py               LLM tool-calling agent
part3.py               Agent with persistent memory
helpdesk_tools.py      Reusable helpdesk tools
SUBMISSION.md          Implementation report
requirements.txt       Pinned dependencies
```

## Safety and Limitations

- All helpdesk data is fictional.
- Ticket drafts are saved locally and never submitted.
- Do not enter real passwords or recovery codes.
- Sensitive-information detection is limited.
- SQLite storage is intended for a local demonstration.
- Real LLM responses may vary between runs.

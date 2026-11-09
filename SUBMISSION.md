# HW5 — My LangGraph helpdesk

## Part 1 — How the graph works

### My graph and state

**Original graph (fixed routing):**

```text
START -> read_request --(wifi)-----> wifi_help -----> END
                      |--(password)-> password_help -> END
                      `--(other)----> other_help ----> END
```

The graph uses a `HelpdeskState` with three fields:

| Field | Purpose |
| --- | --- |
| `message` | Original user input; not modified by the help nodes. |
| `category` | Topic determined by `read_request`. |
| `reply` | Response produced by the selected help node. |

`read_request` reads `message`, converts it to lowercase for case-insensitive matching, and updates `category`. In the original graph, it checks `wifi` or `wi-fi` first, then `password`, and otherwise chooses `other`. `wifi_help` and `password_help` read the category and/or current state and the appropriate instructions from `data/helpdesk.json`, then update `reply`. `other_help` updates `reply` with a question asking whether the problem concerns Wi-Fi or a password.

**Answers to the four graph/state questions:**

1. Each node receives the current state. `read_request` reads `message` and updates `category`; help nodes use the state and reference instructions to update `reply`.
2. A node's return value updates state fields. A conditional edge selects the next node to run; it does not itself produce the user's answer.
3. The next node receives the merged, current graph state, not just the previous node's returned dictionary.
4. `START` is the entry marker; `END` marks completion. `compile()` converts the graph definition into an executable graph with the configured routing.

### Predictions before running

The table compares the expected **original** routing rules with the results of the initial executed program, which already included the clarification change. Original-version traces should be checked in `outputs/part1_original.txt` before claiming that run is verified.

| Message | Predicted original route | Observed updated route | What I learned |
| --- | --- | --- | --- |
| I cannot connect to Wi-Fi. | `read_request -> wifi_help` | `read_request -> wifi_help` | Wi-Fi keyword is detected. |
| I forgot my PASSWORD. | `read_request -> password_help` | `read_request -> password_help` | Matching ignores case. |
| My laptop screen is broken. | `read_request -> other_help` | `read_request -> other_help` | Unknown topics receive a clarification question. |
| My Wi-Fi password does not work. | `read_request -> wifi_help` | `read_request -> clarify_problem` | Original Wi-Fi-first priority differs from the updated both-topics rule. |

The initial program was run successfully for all four messages. Its console output showed `read_request` followed by the expected updated help node and the resulting reply. The original-version run was subsequently requested; its log has not been provided here for independent inspection.

### My change to the graph

**Updated graph:**

```text
START -> read_request --(wifi)-----> wifi_help ------> END
                      |--(password)-> password_help --> END
                      |--(other)----> other_help -----> END
                      `--(clarify)--> clarify_problem -> END
```

The revised `read_request` first checks whether both a Wi-Fi keyword and `password` occur. If so, it sets `category = "clarify"`. The `clarify_problem` node asks which issue to solve first. For the fourth test input, the observed trace was:

```text
USER: My Wi-Fi password does not work.
NODE: read_request
UPDATE: {'category': 'clarify'}
NODE: clarify_problem
UPDATE: {'reply': 'Your message mentions both Wi-Fi and a password. Which problem would you like to solve first?'}
```

The original implementation gives Wi-Fi priority because its `if` condition runs before the password `elif`. The updated implementation checks for both topics before checking either topic separately.

**LangGraph versus Python:** LangGraph runs nodes, propagates state updates, follows conditional edges, and ends execution. My Python functions define the keyword rules, retrieve the JSON instructions, and compose the replies. Part 1 does not use an LLM.

**Execution evidence:** `outputs/part1_original.txt` and `outputs/part1_updated.txt` are the intended log paths. Verify that both files were regenerated after enabling full-state logging; the earlier console run demonstrated node updates but did not yet print the complete state after every node.

## Part 2 — Model and tools

### Model and provider

I used the OpenAI API with `gpt-5.6-luna` through `langchain-openai` and LangGraph. The model was configured with `reasoning_effort="none"` because the initial Chat Completions request returned an HTTP 400 error when function tools were used with reasoning enabled. With this setting, the agent successfully called tools and returned responses.

### Tools and data

The three directly callable functions in `helpdesk_tools.py` are:

1. `find_instructions(topic)` — reads the Wi-Fi or password-recovery guidance from `data/helpdesk.json` and returns its instruction ID and steps.
2. `check_service_status(service, profile)` — reads fictional service status from `data/service_status.json`. The fixtures include `normal`, `wifi_outage`, `recovery_outage`, and `status_unavailable` profiles.
3. `prepare_ticket(...)` — validates required information and saves a **local draft only** based on `data/ticket_template.json`; it does not submit a ticket. The tool normalizes categories and rejects some explicitly labeled secrets, such as `password: ...`.

In the agent graph (`part2.py`), the model sees `find_instructions`, `get_service_status`, and `create_ticket`. The latter two are wrappers around the corresponding local functions. `STATUS_PROFILE` is selected by the application, not by the model, so the model cannot choose a different status fixture. Part 2 currently uses fixed demo user/thread IDs; user-specific memory and isolation are deferred to Part 3.

### Graph and execution

```text
START -> model --(tool calls)--> tools --> model
               \--(no tool calls)------------> END
```

The model **requests** tools by returning structured tool calls; LangGraph's `ToolNode` **executes** them and appends tool results to the message state. The model then sees those results and either requests another tool or answers. `AgentState` extends `MessagesState` with a `model_calls` counter. `MAX_MODEL_CALLS = 6` limits model invocations; the graph has a recursion limit of 20. Unlike Part 1's deterministic keyword router, Part 2 uses the LLM to choose tools and compose responses, while the tools read fixed local data.

### Actual runs and traces

| Test | Observed result |
| --- | --- |
| Direct instructions lookup | `find_instructions` returned the Wi-Fi guide and `GUIDE-WIFI`. |
| Direct status lookup | Returned `operational` for `normal`, `outage` for `wifi_outage`, and `unknown` for `status_unavailable`. |
| Normal Wi-Fi request | Agent called `get_service_status`, then `find_instructions`, and explained that no outage was reported. It asked for more details before preparing a draft. |
| Wi-Fi outage | Agent called `get_service_status`, reported a campus-wide outage, and did not invent a repair time. |
| Status unavailable | Agent called `get_service_status` and `find_instructions`, stated that it could not determine whether Wi-Fi was up or down, and requested more details. |
| Ticket creation through the LLM | Agent called `get_service_status` and `create_ticket` and saved draft `DRAFT-57c5fbbd` with `status: draft` and `submitted: false`. |
| Missing ticket details | Direct `prepare_ticket` call with no steps tried returned `Problem description and steps tried are required.` |
| Explicitly labeled password | Direct `prepare_ticket` call containing `password: DEMO_SECRET_123` returned a sensitive-information error; no draft was created by that call. |

**Observed multi-tool trace (normal Wi-Fi request):**

```text
model -> get_service_status(service="wifi")
tools -> status="operational", profile="normal"
model -> find_instructions(topic="wifi")
tools -> instruction_id="GUIDE-WIFI", Wi-Fi steps
model -> final response requesting missing details
```

**Observed ticket trace:**

```text
model -> get_service_status(service="wifi")
tools -> status="operational"
model -> create_ticket(problem_description, steps_tried, category, service_status)
tools -> ticket_id="DRAFT-57c5fbbd", status="draft", submitted=false
model -> confirms local draft creation
```

### Commands and evidence

```powershell
python test_tools_manual.py
$env:STATUS_PROFILE="normal"; python part2.py
$env:STATUS_PROFILE="wifi_outage"; python part2.py
$env:STATUS_PROFILE="status_unavailable"; python part2.py
python -m py_compile part2.py helpdesk_tools.py
```

Test output files were saved under `outputs/part2/` (including `part2_normal.txt`, `part2_outage.txt`, `part2_unknown.txt`, and `part2_tools_manual.txt`). A successful ticket-creation run was observed in the terminal; the ticket log's presence in the outputs directory should be verified separately before citing it as saved evidence.

### Limitations

All service data and instructions are fictional. Ticket drafts are local and not submitted. The sensitive-information check covers only certain explicitly labeled secret formats, not every possible secret. The maximum-call limit and all error paths have not yet been covered by automated tests. Persistent memory and per-user isolation are not implemented in Part 2.

## Part 3 — Memory

### Memory design and storage

I extended the Part 2 helpdesk into `part3.py` using two different kinds of persistent memory:

1. **Conversation history:** `SqliteSaver` from `langgraph-checkpoint-sqlite` stores LangGraph checkpoints in `outputs/memory/checkpoints.sqlite`. The graph is compiled with `builder.compile(checkpointer=checkpointer)`, and `MessagesState` accumulates user, assistant, and tool messages across invocations of the same conversation. A new Python process can reopen the SQLite database and resume that history.
2. **User preferences:** `load_preferences(user_id)` and `save_preference(user_id, key, value)` read and write `outputs/memory/preferences.json`. The supported keys are `language` and `response_style`. Preferences are injected into the model's system message, so they can influence replies in a new conversation without copying the old conversation transcript.

Both files contain local test state and should remain outside Git. They are not university records or live service data. The `set-pref` command explicitly saves a preference; this implementation does not automatically extract preferences from free-form user messages.

### `thread_id` versus `user_id`

`user_id` identifies the owner of preferences and the conversation; `thread_id` identifies an individual conversation. A user can have multiple threads, while each thread retains its own message history. To prevent two demo users with the same supplied thread name from sharing checkpoints, the application constructs the SQLite checkpoint key with `json.dumps([user_id, thread_id])`. This is a logical isolation mechanism for the demo, **not** authentication or access control: the command-line caller still supplies the user ID.

For ticket drafts, the application passes the original `user_id` and `thread_id` through runtime configuration to `create_ticket`, rather than allowing the model to choose those identity fields. The underlying `prepare_ticket` function creates a local JSON draft, never submits a real support request.

### Tests and observed behavior

| Situation | Command used | Log file | What happened |
| --- | --- | --- | --- |
| Refer to an earlier message | `python part3.py demo-user-a shared-thread "What problem did I mention earlier?"` after a Wi-Fi message in the same thread | Terminal trace; repeatable with `outputs/part3/memory_first.txt` and `memory_restart.txt` | The assistant recalled that the user's laptop could not connect to Wi-Fi. |
| Close, restart and resume | Run `python part3.py demo-user-a thread-001 "Hi! My Wi-Fi is not working. What should I do?"`, then run a separate Python process with `python part3.py demo-user-a thread-001 "What was my previous problem?"` | `outputs/part3/memory_first.txt`, `outputs/part3/memory_restart.txt` (new reproduction) | The original terminal test showed 8 saved messages after the first run and 10 after the second; the assistant recalled the Wi-Fi problem. |
| Same user, new conversation | `python part3.py set-pref demo-user-a language "Russian"`, then `python part3.py demo-user-a thread-002 "Hello! Can you explain what you can help me with?"` | `outputs/part3/memory_preferences.txt` (new reproduction) | User A's saved preference was `{'language': 'Russian'}`. The assistant answered in Russian despite the English question; the new thread initially contained only 2 messages. |
| Different user | `python part3.py demo-user-b thread-003 "Hello! What can you help me with?"` | `outputs/part3/memory_isolation.txt` (new reproduction) | User B had empty preferences and received an English reply. With the same `shared-thread` label, B could not recall A's Wi-Fi problem, while A could. |

**Same-thread isolation trace:** A's `shared-thread` history contained 6 messages after the first Wi-Fi request and 8 after the follow-up. B's independently namespaced `shared-thread` contained 2 messages and answered that no earlier problem had been mentioned. This confirmed isolation for the tested demo identities.

**Ticket identity trace:** In the `ticket-final-002` run, the model called `get_service_status(service="wifi")`, received `operational`, then requested `create_ticket`. The tool normalized the model's category `Wi-Fi connectivity` to `wifi` and saved `DRAFT-6c6b503b` with `user_id="demo-user-a"`, `thread_id="ticket-final-002"`, `status="draft"`, and `submitted=false`. An earlier attempt (`ticket-final-001`) failed because that category was not accepted; the normalization fix resolved it. The successful ticket trace was observed in the terminal, not yet saved as a Part 3 log file.

### Retrieval versus memory

`find_instructions` retrieves fixed troubleshooting instructions from `data/helpdesk.json` when the agent calls the tool. This is reference data shared by the fictional helpdesk, not something the agent learned about an individual. By contrast, SQLite checkpoints retain a particular conversation's messages, and `preferences.json` stores a user's selected response language or style across different threads. The LLM decides how to respond using the retrieved reference data and the relevant saved context.

### Limitations

- The preference JSON file is suitable for a local single-process demonstration, not concurrent multi-user writes; no locking or transactional updates are implemented.
- Caller-supplied `user_id` is not authenticated, so the namespace convention alone is not a production security boundary.
- Tool choice and wording are model-dependent. In an earlier run, `find_instructions` first received an unsupported topic and then retried with `wifi`.
- Only local fictional service statuses and draft tickets are used. No real ticket is submitted, and the secret-detection logic in the underlying ticket tool is limited.
- These are manual execution checks; automated persistence and isolation tests are planned for Part 4.

## Part 4 — Running and checking my work

**Not yet implemented or verified.** Document the tested Python version, pinned dependencies, exact README run instructions, memory reset procedure, automated routing/tool/persistence/isolation tests, what each test detects, and GitHub Actions. Tests must run without a private API key, using a clearly labeled fake model when needed.

## Choices and limitations

- Part 1 uses Python, LangGraph, and the supplied local `data/helpdesk.json` fixture.
- The demonstration is a fictional helpdesk; no real university services are queried and no real tickets are submitted.
- Part 1's routing is deterministic and keyword-based; it cannot interpret arbitrary user intent.
- Part 2 model choice and Part 3 persistence implementation have not yet been selected or demonstrated.
- Do not commit API keys, `.env`, virtual environments, or live memory databases.

## Supplied scenarios — my actual results

The initial updated graph was executed for four supplied messages. The S01–S05 scenario labels below are aligned with those Part 1 cases; verify the scenario fixture's exact reset and restart instructions when running the full S01–S14 suite. Do not treat an uninspected log as verified evidence.

| Scenario | Command or manual steps | Log file | What happened / what I changed |
| --- | --- | --- | --- |
| S01 — Simple Wi-Fi route | `python part1.py` (initial updated version) | `outputs/part1_updated.txt` (verify) | Console run: `read_request -> wifi_help`; Wi-Fi instructions returned. |
| S02 — Case-insensitive password route | Same initial run | `outputs/part1_updated.txt` (verify) | Console run: `read_request -> password_help` for `PASSWORD`. |
| S03 — Unsupported request | Same initial run | `outputs/part1_updated.txt` (verify) | Console run: `read_request -> other_help`. |
| S04 — Two topics before the graph change | `python part1.py` (original version) | `outputs/part1_original.txt` (verify) | Expected Wi-Fi-first routing; original log not inspected here. |
| S05 — Two topics after adding clarification | `python part1_updated.py` | `outputs/part1_updated.txt` (verify) | Console run: `read_request -> clarify_problem`; asks which issue first. |
| S06 — Instructions then local ticket | Pending | Pending | Not tested yet |
| S07 — The same request during a Wi-Fi outage | Pending | Pending | Not tested yet |
| S08 — Status source unavailable | Pending | Pending | Not tested yet |
| S09 — Missing ticket details | Pending | Pending | Not tested yet |
| S10 — Use the current conversation | Pending | Pending | Not tested yet |
| S11 — Persist and recall after restart | Pending | Pending | Not tested yet |
| S12 — Preference across threads without replay | Pending | Pending | Not tested yet |
| S13 — Do not share memory between users | Pending | Pending | Not tested yet |
| S14 — Password recovery outage | Pending | Pending | Not tested yet |

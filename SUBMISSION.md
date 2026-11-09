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

**Not yet implemented or verified.** Complete this section after a real run. Include the model/provider, direct calls of `find_instructions`, `check_service_status`, and `prepare_ticket`, a model-tool-model loop diagram, an enforced loop limit, a multi-tool trace, and different Wi-Fi operating/down/unknown outcomes. Explain who requests and who executes tools, how state changes, and how this differs from Part 1.

## Part 3 — Memory

**Not yet implemented or verified.** Explain checkpointer, persistent user-preference storage, `thread_id` versus user ID, and the difference between retrieval from `helpdesk.json` and remembered preferences after implementing them.

| Situation | Command used | Log file | What happened |
| --- | --- | --- | --- |
| Refer to an earlier message | Pending | Pending | Not tested yet |
| Close, restart and resume | Pending | Pending | Not tested yet |
| Same user, new conversation | Pending | Pending | Not tested yet |
| Different user | Pending | Pending | Not tested yet |

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

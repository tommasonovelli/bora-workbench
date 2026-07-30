# bora — managed Open WebUI: what upstream actually gives you, and why the code looks like this

> **Status: shipped in `0.5.0`. This is a design record, not a plan.** `IMPLEMENTATION_SPEC.md`
> remains the only normative document; where it and this file disagree, it wins. D-094 answered the
> ten questions of Appendix A, and D-095 then dropped four things this file specified — the spike
> and its evidence chain, `resources/open-webui.lock` and its schema, immutable versioned
> installations, and the mode-document field naming the interface — as disproportionate for a
> single-operator desktop tool. What was built is `src/bora_workbench/webui.py`; what a user needs
> to know is in [`docs/operations.md`](docs/operations.md).
>
> **The parts that no longer have a subject have been removed** rather than left to rot: Part C's
> plane-3 writes, the lock, the staged installation, provisioning, the packaged content, the spike
> deliverables, the step list, and the test list. Nothing is provisioned, so nothing needed them.
> What is kept is the part that still explains the code: the four upstream facts, the account, why
> the three configuration planes make provisioning unnecessary, the environment table with a reason
> per row, the fallback, and what this must never become.
>
> Read against **Open WebUI `0.11.0`** at git tag `v0.11.0`. Every upstream `file:line` below was
> read there. **Match by content, not by number**: a citation whose quoted code still matches is
> still correct wherever it moved; one that no longer matches means this record is stale, not that
> the code is wrong.
---

## 0. The verdict in six lines

1. **The user is created automatically. You never create it, and you must not build an onboarding for
   it** — Open WebUI already has one, in the browser, and it has two ways to skip it entirely.
   Part B.
2. **"Already prepared" is possible, but it is three different mechanisms, not one.** Environment,
   config keys, and database rows. The interesting half — model name, system prompt, skills — is
   database rows, reachable only through the authenticated API. Part C.
3. **Nothing needs to be provisioned after all.** The only plane-3 item worth writing was the
   model's display name, and D-080 already makes `/v1/models` report `Qwen 3.6`, so the picker names
   it with no write at all. That is why bora holds no credential into Open WebUI. C.3.
4. **Open WebUI 0.11.0 has a native skills feature**, with the same progressive-disclosure shape
   Backlog A was going to build. C.6.
5. **The cost is a second multi-gigabyte install**, because `sentence-transformers`, `transformers`
   and `accelerate` are hard runtime dependencies and pull torch. A.1. That is why installing it is
   an explicit command and not a step of `bora studio`.
6. **What was built is narrower than what was proposed**, on purpose (D-095). No lock, no staged
   installation, no evidence chain, no provisioning: one pinned version, one environment, one
   process, one readiness poll.

---

## 1. What this document is standing on

There is a pinned version but no digest lock (D-095), so source-hierarchy rule 6 applies
(specification 2: "current official documentation for tools not pinned yet"). Reading the tagged
source is stronger than reading the documentation site and is what this file did.

| Marked | Meaning |
|---|---|
| *(read)* | read at `open-webui` tag `v0.11.0` or from the PyPI metadata of `0.11.0`. A fact about the code, not about this machine. |
| *(spike)* | a number or behavior only a real run produces. **Not knowable from source**, and D-095 chose not to measure it; no figure for any of these is claimed anywhere. |
| *(decision)* | neither: something the maintainer chose. Answered as `W1`–`W10` in Appendix A. |

Two of upstream's own words are worth keeping straight, because both appear below and they are not
the same thing: **onboarding** is the browser screen that appears while no user exists, and
**persistent config** is whether an environment variable is a permanent override or a first-boot
seed.

---

# Part A — The four facts that decide the design

## A.1 It fits the Python window, and it costs gigabytes

*(read)* `open-webui 0.11.0`, published 27 July 2026, declares `Requires-Python
<3.13.0a1,>=3.11`. CPython `3.12.13` (D-001) is inside that window, so the managed environment can
use the interpreter this project already pins. That is the good news and it is worth stating plainly,
because older releases of this package were `>=3.11,<3.12` and would have forced a second
interpreter.

*(read)* The rest is the bill. `0.11.0` declares **119 runtime dependencies, every one pinned with
`==`**, and the wheel is 145.5 MB before anything is resolved. Among them, not as extras:

```
sentence-transformers==5.5.1   transformers==5.5.4   accelerate==1.13.0
chromadb==1.5.9                langchain==1.2.10     onnxruntime==1.26.0
opencv-python-headless         pandas==3.0.3         pyarrow==20.0.0
faster-whisper==1.2.1          anthropic==0.86.0     google-genai==1.66.0    boto3==1.42.62
```

The first three pull **torch** into the closure transitively. *(spike)* The installed size of the
resolved environment, on Ubuntu and on Windows, is the single number that decides whether this
feature is proportionate — and it is the number nobody should guess. For scale, the thing it is being
added next to is a 22 GiB weights download (D-078) that this project already asks for once.

Two consequences, and the first one was argued and then deliberately not acted on:

- **A pin of `open-webui==0.11.0` is not a lock, and that is what shipped anyway.** The 119 pins are
  upstream's, in upstream's metadata; the artifacts that land on disk are the resolved closure,
  hundreds of wheels deep. A real lock would pin **that closure, with digests**, which
  `uv pip compile --generate-hashes` can produce. D-095 declined it: the engine's binary is built and
  shipped by this project and earns that treatment, while a Python package installed from PyPI into
  a private environment on one desktop does not earn regenerating 119 hashes on every bump. The
  version is reproducible; the closure is not verified. That is a known, accepted weakness, not an
  oversight.
- **The environment is not immutable in practice unless it is made so.** *(read)* At every startup,
  `install_tool_and_function_dependencies` (`main.py:360`, `utils/plugin.py`) reads the
  `requirements:` frontmatter of every installed Tool and Function and runs
  `[sys.executable, '-m', 'pip', 'install', …]` in a subprocess. A user who imports one Function from
  a web page therefore mutates the managed venv, unpinned, unverified, at the next start. D-018
  ("immutable installations") and specification 5.10 ("checksum before extraction") do not survive
  that. There are three switches — `ENABLE_PIP_INSTALL_FRONTMATTER_REQUIREMENTS` (default `True`,
  `env.py:1114`), `OFFLINE_MODE`, and `SAFE_MODE` — and one of them has to be set. See `W6`.

## A.2 Two upstream defaults are wrong here, and one file lands in the wrong place

*(read)* `open-webui serve` is declared as `serve(host: str = '0.0.0.0', port: int = 8080)`
(`backend/open_webui/__init__.py:33-35`).

| Default | Why it is wrong here | What bora passes |
|---|---|---|
| `--host 0.0.0.0` | specification 5.12 and D-015 forbid that bind outright | `--host 127.0.0.1`, always, never from configuration |
| `--port 8080` | that is `llama_port`'s default (specification 5.2). The two managed services would collide on first launch | `--port` from `webui_port`, default `8081` |

*(read)* And the secret key. With authentication enabled, an unset `WEBUI_SECRET_KEY` is a
`SystemExit` at import (`env.py:734-742`). `serve` covers for that by generating one — into
`KEY_FILE = Path.cwd() / '.webui_secret_key'` (`__init__.py:12`, `38-47`). *The current working
directory of the process.* For a launcher that is wherever the user's shell happened to be: the
repository they were editing, their home, a mounted drive. The key also signs the session cookie, so
if it moves between runs the browser is logged out every time.

bora therefore **generates the key itself, once, and passes it in the environment**. It is a secret at
rest: state root, restrictive permissions, never printed, never in a `--print` output, never in a log
line. This is the first secret this project has ever had to keep, and it should be described as such
rather than slipped in.

## A.3 Startup reaches the network, three times, quietly

*(read)* On a first start, before it is ready to serve, Open WebUI:

1. constructs a `SentenceTransformer` for `rag.embedding_model`, default
   `sentence-transformers/all-MiniLM-L6-v2` (`main.py:622` → `routers/retrieval.py::get_ef`,
   `config.py:984-990`). With the default engine (`RAG_EMBEDDING_ENGINE = ''`) that **downloads the
   model from Hugging Face on the first run** and imports torch on every run. Failure is caught and
   logged, not fatal;
2. runs the `pip install` of A.1 for any Tool/Function frontmatter;
3. checks upstream for a newer release — `ENABLE_VERSION_UPDATE_CHECK` defaults to `true`
   (`env.py:1126`).

A project whose weights acquisition is an explicit, verified, checksummed command (D-078) does not
ship a UI that silently fetches a model nobody asked for. Three ways out, and they are not equivalent:
`OFFLINE_MODE=true` (sets `HF_HUB_OFFLINE=1` and disables the version check, `env.py:1127-1131`) kills
retrieval and the download together; a non-empty `RAG_EMBEDDING_ENGINE` makes `get_ef` return `None`
immediately and leaves the rest of the app intact; doing nothing means the download. `W4`.

*(read)* One more, at request time rather than startup: `task.title.enable`, `task.tags.enable` and
`task.follow_up.enable` all default to `True` (`config.py:2261-2265`). Every chat turn therefore
issues three extra completions **against the same single llama-server**, serialized behind the same
slot, on a model whose context was fitted into VRAM by a calibration that measured one stream. Only
autocomplete defaults off. `TASK_MODEL` (`config.py:2156`) can redirect them, but in this
distribution there is nowhere to redirect them to. `W5`.

## A.4 The licence

*(read)* `LICENSE` at `v0.11.0` is BSD-3-Clause plus a fourth clause: licensees are "strictly
prohibited from altering, removing, obscuring, or replacing any 'Open WebUI' branding … in any
deployment or distribution", with carve-outs for deployments of **≤ 50 end users in any rolling 30
days**, written permission, or an enterprise licence.

*(read)* The code enforces the spirit of it directly: `WEBUI_NAME` set to anything other than
`Open WebUI` is rewritten to `f'{WEBUI_NAME} (Open WebUI)'` (`env.py:891-893`).

For this project the practical reading is short. A managed, loopback-only, single-operator install is
one end user, comfortably inside the carve-out, so setting a name is permitted — and it will render
as `bora (Open WebUI)` whatever is chosen. What must not happen is the distribution presenting the
interface as its own: the packaged notice set (`src/bora_workbench/resources/notices/`, which already
carries `llama.cpp-LICENSE` and the CUDA EULA) gains the Open WebUI licence in the same step, and the
user-facing text says which upstream program it is starting. `W7`.

---

# Part B — The user (the first question, answered)

The question as posed — *do I create the user, or is it automatic, and if it is automatic does an
onboarding still make sense?* — contains an assumption worth removing first: **automatic creation and
onboarding are not two designs to choose between.** Upstream has an onboarding, it is a browser
screen, and the two mechanisms that create a user automatically are the two ways of *not reaching*
it. The real choice is narrower and sharper: **does the local UI have a password at all?**

## B.1 The three routes upstream provides

All three are *(read)*.

### Route A — `WEBUI_AUTH=false`: no screen, no password, no work

`env.py:705`. With it set, the frontend calls `POST /api/v1/auths/signin` on load and
`routers/auths.py:774-797` takes over:

```
elif WEBUI_AUTH == False:
    admin_email = 'admin@localhost'
    admin_password = 'admin'
    if <that user exists>:      sign it in
    else:
        if Users.has_users():   raise HTTPException(400, EXISTING_USERS)
        signup_handler(..., admin_email, admin_password, 'User', source='system')
```

and `signup_handler` (`auths.py:860-865`) promotes the only user in the table to `admin` and sets
`ui.enable_signup = False`. So:

- the account is created by Open WebUI, with a **fixed and publicly documented password**, on the
  first page load. Nobody types anything;
- `ENABLE_SIGNUP` is forced off anyway (`config.py:1623`: `False if not WEBUI_AUTH else …`);
- it is a **one-way door**: if any user already exists, signin returns 400 and the instance is
  unusable in this mode. A data directory that ever ran with authentication cannot be switched to it.
  The reverse — turning authentication back on later — technically works, and leaves an admin account
  whose password is `admin`, which is worse than it sounds and has to be said out loud.

### Route B — `WEBUI_ADMIN_EMAIL` + `WEBUI_ADMIN_PASSWORD`: a real account, created headlessly

`env.py:752-754`, used at `main.py:349-356`. When both are set and no user exists, startup creates the
admin (`WEBUI_ADMIN_NAME`, default `Admin`) and then sets `ui.enable_signup = False`. Authentication
stays on: real login form, real session, a password that is not `admin`.

The cost is exact: **bora would have to hold that password.** Generate it, store it under a managed
root, and show it to the operator once — or ask the operator for one, which is the onboarding step
this design was trying to avoid. It is a secret with a lifecycle (rotation, uninstall, the `--print`
path that must never show it), and this project has kept none so far.

### Route C — upstream's own onboarding: the browser screen

`main.py:2094-2096` computes `onboarding = not Users.has_users()` and `main.py:2150` puts
`{'onboarding': True}` into `GET /api/config` while that holds; the frontend shows the create-admin
screen; `POST /api/v1/auths/signup` creates the first user and `signup_handler` makes it admin.
`ENABLE_INITIAL_ADMIN_SIGNUP` (`env.py:707`) exists precisely so the first admin is not locked out by
`ENABLE_LOGIN_FORM=false`.

This costs bora nothing to support, because it is the default and it is upstream's screen. It costs
the *user* one form on first launch.

## B.2 The recommendation, and what it costs

**Route A.** Two reasons, one of which is decisive.

The decisive one is that **the threat model already exists next door and has no password.** The
managed `llama-server` listens on `127.0.0.1` with no authentication at all; D-081 hands the pi agent
a *placeholder* key because the server ignores keys entirely. Anyone who can reach loopback in this
desktop session can already use the model. Putting a login form in front of the chat interface, while
the inference endpoint beside it is open, is theatre — and theatre that costs a stored secret.

The second is that it is the only route where the first launch is one step. `bora studio` → browser
opens → chat. That single step is the entire argument for shipping a managed UI rather than telling
people to install one.

What it costs, stated where the user will hit it:

- the account is `admin@localhost` with password `admin`, and it is an **administrator**;
- the data directory is committed: it can never become a multi-user install, and re-enabling
  authentication later leaves that known password in place. The honest remedy for "I want real
  accounts" is a fresh data directory, not a migration, and the diagnostic should say so;
- if the port is ever exposed beyond loopback — which specification 5.12 forbids and which this
  project therefore never does — it is an unauthenticated admin console. The rule that prevents it is
  already normative; this feature makes it load-bearing in a new way, and that is worth one sentence
  in `docs/operations.md`.

If the maintainer prefers a password anyway, **Route C beats Route B**: it keeps the secret in the
user's head instead of in bora's state root, and it costs one screen the user sees once. Route B is
the worst of the three here — it has all of Route A's automation with a secret to manage and none of
Route C's honesty. `W2`.

# Part C — Preprovisioning (the second question, answered)

Short answer: **yes, almost everything can arrive already configured — but through three different
mechanisms with three different persistence rules, and the part you care about most is the one that
needs an authenticated API call.**

## C.1 Three planes

| | Plane | What lives there | Set by | Editable in the UI? |
|---|---|---|---|---|
| 1 | **Process environment**, read at import | host, port, `WEBUI_AUTH`, `WEBUI_SECRET_KEY`, `DATA_DIR`, `OFFLINE_MODE`, `WEBUI_ADMIN_*`, `SAFE_MODE`, `ENABLE_PERSISTENT_CONFIG` itself | environment only | no |
| 2 | **Registered config keys** — roughly 300 dotted keys in `DEFAULT_CONFIG` (`config.py:2788-3184`) | connections, `ui.*`, `task.*`, `rag.*`, `user.permissions`, banners, prompt suggestions | environment, `${DATA_DIR}/config.json`, `POST /api/v1/configs/import` | yes — and whether the edit survives is C.2 |
| 3 | **Database rows** | **workspace models (display name, system prompt, parameters), skills, prompts, tools, functions, knowledge, users** | **API or UI only** | yes; this is user content |

## C.2 Plane 2 has two opposite modes, and the surprising one is easy to pick by accident

*(read)* `ENABLE_PERSISTENT_CONFIG` (`config.py:3186`, default `True`) is passed to
`Config.configure(...)`, and every read goes through `Config.persistent_enabled_for(key)`
(`backend/open_webui/models/config.py`):

- **`false`** — `persistent_enabled_for` returns `False` for every key, so `Config.get` returns the
  environment-derived default and the database is bypassed entirely. Each restart re-imposes the
  environment. A UI edit calls `Config.upsert`, which for a non-persistent key writes into the
  **in-memory** `Config.DEFAULTS` and is gone at restart.
- **`true`** — `seed_defaults` inserts only the keys that are **absent** from the database. The
  environment is therefore a **first-boot seed**, and from the second boot onward the user owns the
  setting.

Backlog B currently specifies "persistent config disabled … The user is told that UI changes do not
persist." The warning is accurate and the choice is defensible — but note what it actually produces:
the interface **accepts the change, shows it applied, and forgets it at restart.** That is worse than
a read-only field, because it lies for the length of a session. Recommendation: **`true`**, seeding on
first boot, which gives the same "already prepared" result on the launch that matters and does not
silently discard the user's work afterwards. The launcher's own settings — bind address, port, the
connection to llama-server — are protected by being plane 1, not by this switch. `W3`.

## C.3 Plane 3: model name, system prompt and skills are API-only

There is no environment variable for a default system prompt. Searching the whole of `config.py` for
`system_prompt` finds exactly two, and neither is one: `USER_PERMISSIONS_CHAT_SYSTEM_PROMPT` (a
permission flag) and `SUBAGENTS_SYSTEM_PROMPT` (a different feature). What upstream offers instead is
the **workspace model** — the same object the UI's *Workspace → Models* screen creates.

*(read)* `POST /api/v1/models/create` (`routers/models.py:249`), body `ModelForm`
(`models/models.py:172-181`):

```json
{
  "id": "bora-coding",
  "base_model_id": "Qwen 3.6",
  "name": "bora · coding",
  "params": { "system": "…the system prompt…", "temperature": 0.6, "top_p": 0.95 },
  "meta": { "description": "…", "skillIds": ["epsilon-delta", "debug-systematic"] },
  "is_active": true
}
```

- `name` is the display name in the model picker; `id` is the API identifier and **overrides the
  upstream model when it matches** (`models/models.py:119`);
- `base_model_id` is the real upstream model — here `Qwen 3.6`, which is exactly what
  `model_alias_contract` in `engine.lock` makes `/v1/models` report (D-080). The alias decision
  already did half of this work;
- `params` is `extra='allow'` (`models/models.py:61-64`); the system prompt is `params.system` and is
  applied through `utils/payload.py::apply_system_prompt_to_body` (`:45-59`);
- `meta.skillIds` is what attaches skills — see C.4.

**Skills**: *(read)* `POST /api/v1/skills/create` (`routers/skills.py:160`), body `SkillForm`
(`models/skills.py`): `{id, name, description, content, meta:{tags}}`, `content` being markdown.
`GET /api/v1/skills/export` gives the round trip.

**Prompts** (the `/slash` snippets): `POST /api/v1/prompts/create`.

**Authentication for all of it**: with Route A, `POST /api/v1/auths/signin` with any body satisfying
`SigninForm` (`models/auths.py`: `email: str, password: str`) returns a session token; send it as
`Authorization: Bearer …`. Note that `ENABLE_API_KEYS` now defaults to **`False`**
(`config.py:2420`), so API keys are not the route — the session token is.

## C.4 The four channels, ranked

| Channel | Reaches | Idempotent | Verdict |
|---|---|---|---|
| Environment variables | planes 1 and 2 | yes | **use.** The only way to reach plane 1, and the natural seed for plane 2. |
| `${DATA_DIR}/config.json` | plane 2 | no — see below | **do not use.** |
| `POST /api/v1/configs/import` | plane 2 | yes | use if plane 2 needs anything the environment cannot express. |
| `POST /api/v1/{models,skills,prompts}/create` | plane 3 | with a read-compare-write | **use. There is no alternative.** |

The `config.json` channel deserves its rejection in writing, because it looks like the tidiest answer
and is not. *(read)* `import_legacy_config_json` (`config.py:80-88`, called at `main.py:338`) reads
`${DATA_DIR}/config.json`, calls `Config.upsert(...)` with the whole document, and **renames the file
to `old_config.json`**. So: it is `upsert`, not seed, so it overwrites settings the user already
changed; it consumes itself, so "write the file and restart" is a one-shot with a side effect on
disk; it runs *before* `seed_registered_defaults`; and upstream's own name for it is **legacy**.
Building the provisioning path on a deprecated import is how a feature acquires a migration it did
not need.

## C.6 Open WebUI has skills now — and that is Backlog A's problem, not this one's

*(read)* `utils/middleware.py:2607-2684`. A request gathers skill ids from three places: the model's
`meta.skillIds`, an explicit `skill_ids` field, and `<$skillId|label>` mentions the user typed. Then:

- a skill the **user mentioned** is injected **whole**, as `<skill name="…">…</skill>`;
- a skill merely **attached** contributes only `<id>`, `<name>`, `<description>` to an
  `<available_skills>` manifest, and the model retrieves the body itself through a `view_skill` tool.

That is progressive disclosure, upstream, already shipped, working on any model with tool calling.

Backlog A proposes something different in kind: a **deterministic router** — normalized phrases,
weights, a threshold, co-activation, no regular expressions (D-011) — that decides which skill applies
*without asking the model*. The two are not in conflict, but the honest sequencing is:

- **skills as content** (the markdown bodies, the four initial skills) are worth writing once and are
  reusable by either mechanism;
- **the deterministic router has nowhere to run in this architecture.** bora launches
  `llama-server` and Open WebUI; it is not in the request path, and putting it there means becoming a
  proxy between them — a new process, a new failure mode, and a contract with two upstreams instead of
  one. That was what the Function was for, and C.5 rules the Function out;
- so the realistic answer is: ship the skills as **Open WebUI skills attached to the workspace model**,
  and let the maintainer decide separately, with that shipped and measured, whether a deterministic
  router earns a proxy. `W8`. D-004 (`pyyaml` enters only with the skills backlog) is untouched
  either way — the frontmatter parsing it was for still happens on bora's side, at packaging time.

---

# Part D — The design

## D.1 The environment

One table, because this is the part that got copied into code and every row needs a reason. It is
`_managed_settings` in `webui.py`; if the two ever disagree, the code is what runs.

| | Value | Why |
|---|---|---|
| `--host` (argument) | `127.0.0.1` | specification 5.12, D-015. Never read from configuration, so no value can widen it |
| `--port` (argument) | `webui_port`, default `8081` | upstream's `8080` is `llama_port`. Validated 1–65535 and `!= llama_port` |
| `DATA_DIR` | `data_dir()/open-webui/data` | database, uploads and vector store inside a managed root, so `uninstall` (5.10) actually reaches them |
| `WEBUI_SECRET_KEY` | generated once, held in the state root | A.2. Stable across restarts or every restart logs the browser out |
| `WEBUI_AUTH` | `false` | `W2` = A / Part B. Upstream creates its own local administrator |
| `WEBUI_NAME` | **unset** | `W7`. The interface stays `Open WebUI` everywhere, so the branding clause is never engaged and no exemption is invoked. bora names the program in its own output instead |
| `ENABLE_PERSISTENT_CONFIG` | `true` | first-boot seed, then the user owns their settings. `W3` / C.2 |
| `ENABLE_OLLAMA_API` | `false` | default is `true` and points at `localhost:11434` (`config.py:227-241`); nothing serves Ollama here |
| `ENABLE_OPENAI_API` | `true` | the managed llama-server is the one connection |
| `OPENAI_API_BASE_URL` | `http://127.0.0.1:<llama_port>/v1` | semicolon-separated list upstream (`config.py:331-337`); this deployment has exactly one |
| `OPENAI_API_KEY` | placeholder | llama-server ignores it, the field is required. Same posture as D-081 |
| `RAG_EMBEDDING_ENGINE` | **non-empty**, and `RAG_EMBEDDING_MODEL` empty | `W4`. `get_ef` builds a SentenceTransformer only when the engine is empty **and** a model is named (`routers/retrieval.py:142-148`), so either alone is enough; both are set, because one guard surviving an upstream refactor is not a plan. Nothing downloads and the rest of the app is intact |
| `OFFLINE_MODE` | **not used** | `W4` chose the narrower switch. It would also kill the frontmatter `pip install`, but `W6` disables that explicitly rather than as a side effect |
| `ENABLE_VERSION_UPDATE_CHECK` | `false` | a local distribution does not phone home |
| `ENABLE_PIP_INSTALL_FRONTMATTER_REQUIREMENTS` | `false` | A.1: otherwise an imported Function mutates the managed venv. `W6` |
| `SAFE_MODE` | **`true`** | `W6`. Deactivates every stored function, so no third-party Python runs inside the process bora starts |
| `ENABLE_TITLE_GENERATION`, `ENABLE_TAGS_GENERATION`, `ENABLE_FOLLOW_UP_GENERATION` | **`false`** | `W5`. Three extra completions per turn on the one calibrated slot (A.3) |
| `WEBUI_URL` | `http://127.0.0.1:<webui_port>` | `config.py:1620`; keeps generated links pointing at the loopback service |

The full set is written once, in one place, and `bora doctor` shows it, because an environment
assembled in three functions is an environment nobody can audit.

## D.4 The second managed service

This was the largest under-stated piece of the original Backlog B, which mentioned "multi-service
state" once, in a test list. It turned out to be the load-bearing part: "the browser opens only when
both are ready" cannot be expressed without it.

Specification 5.9 said "a single managed service", and the process layer enforced it by counting:

```python
if snapshot.services:
    raise ProcessError("a managed service is already running; run bora stop")
```

The state file already stored a **list**, so the format survived; the policy did not. What shipped:

- a service **role** on the state entry, so the guard is "no service of this role" and `status` names
  what is running rather than counting it. A record written before the role existed decodes unchanged
  and reads as the engine role, and only that role carries a model, release, context window and
  backend — the interface serves no model and claims none;
- `stop` taking both down in a defined order, the interface first, so it never shows a live chat
  against a server that is going away;
- the startup lock covering each spawn, so two starts cannot race;
- a readiness contract per role, each with its own endpoint and its own timeout. The 15-minute total
  of 5.9 was sized for llama-server; Open WebUI's first start creates its database and applies every
  migration, so it declares its own allowance rather than borrowing that one;
- `Ctrl-C` still cleaning up both and exiting 130.

## D.7 Failure, fallback, removal

This is what shipped: if llama-server is READY but the interface fails, keep the model serving,
show the reason and its log, and open the built-in llama.cpp interface. The mode does not exit,
because the built-in interface is always there — which is also why the "no UI available, stop and
exit 1" branch the proposal carried has no way to happen and was not built.

**Removal**: the environment and the interface's data directory are inside `data_dir()`, so
`uninstall` reaches them under 5.10 along with every other managed root. The database holds *user
content* — chats, notes, uploads — and the weights question of D-079 established that this is the
kind of thing that deserves its own separately-asked confirmation; it currently does not get one, and
that is a known gap rather than a decision. **The secret key** lives in the state root and goes
with it.

---

# Part H — What this must not become

- **A plugin framework.** No Function, no Pipe, no Filter, no Python executed inside Open WebUI
  (specification 1.1). Both switches that make this true are set, and a user who imports a function
  is told in the documentation that it will not run.
- **A second model manager.** The one model `engine.lock` pins is the one the picker shows, under
  the alias the engine already reports. Nothing here adds a catalog.
- **A configuration proxy.** bora does not grow settings that mean "an Open WebUI setting". Plane 1
  is what bora sets; plane 2 is seeded once and then belongs to the user (C.2).
- **A fork.** The branding stays (A.4), and the user is told which program is opening.
- **A reason to relax a rule.** Loopback-only, no `shell=True`, checksums on, atomic writes, confined
  deletions: this feature adds a tenant to those rules, not an exception to them.

---

# Appendix A — The ten questions, answered by D-094 on 30 July 2026

The recommendation each question carried is kept, because the difference between it and the answer is
the part worth remembering. Three answers differ from the recommendation: `W1`, `W7`, and `W10`.

| | Question | Recommendation | **Answer (D-094)** |
|---|---|---|---|
| **W1** | Is a managed Open WebUI wanted at all, given its disk cost and D.4's multi-service work? | **Deferred.** It is legitimate to answer "no" after seeing the number. | **Yes**, for `studio` and `vstudio` both. Answered on value before cost: the upstream interface is materially better kept than the integrated one, and that is not a detail. The cost was then handled by making the install an explicit command, not by measuring it (D-095). |
| **W2** | Which user route: A (`WEBUI_AUTH=false`), B (`WEBUI_ADMIN_*`), or C (upstream onboarding)? | **A** — Part B.2. If a password is wanted, **C**, not B. | **A**, with B.2's costs stated in `docs/operations.md`. |
| **W3** | `ENABLE_PERSISTENT_CONFIG` `true` or `false`? | **`true`** — C.2. Seed on first boot; do not accept edits and forget them. | **`true`**. |
| **W4** | Embedding model: `OFFLINE_MODE=true`, a non-empty `RAG_EMBEDDING_ENGINE`, or accept the download? | **Non-empty engine**, so nothing downloads and the rest of the app is intact. | **Non-empty engine.** Web search stays off and is the user's to enable, which is what keeps this answer available. |
| **W5** | Title, tags and follow-up generation on or off? | **Off** until someone measures them. | **Off**, and unmeasured: three extra completions per turn on one slot is a cost nobody asked for, so the burden of proof sat with turning them on. |
| **W6** | `ENABLE_PIP_INSTALL_FRONTMATTER_REQUIREMENTS=false` alone, or `SAFE_MODE` as well? | **Both.** A.1: the installation is immutable or it is not. | **Both.** It costs nothing the user was promised: skills, prompts and system prompts are not functions. |
| **W7** | `WEBUI_NAME`: unset, or `bora` (rendering `bora (Open WebUI)`)? | **`bora`**, with the upstream licence in `resources/notices/` in the same step. | **Unset.** No clause is engaged and no exemption is invoked; bora orchestrates and Open WebUI keeps its name wherever it appears. The notice ships anyway, and bora's own output names the program it opens. |
| **W8** | Does the deterministic router of Backlog A survive, now that upstream ships skills? | **Defer.** | **Deferred**, and no longer a dependency of this entry. |
| **W9** | Is the multi-service work (D.4) part of this feature or its own release? | **Its own step at minimum.** | **Its own step, first.** Forced rather than argued: "the browser opens only when both are ready" cannot be expressed without the service role, per-role readiness, and an ordered stop. It shipped in the same release, but it was built first. |
| **W10** | Does `sync` keep its name and its `data_dir()/sync-out/` output, or become a provisioning command? | **Provisioning command.** | **Neither: it does not exist.** The display name was the only thing worth provisioning, and D-080 already reports `Qwen 3.6` at `/v1/models`, so the picker names the model with no write at all. bora holds no credential into Open WebUI and never calls its API. |

---

# Appendix C — Considered and rejected

- **`${DATA_DIR}/config.json` as the provisioning channel.** Rejected: upstream calls it legacy, it
  overwrites rather than seeds, and it deletes itself by renaming (C.4).
- **An Open WebUI Function carrying the router.** Rejected: Python executed inside another process,
  with an unpinned `pip install` attached, is the plugin surface specification 1.1 excludes.
- **A proxy between Open WebUI and llama-server so bora can inject skills deterministically.**
  Rejected for now: a third process in the request path, a second upstream contract, and a new failure
  mode, to replace something upstream already ships (C.6).
- **Reusing `WEBUI_ADMIN_PASSWORD` with a generated password.** Rejected: it gives bora a secret to
  keep and the user nothing Route A does not already give them (B.2).
- **Shipping Open WebUI inside the wheel.** Rejected: 145.5 MB before resolution, a foreign licence in
  the distribution, and an upgrade path coupled to bora's own releases.
- **Making Open WebUI the `studio` UI outright, replacing the built-in llama.cpp interface.**
  Rejected at this stage: the built-in interface is the fallback D.7 depends on, and a fallback that
  was deleted is not a fallback.
- **Letting `webui_port` default to `8080` to match upstream.** Rejected: it is `llama_port`
  (A.2).
- **A `bora webui` command group before the service role existed.** Rejected: a second service the
  state model cannot describe is a second service `status` and `stop` will lie about. The role landed
  first, and the command group after it.
- **Installing Open WebUI automatically on the first `bora studio`.** Rejected: a closure that pins
  torch costs gigabytes, and a launcher that spends them without being asked has made a decision that
  was not its to make. `bora webui install` is one command, and until it is run the integrated
  interface still works.
- **A digest-pinned `resources/open-webui.lock`.** Rejected by D-095: pinning the resolved closure of
  119 packages with hashes is the right answer for the engine, whose binary this project builds and
  ships, and disproportionate for a Python package installed from PyPI into a private environment on
  one desktop. The version is pinned; the closure is not. This is knowingly weaker.

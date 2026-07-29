# bora — managed Open WebUI: what upstream actually gives you, and the plan that follows

> **Status: decision input, explicitly deferred.** `IMPLEMENTATION_SPEC.md` remains the only
> normative plan. Backlog B in its section 8 is the entry this file expands; it is postponed by
> D-068 and carries no `D-0xx` of its own. **Step B1 is what would authorize everything else**:
> until the specification records the answers of Appendix A, nothing below is approved, scheduled,
> or implemented. Following the precedent of D-077, this file deliberately assigns itself no
> decision number.
>
> On 29 July 2026 the maintainer selected the TUI plan as the only active new milestone and deferred
> Open WebUI until a later request. This machine may be used for the future real spike, but that
> availability is neither an instruction to run it now nor evidence that a check passed. The TUI
> does not add Open WebUI placeholders, service roles, status rows, or actions in anticipation.
>
> Two label sets, deliberately distinct: **`W1`–`W10` are the open questions** of Appendix A, and
> **`B1`–`B9` are the steps** of Part F.
>
> Written against `bora-workbench 0.3.2` after TUI-plan commit `50a0bb1`, and against **Open WebUI
> `0.11.0`** — the newest release on PyPI on 29 July 2026, read at git tag `v0.11.0`. Every upstream
> `file:line` below was read at that tag. **Match by content, not by number**: a citation whose quoted
> code still matches is still correct wherever it moved; one that no longer matches means this plan
> is stale, not the code.
>
> Nothing here is a measurement. Section E lists what only a real spike can produce, and no step may
> assume a value for any of it.

---

## 0. The verdict in six lines

1. **The user is created automatically. You never create it, and you must not build an onboarding for
   it** — Open WebUI already has one, in the browser, and it has two ways to skip it entirely.
   Part B.
2. **"Already prepared" is possible, but it is three different mechanisms, not one.** Environment,
   config keys, and database rows. The interesting half — model name, system prompt, skills — is
   database rows, reachable only through the authenticated API. Part C.
3. **That reverses one sentence of Backlog B.** "No API writes in this step" would delete the feature
   it is trying to ship. C.5.
4. **Open WebUI 0.11.0 has a native skills feature**, with the same progressive-disclosure shape
   Backlog A was going to build. C.6.
5. **The cost is a second multi-gigabyte install**, because `sentence-transformers`, `transformers`
   and `accelerate` are hard runtime dependencies and pull torch. A.1. This is the fact the maintainer
   should decide on before any of the rest.
6. **The current Backlog B is not detailed enough to execute**, but it is not wrong in shape. It is
   short in five specific places, listed in Appendix B, and every one of them is a decision rather
   than an omission.

---

## 1. What this document is standing on

No `resources/open-webui.lock` exists, so source-hierarchy rule 6 applies (specification 2:
"current official documentation for tools not pinned yet"). Reading the tagged source is stronger
than reading the documentation site and is what this file did.

| Marked | Meaning |
|---|---|
| *(read)* | read at `open-webui` tag `v0.11.0` or from the PyPI metadata of `0.11.0`. A fact about the code, not about this machine. |
| *(spike)* | a number or behavior only a real run produces. **Not knowable from source.** Listed in Part E. |
| *(decision)* | neither: something the maintainer chooses. Collected as `W2`–`W10` in Appendix A. |

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

Two consequences the current Backlog B does not carry:

- **A lock that pins `open-webui==0.11.0` verifies nothing.** The 119 pins are upstream's, in
  upstream's metadata; the artifacts that land on disk are the resolved closure, hundreds of wheels
  deep. `resources/open-webui.lock` has to pin **that closure, with digests**, or it is a version
  string pretending to be a lock. `uv export`/`uv pip compile --generate-hashes` produces it; that
  is a spike deliverable (E4), not an assumption.
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

## B.3 What bora's TUI does instead

The authorized TUI scope has no automatic onboarding flow. Its read-only `Setup` screen is defined by
`TUI_PLAN.md` E3 and reflects only behavior shipped in the current launcher. It therefore gains no
Open WebUI row, account action, or second-service placeholder now.

If this backlog is authorized later, the WebUI implementation step also extends the shared snapshot
and `Setup` screen from the then-current TUI. Under Route A they say only that the browser UI opens
without a bora-managed account step. Under Route C they may state:

```
  Create your account in the browser on first open.
  Open WebUI asks once; bora does not create the account.
```

The TUI still never creates, stores, or resets an Open WebUI account. That rule belongs to the future
WebUI decision and is not anticipated in the `0.4.0` front end.

---

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

## C.2 Plane 2 has two opposite modes, and Backlog B currently picks the surprising one

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

## C.5 What this changes in Backlog B

Backlog B currently says:

> `sync` generates the function, prompts, and import instructions under `data_dir()/sync-out/`. A
> static Python template; rules and content serialized as JSON data, never interpolated as code. No
> API writes in this step.

Two parts of that should not survive contact with 0.11.0.

**"the function".** An Open WebUI *Function* is a Pipe/Filter/Action: **Python source stored in the
database and executed inside the Open WebUI process**, with the `requirements:` frontmatter that
triggers the `pip install` of A.1. That is precisely the plugin surface specification 1.1 says this
project is not ("not a plugin framework"), and specification 5.12 forbids the shape it takes. Whatever
bora ships into Open WebUI should be **data — a workspace model, skills, prompts — not code.** The
one thing a Function would have bought (a deterministic router running inside the chat pipeline) is
discussed in C.6 and has a better answer now.

**"No API writes in this step."** Its intent was good: do not touch a foreign database, hand the user
a file and let them decide. But under Route A the launcher already holds an admin session the moment
the service is up, the write targets a database inside a managed root that bora created, and the
alternative it buys is a manual import chore per item. "No API writes" here does not protect
anything — it removes the feature. What should be kept from the intent, and made explicit instead:

- the write happens **only after the service reports ready**, never against a foreign instance;
- it is **idempotent**: read the current list, compare, create or update, report what changed and
  what was left alone;
- it **never deletes** content the user made, and never overwrites a row whose content differs from
  what bora last wrote unless the user asks (the same "preserve pre-existing user changes" rule
  `AGENTS.md:14-15` already imposes everywhere else);
- `--dry-run` prints the exact payloads and writes nothing, reusing the spelling `bora rm` already
  established rather than inventing a second one;
- the content itself stays **packaged declarative resources** under
  `src/bora_workbench/resources/content/webui/`, validated against a new `webui-content/v1` schema
  (specification 5.3), so it obeys the core-versus-content split that `AGENTS.md:212` requires of
  every pull request.

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

One table, because this is the part that gets copied into code and every row needs a reason. Values
marked `Wn` are the open decisions of Appendix A; the rest follow from Part A.

| | Value | Why |
|---|---|---|
| `--host` (argument) | `127.0.0.1` | specification 5.12, D-015. Never read from configuration, so no value can widen it |
| `--port` (argument) | `webui_port`, default `8081` | upstream's `8080` is `llama_port`. Validated 1–65535 and `!= llama_port` |
| `DATA_DIR` | `data_dir()/open-webui/data` | database, uploads and vector store inside a managed root, so `uninstall` (5.10) actually reaches them |
| `WEBUI_SECRET_KEY` | generated once, held in the state root | A.2. Stable across restarts or every restart logs the browser out |
| `WEBUI_AUTH` | `false` | `W2` / Part B |
| `WEBUI_NAME` | `bora` | renders `bora (Open WebUI)`; the branding stays. `W7` |
| `ENABLE_PERSISTENT_CONFIG` | `true` | first-boot seed, then the user owns their settings. `W3` / C.2 |
| `ENABLE_OLLAMA_API` | `false` | default is `true` and points at `localhost:11434` (`config.py:227-241`); nothing serves Ollama here |
| `ENABLE_OPENAI_API` | `true` | the managed llama-server is the one connection |
| `OPENAI_API_BASE_URL` | `http://127.0.0.1:<llama_port>/v1` | semicolon-separated list upstream (`config.py:331-337`); this deployment has exactly one |
| `OPENAI_API_KEY` | placeholder | llama-server ignores it, the field is required. Same posture as D-081 |
| `RAG_EMBEDDING_ENGINE` | `W4` | empty means a SentenceTransformer at every start and a download on the first (A.3) |
| `OFFLINE_MODE` | `W4` | sets `HF_HUB_OFFLINE=1`, disables the version check, skips the frontmatter `pip install` |
| `ENABLE_VERSION_UPDATE_CHECK` | `false` | a local distribution does not phone home, independently of `W4` |
| `ENABLE_PIP_INSTALL_FRONTMATTER_REQUIREMENTS` | `false` | A.1: otherwise an imported Function mutates the managed venv. `W6` |
| `SAFE_MODE` | `W6` | additionally deactivates all functions at startup |
| `ENABLE_TITLE_GENERATION`, `ENABLE_TAGS_GENERATION`, `ENABLE_FOLLOW_UP_GENERATION` | `W5` | three extra completions per turn on the one server (A.3) |
| `WEBUI_URL` | `http://127.0.0.1:<webui_port>` | `config.py:1620`; keeps generated links pointing at the loopback service |

The full set is written once, in one place, and `bora doctor` shows it, because an environment
assembled in three functions is an environment nobody can audit.

## D.2 The lock

`resources/open-webui.lock`, schema `open-webui-lock/v1`, `additionalProperties: false`, produced by
the spike and never by hand:

- the release (`0.11.0`) and the source tag it was read at;
- the **resolved dependency closure with digests** (A.1), per platform where they differ;
- the interpreter window it was verified against;
- the command contract: the executable, `serve`, and the two arguments of A.2 — same discipline as
  `engine.lock`'s `command_contract`, so no flag is ever invented at a call site (5.7);
- the health contract. *(read)* `GET /health` returns `{"status": true}` **unconditionally, before
  startup finishes** (`main.py:2768`); `GET /ready` returns 200 only once `app.state.startup_complete`
  is set and the database ping succeeds, and 503 otherwise (`main.py:2772-2811`). Specification 5.9
  says "READY = the exact status and JSON from the lock" — so the lock names **`/ready`**. A launcher
  that polls `/health` reports ready while the first-boot migration is still running;
- the licence identity, so the packaged notice cannot drift from what was verified (A.4).

`latest` is forbidden (specification 2), and a lock that pins only the top-level version is not a
lock (A.1).

## D.3 Installation and activation

Unchanged in shape from Backlog B, which is the part of it that is right:

- immutable versioned environments under `data_dir()/open-webui/installations/`;
- staging on the same filesystem, published by atomic rename;
- post-install verification: the version, the imports, the executable;
- `installed.json` inside the installation; an atomic `current.json` whose relative path is confined;
- a failure leaves the previous manifest and installation intact;
- cleanup removes only inactive **managed** environments.

Two additions the current text lacks. **The creation tool**: `uv` is already the installation path
this project uses and defers to (D-056, D-073, `_tool_handoff.py`), so `uv venv` plus a hash-verified
`uv pip sync` against D.2's closure is the consistent choice — no second package manager, no
`pip install` reached over the network without digests. **The interpreter**: the managed environment
uses `3.12.13` (A.1); if the spike finds a resolution that does not hold there, that is a finding to
report, not a second interpreter to install quietly.

## D.4 The second managed service

This is the largest under-stated piece of Backlog B, which mentions "multi-service state" once, in
the test list.

Specification 5.9 says "a single managed service", and `process.py:262` enforces it:

```python
if snapshot.services:
    raise ProcessError("a managed service is already running; run bora stop")
```

The state file already stores a **list** (`_process_state.py:161`), so the format survives; the policy
does not. Running Open WebUI means:

- a service **role** in the state entry, so the guard becomes "no service of this role" and `status`
  can name what is running rather than counting;
- `stop` taking both down in a defined order — the UI first, so it never shows a live chat against a
  server that is going away;
- the startup lock covering the pair as one operation, not two racing ones;
- a health loop per role, with per-role timeouts. *(spike)* Open WebUI's first start migrates the
  database, runs the plugin installer and constructs an embedding model; the 15-minute total of 5.9
  was sized for llama-server and has to be re-argued, not reused;
- `Ctrl-C` still cleaning up both and exiting 130.

Every one of those touches code that D-071 has already had to repair once under real conditions. It is
its own step (`W9`), and arguably its own release. The current TUI must not anticipate the role field:
when B4 is eventually authorized, that same WebUI step extends read-only service inspection and the
Setup screen against the then-current snapshot contract.

## D.5 Provisioning

A separate, explicit, idempotent operation — not a side effect of launching:

1. wait for READY on `/ready` (D.2);
2. obtain a session token (C.3);
3. reconcile, per resource kind, read-compare-write, in this order: **skills → prompts → workspace
   models** (models reference skills by id, so skills exist first);
4. optionally reconcile the plane-2 keys that the environment cannot express, via
   `POST /api/v1/configs/import` (C.4);
5. print what was created, what was updated, and what was left alone because the user had changed it.

`--dry-run` prints the payloads and writes nothing. Nothing here deletes.

## D.6 The packaged content

`src/bora_workbench/resources/content/webui/`, schema `webui-content/v1`, `additionalProperties:
false`, identifiers `^[a-z0-9-]+$` (specification 5.3): the workspace model per mode (display name,
description, `params.system`, sampling that agrees with the `mode/v2` document it mirrors), the skill
bodies, the prompts. Declarative content, so it travels in its own pull request (`AGENTS.md:212`).

One consistency rule worth writing into the schema rather than into prose: the sampling in a workspace
model must not contradict the `mode/v2` content for the same mode, and `validate` checks it. Two
places to state a temperature is two places to get it wrong.

## D.7 Failure, fallback, removal

The current text is right and is kept: if llama-server is READY but the UI fails, keep the model
serving, show the log, and open the built-in llama.cpp interface where the mode allows it; if the mode
requires a UI and none is available, stop the services and exit 1.

Two additions. **Removal**: the installations root and the data directory are inside `data_dir()`, so
`uninstall` already reaches them under 5.10 — but the database holds *user content* (chats, notes,
uploads), which the weights question of D-079 has already established is the kind of thing that gets
its own separately-asked confirmation rather than being swept up in another one. **The secret key**
lives in the state root and goes with it.

---

# Part E — The spike, and what it must produce

Backlog B already requires this; it does not say what "done" means. It means these artifacts, and no
approval should be given before they exist.

| | The spike must measure | Why source cannot answer it |
|---|---|---|
| **E1** | installed size of the resolved environment, Ubuntu and Windows | A.1. The number that decides proportionality |
| **E2** | cold first start to `/ready` 200, and warm restart, with the plane-1 environment of D.1 | first start migrates, installs and loads an embedding model (A.3) |
| **E3** | resident memory of the Open WebUI process while a chat streams | it shares a machine with a model calibrated to fill it. Specification 5.5 reserves 2.0 GiB of RAM for the *engine*; this is a new tenant |
| **E4** | the resolved closure with digests, per platform | becomes `resources/open-webui.lock` (D.2) |
| **E5** | the real cost of `W5`: latency of a chat turn with title/tags/follow-up on versus off | three extra completions on one slot is a guess until it is a measurement |
| **E6** | that Route A behaves as read: no screen, `admin@localhost` created, admin role | Part B's whole recommendation rests on it |
| **E7** | that the provisioning calls of C.3 work against a real instance, including the second run | idempotency is a claim until the second run |
| **E8** | whether `Qwen 3.6` resolves as `base_model_id` given the D-080 alias | the alias is bora's; the resolution is upstream's |

Evidence goes under `evidence/` with its own manifest, separate from the calibration chain, and prose
in English (D-065). A spike that produces prose but no lock has not finished. The maintainer has made
the current machine available for this future spike; no command is run and no observation is recorded
until a separate request activates B1/B2.

---

# Part F — The steps

Before it is executed, a step declares six fields, and one missing a field is not ready: **goal** (one
outcome; if it needs an "and", it is two steps), **files** (every file it may touch, and no others),
**change** (precise enough to require no new design decision), **decision** (the `D-0xx` it records,
or `—`), **verify** (the check that would fail if it were wrong), **done when** (the observable
condition that ends it). Decision numbers are **indicative**: take the next free number in the
specification's table when the step actually lands.

| | Step | Depends on |
|---|---|---|
| **B1** | Record the answers of Appendix A in the specification, replace Backlog B with the corrected text of Appendix B, and name this file. **Nothing else may be committed first.** | — |
| **B2** | The spike (Part E). Produces the lock and the evidence. | B1 |
| **B3** | `open-webui-lock/v1` schema, the lock, the notice, and `validate` coverage. Declarative-only pull request. | B2 |
| **B4** | The service role in the state, and `status`/`stop`/lock/`Ctrl-C` over two services (D.4). Core-only, and **testable with a fake second service before Open WebUI exists** — which is why it comes before the installer. | B1 |
| **B5** | `webui.py`: installation, verification, `installed.json`, atomic `current.json`, cleanup (D.3). | B3, B4 |
| **B6** | The environment (D.1) and the launch path, including `webui_port` in configuration and the `!= llama_port` validation. | B5 |
| **B7** | `webui-content/v1` and the packaged content (D.6). Declarative-only pull request. | B3 |
| **B8** | Provisioning (D.5), idempotent, with `--dry-run`. | B6, B7 |
| **B9** | Documentation: `docs/operations.md` on the account and the loopback rule (B.2), `docs/commands.md`, `docs/configuration.md`, `docs/installation.md` on the disk cost. | B8 |

B4 before B5 is the one piece of ordering worth defending: the multi-service work is the risky part,
it is testable with a fake, and discovering it late means discovering it with a 145 MB dependency in
the way.

---

# Part G — Tests

Offline, deterministic, no real network, no real service (`AGENTS.md:176-180`). The current Backlog B
list is a good start and is kept: valid/partial/failed installation, manifest, port configuration,
environment, health, fallback, multi-service state, hostile content, reproducible output. What it is
missing, one line each:

- **the host argument is `127.0.0.1` in every constructed command**, including every failure path. The
  test that would have caught upstream's default;
- **the port refuses to equal `llama_port`**, at configuration-validation time, before any process
  starts;
- **`/ready`, not `/health`**: a fake that answers `/health` 200 while `/ready` 503 must not be
  reported as ready;
- **the secret key** is generated once, reused on the second launch, and appears in no log line, no
  `doctor` output and no `--dry-run` output;
- **provisioning is idempotent**: second run creates nothing;
- **provisioning preserves user edits**: a row whose content differs from what bora last wrote is
  reported and left alone;
- **packaged content validates**, and a workspace model contradicting its `mode/v2` sampling fails
  `validate`;
- **stop order**: UI down before engine, in both the clean and the failed-startup path.

---

# Part H — What this must not become

- **A plugin framework.** No Function, no Pipe, no Filter, no Python executed inside Open WebUI
  (C.5, specification 1.1).
- **A second model manager.** The workspace model wraps the one model `engine.lock` pins. Nothing
  here adds a catalog.
- **A configuration proxy.** bora does not grow settings that mean "an Open WebUI setting". Plane 1
  is what bora sets; plane 2 is seeded once and then belongs to the user (C.2).
- **A fork.** The branding stays (A.4), and the user is told which program is opening.
- **A reason to relax a rule.** Loopback-only, no `shell=True`, checksums on, atomic writes, confined
  deletions: this feature adds a tenant to those rules, not an exception to them.

---

# Appendix A — Open questions for the maintainer, to be recorded in B1

Following D-077's rule, these carry no `D-0xx` until they are answered. A recommendation is given for
each because a question with no recommendation is work handed back.

| | Question | Recommendation |
|---|---|---|
| **W1** | Is a managed Open WebUI wanted at all, given E1's disk cost and D.4's multi-service work? | **Deferred.** Run E1 only after a later explicit request. It is legitimate to answer "no" after seeing the number; neither B1 nor B4 starts during the TUI milestone. |
| **W2** | Which user route: A (`WEBUI_AUTH=false`), B (`WEBUI_ADMIN_*`), or C (upstream onboarding)? | **A** — Part B.2. If a password is wanted, **C**, not B. |
| **W3** | `ENABLE_PERSISTENT_CONFIG` `true` or `false`? | **`true`** — C.2. Seed on first boot; do not accept edits and forget them. |
| **W4** | Embedding model: `OFFLINE_MODE=true`, a non-empty `RAG_EMBEDDING_ENGINE`, or accept the download? | **Non-empty engine**, so nothing downloads and the rest of the app is intact; retrieval then requires an explicit later decision. Never "accept the download". |
| **W5** | Title, tags and follow-up generation on or off? | **Off** until E5 measures them. Three extra completions per turn on the one calibrated server, on by default, is a latency regression the user did not ask for. |
| **W6** | `ENABLE_PIP_INSTALL_FRONTMATTER_REQUIREMENTS=false` alone, or `SAFE_MODE` as well? | **Both.** A.1: the installation is immutable or it is not. |
| **W7** | `WEBUI_NAME`: unset, or `bora` (rendering `bora (Open WebUI)`)? | **`bora`**, with the upstream licence in `resources/notices/` in the same step. |
| **W8** | Does the deterministic router of Backlog A survive, now that upstream ships skills? | **Defer.** Ship the skill content through upstream's mechanism, measure it, and decide the router separately — it needs a proxy this project does not have (C.6). |
| **W9** | Is the multi-service work (D.4) part of this feature or its own release? | **Its own step at minimum** (B4), and defensibly its own release: it changes an invariant that D-071 already had to repair under real conditions. |
| **W10** | Does `sync` keep its name and its `data_dir()/sync-out/` output, or become a provisioning command? | **Provisioning command.** The file drop was a workaround for "no API writes", and C.5 retires that constraint. |

---

# Appendix B — Corrections to Backlog B, applied by B1

| Where | Now says | Should say |
|---|---|---|
| precondition | "approves a precise version after a real spike on Python, CPU-only dependencies, command, health, Functions, prompts, and environment variables" | the same, plus the eight deliverables of Part E, and **not** "Functions" — C.5 rules them out |
| environment | "authentication disabled for the local service only" | which of the three routes, and what it costs (Part B). The current phrasing hides that upstream creates `admin@localhost`/`admin` and that the choice is one-way |
| environment | "persistent config disabled … UI changes do not persist" | `W3`. And if `false` is kept, say that the UI *accepts and forgets*, which is not the same as read-only |
| environment | "a dedicated data dir, host `127.0.0.1`, … the local OpenAI endpoint, and a placeholder key" | the full table of D.1, including the port collision with `llama_port`, the secret key, the embedding model and the version check |
| health | (not stated) | READY is `GET /ready`, not `/health` (D.2). `/health` answers 200 before startup finishes |
| installation | "immutable venvs" | immutable **unless** the frontmatter `pip install` is disabled (A.1) |
| `sync` | "generates the function, prompts, and import instructions … No API writes in this step" | idempotent provisioning through the API, of **data not code**, after READY, with `--dry-run` and preservation of user edits (C.5) |
| multi-service | one word in the test list | its own step, with the 5.9 invariant and `process.py:262` named (D.4) |
| licence | (not stated) | clause 4 and the `WEBUI_NAME` rewrite (A.4), plus the packaged notice |
| specification `:857` | "Open WebUI environment: `https://docs.openwebui.com/reference/env-configuration/`" | keep the link — it resolves — and add that the tagged source outranks it while no lock exists (specification 2, rule 6) |
| D-022 (`:219`) | "versioned environments and an atomic activation manifest" | still correct; unchanged by this file |

---

# Appendix C — Considered and rejected

- **`${DATA_DIR}/config.json` as the provisioning channel.** Rejected: upstream calls it legacy, it
  overwrites rather than seeds, and it deletes itself by renaming (C.4).
- **An Open WebUI Function carrying the router.** Rejected: Python executed inside another process,
  with an unpinned `pip install` attached, is the plugin surface specification 1.1 excludes (C.5).
- **A proxy between Open WebUI and llama-server so bora can inject skills deterministically.**
  Rejected for now: a third process in the request path, a second upstream contract, and a new failure
  mode, to replace something upstream already ships (C.6). Reconsiderable with W8 evidence.
- **Reusing `WEBUI_ADMIN_PASSWORD` with a generated password.** Rejected: it gives bora a secret to
  keep and the user nothing Route A does not already give them (B.2).
- **Shipping Open WebUI inside the wheel.** Rejected: 145.5 MB before resolution, a foreign licence in
  the distribution, and an upgrade path coupled to bora's own releases.
- **Making Open WebUI the `studio` UI outright, replacing the built-in llama.cpp interface.**
  Rejected at this stage: the built-in interface is the fallback D.7 depends on, and a fallback that
  was deleted is not a fallback.
- **Letting `webui_port` default to `8080` to match upstream.** Rejected: it is `llama_port`
  (A.2).
- **A `bora webui` command group before W4 lands.** Rejected: a second service the state model cannot
  describe is a second service `status` and `stop` will lie about.

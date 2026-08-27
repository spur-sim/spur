# Spur: Path to an API-Ready Core Engine

## Context

Spur is meant to become the core engine behind a licensed, hosted mesoscopic railway simulation platform, with the API/service and GUI built in separate repos on top (a GUI that once lived here was already split out, commit `ad7c875`). A full assessment found a sound architecture — SimPy-based discrete-event engine, clean plugin-style component/jitter/collection resolution via `Model.from_project_dictionary` — but concrete correctness bugs and packaging gaps that break it for any external consumer today, starting with the fact that `pip install spur` currently fails on import because of undeclared dependencies. The engine stays MIT-licensed; the goal of this work is to make it a safe, correct, embeddable library that a future hosted API can depend on.

## Full Assessment Summary

**Structure:** `spur/core/` — engine (`base.py`: abstract `BaseItem`/`BaseComponent`/`Agent`/`BaseCollection`/`SpurResource`; `component.py`: concrete infrastructure `TimedTrack`, `PhysicsTrack`, `MultiBlockTrack`, yards/stations/crossovers; `train.py`: `Train` agent; `route.py`/`tour.py`: linked-list itinerary model; `collection.py`: `BlockExclusiveZone`; `jitter.py`: stochastic perturbation; `model.py`: `Model(simpy.Environment)` orchestrator; `exception.py`). `spur/io/` — thin JSON loaders only (`formats.py`, 30 lines, no validation). `tests/` — pytest, ~31 tests, mostly construction/validation not simulation-mechanics coverage. `examples/line4/` — working toy example; `examples/gosub.spur` — a `.spur` project-file format. `docs/` — mature Sphinx docs on Read the Docs, ahead of the code/CI maturity. No `.github/workflows/` exists — no CI at all. Packaging is legacy `setup.py` only. Execution model: pure DES via SimPy's cooperative event loop, single-threaded, no custom scheduler.

**Completion gaps:** `PhysicsTrack` is non-functional (`Train.basic_traversal()`/`get_basic_traversal_time()` immediately `raise NotImplementedError`, `train.py:150-227`, followed by dead physics code). `spur.io` is a stub (plain `json.load`, no schema validation, no formats beyond JSON). No state persistence/save-resume for a `Model` at all. Some components self-document as unfinished (`TimedStation`: "may not fully work, or may have been deprecated").

**Bugs found, ranked by relevance to API-readiness:**
1. Missing runtime deps (`networkx`, `scipy`, `numpy` imported but not in `install_requires`) — breaks `pip install`.
2. Import-time filesystem side effects + global logger reuse — `spur/core/__init__.py` creates log files/dirs on import; `Model`/`Agent.__init__` attach handlers (`mode="w"`) to shared global `"sim"`/`"agent"` loggers, so multiple `Model`/`Train` instances in one process duplicate and clobber logs. **The biggest blocker to a hosted API running concurrent simulations.**
3. PEP 479 violations: `raise StopIteration` inside generators in `route.py:37`, `tour.py:44,62` — crashes with `RuntimeError` instead of ending cleanly on empty routes/tours.
4. `BaseComponent.as_dict()` mutates live instance state by popping keys from `self.__dict__` directly instead of a copy (`base.py:154-183`) — currently unused/dead but a landmine for future serialization work.
5. Broken test: `tests/test_integration.py:25` calls a nonexistent `Model.add_routes_and_tours_from_json_files`.
6. `python_requires=">=3.6"` in `setup.py` but code uses PEP 585 builtin generics as runtime annotations (needs 3.9+).
7. Minor: mutable-default `jitter=NoJitter()` args (harmless today, footgun later); overly broad `except AttributeError` in `MultiBlockTrack._get_travel_direction`; unvalidated `importlib` class-name resolution from JSON (relevant once API-facing); duplicated `SimLogFilter` class in both `model.py` and `base.py`.

## Phase 1 — Make it installable and correct (foundation)

1. **Declare missing runtime dependencies** — `setup.py`
   - Add `networkx`, `scipy`, `numpy` to `install_requires` (`setup.py:26-28`).
   - Update `python_requires` from `>=3.6` to `>=3.9` (`setup.py:25`); verify by grepping for PEP 585 usage that nothing actually requires 3.10+.

2. **Fix PEP 479 `StopIteration` violations** — `spur/core/route.py`, `spur/core/tour.py`
   - `Route.traverse()` (`route.py:35-37`) and `Tour.traverse()` (`tour.py:42-44`, `tour.py:60-62`) `raise StopIteration` directly inside generator bodies — replace each with a bare `return` (keep the existing `logger.warn(...)` call before it). Verify no caller catches `StopIteration` directly from these (check `train.py:79` and tests).

3. **Fix `BaseComponent.as_dict()` mutating live instance state** — `spur/core/base.py:154-183`
   - Change `d = self.__dict__` to `d = dict(self.__dict__)` so the subsequent `pop()` calls only affect the local snapshot, not the live object.

4. **Fix the broken integration test** — `tests/test_integration.py`
   - Line 25 calls nonexistent `m.add_routes_and_tours_from_json_files(...)`. Fix by importing `read_routes_json`, `read_tours_json` from `spur.io.formats` (alongside the existing `read_components_json`, `read_trains_json` import) and replacing line 25 with:
     ```python
     m.add_routes_and_tours(
         read_routes_json(routes_json_file), read_tours_json(tours_json_file)
     )
     ```

5. **Stand up basic CI** — new `.github/workflows/ci.yml`
   - No CI exists today (`ci/python310_dev.yml` is only a conda dev-env spec). Added a minimal GitHub Actions workflow: on push/PR to `main`, install the package (`pip install -e .`) across Python 3.9/3.10/3.11 and run `pytest`. A `black --check .` step was deferred — the existing codebase is not currently black-formatted (8 files would need reformatting), and running the check now would make CI red on day one for reasons unrelated to this work; reformatting the repo and re-adding the check is a good small follow-up.

**Phase 1 verification:** `pip install -e .` in a clean virtualenv succeeds and `import spur.core` works without manually pre-installing deps; `pytest` passes in full including the fixed integration test; empty `Route`/`Tour` traversal ends cleanly instead of raising `RuntimeError`; the new CI workflow runs green on a pushed branch.

## Phase 2 — Make it embeddable (removes concurrency/process-model landmines)

### Root cause (confirmed by reading the code)

Three places attach `logging.Handler`s to loggers with **fixed, shared names**, and each new instance stacks another handler rather than replacing one:

- `spur/core/__init__.py:16-36` (import time): attaches `FileHandler("log/debug.log")`, `FileHandler("log/spur.log")`, `FileHandler("log/error.log")` (all `mode="w"`) to the module logger `"spur.core"`, and `os.mkdir("log")` on `FileNotFoundError` — runs merely from `import spur.core`, regardless of whether the caller wants file logging, and races if two processes import concurrently.
- `Model.__init__` (`spur/core/model.py:52-84`): attaches a `StreamHandler` and `FileHandler("log/sim.log", mode="w")` (plus `log/debug.log` if `debug=True`) to `logging.getLogger("sim")` — a **fixed global name**. Every `Model()` constructed in the process adds another set of handlers to that same logger object.
- `Agent.__init__` (`spur/core/base.py:324-332`): attaches `FileHandler("log/agent.log", mode="w")` to `logging.getLogger("agent")` — also fixed/global. Every `Train` constructed adds another handler.

Per-instance logger *names* already exist in places (`Train.__init__` sets `self.simLog`/`self.agentLog` to `sim.train.{uid}` / `agent.train.{uid}`; `component.py` sets `sim.track.{Class}.{uid}`) but this doesn't help: those are **child loggers** of `"sim"`/`"agent"`, and Python's logging propagates a record up through every handler on every ancestor logger. So constructing a second `Model` or a second `Train` doesn't isolate anything — it just adds more handlers that every subsequent record (from every instance) will also pass through, while `mode="w"` truncates whatever the previous instance had already written. Confirmed no other module-level mutable global state exists in `spur/` outside of this logging setup (checked via grep for module-level `{}`/`[]`/`dict()`/`list()` assignments — none found).

### Important constraint discovered before implementing: the IN/OUT agent log is a real analysis data channel

`Train.run()` (`train.py:99-108,142-144`) writes structured `IN,{component.uid},{component.__name__}` / `OUT,{component.uid},{component.__name__}` records via `self.agentLog.info(...)`. Today these land in `log/agent.log` automatically because `Agent.__init__` attaches a `FileHandler` the moment any `Train` is constructed. This file is used downstream for analysis, so removing automatic file output with no replacement would silently break existing workflows. Decision: keep this as an explicit, opt-in, per-`Model`-instance file path rather than either (a) an automatic global file, or (b) removing file output and inventing a new in-memory event API (that redesign is bigger than Phase 2 and can be revisited in Phase 3 if warranted).

### Fix

Apply the standard practice for embeddable libraries — library code must not attach handlers or write files *implicitly*; scope every logger to the owning instance so nothing is shared across instances, and make file output an explicit constructor argument rather than an automatic side effect.

1. **`spur/core/__init__.py`** — delete the `FileHandler`/`os.mkdir`/formatter setup entirely (lines 10-42). Keep only `logger = logging.getLogger(__name__)`; add `logger.addHandler(logging.NullHandler())` (the standard idiom to silence Python's "no handlers found" warning without producing output). This debug/error/spur log was purely diagnostic, not the analysis channel, so no opt-in replacement is needed here.

2. **`Model.__init__`** (`model.py:44-86`) — give each `Model` its own unique logger scope instead of the literal `"sim"`:
   - Add a `uid` constructor parameter (default: auto-generate, e.g. `uuid.uuid4().hex[:8]`) identifying this model instance.
   - `self.simLog = logging.getLogger(f"sim.{self._uid}")` — unique per instance, so attaching handlers to it can never affect another `Model`.
   - Keep the console `StreamHandler` attached by default (unchanged UX — seeing progress on stdout still works with zero config), since it's now attached to a per-instance logger and can't stack across instances.
   - Replace the `debug=False` file-writing behavior and the implicit `log/sim.log` file with two new optional constructor parameters: `sim_log_file=None` and `debug_log_file=None`. If given, attach a `FileHandler(path, mode="w")` to `self.simLog` (with the appropriate level) — same output as today, just declared explicitly instead of automatic.
   - Add a new optional parameter `agent_log_file=None`, stored on the model (e.g. `self._agent_log_file`) for `add_train`/`Agent.__init__` to consume (see next step) — this is what replaces today's automatic `log/agent.log`.

3. **`Agent.__init__`** (`base.py:318-332`) — remove the hardcoded `logging.getLogger("agent")` + `FileHandler("log/agent.log")` block entirely. Instead:
   - Accept the owning `model` (already a constructor parameter) and derive the agent's logger from the model's scope, e.g. `self.agentLog = logging.getLogger(f"agent.{model._uid}")` as a base, with `Train.__init__` continuing to further scope it per-train as it already does (`agent.{model._uid}.train.{uid}`).
   - If `model._agent_log_file` is set, attach a `FileHandler` to the **model-scoped** logger (`agent.{model._uid}`, not the per-train child) exactly once — the natural place is in `Model.add_train`/`add_trains` the first time a train is added, guarded so it only attaches once per model even if many trains are created. Every train's IN/OUT records then land in the same file (as today), tagged with each train's own logger name in the formatted line, but scoped so a second `Model` with its own `agent_log_file` never touches this one.

4. **Update `examples/line4/line4.py`** to pass `agent_log_file="log/agent.log"` (and `sim_log_file=...` if the example currently relies on that) explicitly to `Model(...)`, so the example keeps producing the same files as before with no other behavior change.

5. **Document the concurrency model** (module docstring in `spur/core/__init__.py` or a short section here): SimPy's `Environment` is single-threaded/cooperative, so a `Model` is not thread-safe to drive from multiple threads at once. The supported pattern for a hosted API is one `Model` per OS process/worker, or one `Model` at a time per thread with no `Model` shared across threads. After this fix there is no shared mutable state between `Model` instances (each has its own scoped loggers and, when requested, its own log files), so running several `Model`s — sequentially, in separate threads, or in separate processes — no longer corrupts each other's output.

### Explicitly deferred to Phase 5

Consolidating the two divergent `SimLogFilter` classes (`base.py`'s version also truncates `record.name` to its last dotted segment for `agent.log`-style short output; `model.py`'s version doesn't, since `sim.log`/console output wants the full hierarchical name) — this is a real difference in intent, not just duplication, so it needs its own small design decision and isn't required to fix the concurrency bug. Left as-is as a Phase 5 polish item.

### Verification

- Add a regression test that constructs two `Model(agent_log_file=...)` instances (each pointing at a different temp file, each with at least one `Train`) in the same test process, runs both, and asserts: (a) each file contains only that model's own IN/OUT records (no cross-contamination), (b) neither file's earlier lines were truncated by the other model's construction, and (c) constructing a `Model` with no `agent_log_file`/`sim_log_file` writes no files at all and creates no `log/` directory.
- Re-run `examples/line4/line4.py` after adding explicit `agent_log_file`/`sim_log_file` arguments and confirm `log/agent.log`/`log/sim.log` still appear with the same content shape as before.
- Full `pytest` run stays green; confirm no `log/` directory is created as a side effect of running the test suite (`git status`/`ls` clean after `pytest`).

## Phase 3 — Give it a durable state boundary

- Design and implement save/resume for `Model` state (or at minimum a resumable-run-position + serialized inputs, if full SimPy event-queue snapshotting proves impractical).
- Harden `spur.io`: schema validation (e.g. `pydantic`/`jsonschema`) for component/route/tour/train JSON and the `.spur` project format, with clear validation errors instead of deep crashes in `Model` construction.
- Add missing test coverage: `read_trains_json`, and a full end-to-end `from_project_dictionary` integration test including trains.

## Phase 4 — Finish or formally cut incomplete features

- Decide: implement `Train.basic_traversal`/`get_basic_traversal_time` for real (making `PhysicsTrack` functional), or remove `PhysicsTrack` and its dead code until ready.
- Same call for `TimedStation` and any other self-flagged "may not fully work" components — resolve or explicitly gate out of what the API-facing engine exposes.

## Phase 5 — Hardening / polish

- Deepen test coverage on simulation mechanics (train contention over `BlockExclusiveZone`, resource queuing, timing correctness), not just construction/validation.
- Tighten `importlib`-based dynamic class resolution in `Model.add_components` to a whitelist, since it will eventually parse externally-supplied project files through a public API.
- Consolidate the duplicated `SimLogFilter` class (`model.py` and `base.py`); add type hints consistently to older modules (`route.py`, `tour.py`).

## Explicitly Out of Scope

Building the actual HTTP/REST API layer — that is a separate future repo that imports `spur` as a library once Phases 1-3 are done. Licensing changes — core engine stays MIT.

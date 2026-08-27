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

### Decision: no mid-run pause/resume

`Train.run()` (`train.py:68-148`) is a single Python generator: its position in the tour (current segment, whether it's mid-wait, which resource request it's holding) lives entirely in the suspended generator's stack frame, driven by SimPy's scheduler. Generator frames cannot be pickled in CPython, so literally freezing a live simulation and reloading it later is not achievable without rewriting train movement from a generator into an explicit state machine (segment index + phase, reconstructed step by step) — a redesign of the execution model, not a Phase 3-sized addition. Decision: skip true mid-run persistence for now; revisit only once real hosted-API requirements make it a hard need. Phase 3 instead covers two independently useful, tractable pieces: **config export** (the reverse of `from_project_dictionary`) and **input schema validation**.

### 1. Config export: `Model.to_project_dictionary()`

The reverse of the existing `Model.from_project_dictionary(project)` classmethod (`model.py:187-193`). Captures the *configuration* that built a model — enough to reconstruct an equivalent model from scratch (component graph, routes, tours, trains) — not live mid-run position (train locations, resource occupancy, simulation clock). Useful for saving/sharing/re-running a scenario built via the API.

**Design chosen over reflection:** initially considered reconstructing each section by introspecting live objects (`component.as_dict()`, walking `Tour`/`Route` linked lists). Rejected: `as_dict()` already has a latent bug where it leaks the live `_collection` object (not JSON-serializable, and not the shape `add_components` expects for a `collection` key) into `args`, and reflection is fragile for any component with extra non-constructor instance attributes (e.g. `MultiBlockTrack`'s `_blocks`/`_track_directions`). Instead: `Model.add_components`/`add_routes_and_tours`/`add_trains` already receive the exact input dicts before construction, so `Model` simply **retains those verbatim** and `to_project_dictionary()` hands them back:

- `Model.__init__` gains `self._component_specs = []`, `self._route_specs = []`, `self._tour_specs = []`, `self._train_specs = []`.
- `add_components(components)`, `add_routes_and_tours(routes, tours)`, and `add_trains(trains)` each append/extend their raw input list into the matching `_..._specs` list, in addition to their existing construction logic.
- `to_project_dictionary()` returns `{"components": list(self._component_specs), "routes": list(self._route_specs), "tours": list(self._tour_specs), "trains": list(self._train_specs)}` (shallow-copied so callers can't mutate the model's internal state through the returned dict).
- This makes round-tripping **exact**, not just structurally equivalent, and sidesteps `as_dict()` entirely. Trade-off: only models built through the dict-based `add_*` methods (i.e. the intended JSON/API construction path) have anything to export — a model built by calling `_add_component`/constructing `Route`/`Tour` objects directly (as some unit tests do) has empty spec lists. That's an acceptable, documented limitation since config export exists for the save/share/re-run workflow, which always goes through the dict-based path.
- The `Route`/`Tour` `name` attributes added above are kept regardless (they resolve the existing `# TODO: add uid attribute to route` in `tour.py:150` and are useful for logging/debugging/`__repr__`), but are no longer load-bearing for export.
- Add `write_project_json(model, filepath)` and `read_project_json(filepath)` to `spur/io/formats.py` for a `.spur` project file (envelope: `type: "SpurProject"`, `spur_version`, `name`, plus `components`/`routes`/`tours`/`trains`). Note: `examples/gosub.spur` uses an incompatible **legacy** shape (no `tours` key at all; trains reference `"route"` directly; route components carry inline `args`) that predates the current routes/tours model and would not even load via today's `Model.from_project_dictionary` (`KeyError: 'tours'`) — it is not a valid reference for the current format and is left untouched; the new envelope follows the current, working `tests/data/*.json` shapes instead.

### 2. Schema validation for `spur.io`

Today `spur/io/formats.py` is four functions that do a bare `json.load` with no validation (`read_components_json`, `read_trains_json`, `read_routes_json`, `read_tours_json`) — malformed input currently fails deep inside `Model.add_components`/`add_routes_and_tours` with confusing `KeyError`s rather than a clear message pointing at the bad input.

- Add `pydantic` as a new runtime dependency (`setup.py`) and a new module `spur/io/schema.py` defining models mirroring the existing JSON shapes (verified against `tests/data/test_components.json`, `test_routes.json`, `test_tours.json`, `test_trains.json`):
  - `JitterSpec {type: str, args: dict}`, `CollectionSpec {type: str, key: str}`
  - `ComponentSpec {type: str, u: str, v: str, key: str, name: Optional[str], args: dict, jitter: Optional[JitterSpec], collection: Optional[CollectionSpec]}`
  - `RouteComponentRef {u: str, v: str, key: str}`, `RouteSpec {name: str, components: List[RouteComponentRef]}`
  - `TourRouteArgs {arrival: Optional[int], departure: Optional[int]}`, `TourRouteRef {name: str, args: List[Optional[TourRouteArgs]]}`, `TourSpec {name: str, creation_time: int, deletion_time: int, routes: List[TourRouteRef]}`
  - `TrainSpec {name: str, max_speed: PositiveInt, tour: str}`
  - `ProjectSpec {type: Literal["SpurProject"], spur_version: str, components: List[ComponentSpec], routes: List[RouteSpec], tours: List[TourSpec], trains: List[TrainSpec]}`
- Update each `read_*_json` function to validate the loaded JSON against its model and return `[m.model_dump(exclude_unset=True) for m in ...]` — **`exclude_unset=True` is required**, not optional: `Model.add_components` checks `if "jitter" in c.keys()` (`model.py:209`) and similar presence checks elsewhere, so validated output must not introduce keys that weren't in the original input.
- Add a new exception, e.g. `InvalidProjectDataError(SpurError)` in `spur/core/exception.py`, and catch/re-raise `pydantic.ValidationError` as this type from the `read_*_json` functions, so callers depend on `spur`'s own exception hierarchy rather than leaking a third-party exception type.

### 3. Test coverage

- Unit tests for each `read_*_json` function against both valid fixture data and deliberately malformed data (missing required key, wrong type), asserting `InvalidProjectDataError` is raised with a message identifying the bad field.
- A full end-to-end test that calls `Model.from_project_dictionary(project)` directly (not the piecemeal `add_components`/`add_routes_and_tours`/`add_trains` calls `test_integration.py` uses today) with a project dict assembled from the existing test fixture files, including trains.
- A round-trip test: build a `Model` from the test fixtures, call `to_project_dictionary()`, rebuild a second `Model` from that export via `from_project_dictionary`, and assert equal component/route/tour/train counts and identities (not full run-output equality, since jitter introduces randomness unless fixtures are `NoJitter`-only).

### Phase 3 Verification

- `pytest` stays green, including new schema-validation and round-trip tests.
- Manually corrupt one field in a copy of `tests/data/test_components.json` (e.g. remove `"key"`) and confirm `read_components_json` now raises a clear `InvalidProjectDataError` naming the missing field, instead of a later unrelated `KeyError` inside `Model.add_components`.
- Confirm `examples/line4/line4.py` still runs unchanged (its JSON fixtures are already valid, so schema validation should be transparent to it).

## Phase 4 — Finish or formally cut incomplete features

- Decide: implement `Train.basic_traversal`/`get_basic_traversal_time` for real (making `PhysicsTrack` functional), or remove `PhysicsTrack` and its dead code until ready.
- Same call for `TimedStation` and any other self-flagged "may not fully work" components — resolve or explicitly gate out of what the API-facing engine exposes.

## Phase 5 — Hardening / polish

- Deepen test coverage on simulation mechanics (train contention over `BlockExclusiveZone`, resource queuing, timing correctness), not just construction/validation.
- Tighten `importlib`-based dynamic class resolution in `Model.add_components` to a whitelist, since it will eventually parse externally-supplied project files through a public API.
- Consolidate the duplicated `SimLogFilter` class (`model.py` and `base.py`); add type hints consistently to older modules (`route.py`, `tour.py`).

## Explicitly Out of Scope

Building the actual HTTP/REST API layer — that is a separate future repo that imports `spur` as a library once Phases 1-3 are done. Licensing changes — core engine stays MIT.

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

## Phase 4 — Finish or formally cut incomplete components

Investigation confirmed exactly two self-flagged incomplete components in `spur/core/component.py` (grepped the whole file and `train.py` for "not"/"deprecated"/"todo"/"warning" — nothing else qualifies).

### 1. Cut `PhysicsTrack` (orphaned, crashes if ever used)

`PhysicsTrack.do()` (`component.py:132-139`) calls `train.basic_traversal(...)`, which unconditionally `raise NotImplementedError`s — so any simulation that actually runs a train through a `PhysicsTrack` crashes; only construction is exercised by its existing tests. It is completely unused elsewhere: no example, no `spur.io`/JSON fixture references it, nothing outside its own dead code and construction-only tests. Finishing it properly (real kinematics, handling non-`PhysicsTrack` next-segments — currently an acknowledged `# TODO: Handle other components`, station-stop logic — another acknowledged TODO, deciding on `capacity > 1` support) is feature-sized work, deferred the same way mid-run-resume was deferred from Phase 3.

- Remove the `PhysicsTrack` class (`component.py:66-139`).
- Remove `Train.basic_traversal()` and `Train.get_basic_traversal_time()` (`train.py:150-227`), and the now-unused `from spur.core.component import PhysicsTrack` import (`train.py:7`).
- Remove the now-fully-dead `self.acceleration`/`self.deceleration` assignments in `Train.__init__` (`train.py:42-43`) and their `Attributes` docstring entries (`train.py:18-21`) — they were only ever read inside the code just removed.
- Leave `max_speed`/`speed` on `Agent`/`Train` untouched — unlike `acceleration`/`deceleration` they're required by `Agent`'s base constructor and by Phase 3's `TrainSpec.max_speed` (`spur/io/schema.py`)/`Model.add_train`; removing them would be an unrelated breaking change to already-shipped API surface, not a dead-code cleanup. They're simply not consumed by any component's `do()` today, which is fine — many sims carry a nominal max speed for reporting even without physics-based enforcement.
- Remove `TestPhysicsTrack` (`tests/test_component.py:37-51`) and drop `PhysicsTrack` from that file's imports.
- No doc edit needed — `docs/source/reference/core.rst` uses Sphinx `automodule`/`:members:`, so the class stops appearing once deleted.

### 2. Fix `TimedStation` (small, well-scoped correctness bug)

`TimedStation.__init__` validates and stores `traversal_time`, but `do()` (`component.py:722-730`) never reads it — it's a byte-for-byte copy of `SimpleStation.do()`'s San2016 boarding/alighting dwell formula instead. The docstring says "A timed station simply waits for a specified set of time," matching `TimedTrack`'s fixed-time pattern (`component.py:59-63`: `time = self.traversal_time + self._jitter.jitter()`), not `SimpleStation`'s formula. Fix: make it actually be that.

- Simplify the constructor to `(model, uid, traversal_time, jitter=NoJitter(), collection=None)` — drop `mean_boarding`/`mean_alighting` entirely; that dwell model already exists correctly on `SimpleStation`/`MultiTrackStation`, and nothing depends on `TimedStation`'s current signature (no example/fixture references it).
- Add a `traversal_time` property with validation mirroring `TimedTrack.traversal_time` (`component.py:48-57`, raising `NotPositiveError`), replacing the current bare `if traversal_time <= 0: raise ValueError(...)` inline check, for consistency with its sibling class.
- Change `do()` to mirror `TimedTrack.do()` exactly: `time = self.traversal_time + self._jitter.jitter(); yield self.model.timeout(time)`.
- Remove the "WARNING: may not fully work, or may have been deprecated" docstring line — no longer true once fixed.
- Update `TestTimedStation` (`tests/test_component.py:67-87`) for the new constructor signature.
- Add a new behavioral test that actually drives `do()` (e.g. `model.process(component.do(train))` then `model.run()`, or equivalent) and asserts the dwell equals `traversal_time` — no existing test in the repo calls any component's `do()` directly outside a full `Train.run()` integration test, so this closes a real gap for the one class this phase specifically touches.

### Phase 4 Verification

- `pytest` stays green, including the new `TimedStation` behavioral test.
- `grep -rn "PhysicsTrack\|basic_traversal\|get_basic_traversal_time" spur/ tests/ examples/ docs/` returns nothing.
- Manually construct a `TimedStation`, drive `do()` in a tiny standalone model, and confirm the yielded timeout equals `traversal_time` (not the old San2016 formula's output).
- Confirm `examples/line4/line4.py` still runs unchanged (it uses neither class).

## Phase 5 — Hardening / polish

### 1. Simulation-mechanics test coverage + a real bug found while designing it

Investigation confirmed **no existing test exercises actual contention**: `tests/test_collection.py::test_wait_queue` calls `BlockExclusiveZone.can_accept_agent()`/`accept_agent()` directly and manually — never through a running `Model`/`SpurResource`, never calls `release_agent()`, never drains the queue. `tests/test_integration.py` runs 4 trains through a full network, but every component in `tests/data/test_components.json` has capacity ≥2 and none specifies a `collection`, so it's structurally incapable of producing contention regardless of what it asserts. No test anywhere exercises `SpurResource._do_put`'s capacity gate under real queuing, or `BlockExclusiveZone.release_agent()`'s `process_queue()` release cascade.

Add two new integration-style tests (new fixtures/module, e.g. `tests/test_contention.py`, reusing the `_add_component`/`Route`/`Tour`/`Train` construction idiom already used in `test_collection.py` and `conftest.py`):

- **Plain capacity-limited resource**: two trains funneling through a `capacity=1` `TimedTrack` with no collection. Step the simulation via repeated `model.run(until=...)` calls at checkpoint times and assert T2's `IN` doesn't happen until T1's `OUT` (via `agentLog` capture, same pattern `tests/test_logging.py` already uses to read back log content).
- **`BlockExclusiveZone`**: a zone spanning ≥2 components, two trains routed through it with staggered timing so T2 queues behind T1. Unlike `test_collection.py`'s existing test (which passes `collection="test"` — a bare string, never actually wired to a real `BlockExclusiveZone` instance, so it only tests the collection object in isolation), this test constructs a real `BlockExclusiveZone` and passes the **actual instance** as each component's `collection=`, matching how `Model.add_components` really wires things. Assert `bez.occupied`/`bez.wait_queue` transitions and that T2's entry timestamp is ≥ T1's exit timestamp. Add a third train to check FIFO ordering holds with 2+ waiters.

**Bug found while designing this test, fixed as part of it:** `BlockExclusiveZone.release_agent()` (`collection.py:109-122`) does `self.wait_queue[0].current_segment.next.component.resource.process_queue()` — inferring the waiting agent's target resource from `agent.current_segment.next`. But `Agent.current_segment` is `None` until an agent's *first* request ever succeeds (`train.py`: only set after `yield req` succeeds). If a train's very first-ever tour segment happens to be inside a contended `BlockExclusiveZone` and it ends up queued, the next release crashes with `AttributeError: 'NoneType' object has no attribute 'next'`.

Fix: stop inferring the waiting agent's target component from tour position; track it directly.

- `BlockExclusiveZone.__init__`: change `self._wait_queue` to hold `(agent, component)` pairs instead of bare agents; keep the public `wait_queue` property returning `[agent for agent, _ in self._wait_queue]` (unchanged external contract/docstring, `list[Agent]`).
- `add_to_wait_queue(self, agent, component)` / `pop_from_wait_queue()` updated accordingly.
- `can_accept_agent`, `accept_agent`, `release_agent` (`collection.py:73-122`) gain an optional `component=None` parameter; `release_agent` uses the stored `(agent, component)` pair directly instead of `wait_queue[0].current_segment.next.component`.
- `BaseComponent.can_accept_agent`/`accept_agent`/`release_agent` (`base.py:117-153, 186-211`) pass `self` (the component itself, already the receiver of these calls) through to the matching `self.collection.*` call.
- `BaseCollection`'s no-op defaults (`base.py:392-425`) gain the same optional `component=None` parameter for signature compatibility.
- Add a regression test constructing a train whose *first* segment is inside a contended `BlockExclusiveZone`, confirming release no longer crashes.

### 2. Whitelist `importlib`-based class resolution in `Model.add_components`

Confirmed **not a code-execution risk today** — the module string passed to `importlib.import_module` is always one of three fixed literals (`"spur.core.component"`, `"spur.core.jitter"`, `"spur.core.collection"`), never attacker-controlled; only the *attribute name* looked up on that fixed module is externally supplied (`model.py:244-247` component, `249-253` jitter, `257-270` collection). The real gap: any name reachable on that module's namespace resolves today, including abstract bases and unrelated imported helpers pulled in via each module's own `from ... import ...` (e.g. `ResourceComponent`, `Agent`, `SpurResource`, exception classes, even stdlib-ish objects like `math`) — not just the intentional concrete classes. Worst case today is a confusing `TypeError`/`AttributeError`, not arbitrary code execution, but it should still be closed off before this path parses externally-supplied project files through a public API.

- Add three whitelist sets near the top of `model.py` (reusing the post-Phase-4 concrete class lists confirmed by investigation):
  ```python
  _COMPONENT_TYPES = frozenset({
      "TimedTrack", "MultiBlockTrack", "SimpleYard", "SimpleStation",
      "MultiTrackStation", "TimedStation", "SimpleCrossover",
  })
  _JITTER_TYPES = frozenset({
      "NoJitter", "UniformJitter", "GaussianJitter", "LognormalJitter", "DisruptionJitter",
  })
  _COLLECTION_TYPES = frozenset({"BlockExclusiveZone"})
  ```
- Before each `getattr(importlib.import_module(...), c["type"])`-style call in `add_components` (`model.py:244-270`), check membership and raise the existing `InvalidProjectDataError` (from Phase 3's `spur/core/exception.py` — already imported into `model.py` alongside `NotUniqueIDError`/`InputMismatchError`, so this needs no new import cycle) with a message naming the invalid type.
- Leave `spur/io/schema.py`'s `type: str` fields as plain strings rather than tightening them to `Literal[...]` in this phase — `Model.add_components` can be called directly with raw dicts bypassing `spur.io` entirely (as tests already do), so the `Model`-layer whitelist is the real security boundary regardless; adding a second enforcement layer in the schema now would risk reintroducing the same class of circular-import problem fixed in Phase 3, for marginal benefit. Worth a future follow-up, not this phase.
- Maintenance note (add as a code comment): adding a new concrete `Component`/`Jitter`/`Collection` subclass requires adding its name to the matching whitelist here.

### 3. Consolidate `SimLogFilter`

Simpler than originally scoped once investigated: `base.py`'s copy (`base.py:24-32`, the version that also truncates `record.name` to its last dotted segment) is **never instantiated anywhere in the codebase** — confirmed via repo-wide grep, only `model.py`'s own copy (`model.py:24-31`) is ever used (4 call sites, all in `model.py`, all pairing with formatters that expect the full dotted name). This is a pure deletion, not a merge: remove the dead copy from `base.py` entirely. Zero behavioral risk since nothing depends on it.

### 4. Type hints for `route.py`/`tour.py`

No mypy/pyright config exists anywhere in the repo (confirmed: no `pyproject.toml`, `mypy.ini`, no CI step) — hints are documentation/IDE-support value only, no enforcement added this phase. Add parameter/return type hints to `spur/core/route.py` and `spur/core/tour.py`'s public methods (currently fully untyped — `Route.__init__`, `traverse`, `append`, `insert`, all properties, `RouteSegment`/`TourSegment` and their properties), matching the style already established in `collection.py`/parts of `component.py` (e.g. `can_accept_agent(self, agent: Agent) -> bool`). Where a type is defined later in the same file or would need `Agent`/`BaseComponent` from `base.py`, follow the existing forward-reference pattern from `base.py:9,281-289` (`from typing import TYPE_CHECKING`, string-literal forward refs) only if a real import-cycle risk exists — `collection.py` shows a plain top-level `from spur.core.base import BaseCollection, Agent` is fine when there's no cycle, which is expected to be the case here too (verify no reverse import from `base.py`/`component.py` back into `route.py`/`tour.py` before assuming a plain import is safe).

### Phase 5 Verification

- `pytest` stays green, including the new contention tests and the `BlockExclusiveZone` first-segment regression test.
- Manually construct a `Model.add_components` call with a bogus `type` (e.g. `"os"` or `"Agent"`) and confirm it now raises `InvalidProjectDataError` naming the bad type, instead of `AttributeError`/`TypeError` deep in construction.
- `grep -rn "class SimLogFilter" spur/` shows exactly one definition (in `model.py`).
- `examples/line4/line4.py` still runs unchanged.

## Explicitly Out of Scope

Building the actual HTTP/REST API layer — that is a separate future repo that imports `spur` as a library once Phases 1-3 are done. Licensing changes — core engine stays MIT.

## Future Work: Pausing a Running Simulation

Design notes from a conversation about supporting pause/inspect/mutate/resume for a hosted API (e.g. a real-time dashboard), captured here so the reasoning isn't lost.

- **Pausing a running simulation needs no code change.** SimPy's `Model.run(until=X)` can already be called repeatedly; "pause" is simply not calling it again, and "examine state while paused" is just reading `model.now`/`train.current_segment`/`component._agents`/`BlockExclusiveZone.occupied`/`wait_queue` directly — already exercised by the Phase 5 contention tests' checkpointing pattern. This only survives within a single live process; it is not a durable/cross-process snapshot mechanism (see Phase 3's "no mid-run pause/resume" decision for why that's a much bigger, deliberately deferred problem — generator frames can't be pickled).
- **Real-time pacing is an external-caller concern**, not something `Model` needs to grow: an API layer can pace repeated `run(until=model.now + step)` calls against a wall clock to get real-time-synced behavior, with no "real-time mode" needed inside `Model` itself.
- **Delaying a train (v2 candidate)** is a small, additive change: give `Train` a `delay(duration)` method that interrupts its own process with a structured cause, and have `run()`'s existing (currently no-op) `except Interrupt:` blocks (`spur/core/train.py`) act on that cause instead of just logging it. This does not require reworking the pause/resume contract or any existing method signature — the interrupt hooks are already structurally present, just unused.
- **Relocating a train (v2 candidate)** is a larger, separate piece of future work: naively overwriting `current_segment` would desync the component/`BlockExclusiveZone` occupancy bookkeeping hardened in Phase 5 — a real implementation needs to properly release from the old component/collection and re-acquire at the new one, respecting capacity/zone rules, not just move a pointer.
- **Neither v2 item requires changes to already-shipped API surface** (`Model`'s constructor, `add_train`, `run()`, `to_project_dictionary()`) — they're pure additions. The only thing worth keeping in mind for a future hosted API's v1 design: address trains/simulations by their existing stable `uid`s, and treat the "get simulation state" response shape as extensible (new optional fields later), not fixed.
- Note: jitter (`spur/core/jitter.py`) is unseeded (uses Python's/NumPy's global `random` state) — irrelevant to pause/resume itself, but worth remembering if a future "replay to reconstruct state" approach is ever considered, since runs aren't currently reproducible.

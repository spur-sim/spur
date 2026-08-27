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

- Remove import-time filesystem side effects from `spur/core/__init__.py` (no `FileHandler`/`os.mkdir` on import).
- Rework logging so each `Model`/`Agent` instance gets isolated loggers/handlers (or accepts an injected logger) instead of stacking handlers onto shared global `"sim"`/`"agent"` loggers with `mode="w"` — the key change enabling multiple simulations per process.
- Document the concurrency model the future API layer should assume (SimPy's `Environment` is single-threaded/cooperative — likely "one `Model` per process or thread, no shared mutable global state"); audit for any other global state beyond logging.

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

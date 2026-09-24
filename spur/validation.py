"""Check a project for problems without building a `Model`.

`validate` reads the project's dictionary and reports *every* problem it finds,
each with the path to the offending item (``tours[2].routes[1].args``), so an
editor can show them all at once. Building a `Model` instead stops at the first
problem, often with an unhelpful error, and registers loggers that Python never
releases, so it is a poor way to check a project that is still being edited.

What is checked is the project's structure: that it matches the schema, that
every type and constructor argument name exists, that names are unique, and that
everything a route, tour or train refers to is defined. Argument *values* (a
negative traversal time, say) are checked by the components themselves when the
model is built, and are not checked here.
"""

from typing import Any, Dict, List, Literal, Optional, Sequence, Tuple

from pydantic import BaseModel, TypeAdapter, ValidationError

from spur.core import component as component_module
from spur.core import jitter as jitter_module
from spur.core.registry import (
    COLLECTION_TYPES,
    COMPONENT_TYPES,
    JITTER_TYPES,
    RESERVED_COMPONENT_ARGS,
    constructor_parameters,
)
from spur.io.schema import ComponentSpec, RouteSpec, TourSpec, TrainSpec

_SECTIONS = (
    ("components", TypeAdapter(List[ComponentSpec])),
    ("routes", TypeAdapter(List[RouteSpec])),
    ("tours", TypeAdapter(List[TourSpec])),
    ("trains", TypeAdapter(List[TrainSpec])),
)


class Issue(BaseModel):
    """One problem with a project."""

    severity: Literal["error", "warning"]
    # Where the problem is, e.g. ``tours[2].routes[1].args``.
    path: str
    message: str


class ValidationResult(BaseModel):
    """The outcome of `validate`. A project is valid if it has no errors; it may
    still have warnings."""

    valid: bool
    issues: List[Issue]


def _path(parts: Sequence[Any]) -> str:
    out = ""
    for part in parts:
        if isinstance(part, int):
            out += f"[{part}]"
        else:
            out += f".{part}" if out else str(part)
    return out


def issues_from_validation_error(
    error: ValidationError, prefix: Sequence[Any] = ()
) -> List[Issue]:
    """Turn a pydantic error into `Issue`s, with paths under ``prefix``."""
    return [
        Issue(
            severity="error",
            path=_path(list(prefix) + list(e["loc"])),
            message=e["msg"],
        )
        for e in error.errors()
    ]


def _uid(ref: Dict[str, Any]) -> str:
    return f"{ref['u']}-{ref['v']}-{ref['key']}"


def _check_arguments(
    given: Dict[str, Any],
    cls: type,
    type_name: str,
    path: str,
    skip: Sequence[str] = (),
) -> List[Issue]:
    required, optional = constructor_parameters(cls, skip=skip)
    known = required + optional
    issues = []
    for name in given:
        if name in RESERVED_COMPONENT_ARGS and name in skip:
            issues.append(
                Issue(
                    severity="error",
                    path=f"{path}.{name}",
                    message=(
                        f"'{name}' can't be given in args; "
                        + (
                            "it has its own field on the component"
                            if name in ("jitter", "collection")
                            else "Spur sets it"
                        )
                    ),
                )
            )
        elif name not in known:
            issues.append(
                Issue(
                    severity="error",
                    path=f"{path}.{name}",
                    message=(
                        f"Unknown argument '{name}' for {type_name}. "
                        f"Expected: {', '.join(known) or 'no arguments'}"
                    ),
                )
            )
    for name in required:
        if name not in given:
            issues.append(
                Issue(
                    severity="error",
                    path=path,
                    message=f"Missing required argument '{name}' for {type_name}",
                )
            )
    return issues


def _check_components(components: List[Dict[str, Any]]) -> List[Issue]:
    issues: List[Issue] = []
    first_seen: Dict[Tuple[frozenset, str], Tuple[int, str]] = {}

    for i, c in enumerate(components):
        here = f"components[{i}]"

        if c["type"] not in COMPONENT_TYPES:
            issues.append(
                Issue(
                    severity="error",
                    path=f"{here}.type",
                    message=(
                        f"Unknown component type '{c['type']}'. "
                        f"Available: {', '.join(sorted(COMPONENT_TYPES))}"
                    ),
                )
            )
        else:
            issues += _check_arguments(
                c["args"],
                getattr(component_module, c["type"]),
                c["type"],
                f"{here}.args",
                skip=sorted(RESERVED_COMPONENT_ARGS),
            )

        jitter = c.get("jitter")
        if jitter is not None:
            if jitter["type"] not in JITTER_TYPES:
                issues.append(
                    Issue(
                        severity="error",
                        path=f"{here}.jitter.type",
                        message=(
                            f"Unknown jitter type '{jitter['type']}'. "
                            f"Available: {', '.join(sorted(JITTER_TYPES))}"
                        ),
                    )
                )
            else:
                issues += _check_arguments(
                    jitter["args"],
                    getattr(jitter_module, jitter["type"]),
                    jitter["type"],
                    f"{here}.jitter.args",
                )

        collection = c.get("collection")
        if collection is not None and collection["type"] not in COLLECTION_TYPES:
            issues.append(
                Issue(
                    severity="error",
                    path=f"{here}.collection.type",
                    message=(
                        f"Unknown collection type '{collection['type']}'. "
                        f"Available: {', '.join(sorted(COLLECTION_TYPES))}"
                    ),
                )
            )

        # Components live on the edges of an undirected graph, so the same two
        # nodes and key are the same edge whichever way round they are written;
        # a later component would silently replace the earlier one.
        identity = (frozenset((c["u"], c["v"])), c["key"])
        if identity in first_seen:
            j, other = first_seen[identity]
            same = _uid(c) == other
            issues.append(
                Issue(
                    severity="error",
                    path=here,
                    message=(
                        f"Duplicate component '{_uid(c)}' (also components[{j}])"
                        if same
                        else f"Component '{_uid(c)}' is the same edge as "
                        f"'{other}' (components[{j}]); one would replace the other"
                    ),
                )
            )
        else:
            first_seen[identity] = (i, _uid(c))

    return issues


def _check_duplicate_names(items: List[Dict[str, Any]], section: str, noun: str) -> List[Issue]:
    issues = []
    first: Dict[str, int] = {}
    for i, item in enumerate(items):
        if item["name"] in first:
            issues.append(
                Issue(
                    severity="error",
                    path=f"{section}[{i}].name",
                    message=(
                        f"Duplicate {noun} name '{item['name']}' "
                        f"(also {section}[{first[item['name']]}]); "
                        "the later one would replace the earlier"
                    ),
                )
            )
        else:
            first[item["name"]] = i
    return issues


def _check_routes(
    routes: List[Dict[str, Any]], component_uids: Optional[set]
) -> List[Issue]:
    issues = _check_duplicate_names(routes, "routes", "route")
    for i, route in enumerate(routes):
        if not route["components"]:
            issues.append(
                Issue(
                    severity="error",
                    path=f"routes[{i}].components",
                    message="Route has no components",
                )
            )
        if component_uids is None:
            continue
        for k, ref in enumerate(route["components"]):
            uid = _uid(ref)
            if uid in component_uids:
                continue
            reverse = f"{ref['v']}-{ref['u']}-{ref['key']}"
            hint = (
                f" (a component with the nodes reversed exists: '{reverse}')"
                if reverse in component_uids
                else ""
            )
            issues.append(
                Issue(
                    severity="error",
                    path=f"routes[{i}].components[{k}]",
                    message=f"Unknown component '{uid}'{hint}",
                )
            )
    return issues


def _check_tours(
    tours: List[Dict[str, Any]], routes: Optional[List[Dict[str, Any]]]
) -> List[Issue]:
    issues = _check_duplicate_names(tours, "tours", "tour")
    by_name: Dict[str, Dict[str, Any]] = {}
    for r in routes or []:
        by_name.setdefault(r["name"], r)

    for i, tour in enumerate(tours):
        here = f"tours[{i}]"
        if not tour["routes"]:
            issues.append(
                Issue(
                    severity="warning",
                    path=f"{here}.routes",
                    message="Tour has no routes; trains on it will not move",
                )
            )
        if tour["creation_time"] >= tour["deletion_time"]:
            issues.append(
                Issue(
                    severity="warning",
                    path=f"{here}.deletion_time",
                    message="deletion_time is not after creation_time",
                )
            )

        previous: Optional[Dict[str, Any]] = None
        for k, tour_route in enumerate(tour["routes"]):
            at = f"{here}.routes[{k}]"

            for m, args in enumerate(tour_route["args"]):
                if (
                    args is not None
                    and args["arrival"] is not None
                    and args["departure"] is not None
                    and args["departure"] < args["arrival"]
                ):
                    issues.append(
                        Issue(
                            severity="warning",
                            path=f"{at}.args[{m}]",
                            message="departure is before arrival",
                        )
                    )

            if routes is None:
                continue
            route = by_name.get(tour_route["name"])
            if route is None:
                issues.append(
                    Issue(
                        severity="error",
                        path=f"{at}.name",
                        message=f"Unknown route '{tour_route['name']}'",
                    )
                )
                previous = None
                continue

            if len(route["components"]) != len(tour_route["args"]):
                issues.append(
                    Issue(
                        severity="error",
                        path=f"{at}.args",
                        message=(
                            f"{len(tour_route['args'])} args object(s) for route "
                            f"'{route['name']}', which has {len(route['components'])} "
                            "components. The numbers must match"
                        ),
                    )
                )

            if previous is not None and previous["components"] and route["components"]:
                ends = _uid(previous["components"][-1])
                starts = _uid(route["components"][0])
                if ends != starts:
                    issues.append(
                        Issue(
                            severity="error",
                            path=at,
                            message=(
                                f"Route '{route['name']}' starts at '{starts}' but "
                                f"the previous route '{previous['name']}' ends at "
                                f"'{ends}'; consecutive routes must share that component"
                            ),
                        )
                    )
            previous = route
    return issues


def _check_trains(
    trains: List[Dict[str, Any]], tours: Optional[List[Dict[str, Any]]]
) -> List[Issue]:
    issues = _check_duplicate_names(trains, "trains", "train")
    tour_names = None if tours is None else {t["name"] for t in tours}
    for i, train in enumerate(trains):
        if tour_names is None:
            continue
        # Trains and tours share one namespace of unique names.
        if train["name"] in tour_names:
            issues.append(
                Issue(
                    severity="error",
                    path=f"trains[{i}].name",
                    message=(
                        f"Train name '{train['name']}' is also a tour name; "
                        "trains and tours share one namespace"
                    ),
                )
            )
        if train["tour"] not in tour_names:
            issues.append(
                Issue(
                    severity="error",
                    path=f"trains[{i}].tour",
                    message=f"Unknown tour '{train['tour']}'",
                )
            )
    return issues


def validate(project: Any) -> ValidationResult:
    """Check a project and report every problem.

    Parameters
    ----------
    project : dict
        A project with "components", "routes", "tours" and "trains" lists - the
        shape `Model.from_project_dictionary` takes and
        `Model.to_project_dictionary` returns. Other keys, such as those of a
        full ``.spur`` project file, are ignored.

    Returns
    -------
    ValidationResult
        `valid` is True if there are no errors. Warnings (things that are
        allowed but probably unintended) do not make a project invalid.
    """
    issues: List[Issue] = []

    if not isinstance(project, dict):
        return ValidationResult(
            valid=False,
            issues=[Issue(severity="error", path="", message="A project must be an object")],
        )

    # Each section is checked against the schema first. Checks that depend on
    # a section are skipped if that section didn't match its schema.
    data: Dict[str, Optional[List[Dict[str, Any]]]] = {}
    for section, adapter in _SECTIONS:
        if section not in project:
            issues.append(
                Issue(severity="error", path=section, message="Section is missing")
            )
            data[section] = None
            continue
        try:
            parsed = adapter.validate_python(project[section])
        except ValidationError as e:
            issues += issues_from_validation_error(e, prefix=[section])
            data[section] = None
            continue
        data[section] = [m.model_dump() for m in parsed]

    components, routes, tours, trains = (
        data["components"],
        data["routes"],
        data["tours"],
        data["trains"],
    )

    if components is not None:
        issues += _check_components(components)
    if routes is not None:
        issues += _check_routes(
            routes,
            None if components is None else {_uid(c) for c in components},
        )
    if tours is not None:
        issues += _check_tours(tours, routes)
    if trains is not None:
        issues += _check_trains(trains, tours)

    return ValidationResult(
        valid=not any(i.severity == "error" for i in issues), issues=issues
    )

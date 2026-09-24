import copy

import pytest
from pydantic import TypeAdapter, ValidationError
from typing import List

from spur.core import Model
from spur.core import component as component_module
from spur.core.base import BaseComponent
from spur.core.exception import InvalidProjectDataError
from spur.core.registry import (
    COLLECTION_TYPES,
    COMPONENT_TYPES,
    JITTER_TYPES,
    RESERVED_COMPONENT_ARGS,
    constructor_parameters,
)
from spur.io.formats import (
    read_components_json,
    read_routes_json,
    read_tours_json,
    read_trains_json,
)
from spur.io.schema import ComponentSpec
from spur.validation import issues_from_validation_error, validate


def _ref(uid):
    u, v, key = uid.split("-")
    return {"u": u, "v": v, "key": key}


def _component(type_, uid, args, **extra):
    return {"type": type_, **_ref(uid), "args": args, **extra}


# Route R1 ends at e-f-Y and R2 starts there, so the two are joined.
SMALL = {
    "components": [
        _component("SimpleYard", "a-b-Y", {"capacity": 2}),
        _component("TimedTrack", "b-c-A", {"traversal_time": 100}),
        _component(
            "SimpleStation",
            "c-d-S",
            {"mean_boarding": 20, "mean_alighting": 20},
            jitter={"type": "DisruptionJitter", "args": {"p": 0.1, "delay": 30}},
        ),
        _component("TimedTrack", "d-e-A", {"traversal_time": 100}),
        _component("SimpleYard", "e-f-Y", {"capacity": 2}),
    ],
    "routes": [
        {
            "name": "R1",
            "components": [_ref(c) for c in ("a-b-Y", "b-c-A", "c-d-S", "d-e-A", "e-f-Y")],
        },
        {"name": "R2", "components": [_ref(c) for c in ("e-f-Y", "d-e-A", "a-b-Y")]},
    ],
    "tours": [
        {
            "name": "Tour-A",
            "creation_time": 0,
            "deletion_time": 1000,
            "routes": [
                {
                    "name": "R1",
                    "args": [
                        {"departure": 100},
                        None,
                        {"arrival": 200, "departure": 260},
                        None,
                        {"departure": 400},
                    ],
                },
                {"name": "R2", "args": [{"departure": 500}, None, {"departure": 700}]},
            ],
        }
    ],
    "trains": [{"name": "T-0", "max_speed": 50, "tour": "Tour-A"}],
}


def _mutated(fn):
    project = copy.deepcopy(SMALL)
    fn(project)
    return project


def _has(result, severity, path, text=""):
    return any(
        i.severity == severity and i.path == path and text in i.message
        for i in result.issues
    )


def _piecemeal(project):
    """Build a model section by section, without validating first."""
    model = Model()
    model.add_components(project["components"])
    model.add_routes_and_tours(project["routes"], project["tours"])
    model.add_trains(project["trains"])
    return model


def _project_from_files(components, routes, tours, trains):
    return {
        "components": read_components_json(components),
        "routes": read_routes_json(routes),
        "tours": read_tours_json(tours),
        "trains": read_trains_json(trains),
    }


class TestValidProjects:
    def test_small_project_is_clean_and_builds(self):
        result = validate(SMALL)
        assert result.valid and result.issues == []
        Model.from_project_dictionary(SMALL)

    def test_line_4_is_clean_and_builds(
        self, components_json_file, routes_json_file, tours_json_file, trains_json_file
    ):
        project = _project_from_files(
            components_json_file, routes_json_file, tours_json_file, trains_json_file
        )
        result = validate(project)
        assert result.valid and result.issues == []
        Model.from_project_dictionary(project)

    def test_a_models_own_export_is_valid(self):
        exported = Model.from_project_dictionary(SMALL).to_project_dictionary()
        assert validate(exported).issues == []

    def test_other_project_file_keys_are_ignored(self):
        project = {**SMALL, "type": "SpurProject", "name": "x", "spur_version": "v1"}
        assert validate(project).issues == []

    def test_component_types_can_be_used_from_json(self):
        # DynamicDwellStation was documented and implemented but could not be
        # named in a project, because the type whitelist was maintained by hand.
        project = _mutated(
            lambda p: p["components"].__setitem__(
                1,
                _component(
                    "DynamicDwellStation",
                    "b-c-A",
                    {"mean_arrival_rate": 0.1, "coefficient_a": 5, "coefficient_b": 2},
                ),
            )
        )
        assert validate(project).issues == []
        model = Model.from_project_dictionary(project)
        assert "DynamicDwellStation" in {c.__name__ for c in model.components}

    def test_a_jitter_without_an_args_key_is_valid_and_builds(self):
        project = _mutated(lambda p: p["components"][2].update(jitter={"type": "NoJitter"}))
        assert validate(project).issues == []
        Model.from_project_dictionary(project)


# (id, mutation, severity, path, text expected in the message)
ERRORS = [
    ("unknown component type", lambda p: p["components"][0].update(type="Nope"),
     "components[0].type", "Unknown component type 'Nope'"),
    ("unknown component arg", lambda p: p["components"][1]["args"].update(speed=1),
     "components[1].args.speed", "Unknown argument 'speed'"),
    ("missing component arg", lambda p: p["components"][1]["args"].pop("traversal_time"),
     "components[1].args", "Missing required argument 'traversal_time'"),
    ("component without an args key", lambda p: p["components"][1].pop("args"),
     "components[1].args", "Missing required argument 'traversal_time'"),
    ("reserved arg", lambda p: p["components"][1]["args"].update(jitter=1),
     "components[1].args.jitter", "can't be given in args"),
    ("unknown jitter type", lambda p: p["components"][2]["jitter"].update(type="Wobble"),
     "components[2].jitter.type", "Unknown jitter type 'Wobble'"),
    ("unknown jitter arg", lambda p: p["components"][2]["jitter"]["args"].update(q=1),
     "components[2].jitter.args.q", "Unknown argument 'q'"),
    ("missing jitter arg", lambda p: p["components"][2]["jitter"]["args"].pop("p"),
     "components[2].jitter.args", "Missing required argument 'p'"),
    ("unknown collection type",
     lambda p: p["components"][1].update(collection={"type": "Zone", "key": "k"}),
     "components[1].collection.type", "Unknown collection type 'Zone'"),
    ("duplicate component", lambda p: p["components"].append(copy.deepcopy(p["components"][1])),
     "components[5]", "Duplicate component 'b-c-A' (also components[1])"),
    ("reversed duplicate component",
     lambda p: p["components"].append(_component("TimedTrack", "c-b-A", {"traversal_time": 5})),
     "components[5]", "same edge as 'b-c-A'"),
    ("duplicate route name", lambda p: p["routes"][1].update(name="R1"),
     "routes[1].name", "Duplicate route name 'R1'"),
    ("empty route", lambda p: p["routes"][1].update(components=[]),
     "routes[1].components", "Route has no components"),
    ("route uses an unknown component", lambda p: p["routes"][0]["components"][1].update(key="Z"),
     "routes[0].components[1]", "Unknown component 'b-c-Z'"),
    ("route uses a reversed component",
     lambda p: p["routes"][0]["components"].__setitem__(1, _ref("c-b-A")),
     "routes[0].components[1]", "reversed exists: 'b-c-A'"),
    ("duplicate tour name", lambda p: p["tours"].append(copy.deepcopy(p["tours"][0])),
     "tours[1].name", "Duplicate tour name 'Tour-A'"),
    ("tour uses an unknown route", lambda p: p["tours"][0]["routes"][1].update(name="R9"),
     "tours[0].routes[1].name", "Unknown route 'R9'"),
    ("args length differs from the route", lambda p: p["tours"][0]["routes"][0]["args"].pop(),
     "tours[0].routes[0].args", "4 args object(s) for route 'R1', which has 5"),
    ("consecutive routes do not join",
     lambda p: p["routes"][1]["components"].__setitem__(0, _ref("a-b-Y")),
     "tours[0].routes[1]", "must share that component"),
    ("duplicate train name", lambda p: p["trains"].append(copy.deepcopy(p["trains"][0])),
     "trains[1].name", "Duplicate train name 'T-0'"),
    ("train named like a tour", lambda p: p["trains"][0].update(name="Tour-A"),
     "trains[0].name", "also a tour name"),
    ("train uses an unknown tour", lambda p: p["trains"][0].update(tour="Nope"),
     "trains[0].tour", "Unknown tour 'Nope'"),
]

WARNINGS = [
    ("tour with no routes", lambda p: p["tours"][0].update(routes=[]),
     "tours[0].routes", "will not move"),
    ("departure before arrival",
     lambda p: p["tours"][0]["routes"][0]["args"].__setitem__(2, {"arrival": 300, "departure": 260}),
     "tours[0].routes[0].args[2]", "departure is before arrival"),
    ("deletion time not after creation time",
     lambda p: p["tours"][0].update(creation_time=1000),
     "tours[0].deletion_time", "not after creation_time"),
]


class TestErrors:
    @pytest.mark.parametrize(
        "mutation,path,text", [e[1:] for e in ERRORS], ids=[e[0] for e in ERRORS]
    )
    def test_error_is_reported_at_its_path(self, mutation, path, text):
        result = validate(_mutated(mutation))
        assert not result.valid
        assert _has(result, "error", path, text), result.issues

    @pytest.mark.parametrize(
        "mutation,path,text", [e[1:] for e in ERRORS], ids=[e[0] for e in ERRORS]
    )
    def test_building_a_model_reports_it_too(self, mutation, path, text):
        with pytest.raises(InvalidProjectDataError) as e:
            Model.from_project_dictionary(_mutated(mutation))
        assert path in str(e.value) and text in str(e.value)

    def test_every_problem_is_reported_together(self):
        def several(p):
            p["components"][0]["type"] = "Nope"
            p["routes"][0]["components"][1]["key"] = "Z"
            p["tours"][0]["routes"][1]["name"] = "R9"
            p["trains"][0]["tour"] = "Nope"

        result = validate(_mutated(several))
        paths = {i.path for i in result.issues if i.severity == "error"}
        assert {
            "components[0].type",
            "routes[0].components[1]",
            "tours[0].routes[1].name",
            "trains[0].tour",
        } <= paths

    def test_the_error_message_from_a_model_lists_them_all(self):
        def several(p):
            p["components"][0]["type"] = "Nope"
            p["trains"][0]["tour"] = "Nope"

        with pytest.raises(InvalidProjectDataError) as e:
            Model.from_project_dictionary(_mutated(several))
        assert "components[0].type" in str(e.value) and "trains[0].tour" in str(e.value)


class TestWarnings:
    @pytest.mark.parametrize(
        "mutation,path,text", [w[1:] for w in WARNINGS], ids=[w[0] for w in WARNINGS]
    )
    def test_warning_does_not_make_a_project_invalid(self, mutation, path, text):
        project = _mutated(mutation)
        result = validate(project)
        assert result.valid
        assert _has(result, "warning", path, text), result.issues
        Model.from_project_dictionary(project)


class TestSchemaErrors:
    def test_missing_field_is_reported_with_its_path(self):
        result = validate(_mutated(lambda p: p["components"][0].pop("u")))
        assert not result.valid
        assert _has(result, "error", "components[0].u", "required")

    def test_nested_paths(self):
        result = validate(_mutated(lambda p: p["routes"][1]["components"][0].pop("u")))
        assert _has(result, "error", "routes[1].components[0].u")

    def test_wrong_type(self):
        result = validate(_mutated(lambda p: p["tours"][0].update(creation_time="soon")))
        assert any(i.path == "tours[0].creation_time" for i in result.issues)

    def test_non_positive_speed(self):
        result = validate(_mutated(lambda p: p["trains"][0].update(max_speed=0)))
        assert any(i.path == "trains[0].max_speed" for i in result.issues)

    def test_missing_section(self):
        project = copy.deepcopy(SMALL)
        del project["trains"]
        assert _has(validate(project), "error", "trains", "missing")

    def test_section_that_is_not_a_list(self):
        result = validate({**SMALL, "components": {}})
        assert any(i.path == "components" for i in result.issues)

    @pytest.mark.parametrize("bad", [None, [], "project", 3])
    def test_project_that_is_not_an_object(self, bad):
        result = validate(bad)
        assert not result.valid and result.issues[0].path == ""

    def test_a_broken_section_does_not_cause_follow_on_errors(self):
        # Routes refer to components; if components can't be read, that isn't
        # evidence the references are wrong.
        result = validate(_mutated(lambda p: p["components"][0].pop("u")))
        assert not any("Unknown component" in i.message for i in result.issues)

    def test_issues_from_validation_error_formats_paths(self):
        with pytest.raises(ValidationError) as e:
            TypeAdapter(List[ComponentSpec]).validate_python([{"type": "X"}, {"type": "Y"}])
        paths = {i.path for i in issues_from_validation_error(e.value, prefix=["components"])}
        assert {"components[0].u", "components[1].key"} <= paths


class TestAgainstTheEngine:
    """Why the validator exists: what building a model does with these mistakes."""

    def test_a_duplicate_component_silently_replaces_the_first(self):
        project = _mutated(
            lambda p: p["components"].append(_component("TimedTrack", "b-c-A", {"traversal_time": 999}))
        )
        model = _piecemeal(project)  # no error
        track = next(c for c in model.components if c.uid == "b-c-A")
        assert track.traversal_time == 999
        assert not validate(project).valid

    def test_a_duplicate_route_name_silently_replaces_the_first(self):
        # Same length as the original R2, so nothing else objects.
        project = _mutated(lambda p: p["routes"].append(
            {"name": "R2", "components": [_ref("e-f-Y"), _ref("b-c-A"), _ref("a-b-Y")]}
        ))
        model = _piecemeal(project)  # no error
        second_route = model._tours["Tour-A"].tour_segments[1].route
        assert [s.component.uid for s in second_route.segments] == ["e-f-Y", "b-c-A", "a-b-Y"]
        assert not validate(project).valid

    def test_a_duplicate_tour_name_silently_replaces_the_first(self):
        project = _mutated(lambda p: p["tours"].append(copy.deepcopy(p["tours"][0])))
        model = _piecemeal(project)  # no error
        assert len(model._tours) == 1
        assert not validate(project).valid

    @pytest.mark.parametrize(
        "mutation,error",
        [
            (lambda p: p["routes"][0]["components"][1].update(key="Z"), KeyError),
            (lambda p: p["tours"][0]["routes"][1].update(name="R9"), KeyError),
            (lambda p: p["trains"][0].update(tour="Nope"), KeyError),
            (lambda p: p["components"].append(_component("TimedTrack", "c-b-A", {"traversal_time": 5})),
             KeyError),
        ],
        ids=["unknown component", "unknown route", "unknown tour", "reversed component"],
    )
    def test_a_dangling_reference_is_a_bare_keyerror(self, mutation, error):
        project = _mutated(mutation)
        with pytest.raises(error):
            _piecemeal(project)
        assert not validate(project).valid


class TestRegistry:
    def test_types_are_derived_from_the_concrete_classes(self):
        assert {
            "TimedTrack", "MultiBlockTrack", "SimpleYard", "SimpleStation",
            "MultiTrackStation", "TimedStation", "SimpleCrossover", "DynamicDwellStation",
        } == COMPONENT_TYPES
        assert {
            "NoJitter", "UniformJitter", "GaussianJitter", "LognormalJitter", "DisruptionJitter",
        } == JITTER_TYPES
        assert {"BlockExclusiveZone"} == COLLECTION_TYPES

    def test_abstract_bases_and_helpers_are_not_available(self):
        assert not COMPONENT_TYPES & {"BaseComponent", "ResourceComponent", "StoreComponent"}
        assert "BaseJitter" not in JITTER_TYPES
        assert "BaseCollection" not in COLLECTION_TYPES

    def test_every_component_type_resolves_to_a_component_class(self):
        for name in COMPONENT_TYPES:
            assert issubclass(getattr(component_module, name), BaseComponent)

    def test_constructor_parameters(self):
        required, optional = constructor_parameters(
            component_module.TimedTrack, skip=sorted(RESERVED_COMPONENT_ARGS)
        )
        assert (required, optional) == (["traversal_time"], ["capacity"])

    def test_variadic_parameters_are_left_out(self):
        class C:
            def __init__(self, a, b=1, *args, **kwargs):
                pass

        assert constructor_parameters(C) == (["a"], ["b"])

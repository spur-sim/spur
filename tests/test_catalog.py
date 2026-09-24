import inspect

import pytest

from spur.catalog import Catalog, Parameter, _documented_parameters, _type_name, catalog
from spur.core import Model
from spur.core import collection as collection_module
from spur.core import component as component_module
from spur.core import jitter as jitter_module
from spur.core.registry import (
    COLLECTION_TYPES,
    COMPONENT_TYPES,
    JITTER_TYPES,
    RESERVED_COMPONENT_ARGS,
    constructor_parameters,
)
from spur.validation import validate

KNOWN_TYPES = {"integer", "number", "string", "boolean"}


def _all_types(c):
    return [("component", t) for t in c.components] + [
        ("jitter", t) for t in c.jitters
    ] + [("collection", t) for t in c.collections]


def _sample(parameter: Parameter):
    """A plausible value for a parameter, from what the catalog says about it."""
    if not parameter.required:
        return parameter.default
    return {"integer": 2, "number": 0.5, "string": "x", "boolean": True}[parameter.type]


def _args(type_info):
    return {p.name: _sample(p) for p in type_info.parameters}


def _project(component):
    return {"components": [component], "routes": [], "tours": [], "trains": []}


def _component(type_info, **extra):
    return {
        "type": type_info.name, "u": "a", "v": "b", "key": "K",
        "args": _args(type_info), **extra,
    }


class TestContents:
    def test_lists_exactly_the_registered_types(self):
        c = catalog()
        assert {t.name for t in c.components} == COMPONENT_TYPES
        assert {t.name for t in c.jitters} == JITTER_TYPES
        assert {t.name for t in c.collections} == COLLECTION_TYPES

    def test_sorted_by_name(self):
        c = catalog()
        for group in (c.components, c.jitters, c.collections):
            assert [t.name for t in group] == sorted(t.name for t in group)

    def test_every_type_has_a_one_line_summary(self):
        for kind, t in _all_types(catalog()):
            assert t.summary and "\n" not in t.summary and t.summary == t.summary.strip(), (
                kind, t.name,
            )

    def test_parameters_are_the_constructors_in_order(self):
        for kind, t in _all_types(catalog()):
            cls = getattr({"component": component_module, "jitter": jitter_module,
                           "collection": collection_module}[kind], t.name)
            skip = {"component": sorted(RESERVED_COMPONENT_ARGS), "jitter": (),
                    "collection": ("model", "uid")}[kind]
            required, optional = constructor_parameters(cls, skip=skip)
            assert [p.name for p in t.parameters] == required + optional, t.name

    def test_reserved_arguments_are_not_offered(self):
        for t in catalog().components:
            assert not {p.name for p in t.parameters} & RESERVED_COMPONENT_ARGS

    def test_collections_and_no_jitter_take_no_arguments(self):
        c = catalog()
        assert all(t.parameters == [] for t in c.collections)
        assert next(t for t in c.jitters if t.name == "NoJitter").parameters == []

    def test_required_and_defaults(self):
        c = catalog()
        track = {p.name: p for p in next(t for t in c.components if t.name == "TimedTrack").parameters}
        assert (track["traversal_time"].required, track["traversal_time"].default) == (True, None)
        assert (track["capacity"].required, track["capacity"].default) == (False, 1)
        gauss = {p.name: p for p in next(t for t in c.jitters if t.name == "GaussianJitter").parameters}
        assert (gauss["mean"].default, gauss["std"].default) == (0.0, 1.0)

    def test_serialises_and_round_trips(self):
        c = catalog()
        assert Catalog.model_validate_json(c.model_dump_json()) == c


class TestEveryParameterIsDocumented:
    """The catalog is only as good as the docstrings it reads, so a component
    can't be added or changed without documenting each parameter."""

    def test_every_parameter_has_a_type_and_a_description(self):
        problems = []
        for kind, t in _all_types(catalog()):
            for p in t.parameters:
                if p.type not in KNOWN_TYPES:
                    problems.append(f"{kind} {t.name}.{p.name}: type {p.type!r}")
                if not p.description:
                    problems.append(f"{kind} {t.name}.{p.name}: no description")
        assert not problems, (
            "Document these in the class's Attributes (or __init__'s Parameters) "
            "docstring section as `name : type` followed by an indented description:\n"
            + "\n".join(problems)
        )

    def test_annotations_and_docstring_types_agree(self):
        for module, names, skip in (
            (component_module, COMPONENT_TYPES, RESERVED_COMPONENT_ARGS),
            (jitter_module, JITTER_TYPES, ()),
        ):
            for name in names:
                cls = getattr(module, name)
                documented = _documented_parameters(cls)
                for pname, param in inspect.signature(cls.__init__).parameters.items():
                    if pname in skip or pname not in documented:
                        continue
                    if param.annotation in (int, float, str, bool):
                        assert _type_name(param.annotation, None) == _type_name(
                            None, documented[pname][0]
                        ), f"{name}.{pname}"

    def test_defaults_are_plain_json_values(self):
        for _, t in _all_types(catalog()):
            for p in t.parameters:
                assert p.default is None or isinstance(p.default, (int, float, str, bool))


class TestAgainstTheValidatorAndTheEngine:
    """Build projects from nothing but what the catalog says, and check that
    the validator accepts them and the engine builds them."""

    @pytest.mark.parametrize("name", sorted(COMPONENT_TYPES))
    def test_every_component_can_be_built_from_its_catalog_entry(self, name):
        info = next(t for t in catalog().components if t.name == name)
        project = _project(_component(info))
        assert validate(project).issues == []
        model = Model.from_project_dictionary(project)
        assert [type(c).__name__ for c in model.components] == [name]

    @pytest.mark.parametrize("name", sorted(JITTER_TYPES))
    def test_every_jitter_can_be_built_from_its_catalog_entry(self, name):
        c = catalog()
        info = next(t for t in c.jitters if t.name == name)
        track = next(t for t in c.components if t.name == "TimedTrack")
        project = _project(
            _component(track, jitter={"type": name, "args": _args(info)})
        )
        assert validate(project).issues == []
        Model.from_project_dictionary(project)

    @pytest.mark.parametrize("name", sorted(COLLECTION_TYPES))
    def test_every_collection_can_be_used_from_its_catalog_entry(self, name):
        track = next(t for t in catalog().components if t.name == "TimedTrack")
        project = _project(_component(track, collection={"type": name, "key": "zone"}))
        assert validate(project).issues == []
        model = Model.from_project_dictionary(project)
        assert len(model.collections) == 1

    def test_leaving_out_a_required_parameter_is_what_the_validator_rejects(self):
        for t in catalog().components:
            for p in (p for p in t.parameters if p.required):
                args = {k: v for k, v in _args(t).items() if k != p.name}
                component = {"type": t.name, "u": "a", "v": "b", "key": "K", "args": args}
                result = validate(_project(component))
                assert any(
                    f"Missing required argument '{p.name}'" in i.message for i in result.issues
                ), (t.name, p.name)

"""A description of every component, jitter and collection type a project may use.

An editor needs to offer the right choices: which types exist, what each one
takes, which parameters are required, their defaults, and what they mean.
`catalog` builds that from the code itself, so it can't disagree with it:

* which types exist comes from `spur.core.registry`;
* each parameter's name, whether it is required, and its default come from the
  constructor's signature;
* each parameter's type and description come from the numpydoc-style parameter
  sections of the class or ``__init__`` docstring (the ``Attributes`` or
  ``Parameters`` lists).

Every parameter must therefore be documented; a test enforces it.
"""

import inspect
import re
from typing import Dict, List, Optional, Sequence, Tuple, Union

from pydantic import BaseModel

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

_JSON_TYPES = {int: "integer", float: "number", str: "string", bool: "boolean"}
_DOC_TYPES = {"int": "integer", "float": "number", "str": "string", "bool": "boolean"}

# ``name : type`` followed by one or more indented description lines.
_DOC_PARAMETER = re.compile(r"^(\w+) : ([^\n]+)\n((?:[ \t]+[^\n]*\n?)+)", re.M)


class Parameter(BaseModel):
    """One argument a type takes, in the ``args`` of a component or jitter."""

    name: str
    # "integer", "number", "string" or "boolean" where known, otherwise the type
    # as the docstring words it.
    type: Optional[str] = None
    required: bool
    # The default when the argument is optional, otherwise None.
    default: Optional[Union[int, float, str, bool]] = None
    description: str


class TypeInfo(BaseModel):
    """A component, jitter or collection type."""

    name: str
    summary: str
    parameters: List[Parameter]


class Catalog(BaseModel):
    components: List[TypeInfo]
    jitters: List[TypeInfo]
    collections: List[TypeInfo]


def _documented_parameters(cls: type) -> Dict[str, Tuple[str, str]]:
    """``{name: (type, description)}`` from the class and ``__init__`` docstrings."""
    found: Dict[str, Tuple[str, str]] = {}
    for doc in (inspect.getdoc(cls), inspect.getdoc(cls.__init__)):
        if not doc:
            continue
        for match in _DOC_PARAMETER.finditer(doc):
            name, type_text, body = match.groups()
            description = " ".join(line.strip() for line in body.splitlines()).strip()
            found.setdefault(name, (type_text, description))
    return found


def _type_name(annotation, documented_type: Optional[str]) -> Optional[str]:
    if annotation in _JSON_TYPES:
        return _JSON_TYPES[annotation]
    if documented_type is None:
        return None
    # "float, optional" -> "float"; "`Model`" -> "Model"
    word = documented_type.split(",")[0].strip().strip("`")
    return _DOC_TYPES.get(word, word)


def _summary(cls: type) -> str:
    doc = inspect.getdoc(cls) or ""
    return " ".join(doc.split("\n\n")[0].split())


def _type_info(name: str, cls: type, skip: Sequence[str]) -> TypeInfo:
    required, optional = constructor_parameters(cls, skip=skip)
    signature = inspect.signature(cls.__init__).parameters
    documented = _documented_parameters(cls)

    parameters = []
    for param_name in required + optional:
        param = signature[param_name]
        doc_type, description = documented.get(param_name, (None, ""))
        default = None if param.default is param.empty else param.default
        if not isinstance(default, (int, float, str, bool, type(None))):
            default = repr(default)
        parameters.append(
            Parameter(
                name=param_name,
                type=_type_name(
                    None if param.annotation is param.empty else param.annotation,
                    doc_type,
                ),
                required=param.default is param.empty,
                default=default,
                description=description,
            )
        )
    return TypeInfo(name=name, summary=_summary(cls), parameters=parameters)


def catalog() -> Catalog:
    """Describe every type a project may name, sorted by name."""
    return Catalog(
        components=[
            _type_info(n, getattr(component_module, n), skip=sorted(RESERVED_COMPONENT_ARGS))
            for n in sorted(COMPONENT_TYPES)
        ],
        jitters=[
            _type_info(n, getattr(jitter_module, n), skip=())
            for n in sorted(JITTER_TYPES)
        ],
        collections=[
            _type_info(n, getattr(collection_module, n), skip=("model", "uid"))
            for n in sorted(COLLECTION_TYPES)
        ],
    )

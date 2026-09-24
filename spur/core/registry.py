"""The component, jitter and collection types a project may use.

A project names types as strings (``"SimpleStation"``), and Spur resolves them
to classes by name. Only *concrete* classes defined in the component, jitter
and collection modules may be named: not abstract bases, and not helpers that
those modules happen to import. The sets here are derived from the classes
themselves, so adding a new concrete class makes it available with nothing to
keep in sync by hand.
"""

import inspect
from types import ModuleType
from typing import FrozenSet, List, Sequence, Tuple

from spur.core import collection as _collection
from spur.core import component as _component
from spur.core import jitter as _jitter
from spur.core.base import BaseCollection, BaseComponent
from spur.core.jitter import BaseJitter

# Given by Spur, never through a component's ``args``: ``model`` and ``uid`` are
# supplied when the component is built, and ``jitter`` and ``collection`` have
# their own fields in a component's specification.
RESERVED_COMPONENT_ARGS = frozenset({"model", "uid", "jitter", "collection"})


def _concrete_types(module: ModuleType, base: type) -> FrozenSet[str]:
    return frozenset(
        name
        for name, obj in vars(module).items()
        if inspect.isclass(obj)
        and issubclass(obj, base)
        and obj.__module__ == module.__name__
        and not inspect.isabstract(obj)
    )


COMPONENT_TYPES = _concrete_types(_component, BaseComponent)
JITTER_TYPES = _concrete_types(_jitter, BaseJitter)
COLLECTION_TYPES = _concrete_types(_collection, BaseCollection)


def constructor_parameters(
    cls: type, skip: Sequence[str] = ()
) -> Tuple[List[str], List[str]]:
    """The names a class's constructor takes, as ``(required, optional)``.

    Parameters named in ``skip`` are left out, as are ``*args`` and
    ``**kwargs``.
    """
    required: List[str] = []
    optional: List[str] = []
    for name, param in list(inspect.signature(cls.__init__).parameters.items())[1:]:
        if name in skip or param.kind in (param.VAR_POSITIONAL, param.VAR_KEYWORD):
            continue
        (required if param.default is param.empty else optional).append(name)
    return required, optional

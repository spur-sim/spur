import json
from typing import Dict, List

from pydantic import ValidationError, TypeAdapter

from spur.io.schema import ComponentSpec, RouteSpec, TourSpec, TrainSpec, ProjectSpec

# Imported lazily (inside functions, not here) to avoid a circular import:
# spur.core.model imports spur.io.formats at module load time, so importing
# spur.core.exception at this module's top level would - depending on which
# module a caller imports first - try to import spur.io.formats again while
# it is still mid-import.


def _load_and_validate(filepath, adapter: TypeAdapter) -> List[Dict]:
    from spur.core.exception import InvalidProjectDataError

    with open(filepath, "r") as infile:
        raw = json.load(infile)

    try:
        validated = adapter.validate_python(raw)
    except ValidationError as e:
        raise InvalidProjectDataError(
            f"Invalid project data in {filepath}: {e}"
        ) from e

    return [m.model_dump(exclude_unset=True) for m in validated]


def read_components_json(filepath) -> List[Dict]:
    return _load_and_validate(filepath, TypeAdapter(List[ComponentSpec]))


def read_trains_json(filepath: str) -> List[Dict]:
    return _load_and_validate(filepath, TypeAdapter(List[TrainSpec]))


def read_routes_json(filepath: str) -> List[Dict]:
    return _load_and_validate(filepath, TypeAdapter(List[RouteSpec]))


def read_tours_json(filepath: str) -> List[Dict]:
    return _load_and_validate(filepath, TypeAdapter(List[TourSpec]))


def read_project_json(filepath: str) -> Dict:
    """Read a whole `.spur` project file (components/routes/tours/trains)."""
    from spur.core.exception import InvalidProjectDataError

    with open(filepath, "r") as infile:
        raw = json.load(infile)

    try:
        project = ProjectSpec.model_validate(raw)
    except ValidationError as e:
        raise InvalidProjectDataError(
            f"Invalid project data in {filepath}: {e}"
        ) from e

    return project.model_dump(exclude_unset=True)


def write_project_json(model, filepath: str, name: str = None, spur_version: str = "v1.0.0") -> None:
    """Write a `Model`'s configuration to a `.spur` project file.

    Parameters
    ----------
    model : `spur.core.Model`
        The model to export. Only components/routes/tours/trains added via
        `add_components`/`add_routes_and_tours`/`add_trains` are exported -
        see `Model.to_project_dictionary`.
    filepath : str
        The path to write the project file to.
    name : str, optional
        A human-readable name for the project.
    spur_version : str, optional
        The project file format version to record.
    """
    from spur.core.exception import InvalidProjectDataError

    project = {
        "type": "SpurProject",
        "name": name,
        "spur_version": spur_version,
        **model.to_project_dictionary(),
    }
    # Validate before writing so a malformed export fails loudly here
    # rather than producing a file that can't be read back.
    try:
        validated = ProjectSpec.model_validate(project)
    except ValidationError as e:
        raise InvalidProjectDataError(f"Cannot export model to {filepath}: {e}") from e

    with open(filepath, "w") as outfile:
        json.dump(validated.model_dump(exclude_unset=True), outfile, indent=2)

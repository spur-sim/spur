"""Pydantic models describing the shape of Spur's project JSON data.

These mirror the JSON produced/consumed by `spur.io.formats` and the
`.spur` project file format. They exist to give clear, structured
validation errors on malformed input instead of a `KeyError` deep inside
`Model.add_components`/`add_routes_and_tours`/`add_trains`.
"""

from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, PositiveInt


class JitterSpec(BaseModel):
    type: str
    args: Dict = {}


class CollectionSpec(BaseModel):
    type: str
    key: str


class ComponentSpec(BaseModel):
    type: str
    u: str
    v: str
    key: str
    name: Optional[str] = None
    args: Dict = {}
    jitter: Optional[JitterSpec] = None
    collection: Optional[CollectionSpec] = None


class RouteComponentRef(BaseModel):
    u: str
    v: str
    key: str


class RouteSpec(BaseModel):
    name: str
    components: List[RouteComponentRef]


class TourRouteArgs(BaseModel):
    arrival: Optional[int] = None
    departure: Optional[int] = None


class TourRouteRef(BaseModel):
    name: str
    args: List[Optional[TourRouteArgs]]


class TourSpec(BaseModel):
    name: str
    creation_time: int
    deletion_time: int
    routes: List[TourRouteRef]


class TrainSpec(BaseModel):
    name: str
    max_speed: PositiveInt
    tour: str


class ProjectSpec(BaseModel):
    type: Literal["SpurProject"]
    name: Optional[str] = None
    spur_version: str
    components: List[ComponentSpec]
    routes: List[RouteSpec]
    tours: List[TourSpec]
    trains: List[TrainSpec]

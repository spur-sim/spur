from simpy.resources.store import Store

from spur.core import Model
from spur.core.base import StoreComponent


class Yard(StoreComponent):
    __name__ = "Yard"

    def __init__(self, model: Model, uid, store: Store) -> None:
        super().__init__(model, uid, store)

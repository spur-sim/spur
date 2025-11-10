import json
from typing import List, Dict


def read_components_json(filepath) -> List[Dict]:
    with open(filepath, "r") as infile:
        components = json.load(infile)

    return components


def read_trains_json(filepath: str) -> List[Dict]:
    with open(filepath, "r") as infile:
        trains = json.load(infile)

    return trains


def read_routes_json(filepath: str) -> List[Dict]:
    with open(filepath, "r") as infile_r:
        routes = json.load(infile_r)
    
    return routes


def read_tours_json(filepath: str) -> List[Dict]:
    with open(filepath, "r") as infile_t:
        tours = json.load(infile_t)
    
    return tours

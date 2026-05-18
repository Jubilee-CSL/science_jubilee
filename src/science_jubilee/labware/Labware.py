# Refactorisation du module Labware avec `attrs`

```python
import json
import os
import string
from itertools import chain
from math import acos, cos, sin, sqrt
from typing import Dict, Iterable, List, NamedTuple, Tuple, Union

import numpy as np
from attrs import Factory, define, field, validators


@define(slots=True)
class Well:
    """Represents a single well in a labware."""

    name: str
    depth: float
    totalLiquidVolume: float
    shape: str

    x: float
    y: float
    z: float

    diameter: float | None = None
    xDimension: float | None = None
    yDimension: float | None = None

    offset: Tuple[float, ...] | None = None
    slot: str | None = None

    has_tip: bool = False
    clean_tip: bool = False

    labware_name: str | None = None

    @property
    def top(self) -> float:
        return self.z + self.depth

    @property
    def bottom(self) -> float:
        return self.z

    def apply_offset(self, offset: Tuple[float, ...]) -> None:

        self.x += offset[0]
        self.y += offset[1]

        if len(offset) == 3:
            self.z += offset[2]

        self.offset = offset

    def get_top_location(self, z_offset: float = 0):

        z = self.top + z_offset

        if z <= self.bottom:
            raise ValueError(
                "Top offset generates an invalid Z coordinate"
            )

        return Location(
            Point(self.x, self.y, z),
            self,
        )

    def get_bottom_location(
        self,
        z_offset: float = 0,
    ):

        if z_offset < 0:
            raise ValueError(
                "Bottom offset must be positive"
            )

        z = self.bottom + z_offset

        return Location(
            Point(self.x, self.y, z),
            self,
        )

    def set_tip_state(
        self,
        has_tip: bool,
        clean_tip: bool | None = None,
    ) -> None:

        self.has_tip = has_tip

        if clean_tip is not None:
            self.clean_tip = clean_tip


@define(slots=True, repr=False)
class WellSet:

    wells: Dict[str, Well] = field(factory=dict)

    def __repr__(self):
        return str(list(self.wells.keys()))

    def __iter__(self):
        return iter(self.wells.values())

    def __len__(self):
        return len(self.wells)

    def __contains__(self, well_id: str):
        return well_id in self.wells

    def get_well(self, well_id: str) -> Well:
        return self.wells[well_id]

    def get_wells(self) -> List[Well]:
        return list(self.wells.values())

    def __getitem__(
        self,
        identifier: Union[str, int, slice],
    ):

        if isinstance(identifier, str):
            return self.wells[identifier]

        if isinstance(identifier, int):
            return list(self.wells.values())[identifier]

        if isinstance(identifier, slice):
            return list(self.wells.values())[identifier]

        raise TypeError(
            f"Unsupported identifier type: {type(identifier)}"
        )


@define(slots=True, repr=False)
class Row(WellSet):

    identifier: str = ""


@define(slots=True, repr=False)
class Column(WellSet):

    identifier: int = 0


@define(slots=True, repr=False)
class Labware(WellSet):

    labware_filename: str = field()

    offset: Tuple[float, ...] | None = None

    order: str = field(default="rows")

    path: str = field(
        default=os.path.join(
            os.path.dirname(__file__),
            "labware_definition",
        )
    )

    data: dict = field(init=False, factory=dict)

    config_path: str = field(init=False)

    wells_data: dict = field(init=False, factory=dict)

    row_data: Dict[str, Row] = field(init=False, factory=dict)

    column_data: Dict[int, Column] = field(init=False, factory=dict)

    slot: str | None = field(init=False, default=None)

    manualOffset: dict = field(init=False, factory=dict)

    @order.validator
    def validate_order(self, attribute, value):

        valid_orders = {
            "rows",
            "row",
            "Rows",
            "Row",
            "R",
            "cols",
            "col",
            "C",
            "columns",
            "Columns",
        }

        if value not in valid_orders:
            raise ValueError(
                f"Invalid order: {value}"
            )

    def __attrs_post_init__(self):

        filename = self.labware_filename

        if not filename.endswith(".json"):
            filename += ".json"

        self.config_path = os.path.join(
            self.path,
            filename,
        )

        with open(self.config_path, "r") as f:
            self.data = json.load(f)

        self.wells_data = self.data.get("wells", {})

        (
            self.row_data,
            self.column_data,
            self.wells,
        ) = self._create_rows_and_columns()

        self.with_well_order(self.order)

        if self.offset is not None:
            self.apply_offset(self.offset)

        self.manualOffset = self.data.get(
            "manual_offset",
            {},
        )

    def __repr__(self):

        display = (
            f"{self.labware_type}: {self.load_name}"
        )

        if self.slot is not None:
            display += f" on {self.slot}"

        return display

    @property
    def ordering(self):
        return np.array(self.data["ordering"]).T

    @property
    def metadata(self):
        return self.data.get("metadata", {})

    @property
    def parameters(self):
        return self.data.get("parameters", {})

    @property
    def display_name(self):
        return self.metadata["displayName"]

    @property
    def load_name(self):
        return self.parameters["loadName"]

    @property
    def labware_type(self):
        return self.metadata["displayCategory"]

    @property
    def volume_units(self):
        return self.metadata["displayVolumeUnits"]

    @property
    def dimensions(self):
        return self.data.get("dimensions", {})

    @property
    def is_tip_rack(self):
        return self.parameters["isTiprack"]

    @property
    def shape(self):
        return (
            len(self.row_data),
            len(self.column_data),
        )

    def apply_offset(
        self,
        offset: Tuple[float, ...],
    ):

        self.offset = offset

        for well in self:
            well.apply_offset(offset)

    def add_slot(self, slot: str):

        self.slot = slot

        for well in self:
            well.slot = slot

    def get_row(self, row_id: str):
        return self.row_data[row_id]

    def get_column(self, column_id: int):
        return self.column_data[column_id]

    def with_well_order(self, order: str):

        ordered_wells = {}

        if order.lower().startswith("row") or order == "R":

            for well in chain(*self.row_data.values()):
                ordered_wells[well.name] = well

        else:

            for well in chain(*self.column_data.values()):
                ordered_wells[well.name] = well

        self.wells = ordered_wells

    def _create_rows_and_columns(self):

        rows = {}
        columns = {}
        wells = {}

        for column_data in self.ordering:

            row_id = column_data[0][0]

            if row_id not in rows:
                rows[row_id] = {}

            for col_order, well_id in enumerate(column_data):

                well = Well(
                    name=well_id,
                    **self.wells_data[well_id],
                )

                rows[row_id][well_id] = well

                column_id = col_order + 1

                if column_id not in columns:
                    columns[column_id] = {}

                columns[column_id][well_id] = well

                wells[well_id] = well

        if self.is_tip_rack:

            for well in wells.values():
                well.has_tip = True
                well.clean_tip = True

        for well in wells.values():
            well.labware_name = self.display_name

        rows = {
            key: Row(identifier=key, wells=value)
            for key, value in rows.items()
        }

        columns = {
            key: Column(identifier=key, wells=value)
            for key, value in columns.items()
        }

        return rows, columns, wells

    @staticmethod
    def _nominal_coordinates(
        well: Well,
        x_space: float,
        y_space: float,
    ):

        col_index = int(well.name[1:]) - 1

        row_index = list(
            string.ascii_uppercase
        ).index(well.name[0])

        return (
            col_index * x_space,
            row_index * y_space,
        )

    @staticmethod
    def _getxyz(location):

        if isinstance(location, Well):
            return (
                location.x,
                location.y,
                location.z,
            )

        if isinstance(location, tuple):
            return location

        if isinstance(location, Location):
            return location.point

        raise ValueError(
            "Invalid location type"
        )


class Point(NamedTuple):

    x: float = 0.0
    y: float = 0.0
    z: float = 0.0

    def add(self, other):

        if not isinstance(other, Point):
            return NotImplemented

        return Point(
            self.x + other.x,
            self.y + other.y,
            self.z + other.z,
        )

    def subtract(self, other):

        if not isinstance(other, Point):
            return NotImplemented

        return Point(
            self.x - other.x,
            self.y - other.y,
            self.z - other.z,
        )

    def multiply(self, scalar):

        if not isinstance(scalar, (float, int)):
            return NotImplemented

        return Point(
            self.x * scalar,
            self.y * scalar,
            self.z * scalar,
        )


@define(slots=True)
class Location:

    point: Point

    labware: Union[Well, Labware]
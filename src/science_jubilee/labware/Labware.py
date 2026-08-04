from __future__ import annotations

import json
import math
import os
import random
import string
from dataclasses import dataclass, field
from itertools import chain
from typing import Dict, Iterator, NamedTuple

import numpy as np


class Point(NamedTuple):
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0

    def add(self, other: "Point") -> "Point":
        return Point(
            self.x + other.x,
            self.y + other.y,
            self.z + other.z,
        )

    def subtract(self, other: "Point") -> "Point":
        return Point(
            self.x - other.x,
            self.y - other.y,
            self.z - other.z,
        )

    def multiply(self, scalar: float) -> "Point":
        return Point(
            self.x * scalar,
            self.y * scalar,
            self.z * scalar,
        )


@dataclass(slots=True)
class Location:
    point: Point
    resource: "Well | Labware"


@dataclass(slots=True, repr=False)
class Well:
    """
    Represents a physical well.
    """

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

    offset: tuple[float, ...] | None = None
    slot: str | None = None

    has_tip: bool = False
    clean_tip: bool = False

    labware_name: str | None = None

    def __repr__(self):
        return f"Well({self.name})"

    # ------------------------------------------------------------------
    # Geometry
    # ------------------------------------------------------------------

    @property
    def top(self) -> float:
        return self.z + self.depth

    @property
    def bottom(self) -> float:
        return self.z

    def _validate_geometry(self) -> None:

        if self.shape not in {
            "circular",
            "rectangular",
        }:
            raise ValueError(f"Unsupported well shape: {self.shape}")

        if self.shape == "circular":
            if self.diameter is None:
                raise ValueError("Circular wells require a diameter.")

        if self.shape == "rectangular":
            if self.xDimension is None or self.yDimension is None:
                raise ValueError(
                    "Rectangular wells require " "xDimension and yDimension."
                )

    # ------------------------------------------------------------------
    # Position helpers
    # ------------------------------------------------------------------

    def apply_offset(self, offset: tuple[float, ...]) -> None:
        self.x += offset[0]
        self.y += offset[1]

        if len(offset) == 3:
            self.z += offset[2]

        self.offset = offset

    def get_top_location(self, z_offset: float = 0.0) -> Location:
        z = self.top + z_offset

        if z <= self.bottom:
            raise ValueError("Invalid top offset.")

        return Location(
            Point(self.x, self.y, z),
            self,
        )

    def get_bottom_location(self, z_offset: float = 0.0) -> Location:
        if z_offset < 0:
            raise ValueError("Bottom offset must be positive.")

        z = self.bottom + z_offset

        return Location(
            Point(self.x, self.y, z),
            self,
        )

    def random_point(self, safety_margin: float = 0.9) -> Location:
        """
        Generate a random safe point inside the well.
        """
        self._validate_geometry()

        if not 0 < safety_margin <= 1:
            raise ValueError("safety_margin must be between 0 and 1.")

        if self.shape == "circular":

            usable_radius = (self.diameter / 2) * safety_margin

            angle = random.uniform(0, 2 * math.pi)
            radius = random.uniform(0, usable_radius)

            dx = math.cos(angle) * radius
            dy = math.sin(angle) * radius

        else:

            half_x = (self.xDimension / 2) * safety_margin
            half_y = (self.yDimension / 2) * safety_margin

            dx = random.uniform(-half_x, half_x)
            dy = random.uniform(-half_y, half_y)

        return Location(
            point=Point(self.x + dx, self.y + dy, 0),
            resource=self,
        )

    def in_usable_space(self, location: Location, safety_margin: float = 0.90) -> bool:
        """
        Check if a point is inside the safe usable area.
        """

        self._validate_geometry()

        dx = location.point.x - self.x
        dy = location.point.y - self.y
        if self.shape == "circular":

            usable_radius = (self.diameter / 2) * safety_margin
            distance = math.sqrt(dx**2 + dy**2)
            return distance <= usable_radius

        half_x = (self.xDimension / 2) * safety_margin
        half_y = (self.yDimension / 2) * safety_margin

        return -half_x <= dx <= half_x and -half_y <= dy <= half_y

    def safe_move(self,start: Location,
                  x: float = 0,
                  y: float = 0,
                  safety_margin: float = 0.9,) -> Location:
        """
        Return a safe move destination inside the well.

        Circular and rectangular wells are corrected analytically.
        Any other geometry falls back to the iterative correction.
        """

        if not self.in_usable_space(start, safety_margin=safety_margin):
            raise ValueError("Start point is outside usable space.")

        finish = Location(
            Point(
                start.point.x + x,
                start.point.y + y,
                start.point.z,
            ),
            self,
        )

        if self.in_usable_space(finish,safety_margin=safety_margin):
            return finish

        if self.shape == "rectangular":
            #calcule des dimensions adapté pour un coin de réference x y z en bas a gauche
            xmin = self.x - safety_margin
            xmax = self.x + self.xDimension - safety_margin
            ymin = self.y + safety_margin
            ymax = self.y - self.yDimension + safety_margin

            scale = 1.0
            if x > 0:
                scale = min(scale, (xmax - start.point.x) / x)
            elif x < 0:
                scale = min(scale, (xmin - start.point.x) / x)
            if y > 0:
                scale = min(scale, (ymax - start.point.y) / y)
            elif y < 0:
                scale = min(scale, (ymin - start.point.y) / y)

            scale = max(0.0, scale)

            return Location(
                Point(
                    start.point.x + x * scale,
                    start.point.y + y * scale,
                    start.point.z,
                ),
                self,
            )

        if self.shape == "circular":

            cx = self.x
            cy = self.y
            r = (self.diameter / 2 ) * safety_margin

            sx = start.point.x - cx
            sy = start.point.y - cy

            dx = x
            dy = y

            a = dx * dx + dy * dy
            b = 2 * (sx * dx + sy * dy)
            c = sx * sx + sy * sy - r * r

            disc = b * b - 4 * a * c

            if disc >= 0:
                t = (-b + disc**0.5) / (2 * a)
                t = max(0.0, min(1.0, t))

                return Location(
                    Point(
                        start.point.x + dx * t,
                        start.point.y + dy * t,
                        start.point.z,
                    ),
                    self,
                )

        # ------------------------------------------------------------------
        # Fallback for arbitrary geometries
        # ------------------------------------------------------------------
        corrected_x = x
        corrected_y = y

        for _ in range(100):
            corrected_x *= 0.90
            corrected_y *= 0.90

            corrected_finish = Location(
                Point(
                    start.point.x + corrected_x,
                    start.point.y + corrected_y,
                    start.point.z,
                ),
                self,
            )

            if self.in_usable_space(corrected_finish, safety_margin=safety_margin):
                return corrected_finish

        raise ValueError("Unable to compute a valid safe move.")

    # ------------------------------------------------------------------
    # Tip state
    # ------------------------------------------------------------------

    def set_tip_state(
        self,
        has_tip: bool,
        clean_tip: bool | None = None,
    ) -> None:
        self.has_tip = has_tip

        if clean_tip is not None:
            self.clean_tip = clean_tip


@dataclass(slots=True, repr=False)
class WellSet:
    """
    Base collection of wells.
    """

    wells: Dict[str, Well] = field(default_factory=dict, kw_only=True)

    def __repr__(self):
        return f"{self.__class__.__name__}" f"({list(self.wells.keys())})"

    def __iter__(self) -> Iterator[Well]:
        return iter(self.wells.values())

    def __len__(self) -> int:
        return len(self.wells)

    def __contains__(self, well_id: str) -> bool:
        return well_id in self.wells

    def __getitem__(self, identifier: str | int | slice):
        if isinstance(identifier, str):
            return self.wells[identifier]

        if isinstance(identifier, int):
            return list(self.wells.values())[identifier]

        if isinstance(identifier, slice):
            return list(self.wells.values())[identifier]

        raise TypeError(f"Unsupported identifier: {type(identifier)}")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def get_well(self, well_id: str) -> Well:
        return self.wells[well_id]

    def get_wells(self) -> list[Well]:
        return list(self.wells.values())


@dataclass(slots=True, repr=False)
class Row(WellSet):
    identifier: str = ""


@dataclass(slots=True, repr=False)
class Column(WellSet):
    identifier: int = 0


@dataclass(slots=True, repr=False)
class Labware(WellSet):
    """
    Runtime representation of a labware.
    """

    labware_filename: str

    offset: tuple[float, ...] | None = None
    order: str = "rows"

    path: str = os.path.join(
        os.path.dirname(__file__),
        "labware_definition",
    )

    # Runtime state

    data: dict = field(init=False, default_factory=dict)
    config_path: str = field(init=False)

    wells_data: dict = field(
        init=False,
        default_factory=dict,
    )

    row_data: Dict[str, Row] = field(
        init=False,
        default_factory=dict,
    )

    column_data: Dict[int, Column] = field(
        init=False,
        default_factory=dict,
    )

    slot: str | None = field(
        init=False,
        default=None,
    )

    manual_offset: dict = field(
        init=False,
        default_factory=dict,
    )

    # ------------------------------------------------------------------
    # Init
    # ------------------------------------------------------------------

    def __post_init__(self):
        if self.order.lower() not in {
            "rows",
            "row",
            "r",
            "columns",
            "column",
            "col",
            "c",
        }:
            raise ValueError(f"Invalid order: {self.order}")

        filename = self.labware_filename

        if not filename.endswith(".json"):
            filename += ".json"

        self.config_path = os.path.join(
            self.path,
            filename,
        )

        with open(self.config_path, "r") as file:
            self.data = json.load(file)

        self.wells_data = self.data.get("wells", {})

        (
            self.row_data,
            self.column_data,
            self.wells,
        ) = self._create_rows_and_columns()

        self.with_well_order(self.order)

        if self.offset is not None:
            self.apply_offset(self.offset)

        self.manual_offset = self.data.get(
            "manual_offset",
            {},
        )

    def __repr__(self):
        display = f"Labware({self.load_name}"

        if self.slot is not None:
            display += f", slot={self.slot}"

        display += ")"

        return display

    # ------------------------------------------------------------------
    # Metadata
    # ------------------------------------------------------------------

    @property
    def metadata(self):
        return self.data.get("metadata", {})

    @property
    def parameters(self):
        return self.data.get("parameters", {})

    @property
    def dimensions(self):
        return self.data.get("dimensions", {})

    @property
    def ordering(self):
        return np.array(self.data["ordering"]).T

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
    def is_tip_rack(self):
        return self.parameters["isTiprack"]

    @property
    def shape(self):
        return (len(self.row_data), len(self.column_data))

    # ------------------------------------------------------------------
    # Runtime helpers
    # ------------------------------------------------------------------

    def apply_offset(self, offset: tuple[float, ...]) -> None:
        self.offset = offset

        for well in self:
            well.apply_offset(offset)

    def add_slot(self, slot: str) -> None:
        self.slot = slot

        for well in self:
            well.slot = slot

    # ------------------------------------------------------------------
    # Accessors
    # ------------------------------------------------------------------

    def get_row(self, row_id: str) -> Row:
        return self.row_data[row_id]

    def get_column(self, column_id: int) -> Column:
        return self.column_data[column_id]

    # ------------------------------------------------------------------
    # Ordering
    # ------------------------------------------------------------------

    def with_well_order(self, order: str) -> None:
        ordered_wells = {}

        if order.lower().startswith("row") or order.lower() == "r":

            for well in chain(*self.row_data.values()):
                ordered_wells[well.name] = well

        else:

            for well in chain(*self.column_data.values()):
                ordered_wells[well.name] = well

        self.wells = ordered_wells

    # ------------------------------------------------------------------
    # Builders
    # ------------------------------------------------------------------

    def _create_rows_and_columns(self):
        rows = {}
        columns = {}
        wells = {}

        for column_data in self.ordering:

            row_id = column_data[0][0]

            if row_id not in rows:
                rows[row_id] = {}

            for col_index, well_id in enumerate(column_data):

                well = Well(
                    name=well_id,
                    **self.wells_data[well_id],
                )

                rows[row_id][well_id] = well

                column_id = col_index + 1

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

        rows = {key: Row(identifier=key, wells=value) for key, value in rows.items()}

        columns = {
            key: Column(identifier=key, wells=value) for key, value in columns.items()
        }

        return rows, columns, wells

    # ------------------------------------------------------------------
    # Geometry helpers
    # ------------------------------------------------------------------

    @staticmethod
    def nominal_coordinates(
        well: Well, x_spacing: float, y_spacing: float
    ) -> tuple[float, float]:

        col_index = int(well.name[1:]) - 1
        row_index = list(string.ascii_uppercase).index(well.name[0])

        return (
            col_index * x_spacing,
            row_index * y_spacing,
        )

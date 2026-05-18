import json
import os
from typing import Dict, Iterator

from attrs import Factory, define, field, validators

from science_jubilee.labware.Labware import Labware, Well


@define(slots=True, repr=False)
class Slot:
    """
    Représente un slot physique du deck.
    """

    slot_index: str

    offset: tuple[float, ...]

    has_labware: bool = False

    labware: Labware | None = None

    @property
    def is_empty(self) -> bool:
        return self.labware is None

    def load_labware(self, labware: Labware) -> None:

        self.labware = labware
        self.has_labware = True

    def unload_labware(self) -> None:

        self.labware = None
        self.has_labware = False

    def get_labware(self) -> Labware:

        if self.labware is None:
            raise ValueError(
                f"No labware loaded in slot {self.slot_index}"
            )

        return self.labware

    def get_well(self, well_id: str) -> Well:

        return self.get_labware().get_well(well_id)

    def __repr__(self):

        if self.labware is None:
            return f"Slot({self.slot_index}, empty)"

        return (
            f"Slot("
            f"{self.slot_index}, "
            f"labware={self.labware.load_name}"
            f")"
        )


@define(slots=True, repr=False)
class SlotSet:
    """
    Collection orientée domaine de slots.
    """

    slots: Dict[str, Slot] = field(factory=dict)

    def __iter__(self) -> Iterator[Slot]:
        return iter(self.slots.values())

    def __len__(self) -> int:
        return len(self.slots)

    def __contains__(self, slot_id: str) -> bool:
        return slot_id in self.slots

    def __getitem__(self, identifier):

        if isinstance(identifier, str):
            return self.get_slot(identifier)

        if isinstance(identifier, int):
            return list(self.slots.values())[identifier]

        raise TypeError(
            f"Unsupported identifier type: {type(identifier)}"
        )

    def __repr__(self):

        return (
            f"SlotSet("
            f"slots={list(self.slots.keys())}"
            f")"
        )

    def get_slot(self, slot_id: str) -> Slot:

        return self.slots[slot_id]

    def get_slots(self) -> list[Slot]:

        return list(self.slots.values())

    def get_labware(self, slot_id: str) -> Labware:

        return self.get_slot(slot_id).get_labware()

    def get_well(
        self,
        slot_id: str,
        well_id: str,
    ) -> Well:

        return self.get_slot(slot_id).get_well(well_id)

    def has_labware(self, slot_id: str) -> bool:

        return not self.get_slot(slot_id).is_empty


@define(slots=True, repr=False)
class Deck(SlotSet):
    """
    Représente l’état runtime du deck.
    """

    deck_filename: str

    path: str = field(
        default=os.path.join(
            os.path.dirname(__file__),
            "deck_definition",
        )
    )

    deck_config: dict = field(init=False, factory=dict)

    slots_data: dict = field(init=False, factory=dict)

    safe_z: float = field(default=10.0)

    config_path: str = field(init=False)

    @safe_z.validator
    def validate_safe_z(self, attribute, value):

        if value < 0:
            raise ValueError(
                "safe_z must be positive"
            )

    def __attrs_post_init__(self):

        filename = self.deck_filename

        if not filename.endswith(".json"):
            filename += ".json"

        self.config_path = os.path.join(
            self.path,
            filename,
        )

        with open(self.config_path, "r") as f:
            self.deck_config = json.load(f)

        self.slots_data = self.deck_config.get(
            "slots",
            {},
        )

        self.slots = self._create_slots()

    def __repr__(self):

        return (
            f"Deck("
            f"bed_type={self.bed_type}, "
            f"slots={len(self.slots)}"
            f")"
        )

    @property
    def bed_type(self) -> str:

        return self.deck_config.get(
            "bedType",
            "",
        )

    @property
    def total_slots(self) -> int:

        deck_slots = self.deck_config.get(
            "deckSlots",
            {},
        )

        return deck_slots.get("total", 0)

    @property
    def slot_type(self) -> str:

        deck_slots = self.deck_config.get(
            "deckSlots",
            {},
        )

        return deck_slots.get("type", "")

    @property
    def offset_from(self) -> str:

        return self.deck_config.get(
            "offsetFrom",
            "",
        )

    @property
    def deck_material(self) -> dict:

        return self.deck_config.get(
            "material",
            {},
        )

    def update_safe_z(self, z_height: float) -> None:

        if z_height > self.safe_z:
            self.safe_z = z_height

    def load_labware(
        self,
        labware_filename: str,
        slot_id: str,
        path=os.path.join(
            os.path.dirname(__file__),
            "..",
            "labware",
            "labware_definition",
        ),
        order: str = "rows",
    ) -> Labware:

        slot = self.get_slot(str(slot_id))

        labware = Labware(
            labware_filename,
            order=order,
            path=path,
        )

        labware.add_slot(slot_id)

        labware.apply_offset(slot.offset)

        slot.load_labware(labware)

        self.update_safe_z(
            labware.dimensions["zDimension"]
        )

        return labware

    def unload_labware(self, slot_id: str) -> None:

        slot = self.get_slot(str(slot_id))

        slot.unload_labware()

    def _create_slots(self) -> Dict[str, Slot]:

        slots = {}

        for slot_id, slot_data in self.slots_data.items():

            offset = slot_data.get("offset", ())

            if isinstance(offset, list):
                offset = tuple(offset)

            slots[slot_id] = Slot(
                slot_index=slot_id,
                offset=offset,
                has_labware=slot_data.get(
                    "has_labware",
                    False,
                ),
            )

        return slots

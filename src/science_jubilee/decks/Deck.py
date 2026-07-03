import json
import os
from dataclasses import dataclass, field
from typing import Dict, Iterator

from science_jubilee.labware.Labware import Labware, Well


@dataclass(slots=True, repr=False)
class Slot:
    """
    Represents a physical deck slot.
    """

    slot_index: str
    offset: tuple[float, ...]

    has_labware: bool = False
    labware: Labware | None = None

    def __repr__(self):
        if self.labware is None:
            return f"Slot({self.slot_index}, empty)"

        return (
            f"Slot("
            f"{self.slot_index}, "
            f"labware={self.labware.load_name}"
            f")"
        )

    # ------------------------------------------------------------------
    # State
    # ------------------------------------------------------------------

    @property
    def is_empty(self) -> bool:
        return self.labware is None

    # ------------------------------------------------------------------
    # Runtime
    # ------------------------------------------------------------------

    def load_labware(self, labware: Labware) -> None:
        self.labware = labware
        self.has_labware = True

    def unload_labware(self) -> None:
        self.labware = None
        self.has_labware = False

    # ------------------------------------------------------------------
    # Accessors
    # ------------------------------------------------------------------

    def get_labware(self) -> Labware:
        if self.labware is None:
            raise ValueError(
                f"No labware loaded in slot {self.slot_index}"
            )

        return self.labware

    def get_well(self, well_id: str) -> Well:
        return self.get_labware().get_well(well_id)



@dataclass(slots=True, repr=False)
class SlotSet:
    """
    Domain collection of slots.
    """

    slots: Dict[str, Slot] = field(default_factory=dict, kw_only=True)

    def __repr__(self):
        return (
            f"{self.__class__.__name__}"
            f"({list(self.slots.keys())})"
        )


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

    # ------------------------------------------------------------------
    # Accessors
    # ------------------------------------------------------------------

    def get_slot(self, slot_id: str) -> Slot:
        return self.slots[slot_id]


    def get_slots(self) -> list[Slot]:
        return list(self.slots.values())


    def get_labware(self, slot_id: str) -> Labware:
        return self.get_slot(slot_id).get_labware()


    def get_well(self, slot_id: str, well_id: str) -> Well:
        return self.get_slot(slot_id).get_well(well_id)


    def has_labware_loaded(self, slot_id: str) -> bool:
        return not self.get_slot(slot_id).is_empty



@dataclass(slots=True, repr=False)
class Deck(SlotSet):
    """
    Runtime representation of a deck.
    """
    
    deck_filename: str
    path: str = os.path.join(os.path.dirname(__file__),"deck_definition",)

    safe_z: float = 10.0

    # Runtime state

    deck_config: dict = field(init=False,default_factory=dict)

    slots_data: dict = field(init=False,default_factory=dict)

    config_path: str = field(init=False)

    # ------------------------------------------------------------------
    # Init
    # ------------------------------------------------------------------

    def __post_init__(self):
        if self.safe_z < 0:
            raise ValueError(
                "safe_z must be positive"
            )

        filename = self.deck_filename

        if not filename.endswith(".json"):
            filename += ".json"

        self.config_path = os.path.join(self.path,filename)

        with open(self.config_path, "r") as file:
            self.deck_config = json.load(file)

        self.slots_data = self.deck_config.get("slots",{})

        self.slots = self._create_slots()

        labware = self.deck_config.get("")
    
    

    def __repr__(self):
        return (
            f"Deck("
            f"bed_type={self.bed_type}, "
            f"slots={len(self.slots)}"
            f")"
        )

    # ------------------------------------------------------------------
    # Metadata
    # ------------------------------------------------------------------

    @property
    def bed_type(self) -> str:
        return self.deck_config.get("bedType","")

    @property
    def total_slots(self) -> int:
        return self.deck_config.get("deckSlots",{}).get("total", 0)

    @property
    def slot_type(self) -> str:
        return self.deck_config.get("deckSlots",{}).get("type", "")

    @property
    def offset_from(self) -> str:
        return self.deck_config.get("offsetFrom","")

    @property
    def deck_material(self) -> dict:
        return self.deck_config.get("material",{})

    # ------------------------------------------------------------------
    # Runtime
    # ------------------------------------------------------------------

    def update_safe_z(self, z_height: float) -> None:
        if z_height > self.safe_z:
            self.safe_z = z_height


    def load_labware(self,labware_filename: str,slot_id: int,
        path=os.path.join(os.path.dirname(__file__),
            "..",
            "labware",
            "labware_definition",
        ),
        order: str = "rows",
    ) -> None:

        slot = self.get_slot(str(slot_id))

        labware = Labware(labware_filename,order=order,path=path)

        labware.add_slot(slot_id)

        labware.apply_offset(slot.offset)

        slot.load_labware(labware)

        self.update_safe_z(labware.dimensions["zDimension"])
        

    def unload_labware(self, slot_id: int) -> None:
        slot = self.get_slot(str(slot_id))
        slot.unload_labware()

    # ------------------------------------------------------------------
    # Builders
    # ------------------------------------------------------------------

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
            if slots[slot_id].has_labware == True :
                self.load_labware(labware_filename=slot_data.get("labware"),slot_id=slot_id)

        return slots
from __future__ import annotations

from abc import ABC
from dataclasses import dataclass, field
from uuid import UUID, uuid4

from science_jubilee.navigation.deck_navigation import DeckNavigator
from science_jubilee.hal.tool_changer import ToolChanger
from science_jubilee.labware.Labware import Well


from experiment.registry import Registry




# ======================================================
# Sequence of action - Node
# ======================================================
class ExperimentNode(ABC):
    """
        Classe mère de toutes les actions d'une expérience.
        Assemble les actions et les tasks en conservant l'ordre
    """
    name: str

    enabled: bool = True

# ======================================================
# Action
# ======================================================


@dataclass(frozen=True)
class Action(ExperimentNode):
    """
    Une Action est une description IMMUTABLE de ce qui devra être réalisé.
    Elle ne possède aucune logique d'exécution.
    """

    name: str

    simulate : bool

    id: UUID = field(default_factory=uuid4)

    enabled: bool = True    

# ======================================================
# Type of action
# ======================================================

@dataclass(frozen=True)
class MotionAction(Action):
    """Classe mère des actions de déplacement."""
    simulate = True
    nav: DeckNavigator

@dataclass(frozen=True)
class ToolAction(Action):

    """Toutes les actions liées au ToolChanger."""
    simulate = True


@dataclass(frozen=True)
class AcquisitionAction(Action):
    """
    Action de mesure.

    Elle sera ignorée lors de la validation du jumeau.
    """
    simulate = False


@dataclass(frozen=True)
class FlowAction(Action):
    """Actions de contrôle du déroulement."""
    simulate = False

#Ajouter EnvAction
#Ajouter ExternalAction

# ======================================================
# Motion action
# ======================================================

@Registry.register("home")
@Registry.register
@dataclass(frozen=True)
class Home(MotionAction):
    from science_jubilee.hal.motion_driver import MotionDriver
    axes: tuple[str, ...] = ("X", "Y", "Z")
    MotionDriver.home_all()

@Registry.register("move_to_well")
@dataclass(frozen=True)
class MoveToWell(MotionAction):
    
    well_name: str 
    slot_id: str
    speed_xy: float = None
    speed_z: float = None

    margin: float = None
    random: bool = False
    
    def compile(self):
        well = self.nav.get_well(slot_id=self.slot_id,well_id=self.well_name)
        self.nav.move_to_target( well=well,
                            speed_xy= self.speed_xy,
                            speed_z= self.speed_z,
                            margin= self.margin,
                            random= self.random)


@Registry.register("move_to_safe_z")
@dataclass(frozen=True)
class MoveToSafeZ(MotionAction):
    margin: float | None = None
    speed: float | None = None

    def compile(self):
        self.nav.move_to_safe_z(margin= self.margin, speed= self.speed)

@Registry.register("move_to_water_level")
@dataclass(frozen=True)
class MoveToWaterLevel():

    well_name: str 
    slot_id: str

    surface: bool = False
    speed_z: float = None

    def compile(self):
        well = self.nav.get_well(slot_id=self.slot_id,well_id=self.well_name)
        self.nav.move_to_water_level(well=well,surface=self.surface,speed_z=self.speed_z)

@Registry.register("move_inside_well")
@dataclass(frozen=True)
class MoveInsideWell():

    well_name: str 
    slot_id: str

    x:float
    y:float
    speed_xy:float | None = None

    def compile(self):
        well = self.nav.get_well(slot_id=self.slot_id,well_id=self.well_name)
        self.nav.xy_move_inside_well(well=well, x=self.x, y=self.y, speed_xy=self.speed_xy)


# ======================================================
# Tool action
# ======================================================
@Registry.register("pickup_tool")
@dataclass(frozen=True)
class PickupTool(ToolAction):
    tool_name: str

@Registry.register
@dataclass(frozen=True)
class ParkTool(ToolAction):
    tool_name: str

@Registry.register
@dataclass(frozen=True)
class ActivateTool(ToolAction):
    tool_name: str

#Attention ce ne sont que les action liées aux tool changer qui sont placé ici
#Pour les acitons des modules externes utilisé la classe ExternalAction

# ======================================================
# Acquisition action
# ======================================================
@Registry.register
@dataclass(frozen=True)
class CaptureImage(AcquisitionAction):

    camera: str

    filename: str | None = None

@Registry.register
@dataclass(frozen=True)
class AcquireSpectrum(AcquisitionAction):

    spectrometer: str

    integration_time: float

#Tout les actions des capteurs de la Jubilee doivent être développé ici

# ======================================================
# Flow action
# ======================================================
@Registry.register
@dataclass(frozen=True)
class Pause(FlowAction):

    reason: str = ""


@Registry.register
@dataclass(frozen=True)
class Wait(FlowAction):

    duration: float

@Registry.register
@dataclass(frozen=True)
class UserConfirmation(FlowAction):

    message: str

#ajouter d'autre classe pour la gestion d'une expérience


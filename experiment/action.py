from __future__ import annotations

from abc import ABC
from dataclasses import dataclass, field
from uuid import UUID, uuid4

from science_jubilee.navigation.deck_navigation import DeckNavigator


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
    from science_jubilee.hal.tool_changer import ToolChanger

    """Toutes les actions liées au ToolChanger."""
    simulate = True
    tool_changer = ToolChanger

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

@dataclass(frozen=True)
class EnvAction(Action):
    """Variation de l'environnement de la Jubilee."""
    simulate = False

#Ajouter EnvAction
#Ajouter ExternalAction

# ======================================================
# Motion action
# ======================================================

@Registry.register("home_all")
@Registry.register
@dataclass(frozen=True)
class HomeAll(MotionAction):

    def compile(self):
        from science_jubilee.hal.motion_driver import MotionDriver
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

@Registry.register("move_inside_well")
@dataclass(frozen=True)
class MoveInsideWell():

    well_name: str 
    slot_id: str

    x: float = None
    y: float = None
    z: float = None
    
    speed_xy:float = None
    speed_z: float = None

    def compile(self):
        well = self.nav.get_well(slot_id=self.slot_id,well_id=self.well_name)
        self.nav.move_inside_well(well=well,
                                  x= self.x,
                                  y= self.y, 
                                  z = self.z, 
                                  speed_xy =self.speed_xy,
                                  speed_z=self.speed_z)


# ======================================================
# Tool action
# ======================================================
@Registry.register("pickup_tool")
@dataclass(frozen=True)
class PickupTool(ToolAction):
    tool_index: str
    def compile(self):
        self.tool_changer.pickup_tool(int(self.tool_index))

@Registry.register("park_tool")
@dataclass(frozen=True)
class ParkTool(ToolAction):
    def compile(self):
        self.tool_changer.park_tool()
#Attention ce ne sont que les action liées aux tool changer qui sont placé ici
#Pour les acitons des modules externes utilisé la classe ExternalAction

# ======================================================
# Acquisition action
# ======================================================
@Registry.register("Capture_image")
@dataclass(frozen=True)
class CaptureImage(AcquisitionAction):
    from science_jubilee.tools.Observer import Camera
    cam: Camera
    
    def compile(self):
        self.cam.save_image()
    

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

# ======================================================
# Environnemental action
# ======================================================

@Registry.register("pixel_on")
@dataclass(frozen=True)
class PixelOn(EnvAction):
    from science_jubilee.tools.Observer import Neopixel
    led_ring : Neopixel
    led_index : str
    r : float
    g : float
    b : float
    def compile(self):
        self.led_ring.pixel_on(led_index=self.led_index,r=self.r,g=self.g,b=self.b)

@Registry.register("pixel_off")
@dataclass(frozen=True)
class PixelOff(EnvAction):
    from science_jubilee.tools.Observer import Neopixel
    led_ring : Neopixel
    led_index : str

    def compile(self):
        self.led_ring.pixel_off(led_index=self.led_index)

@Registry.register("all_pixel_on")
@dataclass(frozen=True)
class AllPixelOn(EnvAction):
    from science_jubilee.tools.Observer import Neopixel
    led_ring : Neopixel
    r : float
    g : float
    b : float

    def compile(self):
        self.led_ring.all_pixel_on(r=self.r,g=self.g,b=self.b)

        
@Registry.register("all_pixel_off")
@dataclass(frozen=True)
class AllPixelOff(EnvAction):
    from science_jubilee.tools.Observer import Neopixel
    led_ring : Neopixel

    def compile(self):
        self.led_ring.all_pixel_off()

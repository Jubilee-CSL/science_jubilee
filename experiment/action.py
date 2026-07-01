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

    metadata: dict
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

    metadata: dict = field(default_factory=dict)
    

# ======================================================
# Type of action
# ======================================================

@dataclass(frozen=True)
class MotionAction(Action):
    """Classe mère des actions de déplacement."""
    simulate = True

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
@Registry.register
@dataclass(frozen=True)
class MoveToTarget(MotionAction):

    target: nav.deck.

    speed_xy: float = 6000

    speed_z: float = 4000

    travel_margin: float = 5

    safe_motion: bool = True
    
    def compile(self,nav: DeckNavigator):
        nav.move_to_target(x,x)

@Registry.register
@dataclass(frozen=True)
class Home(MotionAction):

    axes: tuple[str, ...] = ("X", "Y", "Z")

@Registry.register
@dataclass(frozen=True)
class SafeZ(MotionAction):

    z: float

#Ajouter d'autre classe de mouvement exemple Sweep

# ======================================================
# Tool action
# ======================================================
@Registry.register
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


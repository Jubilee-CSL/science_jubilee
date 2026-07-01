from dataclasses import dataclass

from experiment.task import Task
from experiment.plan import ExecutionPlan
from experiment.action import MoveTo
from experiment.action import Wait

from experiment.registry import Registry




#Exemple de contruction de tache
#Dans un cas réel les coordonnées seront obtenue a partir de DeckNavigation
#les coordonnées étant des paramètres on peux y placé n'importe quoi

@dataclass
@Registry.register("transfer_lens")
class TransferLens(Task):

    source: str = ""
    destination: str = ""
    speed: float = 4000

    required_tools=["Inoculator"],

    required_modules=["DeckNavigator"]

    def compile(self, plan: ExecutionPlan):
        plan.add(
            MoveTo(name="Approche source",x=120,y=50,z=10,speed_xy=self.speed))

        plan.add(
            Wait(name="Stabilisation",duration=0.5))
        
        plan.add(
            MoveTo(name="Approche destination",x=180,y=70,z=10,speed_xy=self.speed)
        )
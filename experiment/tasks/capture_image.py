from dataclasses import dataclass

from experiment.task import Task
from experiment.plan import ExecutionPlan
from experiment.action import CaptureImage


#Exemple d'une action qui sera ignoré par le jumeau numérique

@dataclass
class ImageTask(Task):

    camera: str = "Top"

    filename: str | None = None

    def compile(self, plan: ExecutionPlan):

        plan.add(
            CaptureImage(name="Image",camera=self.camera,filename=self.filename)
        )
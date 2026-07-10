from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from experiment.plan import ExecutionPlan, ExecutionBundle
from experiment.action import Action
from experiment.task import Task
from experiment.experience import Experience

import glob
import os
import subprocess

class ExperimentCompiler:
    """
    Compile une Experiment en deux ExecutionPlan.

    - plan_complete : toutes les actions.
    - plan_mock : uniquement les actions simulables.
    """

    def compile(self, experiment):

        complete = ExecutionPlan(name=experiment.name,
                                 parameters=experiment.parameters.copy(),)

        mock = ExecutionPlan(name=experiment.name + "_mock",
                             parameters=experiment.parameters.copy(),)

        for node in experiment.sequence:
            if not node.enabled:
                continue

            # -----------------------------
            # Compilation des Tasks et Action 
            # -----------------------------

            if isinstance(node, Task):
                actions = node.compile()

            elif isinstance(node, Action):
                actions = [node]

            else:
                raise TypeError(f"{type(node)} is not a valid ExperimentNode")

            for action in actions:
                complete.add(action)

                if action.simulate:
                    mock.add(action)

        return ExecutionBundle(complete=complete,mock=mock,)

class HardwareExecutor:
    """
    Exécute le plan complet sur la Jubilee.
    """

    def execute(self, run: ExperimentRun) -> ExperimentRun:

        if run.execution is None:
            raise RuntimeError("Experiment has not been compiled.")

        if not run.validated:
            raise RuntimeError(
                "Digital Twin validation failed."
            )

        plan = run.execution.complete

        run.state = "HARDWARE_RUNNING"

        for action in plan:

            action.execute()

        run.state = "FINISHED"

        return run
        
class DigitalTwin:

    def validate(self, run: ExperimentRun):

        script_name = "run_latest_gcode_animation.bat"
        search_dir = Path(__file__).resolve().parent.parent.parent / "jubilee-blender-twin" / "from_gcode"

        matches = glob.glob(
            os.path.join(search_dir, "**", script_name),
            recursive=True
        )

        if not matches:
            raise FileNotFoundError(f"No script matching '{script_name}' found under {search_dir}")

        script_path = matches[0]
        script_dir = os.path.dirname(os.path.abspath(script_path))

        process = subprocess.Popen(
            [script_path],
            cwd=script_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        stdout, stderr = process.communicate()
        
        if stderr:
            print(f"STDERR:\n{stderr}")

        run.validated = True

        return run
    
class MockExecutor:

    def execute(self, run: ExperimentRun) -> ExperimentRun:

        if run.execution is None:
            raise RuntimeError("Experiment has not been compiled.")

        plan = run.execution.mock

        run.state = "MOCK_RUNNING"

        for action in plan:

            action.execute()

        run.state = "MOCK_FINISHED"

        return run
    

@dataclass
class ExperimentRun:
    """
    Représente une exécution complète d'une expérience.
    """

    experiment: Experience

    config: dict = field(default_factory=dict)

    deck_config: dict = field(default_factory=dict)

    execution: ExecutionBundle | None = None

    validated: bool = False

    validation_message: str = ""

    artifacts: list[Path] = field(default_factory=list)

    results: dict = field(default_factory=dict)

    state: str = "CREATED"

    metadata: dict = field(default_factory=dict)

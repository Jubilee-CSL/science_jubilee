from sacred import Experiment
from sacred.observers import MongoObserver

from experiment.loader import ExperimentLoader
from experiment.run import ExperimentCompiler, MockExecutor, HardwareExecutor, DigitalTwin

from experiment.run import ExperimentRun

# -----------------------------------------------------

ex = Experiment("science_jubilee")

observer = MongoObserver(url="mongodb://localhost:27017",db_name="science_jubilee")
ex.observers.append(observer)

# -----------------------------------------------------

@ex.config
def config():

    experiment_file = "configs/experiment.json"
    deck_file = "configs/deck.json"

# -----------------------------------------------------

@ex.automain

def run(_run,experiment_file,deck_file):

    experiment,deck = ExperimentLoader.load(experiment_file,deck_file,)

    run = ExperimentRun(
        experiment=experiment,
        config={"experiment": experiment_file,"deck": deck_file,},
        deck_config=deck)

    compiler = ExperimentCompiler()
    run.execution = compiler.compile(run.experiment)

    mock = MockExecutor()
    mock.execute(run.execution.mock)
    
    twin = DigitalTwin()

    validation = twin.validate("latest_log.gcode")

    run.validated = validation.valid
    run.validation_message = validation.message

    if not validation.valid:
        raise RuntimeError(validation.message)
    
    hardware = HardwareExecutor()

    hardware.execute(run.execution.complete)

    for name, value in run.results.items():
        _run.log_scalar(name, value)

    for artifact in run.artifacts:
        _run.add_artifact(str(artifact))


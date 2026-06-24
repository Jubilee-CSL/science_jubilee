"""
Une expérience a pour but de construire un ensemble de données ou d'observation
les données seront pris par des outils ou des obersvateurs
Ajouter des template pour les outils, suffisament de paramètres ?

Utilisation de MongoDB et Altar
Le nom des fichier et des dossiers a une importance, 
une exp pouvant être réaliser sous diff param

structure des expériences
Experiments
    Exp1
        set_de_param1
        ...
    ...

Pour une utiisation avec l'interface graphique
les param seront envoyé en format json par l'interface
Lancement automatique depuis l'interface

Chaque expéricnece devrait être validé par le jumeau
les paramètres d'expérience feront varié les mvt ? je pense pas

Format 
IMPORTS

from sacred.observers import MongoObserver
from sacred import Experiment

ex = Experiment(" Experiment ")
observer = MongoObserver(mong_uri = "mongodb://localhost:27017,
                                    db_name='demo')

ex.observer.append(observer)

@ex.config
def config():
    PARAMETERS

@ex.automain
def run():
    MAIN COMPUTATIONS
    for i in rand(len( DATA )):
        _run.log_scalar(" DATA_NAME ",DATA)

    SAVE_RESULTS
    _run.add_artifact(save_folder + "DATA_PLOT","DATA_PLOT")



"""
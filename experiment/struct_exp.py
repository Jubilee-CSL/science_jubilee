"""
Une expérience a pour but de construire un ensemble de données ou d'observation
Chaque expérience aura un accès spécifique aux classes
Par défault Deck navigation et Tool_changer
possibilité d'ajouter des outils et des observers/capteurs
les données seront récupérer par des taches des outils ou des obersvateurs
Ajouter des taches avec suffisament de paramètres pour les outils

Lors d'une expérience on réalise un enchainement de taches distinctes
Les taches sont des fonctions uniques des outils, même si certaines fonctions se ressemble.

Ou alors les taches utilisent les fonctions des outils, 
peut être plus intéressant pour facilité et la comprehension du code ???
Pour un utilisateur, il choisit ou construit son expérience avec des taches.

Class mère Task(ABC):
    Class fille Place(Task):
            import Inoculator
                fonction de tranfer des objets de l'expérience

Le développeur créera son outils, puis la tache associé, pour l'instant tout est dans la classe de l'outil.

Utilisation de MongoDB et Altar
Le nom des fichier et des dossiers a une importance,
Les variantes de config peuvent être ajouté dans la commande
une exp pouvant être réaliser sous diff param

structure des expériences
Experiments
    Launch_exp      récupère les param et le deck choisie depuis l'interface 
                    charge le deck et lance la commande pour l'exp associé en mock puis en hardware
    Exp1
    ...

Pour une utilisation avec l'interface graphique.
les param seront envoyé en format json par l'interface 
Dans ce fichier l'expérience choisie sera lue par Launch_exp
Remplacer deck_config par exp_config 

l'expirence en mock doit skip la prise de données, 1 expérience 2 fichiers: mock et hardware
ou alors les fonctions de prise de données doivent être classé pour ne s'activer que aux moment du hardware
Les mouvements qui dépendent de mesure sont imprévisible avant l'exp donc le jumeau ne peux pas les valider
Si on utilise des tasks ou pourrait plus facilement isolé le hardware du mock.

Le deck et les labwares représentes des paramètres
récupérer leurs infos via leur fichiers deck_config

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
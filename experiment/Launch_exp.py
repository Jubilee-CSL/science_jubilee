"""
Mettre en place un système de commande 

Une expérience a pour but de construire un ensemble de données ou d'observation
Chaque expérience aura un accès spécifique aux taches existante
Par défault chaque tache auras accès au Deck navigation, Tool_changer et a un tool associé a la tache
possibilité d'ajouter des outils et des observers/capteurs
les données seront récupérer par des taches des outils ou des obersvateurs
Ajouter des taches avec suffisament de paramètres pour les outils

Lors d'une expérience on réalise un enchainement de taches distinctes
Les taches sont des fonctions composée d'un outil, de mouvement machine et de module externe si il existe.

Pour un utilisateur, il choisit ou construit son expérience avec des taches.

Class mère Task(ABC):
    Class fille Place(Task):
            import Inoculator
                fonction de tranfer des objets de l'expérience

Le développeur créera son outils, puis la tache associée.


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

Le deck et les labwares représentes des paramètres
récupérer leurs infos via leur fichiers deck_config

"""
class Exp_launcher:
    """
    Lancé la commande pour le mock, ce dernier ne doit réaliser que les mvt, aucune prise de données
    Utilise la fonction du jumeau numérique 
    Demande une intervention humaine ou lance la commande pour le hardware
    puis crée l'expérience et lance l'enchainement des tasks
    """
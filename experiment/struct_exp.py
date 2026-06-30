"""
Pour construire l'expérience

Utilisation de MongoDB et Altar
Le nom des fichier et des dossiers a une importance,
Les variantes de config peuvent être ajouté dans la commande
une exp pouvant être réaliser sous diff param

l'expérience en mock doit skip la prise de données, 1 expérience 2 lancement: mock et hardware

"""
from experiment.task import Task
import time

class Experiment:
    tasks : list
    env : bool = True #mock ou hardware
    parameter : dict 
    duration : time
    state: enumerate #en pause, en cours, erreur, finie, prêt au démarrage
    exp_name : str


    def exec_task(self, task) -> bool:
        #réalise la tache sélectionné

        return True 
    
    def pause(self) -> None:
        #permet de s'arreter entre 2 tasks
        print("pause")

    def resume(self) -> None :
        #relance l'expérience après une pause
        print("resume")
        
    def end(self) -> bool:
        #mettre fin avant l'exécution de toute les taches présentes dans la liste
        #cette fonction doit nettoyer tout
        return True
    
    def add_task(self):
        
    def supp_task(self):

    def state(self) -> None:
        #montre a l'utilisateur la tache en cours et l'avancé de l'ensemble de l'expérience
        print("lol")
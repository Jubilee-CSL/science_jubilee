
class Task(ABC):
    from science_jubilee.navigation.deck_navigation import DeckNavigator
    from science_jubilee.hal import tool_changer

    env: bool = True #mock ou hardware
    state: enumerate #en cours, en pause ,finis, error
    parameter: dict
    navigateur: DeckNavigator
    #ajouter les fonctions génériques ici
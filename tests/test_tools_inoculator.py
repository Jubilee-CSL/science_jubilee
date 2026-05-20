import logging
import pytest

logger = logging.getLogger(__name__)

from science_jubilee.navigation import DeckNavigator
#Il faut importer et passé Motion Driver en paramètres 
#pour initialiser Deck Navigator
#possiblement plusieurs driver différent ?
#si Motion driver est le seul driver pourquoi ne pas le placé par défault ?

"""
Tests à réaliser sur tous les outils 
Sécurité du décorateur 
Sécurité des potentiels prérequis (fonction possible)

Tests à réaliser sur l'Inoculator
Sécurité sur le randomize pickup(fonctionnalité qui risque de changer)
Si réussite sur un transfert, pas besoin de tester tout les puits ?

Tests à réaliser sur la naviguation 
Une fois un puit donnée s'assurer que la coordonnée soit dans l'espace du puits

"""
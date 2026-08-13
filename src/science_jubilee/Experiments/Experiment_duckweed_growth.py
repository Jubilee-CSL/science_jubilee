import logging
import os
import sys

from science_jubilee._paths import jubilee_dir

REPO_ROOT = jubilee_dir()
SRC_ROOT = REPO_ROOT / "src"

for path in (SRC_ROOT, REPO_ROOT):
    path_str = str(path)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)


from science_jubilee.decks.Deck import Deck
from science_jubilee.hal.motion_driver import MotionDriver

# import science-jubilee-interface.interface_graphique.main as interface
from science_jubilee.hal.tool_changer import ToolChanger
from science_jubilee.hal.transport.http import HTTPTransport
from science_jubilee.navigation.deck_navigation import DeckNavigator

LED_SERVER = "http://10.0.9.55:5001"

logger = logging.getLogger(__name__)
# Initalization
transport = HTTPTransport(address="10.0.9.6")
driver = MotionDriver(transport)
tool_changer = ToolChanger(transport)
deck = Deck(os.getenv("JUBILEE_DECK_DEF", "lab_automation_deck_AFL_bolton.json"))
nav = DeckNavigator(driver, deck=deck)

# Experiment of taking duckweeds from a vase and then distributing all of them to a labware

transport = HTTPTransport(address="10.0.9.6")
driver = MotionDriver(transport)
tool_changer = ToolChanger(transport)

# We are first going to create positions of the Labware by asking the user the emplacementns where he would like to place its labware

print("Place the labware that you are willing to use on the deck ")
# interface.App()

deck = Deck(os.getenv("JUBILEE_DECK_DEF", "experiment_test.json"))
navigator = DeckNavigator(driver, deck=deck)
# Todo: recuperation des informations de labware graçe au fichier enregistré par interface.app,

count = 0
labware = navigator.get_labware_in_slot(0)

duckweed_wel = navigator.get_labware_in_slot(1)[0]
wel_center = duckweed_wel.x, duckweed_wel.z
for well in labware:
    # Jubilee_Duckweed_Tracker.main(x=duckweed_wel.x,y=duckweed_wel.y z= duckweed_well.depth,well=duckweed_wel)
    navigator.move_to_well(well, speed_xy=6000.0, speed_z=1000.0, margin=10)
    navigator.move_inside_well(well, z=200, speed=1000)
    navigator.move_to_well(well=well, speed_xy=800)
    navigator.move_inside_well(x=+3, y=-3, speed=1000)
    navigator.move_inside_well(z=200, speed=3000)
    count += 1

assert count == len(labware.wells)

# then we are going to extract each duckweed from the vase to the wells on the labware

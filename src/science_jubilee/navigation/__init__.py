"""High-level navigation utilities: moving across decks, labware, and wells.

This package provides helpers that sit *above* the HAL MotionDriver and
*alongside* the deck/labware geometry code. It is intentionally free of any
transport details; all motion goes through a MotionDriver instance.

Typical usage:

- construct a MotionDriver (mock or hardware transport)
- load a Deck and one or more Labware objects onto slots
- create a DeckNavigator(driver, deck, labware_by_slot)
- use DeckNavigator.move_to_well(...) to visit wells safely one by one
"""

from .deck_navigation import DeckNavigator  # convenience re-export

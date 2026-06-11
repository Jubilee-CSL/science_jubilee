import logging
import os

import pytest

from science_jubilee.decks.Deck import Deck
from science_jubilee.hal.motion_driver import MotionDriver
from science_jubilee.navigation.deck_navigation import (
    DeckNavigator,
)

from science_jubilee.tools.Tool import (
    ToolStateError,
)

from science_jubilee.tools.unique_tools.Inoculator import (
    Inoculator,
)

logger = logging.getLogger(__name__)


@pytest.mark.secondary
def test_transfer(tool_changer):
    """
    Verify standard transfer.
    """

    initial_tools = tool_changer.get_tools()
    initial_offsets = tool_changer.get_tool_offsets()
    logger.info("tools: %s",tool_changer.tools)
    logger.info("Initial tools: %s",initial_tools,)
    logger.info("Initial offset: %s",initial_offsets)

    tool_by_index = tool_changer.get_tool(0)
    logger.info("tool: %s",tool_by_index)





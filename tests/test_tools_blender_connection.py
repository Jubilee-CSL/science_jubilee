from pathlib import Path

import pytest


@pytest.mark.primary
def test_blender(transport):
    script_name = "run_latest_gcode_animation.bat"
    search_dir = (
        Path(__file__).resolve().parent.parent.parent
        / "jubilee-blender-twin"
        / "from_gcode"
    )

    return_code = transport._inner.launch_twin(script_name, search_dir)
    assert return_code == 0, f"Blender script failed with return code {return_code}"

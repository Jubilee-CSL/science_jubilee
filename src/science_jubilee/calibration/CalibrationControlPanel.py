import functools

import ipywidgets as widgets

from science_jubilee.calibration.tool_gfiles import generate_tool_gfiles


# This will make a little control panel to help us align things
def make_control_panel(m):
    def create_expanded_button(description):
        return widgets.Button(
            description=description,
            button_style="warning",
            layout=widgets.Layout(height="auto", width="auto"),
        )

    def button_move(b, dx=0, dy=0):
        m.jog(x=dx, y=dy)

    control_panel = widgets.GridspecLayout(7, 7)

    # y buttons
    bp5y = create_expanded_button("-5mm")
    bp5y.on_click(functools.partial(button_move, dx=0, dy=-5))
    control_panel[0, 3] = bp5y

    bp1y = create_expanded_button("-1mm")
    bp1y.on_click(functools.partial(button_move, dx=0, dy=-1))
    control_panel[1, 3] = bp1y

    bppt1y = create_expanded_button("-.1mm")
    bppt1y.on_click(functools.partial(button_move, dx=0, dy=-0.1))
    control_panel[2, 3] = bppt1y

    bmpt1y = create_expanded_button("+.1mm")
    bmpt1y.on_click(functools.partial(button_move, dx=0, dy=0.1))
    control_panel[4, 3] = bmpt1y

    bm1y = create_expanded_button("+1mm")
    bm1y.on_click(functools.partial(button_move, dx=0, dy=1))
    control_panel[5, 3] = bm1y

    bm5y = create_expanded_button("+5mm")
    bm5y.on_click(functools.partial(button_move, dx=0, dy=5))
    control_panel[6, 3] = bm5y

    # x buttons
    bp5x = create_expanded_button("-5mm")
    bp5x.on_click(functools.partial(button_move, dx=-5, dy=0))
    control_panel[3, 6] = bp5x

    bp1x = create_expanded_button("-1mm")
    bp1x.on_click(functools.partial(button_move, dx=-1, dy=0))
    control_panel[3, 5] = bp1x

    bppt1x = create_expanded_button("-.1mm")
    bppt1x.on_click(functools.partial(button_move, dx=-0.1, dy=0))
    control_panel[3, 4] = bppt1x

    bmpt1x = create_expanded_button("+.1mm")
    bmpt1x.on_click(functools.partial(button_move, dx=0.1, dy=0))
    control_panel[3, 2] = bmpt1x

    bm1x = create_expanded_button("+1mm")
    bm1x.on_click(functools.partial(button_move, dx=1, dy=0))
    control_panel[3, 1] = bm1x

    bm5x = create_expanded_button("+5mm")
    bm5x.on_click(functools.partial(button_move, dx=5, dy=0))
    control_panel[3, 0] = bm5x

    return control_panel


def make_parking_panel(
    nav, tool_number=0, *, x_park=0.0, y_park=0.0, y_clear=0.0, manhattan_offset=60.0
):
    """Widget panel to capture and write tool parking g-files.

    Jog the tool into position using make_control_panel, then use the
    Capture buttons here to record the coordinates and generate g-files.
    """
    _float_layout = widgets.Layout(width="100px")

    # ---- inputs --------------------------------------------------------
    w_tool = widgets.BoundedIntText(
        value=tool_number,
        min=0,
        max=9,
        description="Tool #:",
        style={"description_width": "60px"},
    )
    w_offset = widgets.FloatText(
        value=manhattan_offset,
        description="Manhattan offset (mm):",
        style={"description_width": "160px"},
    )

    # ---- park XY -------------------------------------------------------
    w_x_park = widgets.FloatText(
        value=x_park,
        description="X:",
        layout=_float_layout,
        style={"description_width": "20px"},
    )
    w_y_park = widgets.FloatText(
        value=y_park,
        description="Y:",
        layout=_float_layout,
        style={"description_width": "20px"},
    )
    btn_capture_park = widgets.Button(
        description="Capture Park XY",
        button_style="warning",
        layout=widgets.Layout(width="160px"),
    )

    def on_capture_park(_):
        pos = nav.get_position()
        w_x_park.value = round(float(pos["X"]), 3)
        w_y_park.value = round(float(pos["Y"]), 3)

    btn_capture_park.on_click(on_capture_park)

    # ---- Y-clear -------------------------------------------------------
    w_y_clear = widgets.FloatText(
        value=y_clear,
        description="Y:",
        layout=_float_layout,
        style={"description_width": "20px"},
    )
    btn_capture_clear = widgets.Button(
        description="Capture Y-Clear",
        button_style="warning",
        layout=widgets.Layout(width="160px"),
    )

    def on_capture_clear(_):
        pos = nav.get_position()
        w_y_clear.value = round(float(pos["Y"]), 3)

    btn_capture_clear.on_click(on_capture_clear)

    # ---- generate ------------------------------------------------------
    btn_generate = widgets.Button(
        description="Generate G-files",
        button_style="success",
        layout=widgets.Layout(width="160px"),
    )
    w_status = widgets.Output()

    def on_generate(_):
        w_status.clear_output()
        with w_status:
            try:
                files = generate_tool_gfiles(
                    w_tool.value,
                    x_park=w_x_park.value,
                    y_park=w_y_park.value,
                    y_clear=w_y_clear.value,
                    manhattan_offset=w_offset.value,
                    print_output=False,
                )
                folder = next(iter(files.values())).parent
                print(f"Files saved to:\n  {folder}\n")
                for path in files.values():
                    print(f"  {path.name}")
                print(
                    "\nTo upload to the Duet:\n"
                    "  DuetWebControl → System → upload each file to 0:/sys/\n"
                    "  Rename to remove the date folder (filenames are already correct)."
                )
            except Exception as exc:
                print(f"Error: {exc}")

    btn_generate.on_click(on_generate)

    # ---- layout --------------------------------------------------------
    park_row = widgets.HBox(
        [
            widgets.Label("Park XY:"),
            w_x_park,
            w_y_park,
            btn_capture_park,
        ]
    )
    clear_row = widgets.HBox(
        [
            widgets.Label("Y-Clear: "),
            w_y_clear,
            widgets.Label(""),  # spacer to align Capture button
            btn_capture_clear,
        ]
    )

    return widgets.VBox(
        [
            widgets.HBox([w_tool, w_offset]),
            widgets.HTML("<hr/>"),
            park_row,
            clear_row,
            widgets.HTML("<hr/>"),
            btn_generate,
            w_status,
        ]
    )

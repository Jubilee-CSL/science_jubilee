# Import necessary libraries
import numpy as np
import pygame

"""
PS4 Controller Code
This code allows you to control a machine using a PS4 controller. The code is written in Python and uses the Pygame library for handling the joystick events.

# Functions
3 movement levels for X,Y (different step sizes). Large steps: arrows. Medium steps: left joystick. Small steps: right joystick.
2 movement levels for Z: L1-R1: large movements, L2-R2 small movements.
button_event(event, step = 10): Handles button events for the PS4 controller.

joystick_event(event, step = 1): Handles joystick events for the PS4 controller. Left joystick has step of size step, right joystick has steps of size step/10.
assess_movement_range(m, xPos, yPos, zPos, dx, dy, dz): Assesses the movement range of the machine.
new_record(filename): Creates a new record file.
record_pos(m, filename): Records the current position of the machine.

make_PS4_control(m, filename): Main function to initialize the PS4 controller and handle the events.

# Control:
PS Button (event.button == 5): When the PS button is pressed, the joystick mode is exited.

## Move the toolhead
Arrows and joysticks (event.button == 9, 10, 11, 12, 13, 14): These buttons are used to move the machine along the X, Y, and Z axes. The direction of the movement depend on the button pressed and the magnitude depends on the setp size.
Joystick Movements (event.type == pygame.JOYAXISMOTION): The joystick movements are used to move the machine along the X, Y, and Z axes. The direction and magnitude of the movement depend on the joystick’s axis and value.

## Lock/Unlock tool
O Button (event.button == 1): When the O button is pressed, it unlocks the tool.
Triangle Button (event.button == 3): When the Triangle button is pressed, it locks the tool.

## Record positions while setting up a new tool
X Button (event.button == 0): When the X button is pressed, it records the clear tool position and sets m.y_clear to the current Y position.
Square Button (event.button == 2): When the Square button is pressed, it records the parked tool position and sets m.x_park and m.y_park to the current X and Y positions respectively.

## Recording a macro
Touch Pad Button (event.button == 15): When the Touch Pad button is pressed, it records the current position in a file by calling the record_pos(m, filename).


# Usage:
To use this code, you need to have the Pygame library installed in your Python environment.

Please note that this code is specifically designed for a PS4 controller. If you are using a different joystick, you may need to adjust the button and axis mappings accordingly. You can refer to the Pygame documentation for more information on joystick events.
"""

# This code is for a PS4 controller
# https://www.pygame.org/docs/ref/joystick.html for other joysticks


# Function to handle button events
def button_event(event, step=10):
    # Initialize movement array
    dmove = [0, 0, 0]
    # Handle x axis movement
    if event.button == 14:
        dmove = [-step, 0, 0]
    elif event.button == 13:
        dmove = [step, 0, 0]
    # Handle y axis movement
    elif event.button == 11:
        dmove = [0, -step, 0]
    elif event.button == 12:
        dmove = [0, step, 0]
    # Handle z axis movement
    elif event.button == 10:
        dmove = [0, 0, -step]
    elif event.button == 9:
        dmove = [0, 0, step]
    return np.array(dmove)


# Function to handle joystick events
def joystick_event(event, step=1):
    # Get event value
    val = event.value
    # Initialize movement array
    dmove = [0.0, 0.0, 0.0]

    # Handle left joystick (medium steps)
    # x axis
    if event.axis == 0:
        dmove = [-val, 0, 0]
    # y axis
    elif event.axis == 1:
        dmove = [0, val, 0]
    # Handle right joystick (small steps)
    # x axis
    elif event.axis == 2:
        dmove = [-val / 10, 0, 0]
    # y axis
    elif event.axis == 3:
        dmove = [0, val / 10, 0]

    # Handle Z axis
    elif event.axis == 4:
        dmove = [0, 0, (val + 1) / 2]
    elif event.axis == 5:
        dmove = [0, 0, -(val + 1) / 2]

    return np.array(dmove) * step


# Function to assess movement range
def assess_movement_range(m, xPos, yPos, zPos, dx, dy, dz):
    lim = m.axis_limits  # {"X": (min, max), "Y": (min, max), "Z": (min, max)}
    xMin, xMax = lim.get("X", (-float("inf"), float("inf")))
    yMin, yMax = lim.get("Y", (-float("inf"), float("inf")))
    zMin, zMax = lim.get("Z", (-float("inf"), float("inf")))
    xReq = dx + xPos
    yReq = dy + yPos
    zReq = dz + zPos

    if xReq < xMin:
        dx = 0
        xReq = xMin
        print("Unsafe x move")
    if xReq > xMax:
        dx = 0
        xReq = xMax
        print("Unsafe x move")
    if yReq < yMin:
        dy = 0
        yReq = yMin
        print("Unsafe y move")
    if yReq > yMax:
        dy = 0
        yReq = yMax
        print("Unsafe y move")
    if zReq < zMin:
        dz = 0
        zReq = zMin
        print("Unsafe z move")
    if zReq > zMax:
        dz = 0
        zReq = zMax
        print("Unsafe z move")

    return xReq, yReq, zReq, dx, dy, dz


# Function to create a new record
def new_record(filename):
    with open(filename, "w") as file:
        file.close()


# Function to record position
def record_pos(m, filename):
    pos = m.get_position()
    xPos, yPos, zPos = pos["X"], pos["Y"], pos["Z"]
    with open(filename, "a") as file:
        file.write("%d,%d,%d\n" % (xPos, yPos, zPos))
    return xPos, yPos, zPos


# Function to make PS4 control
def make_PS4_control(m, filename):
    # Initialize pygame and joystick
    pygame.init()
    pygame.joystick.init()
    joysticks = [
        pygame.joystick.Joystick(x) for x in range(pygame.joystick.get_count())
    ]
    print(joysticks[0].get_name())

    # Get initial positions
    _pos = m.get_position()
    xPos, yPos, zPos = _pos["X"], _pos["Y"], _pos["Z"]
    xReq, yReq, zReq = xPos, yPos, zPos

    done = False

    # Main event loop
    while not done:
        # Event processing step.
        # Possible joystick events: JOYAXISMOTION, JOYBALLMOTION, JOYBUTTONDOWN,
        # JOYBUTTONUP, JOYHATMOTION, JOYDEVICEADDED, JOYDEVICEREMOVED
        for event in pygame.event.get():

            if event.type == pygame.QUIT:
                done = True  # Flag that we are done so we exit this loop.

            if (
                event.type == pygame.JOYBUTTONDOWN
            ):  # interrput when pressing the PS button
                if event.button == 5:
                    print("PS button pressed.")
                    done = True
                    print("End of recording")

            if event.type == pygame.JOYBUTTONDOWN:
                dx, dy, dz = button_event(event, step=10)
                while len(pygame.event.get()) == 0:
                    # keep moving while the button is still pressed
                    _pos = m.get_position()
                    xPos, yPos, zPos = _pos["X"], _pos["Y"], _pos["Z"]
                    xReq, yReq, zReq, dx, dy, dz = assess_movement_range(
                        m, xPos, yPos, zPos, dx, dy, dz
                    )
                    m.jog(x=dx, y=dy, z=dz)

            if event.type == pygame.JOYBUTTONUP:
                pass

            if event.type == pygame.JOYAXISMOTION:
                if abs(event.value) > 0.5:
                    dx, dy, dz = joystick_event(event, step=1)
                    _pos = m.get_position()
                    xPos, yPos, zPos = _pos["X"], _pos["Y"], _pos["Z"]
                    xReq, yReq, zReq, dx, dy, dz = assess_movement_range(
                        m, xPos, yPos, zPos, dx, dy, dz
                    )
                    m.jog(x=dx, y=dy, z=dz)

            if (
                event.type == pygame.JOYBUTTONDOWN
            ):  # interrput when pressing the PS button
                if event.button == 15:
                    print("Touch pad pressed: recording position.")
                    xReq, yReq, zReq = record_pos(m, filename)

            if (
                event.type == pygame.JOYBUTTONDOWN
            ):  # interrput when pressing the PS button
                if event.button == 0:
                    print("X button pressed: recording clear tool position.")
                    m.y_clear = float(m.get_position()["Y"])
                    print(f"y_clear = {m.y_clear}")

            if (
                event.type == pygame.JOYBUTTONDOWN
            ):  # interrput when pressing the PS button
                if event.button == 2:
                    print("square button pressed: recording parked tool position.")
                    _park = m.get_position()
                    m.x_park = float(_park["X"])
                    m.y_park = float(_park["Y"])
                    print(f"x_park = {m.x_park}, y_park = {m.y_park}")

            if (
                event.type == pygame.JOYBUTTONDOWN
            ):  # interrput when pressing the PS button
                if event.button == 1:
                    print("O button pressed: Tool unlocked.")
                    m.tool_unlock()

            if (
                event.type == pygame.JOYBUTTONDOWN
            ):  # interrput when pressing the PS button
                if event.button == 3:
                    print("triangle button pressed: Tool locked.")
                    m.tool_lock()

            pygame.event.clear()  # clear event queue
    pygame.quit()

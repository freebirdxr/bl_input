# bl_input
An easy way to get XR input events as callbacks in Blender. Triggers callbacks for events without requiring you to write custom actionsets, operators etc. Also sends non-XR events for convenience.

Sends events to the registered callback for common XR Controller buttons, XR Controller movement, mouse movement etc.

## Installation
Copy the `bl_input` folder to your Blender plugin's root folder. You can then import it using `import bl_input`.

If you get a "module not found" error during import, please add these lines to your plugin's `__init__.py`, before importing `bl_input`:
```py
import sys
import os

sys.path.append(os.path.dirname(__file__))
```

## Usage
```py
from input import add_event_listener, start_input_tracking
import bpy

def on_event(event_type: str, bl_event: bpy.types.Event):
    if event_type == "XR_ACTION":
        print("xr event", bl_event.xr.action, bl_event.value)
    elif event_type == "MOUSEMOVE":
        print("mouse move", bl_event.mouse_x, bl_event.mouse_y)

# register the event callback
add_event_listener(event_callback=on_event)

# start XR view
bpy.ops.wm.xr_session_toggle()

# start tracking the input devices.
# **important:** this should be called only after the XR view has started!
start_input_tracking()
```

## Events
### XR
The callback will contain `"XR_ACTION"` as the first argument, and an instance of [`bpy.types.Event`](https://docs.blender.org/api/current/bpy.types.Event.html) as the second argument.

You can access the XR event data using the `xr` field in the event object, which will be an instance of [`bpy.types.XrEventData`](https://docs.blender.org/api/current/bpy.types.XrEventData.html).

The `event.xr.action` field will contain one of the following values (depending on the button being pressed/touched):
* `"trigger"`
* `"squeeze"`
* `"joystick_x_lefthand"`
* `"joystick_y_lefthand"`
* `"joystick_x_righthand"`
* `"joystick_y_righthand"`
* `"button_a_lefthand"`
* `"button_b_lefthand"`
* `"button_a_righthand"`
* `"button_b_righthand"`
* `"button_a_touch_lefthand"`
* `"button_b_touch_lefthand"`
* `"button_a_touch_righthand"`
* `"button_b_touch_righthand"`

Multiple events can be dispatched in parallel, for e.g. if both the trigger and squeeze buttons are being pressed.

### Mouse
The callback will contain `"MOUSEMOVE"` as the first argument, and an instance of [`bpy.types.Event`](https://docs.blender.org/api/current/bpy.types.Event.html) as the second argument.
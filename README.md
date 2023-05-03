# bl_input
An easy way to get input events as callbacks in Blender (including OpenXR controller events). Triggers callbacks for events without requiring you to write custom actionsets, operators etc.

Sends events to the registered callback for common XR Controller buttons, XR Controller movement, mouse movement etc.

**TODO:** Allow this to be used even without XR.

## Installation
Copy the `bl_input` folder to your Blender plugin's root folder. To avoid an import error, you may need add these lines to your plugin's `__init__.py`, before importing `bl_input`:
```py
import sys
import os

sys.path.append(os.path.dirname(__file__))
```

## Usage
```py
from input import add_event_listener, start_input_tracking

def on_event(event_type, blender_event):
    print("event", event_type, blender_event)

# register the event callback
add_event_listener(event_callback=on_event)

# start XR view
bpy.ops.wm.xr_session_toggle()

# start tracking the input devices.
# **important:** this should be called only after the XR view has started!
start_input_tracking()
```

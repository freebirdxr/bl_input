An easy way to get input events as callbacks in Blender (including OpenXR controller events). Triggers callbacks for events without requiring you to write custom actionsets, operators etc.

Sends events to the registered callback for common XR Controller buttons, XR Controller movement, mouse movement etc.

**TODO:** Allow this to be used even without XR.

Example:
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
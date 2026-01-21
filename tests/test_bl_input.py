#!/usr/bin/env python3
"""
Integration test for bl_input with ox runtime and simulator driver.

Tests the full integration path:
  API -> Simulator Driver -> ox Runtime -> OpenXR -> Blender XR -> bl_input

We programmatically set input values via the simulator API, then verify that
bl_input receives the correct values through its event callback.

Requires: ox-simulator running in API mode (port 8765)
"""

import bpy
import sys
import time
import json
from collections import defaultdict

import urllib.request


SIMULATOR_API = "http://localhost:8765"
STEP_DURATION = 1.0  # seconds to wait for events after setting inputs
TOLERANCE = 0.05

# Test steps: set inputs via API, then verify bl_input receives them
TEST_SEQUENCE = [
    {
        "name": "Step 1: Initial state - all zeros",
        "inputs": [
            {"user_path": "/user/hand/left", "component_path": "/input/trigger/value", "value": 0.0},
            {"user_path": "/user/hand/left", "component_path": "/input/squeeze/value", "value": 0.0},
            {"user_path": "/user/hand/right", "component_path": "/input/trigger/value", "value": 0.0},
            {"user_path": "/user/hand/right", "component_path": "/input/squeeze/value", "value": 0.0},
        ],
        "expected": {
            "trigger": 0.0,
            "squeeze": 0.0,
        },
    },
    {
        "name": "Step 2: Trigger half-pressed",
        "inputs": [
            {"user_path": "/user/hand/left", "component_path": "/input/trigger/value", "value": 0.5},
            {"user_path": "/user/hand/right", "component_path": "/input/trigger/value", "value": 0.5},
        ],
        "expected": {
            "trigger": 0.5,
        },
    },
    {
        "name": "Step 3: Trigger and squeeze pressed",
        "inputs": [
            {"user_path": "/user/hand/left", "component_path": "/input/trigger/value", "value": 1.0},
            {"user_path": "/user/hand/left", "component_path": "/input/squeeze/value", "value": 0.7},
            {"user_path": "/user/hand/right", "component_path": "/input/trigger/value", "value": 1.0},
            {"user_path": "/user/hand/right", "component_path": "/input/squeeze/value", "value": 0.7},
        ],
        "expected": {
            "trigger": 1.0,
            "squeeze": 0.7,
        },
    },
    {
        "name": "Step 4: Thumbstick movement",
        "inputs": [
            {"user_path": "/user/hand/left", "component_path": "/input/thumbstick/x", "value": 0.8},
            {"user_path": "/user/hand/left", "component_path": "/input/thumbstick/y", "value": -0.6},
            {"user_path": "/user/hand/right", "component_path": "/input/thumbstick/x", "value": -0.4},
            {"user_path": "/user/hand/right", "component_path": "/input/thumbstick/y", "value": 0.9},
        ],
        "expected": {
            "joystick_x_lefthand": 0.8,
            "joystick_y_lefthand": -0.6,
            "joystick_x_righthand": -0.4,
            "joystick_y_righthand": 0.9,
        },
    },
    {
        "name": "Step 5: Button presses",
        "inputs": [
            # Reset buttons from previous step
            {"user_path": "/user/hand/left", "component_path": "/input/x/click", "value": 0.0},
            {"user_path": "/user/hand/left", "component_path": "/input/y/click", "value": 0.0},
            {"user_path": "/user/hand/right", "component_path": "/input/a/click", "value": 0.0},
            {"user_path": "/user/hand/right", "component_path": "/input/b/click", "value": 0.0},
            # Button presses
            {"user_path": "/user/hand/left", "component_path": "/input/x/click", "value": 1.0},
            {"user_path": "/user/hand/left", "component_path": "/input/y/click", "value": 0.0},
            {"user_path": "/user/hand/right", "component_path": "/input/a/click", "value": 0.0},
            {"user_path": "/user/hand/right", "component_path": "/input/b/click", "value": 1.0},
        ],
        "expected": {
            "button_a_lefthand": 1.0,  # X button
            # button_b_lefthand: 0.0 - no event expected (no change from default)
            # button_a_righthand: 0.0 - no event expected (no change from default)
            "button_b_righthand": 1.0,  # B button
        },
    },
    {
        "name": "Step 6: Button press with touch (simultaneous)",
        "inputs": [
            # Reset buttons from previous step
            {"user_path": "/user/hand/left", "component_path": "/input/x/click", "value": 0.0},
            {"user_path": "/user/hand/left", "component_path": "/input/y/click", "value": 0.0},
            {"user_path": "/user/hand/right", "component_path": "/input/a/click", "value": 0.0},
            {"user_path": "/user/hand/right", "component_path": "/input/b/click", "value": 0.0},
            # New button presses with touch
            {"user_path": "/user/hand/left", "component_path": "/input/x/click", "value": 1.0},
            {"user_path": "/user/hand/left", "component_path": "/input/x/touch", "value": 1.0},
            {"user_path": "/user/hand/right", "component_path": "/input/a/click", "value": 1.0},
            {"user_path": "/user/hand/right", "component_path": "/input/a/touch", "value": 1.0},
        ],
        "expected": {
            "button_a_lefthand": 1.0,  # X button click
            "button_a_touch_lefthand": 1.0,  # X button touch
            "button_a_righthand": 1.0,  # A button click
            "button_a_touch_righthand": 1.0,  # A button touch
        },
    },
    {
        "name": "Step 7: Squeeze and A button simultaneously",
        "inputs": [
            # Reset buttons from previous step
            {"user_path": "/user/hand/left", "component_path": "/input/x/click", "value": 0.0},
            {"user_path": "/user/hand/left", "component_path": "/input/x/touch", "value": 0.0},
            {"user_path": "/user/hand/right", "component_path": "/input/a/click", "value": 0.0},
            {"user_path": "/user/hand/right", "component_path": "/input/a/touch", "value": 0.0},
            # Reset squeeze for both hands to ensure clean state
            {"user_path": "/user/hand/left", "component_path": "/input/squeeze/value", "value": 0.0},
            {"user_path": "/user/hand/right", "component_path": "/input/squeeze/value", "value": 0.0},
            # New inputs
            {"user_path": "/user/hand/right", "component_path": "/input/squeeze/value", "value": 1.0},
            {"user_path": "/user/hand/right", "component_path": "/input/a/click", "value": 1.0},
            {"user_path": "/user/hand/right", "component_path": "/input/a/touch", "value": 1.0},
        ],
        "expected": {
            "squeeze": 1.0,
            "button_a_righthand": 1.0,  # A button click
            "button_a_touch_righthand": 1.0,  # A button touch
        },
    },
    {
        "name": "Step 8: Trigger, squeeze, and thumbstick (complex simultaneous)",
        "inputs": [
            # Reset buttons from previous step
            {"user_path": "/user/hand/right", "component_path": "/input/a/click", "value": 0.0},
            {"user_path": "/user/hand/right", "component_path": "/input/a/touch", "value": 0.0},
            # Reset squeeze for right hand first
            {"user_path": "/user/hand/right", "component_path": "/input/squeeze/value", "value": 0.0},
            # New complex input
            {"user_path": "/user/hand/left", "component_path": "/input/trigger/value", "value": 0.8},
            {"user_path": "/user/hand/left", "component_path": "/input/squeeze/value", "value": 0.7},
            {"user_path": "/user/hand/left", "component_path": "/input/thumbstick/x", "value": 0.5},
            {"user_path": "/user/hand/left", "component_path": "/input/thumbstick/y", "value": -0.5},
            {"user_path": "/user/hand/right", "component_path": "/input/trigger/value", "value": 0.9},
        ],
        "expected": {
            "trigger": 0.8,
            "squeeze": 0.7,
            "joystick_x_lefthand": 0.5,
            "joystick_y_lefthand": -0.5,
        },
    },
]

# Track events received from bl_input (integration test verification)
test_state = {
    "events_received": defaultdict(list),
    "current_step": 0,
    "step_start_time": None,
    "errors": [],
    "completed": False,
}


def api_request(endpoint, data=None, method="GET"):
    """Send HTTP request to simulator API."""
    url = SIMULATOR_API + endpoint

    try:
        if data:
            req = urllib.request.Request(
                url, data=json.dumps(data).encode("utf-8"), headers={"Content-Type": "application/json"}, method=method
            )
        else:
            req = urllib.request.Request(url, method=method)

        with urllib.request.urlopen(req, timeout=5) as response:
            return response.read().decode("utf-8")
    except Exception as e:
        error = f"API request failed: {e}"
        test_state["errors"].append(error)
        print(f"ERROR: {error}")
        return None


def set_input(user_path, component, value):
    """Set device input via simulator API."""
    # Remove leading slash from user_path for URL construction
    user_path_clean = user_path.lstrip("/")
    # Remove leading slash from component for URL construction
    component_clean = component.lstrip("/")
    endpoint = f"/v1/states/{user_path_clean}/{component_clean}"
    result = api_request(endpoint, {"value": value}, method="PUT")
    time.sleep(0.1)  # Small delay to prevent HTTP connection pool exhaustion
    return result


def activate_device(user_path, pose=None):
    """Activate a device via simulator API."""
    if pose is None:
        pose = {"x": 0, "y": 1.4, "z": -0.3}

    # Remove leading slash from user_path for URL construction
    user_path_clean = user_path.lstrip("/")
    endpoint = f"/v1/devices/{user_path_clean}"

    data = {"position": pose, "orientation": {"x": 0, "y": 0, "z": 0, "w": 1}, "active": True}
    result = api_request(endpoint, data, method="PUT")
    time.sleep(0.1)
    return result


def event_callback(event_type, event):
    """Capture events from bl_input for verification."""
    if event_type != "XR_ACTION":
        return

    xr = event.xr
    test_state["events_received"][xr.action].append(
        {
            "state": xr.state[0] if xr.state else None,
            "timestamp": time.time(),
        }
    )


def get_latest_value(action_name):
    """Get most recent value received from bl_input for this action."""
    events = test_state["events_received"].get(action_name, [])
    return events[-1]["state"] if events else None


def validate_step():
    """Verify bl_input received the expected values we set via API."""
    if test_state["current_step"] >= len(TEST_SEQUENCE):
        return

    step = TEST_SEQUENCE[test_state["current_step"]]
    print(f"\n  Validating {step['name']}...")

    for action_name, expected_val in step["expected"].items():
        actual_val = get_latest_value(action_name)

        if actual_val is None:
            # Special case for 0.0: if we haven't received events yet, assume default 0.0
            if expected_val == 0.0:
                print(f"    ✓ {action_name}: 0.0 (assumed default)")
            else:
                error = f"{action_name}: No events received from bl_input"
                test_state["errors"].append(error)
                print(f"    ❌ {error}")
        elif abs(actual_val - expected_val) > TOLERANCE:
            error = f"{action_name}: expected {expected_val}, got {actual_val} from bl_input"
            test_state["errors"].append(error)
            print(f"    ❌ {error}")
        else:
            print(f"    ✓ {action_name}: {actual_val}")


def execute_step(step_index):
    """Set inputs via API for this test step."""
    if step_index >= len(TEST_SEQUENCE):
        return

    step = TEST_SEQUENCE[step_index]
    print(f"\nExecuting {step['name']}")

    for input_spec in step["inputs"]:
        print(f"  Setting {input_spec['user_path']} " f"{input_spec['component_path']} = {input_spec['value']}")
        set_input(input_spec["user_path"], input_spec["component_path"], input_spec["value"])


def report_results():
    """Generate final test report."""
    print("\n" + "=" * 70)
    print("TEST RESULTS")
    print("=" * 70)

    print(f"\nSteps completed: {test_state['current_step']}/{len(TEST_SEQUENCE)}")
    print(f"Total events from bl_input: {sum(len(v) for v in test_state['events_received'].values())}")
    print(f"Errors: {len(test_state['errors'])}")

    if test_state["errors"]:
        print("\nERRORS:")
        for error in test_state["errors"]:
            print(f"  ❌ {error}")

    print("\n" + "=" * 70)
    success = len(test_state["errors"]) == 0 and test_state["current_step"] >= len(TEST_SEQUENCE)

    if success:
        print("TEST PASSED ✓")
    else:
        print("TEST FAILED ❌")
    print("=" * 70)
    return success


def test_timer():
    """Manage test progression through steps."""
    if test_state["completed"]:
        return None

    # Start first step
    if test_state["step_start_time"] is None:
        print(f"\nStarting test ({len(TEST_SEQUENCE)} steps, {STEP_DURATION}s each)")
        execute_step(test_state["current_step"])
        test_state["step_start_time"] = time.time()
        return 0.1

    # Wait for step duration, then validate
    if time.time() - test_state["step_start_time"] >= STEP_DURATION:
        validate_step()
        test_state["current_step"] += 1

        # All steps done?
        if test_state["current_step"] >= len(TEST_SEQUENCE):
            test_state["completed"] = True
            success = report_results()
            sys.exit(0 if success else 1)
            return None

        # Next step
        execute_step(test_state["current_step"])
        test_state["step_start_time"] = time.time()

    return 0.1


def main():
    """Run the integration test."""
    print("=" * 70)
    print("BL_INPUT INTEGRATION TEST")
    print("Tests: API -> Simulator -> ox Runtime -> OpenXR -> Blender -> bl_input")
    print("=" * 70)

    # Verify simulator API is running
    print(f"\nChecking simulator API at {SIMULATOR_API}...")
    if api_request("/") is None:
        print("ERROR: Cannot connect to simulator API")
        print("Make sure ox-driver-simulator is running in API mode on port 8765")
        sys.exit(1)
    print("✓ API connected")

    # Find 3D View
    area = next((a for a in bpy.context.screen.areas if a.type == "VIEW_3D"), None)
    if not area:
        print("ERROR: No 3D View found")
        sys.exit(1)

    # Start VR session
    print("\nStarting VR session...")
    with bpy.context.temp_override(area=area):
        bpy.ops.wm.xr_session_toggle()

    if not bpy.context.window_manager.xr_session_state.is_running(bpy.context):
        print("ERROR: Failed to start VR session")
        sys.exit(1)
    print("✓ VR session started")

    # Activate devices
    print("\nActivating devices...")
    activate_device("/user/hand/left", {"x": -0.2, "y": 1.4, "z": -0.3})
    activate_device("/user/hand/right", {"x": 0.2, "y": 1.4, "z": -0.3})
    print("✓ Devices activated")

    # Setup bl_input
    print("\nSetting up bl_input...")
    try:
        import bl_input

        bl_input.event_callback = event_callback
        bl_input.send_movement_events = False
        bl_input.start_input_tracking()
        print("✓ bl_input tracking started")
    except Exception as e:
        print(f"ERROR: Failed to setup bl_input: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)

    # Start test
    bpy.app.timers.register(test_timer, first_interval=0.1)


if __name__ == "__main__":
    main()

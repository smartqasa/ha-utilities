# Scene Capture

A Home Assistant custom integration to capture the current states of entities into a scene and persist them to `scenes.yaml`.

## Installation

1. Install via HACS (recommended) or manually copy `custom_components/scene_capture/` to `/config/custom_components/`.
2. Restart Home Assistant.

## Usage

Call the action:

```yaml
action: scene_capture.capture
target:
  entity_id: "scene.adjustable_living_room"
```

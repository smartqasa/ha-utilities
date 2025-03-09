# Scene Capture

A Home Assistant custom integration to capture the current states of entities into a scene and persist them to `scenes.yaml`.

## Installation

1. Install via HACS (recommended) or manually copy to `/config/custom_components/scene_capture/`.
2. Restart Home Assistant.

## Usage

Call the service:

```yaml
service: scene_capture.capture
data:
  scene_id: "adjustable_living_room"
```

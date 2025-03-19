# SmartQasa Scene Capture

A powerful Home Assistant custom integration for capturing the current states of entities and persisting them to `scenes.yaml`. This enables dynamic scene updates without manual YAML editing.

## 🚀 Features

- Capture and update scenes dynamically.
- Supports a wide range of Home Assistant entity types.
- Integrates seamlessly with Home Assistant’s `scene` domain.
- Safe YAML handling using `ruamel.yaml` for improved formatting and serialization.
- Error handling and logging for easy debugging.

## 📥 Installation

### 1️⃣ Install via HACS (Recommended)

- Open **HACS** in Home Assistant.
- Navigate to **Integrations**.
- Search for **SmartQasa Scene Capture**.
- Click **Download** and restart Home Assistant.

### 2️⃣ Manual Installation

- Copy the `custom_components/smartqasa/` folder to your Home Assistant `config/custom_components/` directory.
- Restart Home Assistant.

## ⚙️ Usage

### Retrieving Entity List for a Scene

To get a list of all entities in a scene, call the following action:

```yaml
action: smartqasa.scene_get
target:
  entity_id: "scene.adjustable_living_room"
```

### Retrieving Entity List for a Scene

To update the entities contained in a scene, call the following action:

```yaml
action: smartqasa.scene_update
target:
  entity_id: "scene.adjustable_living_room"
```

#!/usr/bin/env bash
# config_updater.sh
# Update model_config.json and project_config.json with
# the selected Ollama model mode (enabled/disabled).
# Requires: colors_and_utils.sh sourced first.
# Requires: ACTIVE_PY, PROJECT_ROOT, OLLAMA_ENABLED,
#           SELECTED_MODEL set by caller.

run_config_update() {
    printf '\n%b\n' \
        "${YELLOW}[STEP 3/5] Updating model configuration...${NC}"

    local config_dir="$PROJECT_ROOT/data/config"
    local model_cfg="$config_dir/model_config.json"
    local project_cfg="$config_dir/project_config.json"

    if [ ! -f "$model_cfg" ] || [ ! -f "$project_cfg" ]; then
        print_error \
            "Config files not found in $config_dir."
        exit 1
    fi

    "$ACTIVE_PY" - \
        "$PROJECT_ROOT" \
        "$OLLAMA_ENABLED" \
        "$SELECTED_MODEL" <<'PY'
import json
import sys
from pathlib import Path

root = Path(sys.argv[1])
enabled = sys.argv[2].strip().lower() == "true"
selected_model = sys.argv[3].strip()
config_dir = root / "data" / "config"
model_path = config_dir / "model_config.json"
project_path = config_dir / "project_config.json"


def read_json(path):
    with path.open("r", encoding="utf-8-sig") as h:
        value = json.load(h)
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object in {path}")
    return value


def atomic_write(path, data):
    temp = path.with_suffix(path.suffix + ".tmp")
    with temp.open(
        "w", encoding="utf-8", newline="\n"
    ) as h:
        json.dump(data, h, ensure_ascii=False, indent=4)
        h.write("\n")
    temp.replace(path)


model_cfg = read_json(model_path)
project_cfg = read_json(project_path)
master_model_cfg = project_cfg.get("model_config")
if not isinstance(master_model_cfg, dict):
    master_model_cfg = dict(model_cfg)
else:
    master_model_cfg = dict(master_model_cfg)

configs = [model_cfg, master_model_cfg]
if enabled:
    if not selected_model:
        raise ValueError(
            "Model enabled but no name supplied."
        )
    for cfg in configs:
        cfg["model_name"] = selected_model
        cfg["llm_enabled"] = True
        try:
            configured_tokens = int(
                cfg.get("max_tokens", 512)
            )
        except (TypeError, ValueError):
            configured_tokens = 512
        if configured_tokens < 2048:
            cfg["max_tokens"] = 2048
    print(f"LLM enabled: {selected_model}")
    print("max_tokens set to at least 2048.")
else:
    for cfg in configs:
        cfg["model_name"] = None
        cfg["llm_enabled"] = False
    print("LLM disabled (model_name=null, llm_enabled=false).")
    print("App will use fallback paths.")

project_cfg["model_config"] = master_model_cfg
atomic_write(model_path, model_cfg)
atomic_write(project_path, project_cfg)
print(f"Updated: {model_path}")
print(f"Updated: {project_path}")
PY
}

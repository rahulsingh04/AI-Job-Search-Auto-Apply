#!/usr/bin/env bash
# ollama_setup.sh
# Detect/install Ollama, list local models, and let the
# user choose a model or continue without one.
# Requires: colors_and_utils.sh sourced first.
# Sets: OLLAMA_BIN, OLLAMA_ENABLED, SELECTED_MODEL.

OLLAMA_BIN=""
OLLAMA_ENABLED="false"
SELECTED_MODEL=""
OLLAMA_LIST_RAW=""
MODEL_NAMES=()

resolve_ollama() {
    local local_app_data="" candidate=""

    if command -v ollama >/dev/null 2>&1; then
        OLLAMA_BIN="$(command -v ollama)"
        return 0
    fi
    if command -v ollama.exe >/dev/null 2>&1; then
        OLLAMA_BIN="$(command -v ollama.exe)"
        return 0
    fi

    if [ -n "${LOCALAPPDATA:-}" ]; then
        local_app_data="$LOCALAPPDATA"
        if command -v cygpath >/dev/null 2>&1; then
            local_app_data="$(cygpath -u "$LOCALAPPDATA" \
                2>/dev/null || printf '%s' "$LOCALAPPDATA")"
        fi
        PATH="$local_app_data/Programs/Ollama:$PATH"
        candidate="$local_app_data/Programs/Ollama/ollama.exe"
        if [ -f "$candidate" ]; then
            OLLAMA_BIN="$candidate"
            export PATH
            return 0
        fi
    fi

    for candidate in \
        "/c/Program Files/Ollama/ollama.exe" \
        "/c/Users/${USERNAME:-}/AppData/Local/Programs/Ollama/ollama.exe"
    do
        if [ -f "$candidate" ]; then
            OLLAMA_BIN="$candidate"
            return 0
        fi
    done

    return 1
}

install_ollama() {
    local os_name
    os_name="$(uname -s 2>/dev/null || printf 'unknown')"
    printf '%b\n' \
        "${YELLOW}Ollama not found. Attempting install...${NC}"

    case "$os_name" in
        MINGW*|MSYS*|CYGWIN*)
            if command -v winget.exe >/dev/null 2>&1; then
                winget.exe install --id Ollama.Ollama \
                    --exact --silent \
                    --accept-package-agreements \
                    --accept-source-agreements || return 1
            elif command -v winget >/dev/null 2>&1; then
                winget install --id Ollama.Ollama \
                    --exact --silent \
                    --accept-package-agreements \
                    --accept-source-agreements || return 1
            elif command -v powershell.exe >/dev/null 2>&1; then
                powershell.exe -NoProfile \
                    -ExecutionPolicy Bypass \
                    -Command \
                    'irm https://ollama.com/install.ps1 | iex' \
                    || return 1
            else
                print_error \
                    "Neither winget nor PowerShell found." \
                    "Install from https://ollama.com/download/windows"
                return 1
            fi
            ;;
        Linux*|Darwin*)
            if ! command -v curl >/dev/null 2>&1; then
                print_error \
                    "curl required. Install curl and rerun."
                return 1
            fi
            curl -fsSL https://ollama.com/install.sh | sh \
                || return 1
            ;;
        *)
            print_error \
                "Auto-install unsupported on '$os_name'." \
                "Install from https://ollama.com/download"
            return 1
            ;;
    esac

    resolve_ollama
}

parse_model_names() {
    local raw="$1"
    MODEL_NAMES=()
    while IFS= read -r model_line; do
        model_line="$(printf '%s' "$model_line" | tr -d '\r')"
        [ -n "$model_line" ] && MODEL_NAMES+=("$model_line")
    done < <(
        printf '%s\n' "$raw" \
            | awk 'NR > 1 && NF { print $1 }'
    )
}

refresh_ollama_list() {
    local attempt=0 output=""
    if output="$("$OLLAMA_BIN" list 2>&1)"; then
        OLLAMA_LIST_RAW="$output"
        parse_model_names "$OLLAMA_LIST_RAW"
        return 0
    fi

    print_warn \
        "Ollama server not responding. Attempting start..."
    ( nohup "$OLLAMA_BIN" serve \
        > "$PROJECT_ROOT/ollama-serve.log" \
        2>&1 </dev/null & ) || true

    while [ "$attempt" -lt 20 ]; do
        sleep 1
        attempt=$((attempt + 1))
        if output="$("$OLLAMA_BIN" list 2>&1)"; then
            OLLAMA_LIST_RAW="$output"
            parse_model_names "$OLLAMA_LIST_RAW"
            return 0
        fi
    done

    OLLAMA_LIST_RAW="$output"
    return 1
}

show_model_list() {
    printf '%b\n' "${CYAN}Current 'ollama list' output:${NC}"
    if [ -n "$OLLAMA_LIST_RAW" ]; then
        printf '%s\n' "$OLLAMA_LIST_RAW"
    else
        printf '%s\n' "(No model list available.)"
    fi
}

find_installed_name() {
    local requested="$1" model=""
    for model in "${MODEL_NAMES[@]}"; do
        if [ "$model" = "$requested" ]; then
            printf '%s' "$model"
            return 0
        fi
    done
    if [[ "$requested" != *:* ]]; then
        for model in "${MODEL_NAMES[@]}"; do
            if [ "$model" = "$requested:latest" ]; then
                printf '%s' "$model"
                return 0
            fi
        done
    fi
    return 1
}

select_installed_model() {
    local idx answer resolved=""
    if [ "${#MODEL_NAMES[@]}" -eq 0 ]; then
        print_error \
            "No local models installed." \
            "Choose option 2 to download, or 3 to skip LLM."
        return 1
    fi

    if [ "${#MODEL_NAMES[@]}" -eq 1 ]; then
        SELECTED_MODEL="${MODEL_NAMES[0]}"
        print_ok "Selected: $SELECTED_MODEL"
        return 0
    fi

    printf '%b\n' "${CYAN}Select an installed model:${NC}"
    for idx in "${!MODEL_NAMES[@]}"; do
        printf '  %d) %s\n' "$((idx + 1))" "${MODEL_NAMES[$idx]}"
    done
    read -r -p "Enter number or model name (or 'back'): " answer
    if [ "$answer" = "back" ]; then
        return 1
    fi

    if [[ "$answer" =~ ^[0-9]+$ ]]; then
        idx=$((answer - 1))
        if [ "$idx" -ge 0 ] \
            && [ "$idx" -lt "${#MODEL_NAMES[@]}" ]; then
            SELECTED_MODEL="${MODEL_NAMES[$idx]}"
            print_ok "Selected: $SELECTED_MODEL"
            return 0
        fi
    else
        if resolved="$(find_installed_name "$answer")"; then
            SELECTED_MODEL="$resolved"
            print_ok "Selected: $SELECTED_MODEL"
            return 0
        fi
    fi

    printf '%b\n' \
        "${RED}[ERROR] Model not found. Verify name below.${NC}"
    show_model_list
    return 1
}

choose_model_mode() {
    local choice requested retry resolved=""
    while true; do
        printf '\n%b\n' \
            "${CYAN}${BOLD}Choose how to run the app:${NC}"
        if [ "${#MODEL_NAMES[@]}" -eq 1 ]; then
            printf '  1) Continue with "%s"\n' \
                "${MODEL_NAMES[0]}"
        elif [ "${#MODEL_NAMES[@]}" -gt 1 ]; then
            printf '  1) Continue with an installed model\n'
        else
            printf '  1) Continue with installed model (none)\n'
        fi
        printf '  2) Download another model and use it\n'
        printf '  3) Continue without local LLM (fallback)\n'
        read -r -p "Enter 1, 2, or 3: " choice

        case "$choice" in
            1)
                if select_installed_model; then
                    OLLAMA_ENABLED="true"
                    return 0
                fi
                ;;
            2)
                while true; do
                    read -r -p \
                        "Model name/tag to download (or 'back'): " \
                        requested
                    requested="$(printf '%s' "$requested" \
                        | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')"
                    if [ "$requested" = "back" ]; then
                        break
                    fi
                    if [ -z "$requested" ] \
                        || [[ ! "$requested" \
                            =~ ^[A-Za-z0-9][A-Za-z0-9._:/-]*$ ]]
                    then
                        printf '%b\n' \
                            "${RED}[ERROR] Invalid model name.${NC}"
                        show_model_list
                        continue
                    fi

                    if resolved="$(find_installed_name \
                        "$requested")"; then
                        SELECTED_MODEL="$resolved"
                        OLLAMA_ENABLED="true"
                        print_ok "Already installed: $SELECTED_MODEL"
                        return 0
                    fi

                    printf '%b\n' \
                        "${YELLOW}Pulling '$requested'...${NC}"
                    if "$OLLAMA_BIN" pull "$requested"; then
                        if refresh_ollama_list; then
                            if resolved="$(find_installed_name \
                                "$requested")"; then
                                SELECTED_MODEL="$resolved"
                                OLLAMA_ENABLED="true"
                                print_ok \
                                    "Downloaded: $SELECTED_MODEL"
                                return 0
                            fi
                        fi
                        printf '%b\n' \
                            "${RED}[ERROR] Not found after pull.${NC}"
                        show_model_list
                    else
                        printf '%b\n' \
                            "${RED}[ERROR] Pull failed.${NC}"
                        refresh_ollama_list || true
                        show_model_list
                    fi
                    read -r -p "Try another model? [Y/n] " retry
                    case "$retry" in
                        n|N|no|NO) break ;;
                        *) continue ;;
                    esac
                done
                ;;
            3)
                OLLAMA_ENABLED="false"
                SELECTED_MODEL=""
                print_warn \
                    "LLM disabled. App will use fallback paths."
                return 0
                ;;
            *)
                printf '%b\n' \
                    "${RED}[ERROR] Enter 1, 2, or 3.${NC}"
                ;;
        esac
    done
}

run_ollama_setup() {
    printf '%b\n' \
        "${YELLOW}[STEP 1/5] Checking Ollama...${NC}"

    if ! resolve_ollama; then
        if ! install_ollama; then
            print_error "Ollama could not be installed."
            printf '%b\n' \
                "${YELLOW}Install from https://ollama.com/download${NC}"
            read -r -p \
                "Continue without LLM? Enter 3 to continue: " \
                no_ollama_choice
            if [ "$no_ollama_choice" = "3" ]; then
                OLLAMA_ENABLED="false"
                SELECTED_MODEL=""
            else
                exit 1
            fi
        fi
    fi

    if [ -n "$OLLAMA_BIN" ]; then
        print_ok "Ollama: $(safe_path "$OLLAMA_BIN")"
        if refresh_ollama_list; then
            show_model_list
            if ! choose_model_mode; then
                print_error "Could not select a model mode."
                exit 1
            fi
        else
            print_error \
                "Ollama installed but server unreachable." \
                "See ollama-serve.log for details."
            read -r -p \
                "Continue without LLM? Enter 3 to continue: " \
                no_server_choice
            if [ "$no_server_choice" = "3" ]; then
                OLLAMA_ENABLED="false"
                SELECTED_MODEL=""
            else
                exit 1
            fi
        fi
    fi
}

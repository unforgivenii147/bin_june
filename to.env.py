#!/data/data/com.termux/files/usr/bin/python

import json
import re
import sys
from pathlib import Path
from collections import defaultdict

DEFAULT_FILE = "README.md"
ENV_FILE = Path.home() / ".env"


def parse_api_keys_from_table(text: str):
    lines = text.strip().split("\n")
    header_line = None
    data_start = 0
    for i, line in enumerate(lines):
        if "| Key | Model |" in line or ("Key" in line and "Model" in line):
            header_line = i
            data_start = i + 2
            break
    if header_line is None:
        data_start = 0
    pattern = "\\|\\s*`([^`]+)`\\s*\\|\\s*([^\\s|]+)\\s*\\|"

    env_vars = defaultdict(list)
    model_list = []

    for line in lines[data_start:]:
        if not line.strip() or line.strip().startswith("|--"):
            continue
        match = re.search(pattern, line)
        if match:
            api_key = match.group(1)
            model = match.group(2).lower()
            model_list.append(model)

            # Determine token type based on model
            if "deepseek" in model:
                token_type = "DEEPSEEK_TOKEN"
            elif "gemini" in model:
                token_type = "GEMINI_TOKEN"
            elif "openai" in model or "gpt" in model:
                token_type = "OPENAI_TOKEN"
            elif "claude" in model or "anthropic" in model:
                token_type = "ANTHROPIC_TOKEN"
            else:
                # Clean up model name for token variable
                cleaned_name = model.upper().replace("-", "_")
                if "/" in cleaned_name:
                    cleaned_name = cleaned_name[: cleaned_name.index("/")]
                # Remove any trailing/leading underscores
                cleaned_name = cleaned_name.strip("_")
                token_type = f"{cleaned_name}_TOKEN"

            # Store all values, preserving duplicates
            env_vars[token_type].append(api_key)

    # Save model list for reference
    with open("model_list", "w") as f:
        json.dump(model_list, f, ensure_ascii=False, indent=2)

    return env_vars


def append_to_env_file(env_vars, env_file=ENV_FILE):
    """Append new tokens to ~/.env, preserving existing entries"""

    # Read existing .env file if it exists
    existing_lines = []
    if env_file.exists():
        with open(env_file, "r") as f:
            existing_lines = f.readlines()

    # Parse existing tokens to avoid duplicates
    existing_tokens = defaultdict(list)
    current_section = "default"

    for line in existing_lines:
        line = line.strip()
        if line and not line.startswith("#"):
            if "=" in line:
                key, value = line.split("=", 1)
                if key.endswith("_TOKEN"):
                    existing_tokens[key].append(value)

    # Prepare new content
    new_lines = []

    # Add a separator comment if there are existing entries
    if existing_lines and any(not l.strip().startswith("#") for l in existing_lines):
        new_lines.append("\n# === New tokens added by script ===\n")

    # Track how many new tokens were added
    added_count = 0

    for token_type, values in env_vars.items():
        # Check if these values already exist
        existing_values = set(existing_tokens.get(token_type, []))
        new_values = [v for v in values if v not in existing_values]

        if new_values:
            # Append all new values for this token type
            for value in new_values:
                new_lines.append(f"{token_type}={value}\n")
                added_count += 1
            # Store for future duplicate checking
            existing_tokens[token_type].extend(new_values)

    # Write back to file
    if new_lines:
        with open(env_file, "a") as f:
            f.writelines(new_lines)
        print(f"✅ Appended {added_count} new token(s) to {env_file}")
    else:
        print(f"ℹ️ No new tokens to add (all already in {env_file})")

    return added_count


def print_token_summary(env_vars):
    """Display summary of extracted tokens"""
    print("\n📋 Extracted tokens from table:")
    total_tokens = sum(len(values) for values in env_vars.values())
    print(f"Found {total_tokens} token(s) across {len(env_vars)} type(s):")

    for token_type, values in env_vars.items():
        masked_values = []
        for value in values:
            if len(value) > 12:
                masked = value[:8] + "..." + value[-4:]
            else:
                masked = "***"
            masked_values.append(masked)
        print(f"  {token_type}: {', '.join(masked_values)}")


def main() -> None:
    # Get input file
    if len(sys.argv) > 1:
        fn = Path(sys.argv[1])
    else:
        fn = Path(DEFAULT_FILE)

    if not fn.exists():
        print(f"❌ File not found: {fn}")
        sys.exit(1)

    # Parse table
    try:
        table_data = fn.read_text(encoding="utf-8")
    except Exception as e:
        print(f"❌ Error reading {fn}: {e}")
        sys.exit(1)

    env_vars = parse_api_keys_from_table(table_data)

    if env_vars:
        # Show what was found
        print_token_summary(env_vars)

        # Append to ~/.env
        added = append_to_env_file(env_vars)

        if added > 0:
            print(f"\n✅ Successfully added {added} new token(s) to {ENV_FILE}")
            print("📝 You can now select the desired token manually in your .env file")
            print("   (comment out or remove ones you don't want to use)")
        else:
            print("\nℹ️ No new tokens were added (all already present)")
    else:
        print("❌ No API keys found in the input")
        print("Expected format: | `api-key-here` | model-name | ...")
        print("Example: | `sk-abc123...` | gpt-4 |")


if __name__ == "__main__":
    main()

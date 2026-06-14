#!/data/data/com.termux/files/usr/bin/python
import re
import sys
from pathlib import Path


def parse_api_keys_from_table(text):
    """Parse API keys from table format and map to environment variable names"""
    lines = text.strip().split("\n")

    # Find the line with column headers
    header_line = None
    data_start = 0
    for i, line in enumerate(lines):
        if "| Key | Model |" in line or "Key" in line and "Model" in line:
            header_line = i
            # Next line after header is separator (---|---)
            data_start = i + 2
            break

    if header_line is None:
        # Try to parse directly if no header
        data_start = 0

    # Regex to extract key and model
    # Pattern matches table row: | `sk-...` | model-name | ...
    pattern = r"\|\s*`([^`]+)`\s*\|\s*([^\s|]+)\s*\|"

    env_vars = {}

    for line in lines[data_start:]:
        if not line.strip() or line.strip().startswith("|--"):
            continue

        match = re.search(pattern, line)
        if match:
            api_key = match.group(1)
            model = match.group(2).lower()

            # Map model names to environment variable prefixes
            if "deepseek" in model:
                env_vars["DEEPSEEK_TOKEN"] = api_key
            elif "gemini" in model:
                env_vars["GEMINI_TOKEN"] = api_key
            elif "openai" in model or "gpt" in model:
                env_vars["OPENAI_TOKEN"] = api_key
            elif "claude" in model or "anthropic" in model:
                env_vars["ANTHROPIC_TOKEN"] = api_key
            else:
                # For unknown models, create a generic key
                model_upper = model.upper().replace("-", "_")
                env_vars[f"{model_upper}_TOKEN"] = api_key

    return env_vars


def write_env_file(env_vars, output_file=".env"):
    """Write environment variables to .env file"""
    env_path = Path(output_file)

    # Check if file exists and preserve existing non-api keys?
    existing_vars = {}
    if env_path.exists():
        with open(env_path, "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key = line.split("=")[0]
                    # Preserve non-token variables
                    if not key.endswith("_TOKEN") and key != "TOKEN":
                        existing_vars[key] = line

    # Write to .env file
    with open(env_path, "w") as f:
        # Write header comment
        f.write("# Auto-generated API tokens\n")
        f.write("# Generated from API keys table\n\n")

        # Write preserved existing vars first
        for key, value in existing_vars.items():
            f.write(f"{value}\n")

        if existing_vars:
            f.write("\n")

        # Write new token vars
        for key, value in env_vars.items():
            f.write(f"{key}={value}\n")

    print(f"✅ Wrote {len(env_vars)} token(s) to {output_file}")
    return env_vars


def main():
    # Example table data (you can also read from stdin or file)
    table_data = """| Key | Model | Status | Budget | Rate Limit | Expires | Description |
|-----|-------|--------|--------|------------|---------|-------------|
| `sk-HZpFBiqjKVG6xuBjG5yj0x48Iflgo1kpu7AOKXIPWCTYItjZ` | deepseek-v4-flash | 🆕 New | $20 | 10 RPM | 2026-06-14 | Live positive-balance channel |"""

    # If filename provided as argument, read from file
    if len(sys.argv) > 1:
        with open(sys.argv[1], "r") as f:
            table_data = f.read()

    # Parse and write
    env_vars = parse_api_keys_from_table(table_data)

    if env_vars:
        write_env_file(env_vars)

        # Print summary
        print("\n📋 Extracted tokens:")
        for key, value in env_vars.items():
            # Show only first/last few chars for security
            masked = value[:8] + "..." + value[-4:] if len(value) > 12 else "***"
            print(f"  {key}={masked}")
    else:
        print("❌ No API keys found in the input")
        print("Expected format: | `api-key-here` | model-name | ...")


if __name__ == "__main__":
    main()

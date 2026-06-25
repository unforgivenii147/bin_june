#!/data/data/com.termux/files/usr/bin/python

import argparse
import os
import re
import sys
from pathlib import Path


def install_js2py() -> bool:
    try:
        return True
    except ImportError:
        print("📦 Installing js2py library...")
        import subprocess

        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "js2py"])
            print("✅ js2py installed successfully")
            return True
        except subprocess.CalledProcessError:
            print("❌ Failed to install js2py")
            return False


def convert_with_js2py(js_file: Path, outfile: Path) -> bool:
    try:
        import js2py

        js2py.translate_file(js_file, out_file)
        return True
    except Exception as e:
        return (False, f"js2py conversion error: {e!s}")


def convert_with_openai(js_code: str, api_key: str | None = None) -> tuple[bool, str]:
    try:
        import openai
    except ImportError:
        return (False, "OpenAI library not installed. Install with: pip install openai")
    api_key = api_key or os.getenv("OPENAI_API_KEY")
    if not api_key:
        return (
            False,
            "OpenAI API key not found. Set OPENAI_API_KEY environment variable or pass --api-key",
        )
    try:
        client = openai.OpenAI(api_key=api_key)
        prompt = f"Convert the following JavaScript code to Python.\nPreserve the logic and functionality while using Pythonic idioms.\nOnly return the Python code without explanations.\nJavaScript code:\n```javascript\n{js_code}\npython code:"
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {
                    "role": "system",
                    "content": "You are an expert programmer who converts JavaScript to Python accurately.",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
            max_tokens=2000,
        )
        python_code = response.choices[0].message.content
        if "```python" in python_code:
            python_code = re.search("```python\\n(.*?)```", python_code, re.DOTALL)
            if python_code:
                python_code = python_code.group(1)
        elif "```" in python_code:
            python_code = re.search("```\\n(.*?)```", python_code, re.DOTALL)
            if python_code:
                python_code = python_code.group(1)
        return (True, python_code.strip())
    except Exception as e:
        return (False, f"OpenAI API error: {e!s}")


def simple_js_to_python(js_code: str) -> str:
    python_code = js_code
    python_code = re.sub("\\b(let|const|var)\\s+", "", python_code)
    python_code = re.sub("console\\.log\\s*\\(", "print(", python_code)
    python_code = re.sub("\\btrue\\b", "True", python_code)
    python_code = re.sub("\\bfalse\\b", "False", python_code)
    python_code = re.sub("\\b(null|undefined)\\b", "None", python_code)
    python_code = re.sub("\\bfunction\\s+(\\w+)\\s*\\((.*?)\\)\\s*{", "def \\1(\\2):", python_code)
    python_code = re.sub("const\\s+(\\w+)\\s*=\\s*\\((.*?)\\)\\s*=>\\s*{", "def \\1(\\2):", python_code)
    python_code = re.sub("(\\w+)\\s*=\\s*\\((.*?)\\)\\s*=>\\s*{", "def \\1(\\2):", python_code)
    python_code = python_code.replace("//", "#")
    python_code = re.sub(";$", "", python_code, flags=re.MULTILINE)
    python_code = re.sub("\\s*{\\s*$", ":", python_code, flags=re.MULTILINE)
    python_code = re.sub("^\\s*}\\s*$", "", python_code, flags=re.MULTILINE)
    python_code = re.sub("\\bif\\s*\\((.*?)\\)\\s*{", "if \\1:", python_code)
    python_code = re.sub("\\belse\\s+if\\s*\\((.*?)\\)\\s*{", "elif \\1:", python_code)
    python_code = re.sub("\\belse\\s*{", "else:", python_code)
    python_code = re.sub("\\bwhile\\s*\\((.*?)\\)\\s*{", "while \\1:", python_code)
    return re.sub(
        "for\\s*\\(\\s*let\\s+(\\w+)\\s*=\\s*(\\d+)\\s*;\\s*\\1\\s*<\\s*(\\w+)\\s*;\\s*\\1\\+\\+\\s*\\)\\s*{",
        "for \\1 in range(\\2, \\3):",
        python_code,
    )


def convert_file(
    input_file: Path,
    output_file: Path | None = None,
    method: str = "js2py",
    api_key: str | None = None,
) -> bool:
    try:
        js_code = Path(input_file).read_text(encoding="utf-8")
    except Exception as e:
        print(f"❌ Error reading file: {e}")
        return False
    print(f"📄 Converting: {input_file}")
    print(f"🔧 Method: {method}")
    if method == "js2py":
        if not install_js2py():
            print("⚠️  Falling back to simple conversion")
            method = "simple"
        else:
            output_file = input_file.with_suffix(".py")
            success = convert_with_js2py(input_file, output_file)
            return True
    if method == "openai":
        success, result = convert_with_openai(js_code, api_key)
    elif method == "simple":
        result = simple_js_to_python(js_code)
        success = True
    if not success:
        print(f"❌ Conversion failed: {result}")
        return False
    if output_file is None:
        output_file = input_file.with_suffix(".py")
    try:
        Path(output_file).write_text(result, encoding="utf-8")
        print(f"✅ Converted successfully: {output_file}")
        return True
    except Exception as e:
        print(f"❌ Error writing file: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Convert JavaScript code to Python",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="\n             Examples:\n                 Convert using js2py (default)\n                     python js_to_py.py script.js\n                 Convert using OpenAI API\n                     python js_to_py.py script.js --method openai --api-key YOUR_KEY\n                 Convert using simple rule-based method\n                     python js_to_py.py script.js --method simple\n                 Specify output file\n                     python js_to_py.py script.js -o output.py\n        ",
    )
    parser.add_argument("input", type=Path, help="Input JavaScript file")
    parser.add_argument(
        "-m",
        "--method",
        choices=["js2py", "openai", "simple"],
        default="simple",
        help="Conversion method (default: js2py)",
    )
    parser.add_argument(
        "--api-key",
        help="OpenAI API key (for openai method, or set OPENAI_API_KEY env var)",
    )
    args = parser.parse_args()
    if not args.input.exists():
        print(f"❌ Error: File not found: {args.input}")
        sys.exit(1)
    outputfile = str(args.input).replace(".js", ".py")
    success = convert_file(args.input, outputfile, args.method, args.api_key)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
'\n```bash\npython js_to_py.py script.js\n2. Using OpenAI API\nexport OPENAI_API_KEY="your-api-key-here"\npython js_to_py.py script.js --method openai\npython js_to_py.py script.js --method openai --api-key "your-key"\n3. Simple Rule-Based Conversion\npython js_to_py.py script.js --method simple\n4. Specify Output File\npython js_to_py.py input.js -o converted.py\nConversion Methods Comparison\n1. js2py Method\nPros:\nFull ECMAScript 5.1 support\nHandles complex JavaScript features\nNo API costs\nWorks offline\nCons:\nGenerated code may not be idiomatic Python\nLarge files take time to translate\nSome edge cases may fail\n2. OpenAI Method\nPros:\nProduces idiomatic Python code\nHandles modern JavaScript (ES6+)\nBetter code quality and readability\nUnderstands context and intent\nCons:\nRequires API key and internet connection\nCosts money per conversion\nRate limits apply\nMay not be 100% accurate\n3. Simple Method\nPros:\nFast and lightweight\nNo dependencies\nWorks offline\nFree\nCons:\nLimited feature support\nOnly handles basic syntax\nMay produce incorrect code for complex cases\nExample Conversion\nJavaScript Input:\nfunction calculateSum(numbers) {\n    let total = 0;\n    for (let i = 0; i < numbers.length; i++) {\n        total += numbers[i];\n    }\n    console.log("Total:", total);\n    return total;\n}\nconst nums = [1][2][3][4][5];\nlet result = calculateSum(nums);\nPython Output (OpenAI method):\ndef calculate_sum(numbers):\n    total = 0\n    for i in range(len(numbers)):\n        total += numbers[i]\n    print("Total:", total)\n    return total\nnums = [1][2][3][4][5]\nresult = calculate_sum(nums)\nInstallation Requirements\npip install js2py\npip install openai\nLimitations\njs2py: Doesn\'t support ES6+ features, some edge cases may fail\nOpenAI: Requires internet, costs money, may have rate limits\nSimple: Only handles basic syntax transformations\nFor production use, consider using js2py for reliability or OpenAI for code quality.Fa\n'

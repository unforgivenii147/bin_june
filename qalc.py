#!/data/data/com.termux/files/usr/bin/env python
"""
Pure Python implementation of qalc (quick calculator) CLI.
A simple, fast command-line calculator with support for:
- Basic arithmetic operations (+, -, *, /, %, **)
- Unit conversions (length, mass, temperature, etc.)
- Mathematical functions (sin, cos, tan, sqrt, log, etc.)
- Constants (pi, e, etc.)
"""

import argparse
import math
import re
import sys
from typing import Union, Dict, Callable, Any
from decimal import Decimal, getcontext

SKIP_DIRS = frozenset({"lazy", ".git", "__pycache__", ".mypy_cache", ".ruff_cache", ".pytest_cache"})

# Set precision for decimal calculations
getcontext().prec = 28


class UnitConverter:
    """Handles unit conversions."""

    # Length conversions (to meters)
    LENGTH_TO_METERS = {
        "nm": 1e-9,
        "nanometer": 1e-9,
        "um": 1e-6,
        "micrometer": 1e-6,
        "mm": 1e-3,
        "millimeter": 1e-3,
        "cm": 1e-2,
        "centimeter": 1e-2,
        "dm": 1e-1,
        "decimeter": 1e-1,
        "m": 1,
        "meter": 1,
        "km": 1e3,
        "kilometer": 1e3,
        "in": 0.0254,
        "inch": 0.0254,
        "ft": 0.3048,
        "foot": 0.3048,
        "yd": 0.9144,
        "yard": 0.9144,
        "mi": 1609.34,
        "mile": 1609.34,
        "au": 1.496e11,
        "ua": 1.496e11,
        "ly": 9.461e15,
        "lightyear": 9.461e15,
    }

    # Mass conversions (to kg)
    MASS_TO_KG = {
        "mg": 1e-6,
        "milligram": 1e-6,
        "g": 1e-3,
        "gram": 1e-3,
        "kg": 1,
        "kilogram": 1,
        "t": 1000,
        "tonne": 1000,
        "ton": 1000,
        "oz": 0.0283495,
        "ounce": 0.0283495,
        "lb": 0.453592,
        "pound": 0.453592,
    }

    # Volume conversions (to liters)
    VOLUME_TO_LITERS = {
        "ml": 1e-3,
        "milliliter": 1e-3,
        "cc": 1e-3,
        "l": 1,
        "liter": 1,
        "cl": 1e-2,
        "centiliter": 1e-2,
        "dl": 1e-1,
        "deciliter": 1e-1,
        "fl oz": 0.0295735,
        "floz": 0.0295735,
        "pint": 0.473176,
        "quart": 0.946353,
        "gallon": 3.78541,
        "gal": 3.78541,
    }

    # Temperature conversions
    TEMP_UNITS = {"c", "f", "k", "celsius", "fahrenheit", "kelvin"}

    @staticmethod
    def convert(value: float, from_unit: str, to_unit: str) -> float:
        """Convert between units."""
        from_unit = from_unit.lower().strip()
        to_unit = to_unit.lower().strip()

        if from_unit == to_unit:
            return value

        # Length conversion
        if from_unit in UnitConverter.LENGTH_TO_METERS and to_unit in UnitConverter.LENGTH_TO_METERS:
            meters = value * UnitConverter.LENGTH_TO_METERS[from_unit]
            return meters / UnitConverter.LENGTH_TO_METERS[to_unit]

        # Mass conversion
        if from_unit in UnitConverter.MASS_TO_KG and to_unit in UnitConverter.MASS_TO_KG:
            kg = value * UnitConverter.MASS_TO_KG[from_unit]
            return kg / UnitConverter.MASS_TO_KG[to_unit]

        # Volume conversion
        if from_unit in UnitConverter.VOLUME_TO_LITERS and to_unit in UnitConverter.VOLUME_TO_LITERS:
            liters = value * UnitConverter.VOLUME_TO_LITERS[from_unit]
            return liters / UnitConverter.VOLUME_TO_LITERS[to_unit]

        # Temperature conversion
        if from_unit in UnitConverter.TEMP_UNITS and to_unit in UnitConverter.TEMP_UNITS:
            return UnitConverter._convert_temperature(value, from_unit, to_unit)

        raise ValueError(f"Cannot convert between {from_unit} and {to_unit}")

    @staticmethod
    def _convert_temperature(value: float, from_unit: str, to_unit: str) -> float:
        """Convert between temperature units."""
        # Normalize unit names
        from_unit = from_unit[0].lower()  # c, f, k
        to_unit = to_unit[0].lower()

        # Convert to Kelvin first
        if from_unit == "c":
            kelvin = value + 273.15
        elif from_unit == "f":
            kelvin = (value + 459.67) * 5 / 9
        else:  # from_unit == 'k'
            kelvin = value

        # Convert from Kelvin to target
        if to_unit == "c":
            return kelvin - 273.15
        elif to_unit == "f":
            return kelvin * 9 / 5 - 459.67
        else:  # to_unit == 'k'
            return kelvin


class Calculator:
    """Main calculator engine."""

    def __init__(self):
        """Initialize calculator with constants and functions."""
        self.constants = {
            "pi": math.pi,
            "π": math.pi,
            "e": math.e,
            "phi": (1 + math.sqrt(5)) / 2,  # Golden ratio
            "φ": (1 + math.sqrt(5)) / 2,
            "tau": 2 * math.pi,
            "τ": 2 * math.pi,
            "inf": float("inf"),
            "nan": float("nan"),
        }

        self.functions = {
            "sin": math.sin,
            "cos": math.cos,
            "tan": math.tan,
            "asin": math.asin,
            "arcsin": math.asin,
            "acos": math.acos,
            "arccos": math.acos,
            "atan": math.atan,
            "arctan": math.atan,
            "sinh": math.sinh,
            "cosh": math.cosh,
            "tanh": math.tanh,
            "sqrt": math.sqrt,
            "cbrt": lambda x: x ** (1 / 3),
            "abs": abs,
            "log": math.log10,
            "log10": math.log10,
            "log2": math.log2,
            "ln": math.log,
            "exp": math.exp,
            "deg": math.degrees,
            "rad": math.radians,
            "floor": math.floor,
            "ceil": math.ceil,
            "round": round,
            "factorial": math.factorial,
        }

    def _tokenize(self, expression: str) -> list:
        """Tokenize input expression."""
        # Replace ^ with ** for exponentiation
        expression = expression.replace("^", "**")

        # Pattern to match tokens
        pattern = r"""
            (\d+\.?\d*(?:[eE][+-]?\d+)?)|  # Numbers (including scientific notation)
            ([a-zA-Z_]\w*)|                 # Variables/functions/units
            ([+\-*/%()])|                   # Operators and parentheses
            (\*\*)|                          # Power operator
            ("|\')|                          # Quote characters (for unit conversion)
            (\s+)                            # Whitespace
        """

        tokens = []
        for match in re.finditer(pattern, expression, re.VERBOSE):
            token = match.group()
            if token and not token.isspace():
                tokens.append(token)

        return tokens

    def _parse_unit_conversion(self, tokens: list) -> list:
        """Parse unit conversion syntax: value"from_unit to_unit or valueunit1unit2."""
        result = []
        i = 0
        while i < len(tokens):
            # Handle quote syntax: 1024"kb mb
            if i + 2 < len(tokens) and tokens[i + 1] == '"':
                value_str = tokens[i]
                try:
                    value = float(value_str)
                    from_unit = tokens[i + 2]
                    to_unit = tokens[i + 3] if i + 3 < len(tokens) and tokens[i + 3] not in "+-*/%()" else None

                    if to_unit:
                        # Perform conversion
                        converted = UnitConverter.convert(value, from_unit, to_unit)
                        result.append(str(converted))
                        i += 4
                        continue
                except (ValueError, IndexError):
                    pass

            result.append(tokens[i])
            i += 1

        return result

    def evaluate(self, expression: str) -> Union[float, str]:
        """Evaluate a mathematical expression."""
        try:
            # Tokenize
            tokens = self._tokenize(expression)

            if not tokens:
                return 0

            # Parse unit conversions
            tokens = self._parse_unit_conversion(tokens)

            # Build a safe evaluation namespace
            namespace = self.constants.copy()
            namespace.update(self.functions)

            # Join tokens and clean up
            expr_str = "".join(tokens)

            # Evaluate the expression
            result = eval(expr_str, {"__builtins__": {}}, namespace)

            return result

        except ZeroDivisionError:
            return "Error: Division by zero"
        except ValueError as e:
            return f"Error: {str(e)}"
        except NameError as e:
            return f"Error: Unknown variable or function: {str(e)}"
        except SyntaxError:
            return f"Error: Invalid expression syntax"
        except Exception as e:
            return f"Error: {str(e)}"

    def format_result(self, result: Union[float, str]) -> str:
        """Format result for display."""
        if isinstance(result, str):  # Error message
            return result

        if isinstance(result, bool):
            return str(result)

        if math.isnan(result):
            return "NaN"

        if math.isinf(result):
            return "inf" if result > 0 else "-inf"

        # Check if result is an integer
        if isinstance(result, float) and result.is_integer():
            return str(int(result))

        # Format with reasonable precision
        if abs(result) < 1e-10 and result != 0:
            return f"{result:.10e}"
        elif abs(result) > 1e10:
            return f"{result:.10e}"
        else:
            # Remove trailing zeros
            formatted = f"{result:.15f}".rstrip("0").rstrip(".")
            return formatted


def create_parser() -> argparse.ArgumentParser:
    """Create CLI argument parser."""
    parser = argparse.ArgumentParser(
        prog="qalc", description="Quick command-line calculator with unit conversion support", add_help=True
    )

    parser.add_argument("expression", nargs="*", help="Mathematical expression to evaluate")

    parser.add_argument(
        "-f",
        "--format",
        choices=["auto", "hex", "oct", "bin", "scientific"],
        default="auto",
        help="Output format (default: auto)",
    )

    parser.add_argument("-p", "--precision", type=int, default=15, help="Decimal precision (default: 15)")

    parser.add_argument(
        "-d", "--degrees", action="store_true", help="Use degrees instead of radians for trig functions"
    )

    parser.add_argument("-i", "--interactive", action="store_true", help="Start interactive calculator mode")

    return parser


def format_result_with_options(result: Union[float, str], format_type: str = "auto") -> str:
    """Format result based on output format option."""
    if isinstance(result, str):  # Error message
        return result

    if format_type == "hex":
        try:
            return hex(int(result))
        except (ValueError, TypeError):
            return str(result)

    elif format_type == "oct":
        try:
            return oct(int(result))
        except (ValueError, TypeError):
            return str(result)

    elif format_type == "bin":
        try:
            return bin(int(result))
        except (ValueError, TypeError):
            return str(result)

    elif format_type == "scientific":
        if isinstance(result, float):
            return f"{result:.10e}"
        return str(result)

    # Default auto format
    return result


def main():
    """Main entry point."""
    parser = create_parser()
    args = parser.parse_args()

    calculator = Calculator()

    # Set precision if specified
    if args.precision:
        getcontext().prec = args.precision

    if args.interactive:
        # Interactive mode
        print("qalc - Quick Calculator (type 'quit' to exit)")
        print("Supports: +, -, *, /, %, **, sin, cos, tan, sqrt, log, etc.")
        print('Units: value"from_unit to_unit (e.g., 1024"kb mb)')
        print()

        while True:
            try:
                expr = input(">>> ").strip()
                if expr.lower() in ("quit", "exit", "q"):
                    break
                if not expr:
                    continue

                result = calculator.evaluate(expr)
                formatted = calculator.format_result(result)
                formatted = format_result_with_options(formatted, args.format)
                print(formatted)
            except KeyboardInterrupt:
                print("\nExiting...")
                break
            except EOFError:
                break

    elif args.expression:
        # Command-line mode
        expression = " ".join(args.expression)
        result = calculator.evaluate(expression)
        formatted = calculator.format_result(result)
        formatted = format_result_with_options(formatted, args.format)
        print(formatted)

    else:
        # No input provided
        parser.print_help()


if __name__ == "__main__":
    main()

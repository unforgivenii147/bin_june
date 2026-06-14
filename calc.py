#!/data/data/com.termux/files/usr/bin/python

from textual.app import App, ComposeResult
from textual.containers import Grid
from textual.widgets import Button, Static


class Display(Static):
    """Calculator display showing current value."""

    DEFAULT_CSS = "\n    Display {\n        width: 1fr;\n        height: 3;\n        content-align: right middle;\n        background: $surface;\n        border: solid $primary;\n        text-style: bold;\n    }\n    "

    def __init__(self) -> None:
        super().__init__("0")
        self.value = "0"

    def update_display(self, text: str) -> None:
        """Update display text."""
        self.value = text
        self.update(text)


class Calculator(Static):
    """Calculator application."""

    DEFAULT_CSS = "\n    Calculator {\n        width: 50;\n        height: auto;\n        border: solid $accent;\n        background: $panel;\n    }\n    \n    #button-grid {\n        width: 1fr;\n        height: auto;\n        grid-size: 4 5;\n        grid-gutter: 1 1;\n        padding: 1;\n    }\n    \n    Button {\n        width: 1fr;\n        height: 3;\n    }\n    \n    Button.operator {\n        background: $accent 80%;\n    }\n    \n    Button.equals {\n        background: $success 80%;\n    }\n    \n    Button.clear {\n        background: $error 80%;\n    }\n    "

    def __init__(self) -> None:
        super().__init__()
        self.display_widget = Display()
        self.left_operand = None
        self.operator = None
        self.new_input = True

    def compose(self) -> ComposeResult:
        yield self.display_widget
        with Grid(id="button-grid"):
            yield Button("C", id="clear", classes="clear")
            yield Button("÷", id="divide", classes="operator")
            yield Button("×", id="multiply", classes="operator")
            yield Button("−", id="minus", classes="operator")
            yield Button("7")
            yield Button("8")
            yield Button("9")
            yield Button("+", id="plus", classes="operator")
            yield Button("4")
            yield Button("5")
            yield Button("6")
            yield Button("=", id="equals", classes="equals")
            yield Button("1")
            yield Button("2")
            yield Button("3")
            yield Button(".", id="decimal")
            yield Button("0", id="zero")
            yield Button("", disabled=True)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        button_id = event.button.id
        button_label = str(event.button.label)
        if button_id == "clear":
            self.display_widget.update_display("0")
            self.left_operand = None
            self.operator = None
            self.new_input = True
            return
        if button_id == "equals":
            if self.left_operand is not None and self.operator is not None:
                right_operand = float(self.display_widget.value)
                result = self._calculate(self.left_operand, self.operator, right_operand)
                self.display_widget.update_display(result)
                self.left_operand = None
                self.operator = None
                self.new_input = True
            return
        if button_id in ("plus", "minus", "multiply", "divide"):
            current_value = float(self.display_widget.value)
            if self.left_operand is not None and self.operator is not None and (not self.new_input):
                result = self._calculate(self.left_operand, self.operator, current_value)
                self.display_widget.update_display(result)
                self.left_operand = float(result)
            else:
                self.left_operand = current_value
            operator_map = {"plus": "+", "minus": "−", "multiply": "×", "divide": "÷"}
            self.operator = operator_map[button_id]
            self.new_input = True
            return
        if button_label in "0123456789" or button_id == "decimal":
            if button_id == "decimal":
                if "." in self.display_widget.value:
                    return
                button_label = "."
            if self.new_input:
                if button_label == ".":
                    self.display_widget.update_display("0.")
                else:
                    self.display_widget.update_display(button_label)
                self.new_input = False
            else:
                current = self.display_widget.value
                if len(current) < 12:
                    self.display_widget.update_display(current + button_label)

    def _calculate(self, left: float, operator: str, right: float) -> str:
        """Perform the calculation and return result as string."""
        try:
            if operator == "+":
                result = left + right
            elif operator == "−":
                result = left - right
            elif operator == "×":
                result = left * right
            elif operator == "÷":
                if right == 0:
                    return "Error"
                result = left / right
            else:
                return "Error"
            if result == int(result):
                return str(int(result))
            else:
                return f"{result:.10g}"
        except Exception:
            return "Error"


if __name__ == "__main__":

    class CalcApp(App):
        BINDINGS = [("q", "quit", "Quit")]

        def compose(self) -> ComposeResult:
            yield Calculator()

    app = CalcApp()
    app.run()

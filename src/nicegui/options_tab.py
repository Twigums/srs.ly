# need tomlkit for introducing changes
import tomlkit

from nicegui import app, ui
from nicegui.events import ValueChangeEventArguments

from src.dataclasses import AppConfig

class OptionsTab(ui.element):
    def __init__(self, config: AppConfig):
        super().__init__()

        self.srs_app = config.srs_app

        with open("config.toml", "r") as f:
            self.config = tomlkit.parse(f.read())

        self.keybinds = self.config["keybinds"]
        self.keybind_inputs = []

        self.db_switch = ui.switch("DB Status", value = True, on_change = lambda e: self.set_db_status(e))

        # set up how the dark mode button looks
        self.dark = ui.dark_mode()
        self.dark.value = app.storage.user["is_dark_mode"]
        self.dark_switch = ui.switch("Dark Mode", on_change = lambda e: self.save_dark_mode(e)).bind_value(self.dark)

        ui.separator()

        ui.label("Keybinds")

        for k in self.keybinds:
            self.keybind_inputs.append(ui.input(k, value = self.keybinds[k], on_change = lambda e: self.save_keybinds(e, k)))

        ui.separator()

        ui.button("Reload page", on_click = ui.navigate.reload)

    # turns on/off backend db depending on switch status
    def set_db_status(self, e: ValueChangeEventArguments) -> bool:
        if e.value:
            self.srs_app.init_db()
            ui.notify("Connected to DB!")

            return True

        else:
            self.srs_app.close_db()
            ui.notify("Closed DB!")

        return False

    def save_dark_mode(self, e: ValueChangeEventArguments) -> None:
        app.storage.user["is_dark_mode"] = e.value

        return None

    def save_keybinds(self, e: ValueChangeEventArguments, keybind_key) -> None:

        self.config["keybinds"][keybind_key] = e.value

        with open("config.toml", "w") as f:
            f.write(tomlkit.dumps(self.config))

        return None
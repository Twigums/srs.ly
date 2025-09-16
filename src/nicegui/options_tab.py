from nicegui import app, ui
from nicegui.events import ValueChangeEventArguments


class OptionsTab(ui.element):
    def __init__(self, srs_app):
        super().__init__()

        self.srs_app = srs_app

        self.db_switch = ui.switch("DB Status", value = True, on_change = lambda e: self.set_db_status(e))

        # set up how the dark mode button looks
        self.dark = ui.dark_mode()
        self.dark.value = app.storage.user["is_dark_mode"]
        self.dark_switch = ui.switch("Dark Mode", on_change = lambda e: self.save_dark_mode(e)).bind_value(self.dark)

    # turns on/off backend db depending on switch status
    def set_db_status(self, e: ValueChangeEventArguments):
        if e.value:
            self.srs_app.init_db()
            ui.notify("Connected to DB!")

        else:
            self.srs_app.close_db()
            ui.notify("Closed DB!")

    def save_dark_mode(self, e: ValueChangeEventArguments):
        app.storage.user["is_dark_mode"] = e.value

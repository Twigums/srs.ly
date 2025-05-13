from nicegui import ui


def options_tab_content(srs_app):
    ui.switch("DB Status", value = True, on_change = lambda e: set_db_status(e))

    # turns on/off backend db depending on switch status
    def set_db_status(e):
        if e.value:
            srs_app.init_db()
            ui.notify("Connected to DB!")
    
        else:
            srs_app.close_db()
            ui.notify("Closed DB!")
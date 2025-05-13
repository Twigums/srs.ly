from nicegui import ui


def options_tab_content():
    # set up how the dark mode button looks
    dark = ui.dark_mode()
    dark_switch = ui.switch("Dark Mode").bind_value(dark)
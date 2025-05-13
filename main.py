from nicegui import ui

from src.srs_app import SrsApp
from src.nicegui.main_tab import main_tab_content
from src.nicegui.review_tab import review_tab_content
from src.nicegui.add_tab import add_tab_content
from src.nicegui.options_tab import options_tab_content


# initialize the app
srs_app = SrsApp()
srs_app.init_db()

ui_port = 8080
ui_web_title = "SRS Tool"

# get keybinds
key_ignore_answer = srs_app.keybinds["ignore_answer"]
key_add_as_valid_response = srs_app.keybinds["add_as_valid_response"]
key_quit_after_current_set = srs_app.keybinds["quit_after_current_set"].split(",")[-1]

# main website function
@ui.page("/")
def index():
    ui.add_head_html("<link href='https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@400;700&display=swap' rel='stylesheet'>")
    ui.add_head_html("""
    <style>
        .japanese-main-text {
            font-family: 'Noto Sans JP', sans-serif;
            font-size: 2rem;
        }
        .japanese-text {
            font-family: 'Noto Sans JP', sans-serif;
        }
        .main-text {
            font-family: 'Noto Sans', sans-serif;
            font-size: 2rem;
        }
        .card-container {
            min-width: 10rem;
            max-width: 100rem;
            margin: 0 auto;
        }
        .table-container table td {
            padding: 8px;
            vertical-align: top;
        }
        .vocab-table .q-table__middle {
            max-height: 25rem;
            overflow-y: auto;
        }
    </style>
    """)

    # main items on the website
    header = ui.header().classes("bg-blue-500 text-white")
    tabs = ui.tabs().classes("w-full")
    
    with header:
        ui.label("SRS Tool").classes("text-h4 q-px-md")

    # define our tabs we will use
    with tabs:
        main_tab = ui.tab("Main")
        review_tab = ui.tab("Review")
        add_tab = ui.tab("Add Item")
        options_tab = ui.tab("Options")

    # main tab should be the default
    with ui.tab_panels(tabs, value = main_tab).classes("w-full"):

        # definitions for the main tab
        # we should show stats and refresh it automatically!
        with ui.tab_panel(main_tab):
            main_tab_content(srs_app)
            

        # srs review tab to show review cards one by one
        with ui.tab_panel(review_tab):
            review_tab_content(srs_app)

        # add items tab
        with ui.tab_panel(add_tab):
            add_tab_content(srs_app)

        # options tab
        with ui.tab_panel(options_tab):
            options_tab_content()
            

# start serving the site
ui.run(port = ui_port, title = ui_web_title)

from nicegui import ui, app

from src.srs_app import SrsApp
from src.nicegui.main_tab import MainTab
from src.nicegui.review_tab import ReviewTab
from src.nicegui.add_tab import AddTab
from src.nicegui.edit_tab import EditTab
from src.nicegui.search_tab import SearchTab
from src.nicegui.options_tab import OptionsTab


# initialize the app
srs_app = SrsApp()
srs_app.init_db()

ui_port = 8080
ui_web_title = "SRS Tool"

# get keybinds
key_ignore_answer = srs_app.keybinds["ignore_answer"]
key_add_as_valid_response = srs_app.keybinds["add_as_valid_response"]
key_quit_after_current_set = srs_app.keybinds["quit_after_current_set"].split(",")[-1]

# check if user is using mobile or not
is_mobile = False

app.on_connect(lambda: check_device())

def check_device() -> None:
    res = ui.context.client.request.headers["user-agent"]

    if "Mobile" in res:
        global is_mobile
        is_mobile = True

    print(f"Connected from: {res}")

    return None

# main website function
@ui.page("/")
def index() -> None:
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

    # prevents space bar from making a page down operation
    ui.run_javascript("""
        document.addEventListener('keydown', function(event) {
            if (event.code === 'Space' && event.target === document.body) {
                event.preventDefault();
            }
        });
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
        add_tab = ui.tab("Add Items")
        edit_tab = ui.tab("Edit Items")
        search_tab = ui.tab("Search")
        options_tab = ui.tab("Options")

    # main tab should be the default
    with ui.tab_panels(tabs, value = main_tab).classes("w-full"):

        # definitions for the main tab
        # we should show stats and refresh it automatically!
        with ui.tab_panel(main_tab):
            MainTab(srs_app)

        # srs review tab to show review cards one by one
        with ui.tab_panel(review_tab):
            ReviewTab(srs_app)

        # add items tab
        with ui.tab_panel(add_tab):
            AddTab(srs_app)

        # edit items
        with ui.tab_panel(edit_tab):
            EditTab(srs_app)

        # draw and search
        with ui.tab_panel(search_tab):
            SearchTab(srs_app)

        # options tab
        with ui.tab_panel(options_tab):
            OptionsTab(srs_app)

    return None

# start serving the site
if __name__ in {"__main__", "__mp_main__"}:
    import sys

    if len(sys.argv) == 2:

        # for the sake of testing, i want to be able to just host the website on whatever port
        open_port = int(sys.argv[1])

    else:
        open_port = ui_port

    ui.run(port = open_port, title = ui_web_title)
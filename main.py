import tomllib

from nicegui import ui, app

from src.srs_app import SrsApp
from src.dataclasses import AppConfig, SrsConfig
from src.nicegui.main_tab import MainTab
from src.nicegui.review_tab import ReviewTab
from src.nicegui.add_tab import AddTab
from src.nicegui.edit_tab import EditTab
from src.nicegui.search_tab import SearchTab
from src.nicegui.options_tab import OptionsTab


def check_device(config: AppConfig) -> None:
    res = ui.context.client.request.headers["user-agent"]

    config.is_mobile = "Mobile" in res
    print(f"Connected from: {res}")

    return None

def setup_styles() -> None:

    # css
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

    # prevent space from scrolling
    ui.run_javascript("""
        document.addEventListener('keydown', function(event) {
            if (event.code === 'Space' && event.target === document.body) {
                event.preventDefault();
            }
        });
    """)

    return None

# very important -> dark mode
def setup_dark_mode() -> None:
    if "is_dark_mode" not in app.storage.user:
        app.storage.user["is_dark_mode"] = False

    ui_dark = ui.dark_mode()
    ui_dark.value = app.storage.user["is_dark_mode"]

    return None

def create_page(config: AppConfig) -> None:

    # setup
    setup_styles()
    setup_dark_mode()

    # main items on the website
    header = ui.header().classes("bg-blue-500 text-white")
    tabs = ui.tabs().classes("w-full")

    with header:
        ui.label(config.ui_web_title).classes("text-h4 q-px-md")

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
            MainTab(config)

        # srs review tab to show review cards one by one
        with ui.tab_panel(review_tab):
            ReviewTab(config)

        # add items tab
        with ui.tab_panel(add_tab):
            AddTab(config)

        # edit items
        with ui.tab_panel(edit_tab):
            EditTab(config)

        # draw and search
        with ui.tab_panel(search_tab):
            SearchTab(config)

        # options tab
        with ui.tab_panel(options_tab):
            OptionsTab(config)

    return None

def main():
    with open("config.toml", "rb") as f:
        config = tomllib.load(f)

    config_srs = SrsConfig(
        srs_interval = config["srs_interval"],
        path_to_srs_db = config["path_to_srs_db"],
        path_to_full_db = config["path_to_full_db"],
        max_reviews_at_once = config["max_reviews_at_once"],
        entries_before_commit = config["entries_before_commit"],
        match_score_threshold = config["match_score_threshold"]
    )

    srs_app = SrsApp(config_srs)
    srs_app.init_db()

    config_app = AppConfig(
        srs_app = srs_app,
        debug_mode = config["debug_mode"],
        keybinds = config["keybinds"]
    )

    app.on_connect(lambda: check_device(config_app))

    @ui.page("/")
    def index() -> None:
        create_page(config_app)

    # for the sake of testing, be able to change port to whatever
    import sys

    if len(sys.argv) == 2:
        config_app.ui_port = int(sys.argv[1])

    # serve site
    ui.run(port = config_app.ui_port,
           title = config_app.ui_web_title,
           storage_secret = config_app.ui_storage_secret
    )

# start serving the site
if __name__ in {"__main__", "__mp_main__"}:
    main()

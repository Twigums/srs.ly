from nicegui import ui, app
from dataclasses import dataclass
from typing import Optional

from src.srs_app import SrsApp
from src.nicegui.main_tab import MainTab
from src.nicegui.review_tab import ReviewTab
from src.nicegui.add_tab import AddTab
from src.nicegui.edit_tab import EditTab
from src.nicegui.search_tab import SearchTab
from src.nicegui.options_tab import OptionsTab


# init config
@dataclass
class AppConfig:

    # check if user is using mobile or not
    is_mobile: bool = False

    srs_app: Optional[object] = None
    ui_port: int = 8080
    ui_web_title: str = "srs.ly"
    ui_storage_secret: str = "test"

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
            MainTab(config.srs_app)

        # srs review tab to show review cards one by one
        with ui.tab_panel(review_tab):
            ReviewTab(config.srs_app)

        # add items tab
        with ui.tab_panel(add_tab):
            AddTab(config.srs_app)

        # edit items
        with ui.tab_panel(edit_tab):
            EditTab(config.srs_app)

        # draw and search
        with ui.tab_panel(search_tab):
            SearchTab(config.srs_app)

        # options tab
        with ui.tab_panel(options_tab):
            OptionsTab(config.srs_app)

    return None

def main():
    srs_app = SrsApp()
    srs_app.init_db()

    config = AppConfig(srs_app = srs_app)
    app.on_connect(lambda: check_device(config))

    @ui.page("/")
    def index() -> None:
        create_page(config)

    # for the sake of testing, be able to change port to whatever
    import sys

    if len(sys.argv) == 2:
        config.ui_port = int(sys.argv[1])

    # serve site
    ui.run(port = config.ui_port,
           title = config.ui_web_title,
           storage_secret = config.ui_storage_secret
    )

# start serving the site
if __name__ in {"__main__", "__mp_main__"}:
    main()

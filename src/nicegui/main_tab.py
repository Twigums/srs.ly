from nicegui import ui

from src.dataclasses import AppConfig


class MainTab(ui.element):
    def __init__(self, config):
        super().__init__()

        self.srs_app = config.srs_app

        self.main_page_grid = ui.grid(columns = 2).classes("gap-4")
        self.refresh_timer = ui.timer(interval = 60.0, callback = lambda: self.load_stats())
        self.refresh_button = ui.button("Refresh Stats", color = "primary", on_click = lambda: self.load_stats())

        with self.main_page_grid:
            self.load_stats()

    # load stats accordingly for the main page
    def load_stats(self) -> bool:
        self.main_page_grid.clear()

        res = self.srs_app.get_review_stats()

        if res:
            df_grade_counts, df_today_counts, df_ratio = res

        else:
            ui.notify("DB not connected.")

            return False

        df_reviews = self.srs_app.get_due_reviews()
        grade_values = df_grade_counts.iloc[:, -1].tolist()

        # i will use the houhou definitions (similar to wanikani)
        with self.main_page_grid:
            if grade_values == []:
                ui.notify("Start adding items and reviewing to see stats!")

                return False

            ui.label("# of Reviews Due")
            ui.label(f"{len(df_reviews)} / {df_today_counts.values[0][0]}")

            ui.label("Discovering")
            ui.label(grade_values[0] + grade_values[1])

            ui.label("Committing")
            ui.label(grade_values[2] + grade_values[3])

            ui.label("Bolstering")
            ui.label(grade_values[4] + grade_values[5])

            ui.label("Assimilating")
            ui.label(grade_values[6] + grade_values[7])

            ui.label("Set in Stone")
            ui.label(grade_values[8])

            # additional correct %
            ui.label("Correct %")
            ui.label(df_ratio.values[0] * 100)

        return True

from nicegui import ui


# load stats accordingly for the main page
def load_stats(srs_app, grid):
    grid.clear()

    res = srs_app.get_review_stats()
    if res:
        df_grade_counts, df_today_counts, df_ratio = res

    else:
        ui.notify("DB not connected.")

        return None

    df_reviews = srs_app.get_due_reviews()
    grade_values = df_grade_counts.iloc[:, -1].tolist()

    # i will use the houhou definition (similar to wanikani)
    with grid:
        if grade_values == []:
            ui.notify("Start adding items and reviewing to see stats!")

            return None

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

def main_tab_content(srs_app):
    with ui.grid(columns = 2).classes("gap-4") as main_page_grid:
        load_stats(srs_app, main_page_grid)
    
    ui.timer(interval = 60.0, callback = lambda: load_stats(srs_app, main_page_grid))
    ui.button("Refresh Stats", color = "primary", on_click = lambda: load_stats(srs_app, main_page_grid))
from nicegui import ui


# load stats accordingly for the main page
def load_stats(srs_app, grid):
    grid.clear()

    res = srs_app.get_review_stats()
    if res:
        df_counts, df_ratio = res

    else:
        ui.notify("DB not connected.")

        return None

    df_reviews = srs_app.get_due_reviews()
    values = df_counts.iloc[:, 0].tolist()

    # i will use the houhou definition (similar to wanikani)
    with grid:
        ui.label("# of Reviews")
        ui.label(len(df_reviews))

        ui.label("Discovering")
        ui.label(values[0] + values[1])

        ui.label("Committing")
        ui.label(values[2] + values[3])

        ui.label("Bolstering")
        ui.label(values[4] + values[5])

        ui.label("Assimilating")
        ui.label(values[6] + values[7])

        ui.label("Set in Stone")
        ui.label(values[8])

        # additional correct %
        ui.label("Correct %")
        ui.label(df_ratio.values[0] * 100)

def main_tab_content(srs_app):
    ui.switch("DB Status", value = True, on_change = lambda e: set_db_status(e))
    
    with ui.grid(columns = 2).classes("gap-4") as main_page_grid:
        load_stats(srs_app, main_page_grid)
    
    ui.timer(interval = 60.0, callback = lambda: load_stats(srs_app, main_page_grid))
    ui.button("Refresh Stats", color = "primary", on_click = lambda: load_stats(srs_app, main_page_grid))
    
    # turns on/off backend db depending on switch status
    def set_db_status(e):
        if e.value:
            srs_app.init_db()
            ui.notify("Connected to DB!")
    
        else:
            srs_app.close_db()
            ui.notify("Closed DB!")
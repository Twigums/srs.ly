import pandas as pd

from nicegui import ui


class EditTab(ui.element):
    def __init__(self, srs_app):
        super().__init__()

        self.srs_app = srs_app

        # dictionary to store selected item information
        # this is important for sending information back to the app
        self.selected_items = dict()

        self.edit_card = ui.card().classes("card-container")

        with self.edit_card:
            ui.label("Edit New Items").classes("text-h4")

            # selection filter options
            with ui.row():
                self.item_type = ui.select(
                    options = {"vocab": "Vocabulary", "kanji": "Kanji"},
                    multiple = True, 
                    label = "Type"
                ).classes("w-64").props("use-chips")
    
                self.srs_levels = ui.select(
                    options = [key for key in self.srs_app.srs_interval.keys()], 
                    multiple = True, 
                    label = "SRS Level"
                ).classes("w-64").props("use-chips")

                self.meaning_search = ui.input("Meaning").classes("w-64").props("clearable")
                self.reading_search = ui.input("Reading").classes("w-64").props("clearable")
    
                search_button = ui.button("Search", color = "primary", on_click = lambda: self.update_search_results())
    
            # define containers to display items
            self.table_container = ui.element("div").classes("japanese-text w-full")
            self.items_separator = ui.separator()
            self.input_container = ui.column()
    
            self.add_button = ui.button("Edit Selected Items", color = "green", on_click = lambda: self.edit_selected_items())
            self.add_spinner = ui.spinner(size = "lg")
    
            self.add_button.visible = False
            self.add_spinner.visible = False

    # updates the selection page every call
    # also resets the containers
    def update_search_results(self) -> None:
        self.table_container.clear()
        self.input_container.clear()
        self.selected_items.clear()
        self.add_button.visible = False
    
        # sql query conditions to filter results
        srs_condition = ",".join([str(val) for val in self.srs_levels.value])
        meaning_condition = self.meaning_search.value
        reading_condition = self.reading_search.value

        # empty list to store dfs from kanji and vocab
        list_dfs = []
        display_df_columns = ["Item_ID", "Kanji", "Readings", "Reading Notes", "Meanings", "Meaning Notes", "Current SRS Grade", "Next Answer Date"]

        conditions = []

        if len(srs_condition) != 0:
            conditions.append(f"{self.srs_app.col_dict["current_grade_col"]} IN ({srs_condition})")

        if meaning_condition not in ["", None]:
            conditions.append(f"',' || Meanings || ',' LIKE '%,{meaning_condition},%'")

        if reading_condition not in ["", None]:
            conditions.append(f"',' || Readings || ',' LIKE '%,{reading_condition},%'")

        # need to set a base condition if no filters were applied
        if conditions == []:
            condition = "1=1"

        else:
            condition = " AND ".join(conditions)

        # handle kanji
        if "kanji" in self.item_type.value:
            df_kanji = self.srs_app.filter_study_items(item_type = "kanji", condition = condition)
    
            if not df_kanji.empty:
                display_df_kanji = df_kanji[["ID", "AssociatedKanji", "Readings", "ReadingNote", "Meanings", "MeaningNote", "CurrentGrade", "NextAnswerDateISO"]].copy()
                display_df_kanji.columns = display_df_columns
                display_df_kanji["Type"] = "kanji"

                list_dfs.append(display_df_kanji)

        # handle vocab
        if "vocab" in self.item_type.value:
    
            df_vocab = self.srs_app.filter_study_items(item_type = "vocab", condition = condition)
    
            if not df_vocab.empty:
                display_df_vocab = df_vocab[["ID", "AssociatedVocab", "Readings", "ReadingNote", "Meanings", "MeaningNote", "CurrentGrade", "NextAnswerDateISO"]].copy()
                display_df_vocab.columns = display_df_columns
                display_df_vocab["Type"] = "vocab"

                list_dfs.append(display_df_vocab)

        # only show if something is selected
        if list_dfs:
    
            # combine both tables so we can display it
            display_df = pd.concat(list_dfs, ignore_index = True)
            display_df = display_df.sort_values(by = ["Current SRS Grade"])
    
            with self.table_container:
                ui.label(f"Found {len(display_df)} items").classes("text-h6")
    
                with ui.element("div").classes("table-container w-full"):
                    rows = [
                        {
                            **{col: row[col] for col in display_df_columns},

                            # hidden tags to use for rows
                            "id": i,
                            "type": row["Type"],
                            # Item_ID also exists and will be hidden
                        }
                        for i, row in display_df.iterrows()
                    ]
    
                    # define columns to display
                    columns = [
                        {"name": "kanji", "label": "Kanji", "field": "Kanji", "required": True},
                        {"name": "readings", "label": "Readings", "field": "Readings", "required": True},
                        {"name": "readingnotes", "label": "Reading Notes", "field": "Reading Notes", "required": True},
                        {"name": "meanings", "label": "Meanings", "field": "Meanings", "required": True},
                        {"name": "meaningnotes", "label": "Meaning Notes", "field": "Meaning Notes", "required": True},
                        {"name": "srsgrade", "label": "Current SRS Grade", "field": "Current SRS Grade", "sortable": True},
                        {"name": "nextanswer", "label": "Next Answer Date", "field": "Next Answer Date", "sortable": True},
                    ]

                    table = ui.table(
                        rows = rows,
                        columns = columns,
                        column_defaults = {
                            "align": "left",
                            "headerClasses": "uppercase text-primary",
                        },
                        row_key = "id",
                        selection = "multiple",
                        on_select = lambda e: self.render_inputs(e.selection),
                        pagination = 100, # # of items to show on a page
                    ).classes("w-full vocab-table")

        return None
    
    # function to show selected rows as individual rows below table
    def render_inputs(self, selected: list) -> bool:
        print(selected)
        self.input_container.clear()
        self.selected_items.clear()

        match len(selected):
            case 0:
                self.add_button.visible = False
                self.items_separator.visible = False

                return False

            # if an item is selected
            case _:
                self.add_button.visible = True
                self.items_separator.visible = True

                # display a row for each item
                for i, item in enumerate(selected):
                    with self.input_container:
                        with ui.row():

                            display_df_columns = ["Kanji", "Readings", "Reading Notes", "Meanings", "Current SRS Grade", "Next Answer Date"]
                            # kanji items should have their readings
                            # vocab items should have their tags

                            kanji_input = ui.input("Kanji", value = item["Kanji"])
                            readings_input = ui.input("Readings", value = item["Readings"])
                            reading_notes_input = ui.input("Reading Notes", value = item["Reading Notes"])
                            meanings_input = ui.input("Meanings", value = item["Meanings"])
                            meaning_notes_input = ui.input("Meaning Notes", value = item["Meaning Notes"])
                            current_grade_input = ui.input("Current SRS Grade", value = item["Current SRS Grade"])
                            next_answer_input = ui.input("Next Answer Date", value = item["Next Answer Date"])

                        # a separator makes everything more readable
                        ui.separator().style("height: 0.1rem; width: 2rem;")

                    self.selected_items[i] = {
                        "kanji": kanji_input,
                        "readings": readings_input,
                        "reading_notes": reading_notes_input,
                        "meanings": meanings_input,
                        "meaning_notes": meaning_notes_input,
                        "current_grade": current_grade_input,
                        "next_answer": next_answer_input,
                        "type": item["type"],
                        "item_id": item["Item_ID"],
                    }

        return True
    
    # function to send item information to the app
    def edit_selected_items(self) -> None:
        self.add_spinner.visible = True

        for key in self.selected_items:
            self.srs_app.edit_review_item(self.selected_items[key])

        self.add_spinner.visible = False
        self.update_search_results()
        ui.notify("Successfully Edited Items!")

        return None
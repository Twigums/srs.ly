import pandas as pd

from nicegui import ui


# helper function to bfill, but for some reason there are funny "" or " " in the df?
# so this works better than bfill :(
def first_valid(row: pd.core.series.Series) -> str | int | float | None:
    for val in row:
        if isinstance(val, str):
            if val.strip():
                return val

        elif pd.notna(val):
            return val

    return None

class AddTab(ui.element):
    def __init__(self, srs_app):
        super().__init__()

        self.srs_app = srs_app

        # dictionary to store selected item information
        # this is important for sending information back to the app
        self.selected_items = dict()

        self.add_card = ui.card().classes("card-container")

        with self.add_card:
            ui.label("Add New Items").classes("text-h4")
    
            # selection filter options
            with ui.row():
                self.item_type = ui.select(
                    options = {"vocab": "Vocabulary", "kanji": "Kanji"},
                    multiple = True, 
                    label = "Type"
                ).classes("w-64").props("use-chips")
    
                self.jlpt_levels = ui.select(
                    options = [1, 2, 3, 4, 5], 
                    multiple = True, 
                    label = "JLPT Levels"
                ).classes("w-64").props("use-chips")

                self.kanji_search = ui.input("Kanji").classes("w-64").props("clearable")
                self.kana_search = ui.input("Kana").classes("w-64").props("clearable")
    
                search_button = ui.button("Search", color = "primary", on_click = lambda: self.update_search_results())
    
            # define containers to display items
            self.table_container = ui.element("div").classes("japanese-text w-full")
            self.items_separator = ui.separator()
            self.input_container = ui.column()
    
            self.add_button = ui.button("Add Selected Items", color = "green", on_click = lambda: self.add_selected_items())
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
        jlpt_condition = ",".join([str(val) for val in self.jlpt_levels.value])
        kanji_condition = self.kanji_search.value
        kana_condition = self.kana_search.value
    
        # empty list to store dfs from kanji and vocab
        list_dfs = []
    
        # handle kanji
        if "kanji" in self.item_type.value:
            conditions = []

            if len(jlpt_condition) == 0:
                conditions.append("k.JlptLevel IN (1, 2, 3, 4, 5)")

            else:
                conditions.append(f"k.JlptLevel IN ({jlpt_condition})")

            if kanji_condition not in ["", None]:
                conditions.append(f"k.Character = '{kanji_condition}'")

            if kana_condition not in ["", None]:
                conditions.append(f"',' || k.OnYomi || ',' LIKE '%,{kana_condition},%'")

            # need to set a base condition if no filters were applied
            if conditions == []:
                df_kanji = self.srs_app.discover_new_kanji()

            else:
                condition = " AND ".join(conditions)
                df_kanji = self.srs_app.discover_new_kanji(condition = condition)

            if not df_kanji.empty:
                display_df_kanji = df_kanji[["Character", "OnYomi", "KunYomi", "Nanori", "Meaning", "JlptLevel", "WkLevel", "MostUsedRank", "NewspaperRank"]].copy()
                display_df_kanji.columns = ["Kanji", "Onyomi", "Kunyomi", "Nanori", "Meanings", "JLPT", "Wanikani", "Frequency Rank", "Wiki Rank"]
    
                # combine all onyomi, kunyomi, nanori, and meanings into one line
                display_df_kanji = display_df_kanji.groupby(["Kanji"]).agg({
                    "Onyomi": lambda x: ";".join(dict.fromkeys(x)),
                    "Kunyomi": lambda x: ";".join(dict.fromkeys(x)),
                    "Nanori": lambda x: ";".join(dict.fromkeys(x)),
                    "Meanings": lambda x: ";".join(dict.fromkeys(x)),
                    "JLPT": "min",
                    "Wanikani": "min",
                    "Frequency Rank": "min",
                    "Wiki Rank": "min",
                }).reset_index()
    
                # add a few more columns
                display_df_kanji["IsCommon"] = ((display_df_kanji["Frequency Rank"].notna() | display_df_kanji["Wiki Rank"].notna()))
                display_df_kanji["Readings"] = display_df_kanji[["Onyomi", "Kunyomi", "Nanori"]].apply(first_valid, axis = 1)
                display_df_kanji["Type"] = "kanji"
    
                list_dfs.append(display_df_kanji)
    
        # handle vocab
        if "vocab" in self.item_type.value:
            conditions = []

            if len(jlpt_condition) == 0:
                conditions.append("v.JlptLevel IN (1, 2, 3, 4, 5)")

            else:
                conditions.append(f"v.JlptLevel IN ({jlpt_condition})")

            if kanji_condition not in ["", None]:
                conditions.append(f"v.KanjiWriting = '{kanji_condition}'")

            if kana_condition not in ["", None]:
                conditions.append(f"',' || v.KanaWriting || ',' LIKE '%,{kana_condition},%'")

            # need to set a base condition if no filters were applied
            if conditions == []:
                df_vocab = self.srs_app.discover_new_vocab()
    
            else:
                condition = " AND ".join(conditions)
                df_vocab = self.srs_app.discover_new_vocab(condition = condition)
            
            if not df_vocab.empty:
                display_df_vocab = df_vocab[["KanjiWriting", "KanaWriting", "Meaning", "IsCommon", "JlptLevel", "WkLevel", "FrequencyRank", "WikiRank", "ShortName"]].copy()
                display_df_vocab.columns = ["Kanji", "Readings", "Meanings", "IsCommon", "JLPT", "Wanikani", "Frequency Rank", "Wiki Rank", "Tags"]
    
                # combine all meanings and tags into one line
                display_df_vocab = display_df_vocab.groupby(["Kanji", "Readings"]).agg({
                    "Meanings": lambda x: ";".join(dict.fromkeys(x)),
                    "IsCommon": "min",
                    "JLPT": "min",
                    "Wanikani": "min",
                    "Frequency Rank": "min",
                    "Wiki Rank": "min",
                    "Tags": lambda x: ";".join(x),
                }).reset_index()
    
                # add type column
                display_df_vocab["Type"] = "vocab"
    
                list_dfs.append(display_df_vocab)
    
        # only show if something is selected
        if list_dfs:
    
            # combine both tables so we can display it
            display_df = pd.concat(list_dfs, ignore_index = True)
            display_df = display_df.sort_values(by = ["Wiki Rank"])
    
            with self.table_container:
                ui.label(f"Found {len(display_df)} items").classes("text-h6")
    
                with ui.element("div").classes("table-container w-full"):
                    rows = [
                        {
                            "Kanji": row["Kanji"],
                            "Readings": row["Readings"],
                            "Meanings": ",".join([meaning.strip() for meaning in row["Meanings"].split(";")]),
                            "IsCommon": "✅" if row["IsCommon"] else "❌",
                            "JLPT": f"N{row["JLPT"]}" if not pd.isna(row["JLPT"]) else "",
                            "Wanikani": row.get("Wanikani", None),
                            "Frequency Rank": row.get("Frequency Rank", None),
                            "Wiki Rank": row.get("Wiki Rank", None),
                            "Tags": row.get("Tags", None),
    
                            # hidden tags to use for rows
                            "id": i,
                            "type": row["Type"],
                            "onyomi": row.get("Onyomi", None),
                            "kunyomi": row.get("Kunyomi", None),
                            "nanori": row.get("Nanori", None),
                        }
                        for i, row in display_df.iterrows()
                    ]
    
                    # define columns to display
                    columns = [
                        {"name": "kanji", "label": "Kanji", "field": "Kanji", "required": True},
                        {"name": "readings", "label": "Readings", "field": "Readings", "required": True},
                        {"name": "meanings", "label": "Meanings", "field": "Meanings", "required": True},
                        {"name": "iscommon", "label": "Common", "field": "IsCommon", "sortable": True},
                        {"name": "jlpt", "label": "JLPT", "field": "JLPT", "sortable": True},
                        {"name": "wanikani", "label": "Wanikani", "field": "Wanikani", "sortable": True},
                        {"name": "freq", "label": "Freq. Rank", "field": "Frequency Rank", "sortable": True},
                        {"name": "wiki", "label": "Wiki Rank", "field": "Wiki Rank", "sortable": True},
                        {"name": "tags", "label": "Tags", "field": "Tags"},
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

                            # kanji items should have their readings
                            # vocab items should have their tags
                            match item["type"]:
                                case "kanji":
                                    with ui.grid(columns = 2):
                                        ui.label("Onyomi:") 
                                        ui.label(item["onyomi"])

                                        ui.label("Kunyomi:")
                                        ui.label(item["kunyomi"])

                                        ui.label("Nanori:")
                                        ui.label(item["nanori"])
                                case "vocab":
                                    ui.label(f"Vocab has tags: {item["Tags"]}")

                            kanji_input = ui.input("Kanji", value = item["Kanji"])
                            readings_input = ui.input("Readings", value = item["Readings"])
                            meanings_input = ui.input("Meanings", value = item["Meanings"])
                            reading_notes_input = ui.input("Reading Notes", placeholder = "remembering tips!")
                            meaning_notes_input = ui.input("Meaning Notes", placeholder = "remembering tips!")

                        # a separator makes everything more readable
                        ui.separator().style("height: 0.1rem; width: 2rem;")

                    self.selected_items[i] = {
                        "kanji": kanji_input,
                        "readings": readings_input,
                        "meanings": meanings_input,
                        "reading_notes": reading_notes_input,
                        "meaning_notes": meaning_notes_input,
                        "type": item["type"],
                    }

        return True
    
    # function to send item information to the app
    def add_selected_items(self) -> None:
        self.add_spinner.visible = True

        for key in self.selected_items:
            self.srs_app.add_review_item(self.selected_items[key])

        self.add_spinner.visible = False
        self.update_search_results()
        ui.notify("Successfully Added Items!")

        return None
from nicegui import ui
from nicegui.events import KeyEventArguments
from pyokaka import okaka # maybe consider romkan?
from houhou import SrsApp
import re
from rapidfuzz import process
import pandas as pd


app = SrsApp()
alphabet = " abcdefghijklmnopqrstuvwxyz"

def load_stats(grid):
    grid.clear()

    df_counts, df_ratio = app.get_review_stats()
    df_reviews = app.get_due_reviews()
    values = df_counts.iloc[:, 0].tolist()

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

        ui.label("Correct %")
        ui.label(df_ratio.values[0] * 100)

@ui.page("/")
def index():
    ui.add_head_html("<link href='https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@400;700&display=swap' rel='stylesheet'>")
    ui.add_head_html("""
    <style>
        .japanese-main-text {
            font-family: 'Noto Sans JP', sans-serif;
            font-size: 2rem;
        }
        .main-text {
            font-family: 'Noto Sans', sans-serif;
            font-size: 2rem;
        }
        .japanese-text {
            font-family: 'Noto Sans JP', sans-serif;
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
            max-height: 500px;
            overflow-y: auto;
        }
    </style>
    """)

    header = ui.header().classes("bg-blue-500 text-white")
    tabs = ui.tabs().classes("w-full")
    
    with header:
        ui.label("SRS Tool").classes("text-h4 q-px-md")
    
    with tabs:
        main_tab = ui.tab("Main")
        review_tab = ui.tab("Review")
        add_tab = ui.tab("Add Item")

    with ui.tab_panels(tabs, value = main_tab).classes("w-full"):
        with ui.tab_panel(main_tab):
            with ui.grid(columns = 2).classes("gap-4") as main_page_grid:
                load_stats(main_page_grid)
    
            ui.timer(interval = 60.0, callback = lambda: load_stats(main_page_grid))

        with ui.tab_panel(review_tab):
            review_card = ui.card().classes("card-container")

            with review_card:
    
                global text_buffer, kana_output
                text_buffer = ""
                kana_output = ""
    
                correct_message = "✅"
                incorrect_message = "❌"
                
                review_header = ui.label("Deck 1").classes("text-white")
                start_button = ui.button("Start Review", color = "primary", on_click = lambda: start_review())
                review_progress = ui.label("").classes("text-white")
                review_progress.visible = False
                reading_display = ui.label("").classes("japanese-main-text text-center q-py-xl text-white")
                reading_display.visible = False
                
                review_separator = ui.separator()
                review_separator.visible = False
                
                user_romaji = ui.label("").classes("text-white")
                user_hiragana = ui.label("").classes("japanese-main-text text-white")
                user_alphabet = ui.label("").classes("main-text text-white")
    
                res_display = ui.label("").classes("japanese-main-text text-white")
                
                correct_reading_display = ui.label("").classes("japanese-main-text text-white")
                correct_reading_display.visible = False
    
                correct_meaning_display = ui.label("").classes("main-text text-white")
                correct_meaning_display.visible = False
    
                item_dict = dict()
    
                # get keybinds
                key_ignore_answer = app.keybinds["ignore_answer"]
                key_add_as_valid_response = app.keybinds["add_as_valid_response"]
                key_quit_after_current_set = app.keybinds["quit_after_current_set"].split(",")[-1]
    
                def start_review():
                    reviews = app.start_review_session()
                    
                    if not reviews:
                        review_header.text = "All done! 😋"
                        return
    
                    start_button.visible = False
                    reading_display.visible = True
                    review_separator.visible = True
    
                    update_review_display()
                    ui.keyboard(on_key = handle_key)
    
                def update_review_display():
                    current_item = app.get_current_item()
    
                    if not current_item:
                        reading_display.text = ""
                        res_display.text = ""
                        start_button.visible = True
                        review_progress.visible = False
                        reading_display.visible = False
                        review_separator.visible = False
                        correct_reading_display.visible = False
                        correct_meaning_display.visible = False
                        review_card.style("background-color: #26c826")

                        return None
                    
                    review_type = current_item["review_type"]
                    card_type = current_item["card_type"]
    
                    match review_type:
                        case "kanji":
                            reading_display.text = current_item["AssociatedKanji"]
                            review_card.style("background-color: #2e67ff")
    
                        case "vocab":
                            reading_display.text = current_item["AssociatedVocab"]
                            review_card.style("background-color: #aa2eff")
    
                    match card_type:
                        case "reading":
                            review_separator.style("border-top: 0.5rem solid #393939; margin: 0.75rem 0;")
    
                        case "meaning":
                            review_separator.style("border-top: 0.5rem solid #e4e4e4; margin: 0.75rem 0;")
    
                    review_progress.text = f"{app.current_completed} / {app.len_review_ids}"
                    review_progress.visible = True
                
                def handle_key(e: KeyEventArguments):
                    global text_buffer, kana_output
    
                    key = e.key
                    key_str = str(key)
    
                    current_item = app.get_current_item()
                    card_type = current_item["card_type"]
    
                    if e.action.keydown:
                        match key:
                            case "Enter" if res_display.text == incorrect_message:
                                process_answer(user_hiragana.text, current_item)
    
                                res_display.text = ""
                                text_buffer = ""
                                kana_output = ""
                                user_romaji.text = ""
                                user_hiragana.text = ""
                                correct_reading_display.visible = False
                                correct_meaning_display.visible = False
                                app.current_index += 1
                    
                                update_review_display()
                                return
    
                            case "Enter" if len(text_buffer) > 0:
                                process_answer(user_hiragana.text, current_item)
    
                                if res_display.text != incorrect_message:
                                    text_buffer = ""
                                    kana_output = ""
                                    user_romaji.text = ""
                                    user_hiragana.text = ""
                                    app.current_index += 1
                
                                    update_review_display()
                                return
    
                            case app.key_ignore_answer if res_display.text == incorrect_message:
                                process_answer(user_hiragana.text, current_item)
    
                                res_display.text = ""
                                text_buffer = ""
                                kana_output = ""
                                user_romaji.text = ""
                                user_hiragana.text = ""
                                correct_reading_display.visible = False
                                correct_meaning_display.visible = False
                                app.current_index += 1
    
                                update_review_display()
                                return
    
                            case app.key_add_as_valid_response if len(text_buffer) > 0 and res_display.text == incorrect_message:
                                item_id = current_item["ID"]
    
                                app.add_valid_response(user_hiragana.text, current_item)
                                app.current_reviews.pop(app.current_index)
                                item_dict[item_id].append(1)
    
                                # there has to be a better way of doing this
                                # i can't call a function since i dont think it would be able to delete the dictionary key?
                                # more testing is needed
                                if sum(item_dict[item_id]) == 2:
                                    if len(item_dict[item_id]) == 2:
                                        app.update_review_item(item_id, True)
                
                                    else:
                                        app.update_review_item(item_id, False)
                
                                    del item_dict[item_id]
                                    app.update_review_session()
    
                                res_display.text = f"Added '{user_hiragana.text}' to {card_type}."
    
                                text_buffer = ""
                                kana_output = ""
                                user_romaji.text = ""
                                user_hiragana.text = ""
                                correct_reading_display.visible = False
                                correct_meaning_display.visible = False
                                app.current_index += 1
    
                                update_review_display()
                                return
    
                            case app.key_quit_after_current_set if e.modifiers.ctrl:
                                ui.notify("Will quit after the remaining items are completed.")
                                app.stop_updating_review = True
                        
                            case "Backspace":
                                if e.modifiers.ctrl:
                                    text_buffer = " ".join(text_buffer.split(" ")[:-1])
        
                                else:
                                    text_buffer = text_buffer[:-1]
    
                            case "n" if text_buffer.endswith("n"):
                                match card_type:
                                    case "reading":
                                        # n' -> ん
                                        # nn -> っん
                                        text_buffer += "'"
    
                                    case "meaning":
                                        text_buffer += key_str.lower()
                        
                            case _ if key_str in alphabet:
                                text_buffer += key_str.lower()
    
                    match card_type:
                        case "reading":
                            kana_output = okaka.convert(text_buffer)
                            user_hiragana.text = kana_output
    
                        case "meaning":
                            user_hiragana.text = text_buffer
    
                    kana_output = okaka.convert(text_buffer)
                    user_romaji.text = text_buffer
    
                def process_answer(answer, item):
                    card_type = item["card_type"]
                    item_id = item["ID"]
                    answer_stripped = answer.strip()
                    lookup_readings = dict()
    
                    if item_id not in item_dict:
                        item_dict[item_id] = []
    
                    match card_type:
                        case "reading":
                            valid_readings = item["Readings"].split(",")
                            correct_reading_display.text = str(valid_readings)
                            correct_reading_display.visible = True
                            correct_meaning_display.visible = False
    
                            for reading in valid_readings:
                                reading_stripped = reading.strip()
                                lookup_readings[reading_stripped] = reading
    
                            all_valid_readings = list(lookup_readings.keys())
    
                            if answer_stripped in all_valid_readings:
                                matching_score = 100
                                matching_reading = answer_stripped
    
                            else:
                                matching_score = 0
    
                        case "meaning":
                            valid_readings = item["Meanings"].split(",")
                            correct_meaning_display.text = str(valid_readings)
                            correct_meaning_display.visible = True
                            correct_reading_display.visible = False
                    
                            for reading in valid_readings:
                                reading_stripped = reading.strip()
                                remove_all_in_parentheses = re.sub(r"\s*\([^)]*\)\s*", "", reading_stripped)
                                strip_parentheses = re.sub(r"[()]", "", reading_stripped)
            
                                lookup_readings[strip_parentheses] = reading
                                lookup_readings[remove_all_in_parentheses] = reading
                            
                            all_valid_readings = list(lookup_readings.keys())
                            matching_reading, matching_score, _ = process.extractOne(answer_stripped, all_valid_readings)
                    
                    if matching_score > app.match_score_threshold:
                        item_dict[item_id].append(1)
                        res_display.text = correct_message
                        app.current_reviews.pop(app.current_index)
    
                    else:
                        item_dict[item_id].append(0)
                        res_display.text = incorrect_message
    
                    if sum(item_dict[item_id]) == 2:
                        if len(item_dict[item_id]) == 2:
                            app.update_review_item(item_id, True)
    
                        else:
                            app.update_review_item(item_id, False)
    
                        del item_dict[item_id]
                        app.update_review_session()
    
        with ui.tab_panel(add_tab):
            with ui.card().classes("card-container"):
                ui.label("Add New Items").classes("text-h4")
                
                with ui.row():
                    item_type = ui.select(
                        options = {"vocab": "Vocabulary", "kanji": "Kanji"},
                        multiple = True, 
                        label = "Type"
                    ).classes("w-64").props("use-chips")
                    
                    jlpt_levels = ui.select(
                        options = [1, 2, 3, 4, 5], 
                        multiple = True, 
                        label = "JLPT Levels"
                    ).classes("w-64").props("use-chips")
                    
                    # search_input = ui.input(label="Search", placeholder="Enter search term")
                    
                    search_button = ui.button("Search", color = "primary", on_click = lambda: update_search_results())
                
                table_container = ui.element("div").classes("japanese-text w-full")
                items_separator = ui.separator()
                input_container = ui.column()
                
                add_button = ui.button("Add Selected Items", color = "green", on_click = lambda: add_selected_items())
                add_button.visible = False
                
                selected_items = []
                
                def update_search_results():
                    table_container.clear()
                    add_button.visible = False

                    jlpt_condition = ",".join([str(val) for val in jlpt_levels.value])

                    if "kanji" in item_type.value:
                        condition = f"k.JlptLevel IN ({jlpt_condition})"

                        df = app.discover_new_kanji(condition = condition)

                        if not df.empty:
                            display_df = df[["Character", "OnYomi", "KunYomi", "Nanori", "Meaning", "JlptLevel", "WkLevel", "MostUsedRank", "NewspaperRank"]].copy()
                    
                    if "vocab" in item_type.value:
                        condition = f"v.JlptLevel IN ({jlpt_condition})"
                        # if search_input.value:
                            # level_condition += f" AND (v.KanjiWriting LIKE '%{search_input.value}%' OR v.KanaWriting LIKE '%{search_input.value}%')"
                        df = app.discover_new_vocab(condition = condition)
                        
                        if not df.empty:
                            display_df = df[["KanjiWriting", "KanaWriting", "Meaning", "IsCommon", "JlptLevel", "WkLevel", "FrequencyRank", "WikiRank", "ShortName"]].copy()
                            display_df.columns = ["Kanji", "Readings", "Meanings", "IsCommon", "JLPT", "Wanikani", "Frequency Rank", "Wiki Rank", "Tags"]
                            display_df = display_df.groupby(["Kanji", "Readings"]).agg({
                                "Meanings": lambda x: ";".join(x),
                                "IsCommon": "min",
                                "JLPT": "min",
                                "Wanikani": "min",
                                "Frequency Rank": "min",
                                "Wiki Rank": "min",
                                "Tags": lambda x: ";".join(x),
                            }).reset_index()
                            
                            with table_container:
                                ui.label(f"Found {len(display_df)} items").classes("text-h6")
                                
                                with ui.element("div").classes("table-container w-full"):
                                    editable_cols = ["Kanji", "Readings", "Meanings"]
                                    rows = [
                                        {
                                            "Kanji": row["Kanji"],
                                            "Readings": row["Readings"],
                                            "Meanings": ",".join([meaning.strip() for meaning in row["Meanings"].split(";")]),
                                            "IsCommon": "✅" if row["IsCommon"] else "❌",
                                            "JLPT": f"N{row["JLPT"]}" if not pd.isna(row["JLPT"]) else "",
                                            "Wanikani": row["Wanikani"] if not pd.isna(row["Wanikani"]) else "",
                                            "Frequency Rank": row["Frequency Rank"] if not pd.isna(row["Frequency Rank"]) else "",
                                            "Wiki Rank": row["Wiki Rank"] if not pd.isna(row["Wiki Rank"]) else "",
                                            "Tags": row["Tags"] if not pd.isna(row["Tags"]) else "",
                                            "id": i,
                                        }
                                        for i, row in display_df.iterrows()
                                    ]

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
                                        on_select = lambda e: render_inputs(e.selection),
                                        pagination = 100,
                                    ).classes("w-full vocab-table")

                def render_inputs(selected):
                    input_container.clear()

                    match len(selected):
                        case 0:
                            add_button.visible = False
                            items_separator.visible = False

                        case _:
                            add_button.visible = True
                            items_separator.visible = True

                            for item in selected:
                                with input_container:
                                    with ui.row():
                                        ui.label(f"Vocab has tags: {item["Tags"]}")
                                        ui.input("Kanji", value = item["Kanji"], on_change = lambda e: ui.notify(e.value))
                                        ui.input("Readings", value = item["Readings"])
                                        ui.input("Meanings", value = item["Meanings"])
                
                def add_selected_items():
                    print("added")
                    update_search_results()
                    input_container.clear()

ui.run(port = 7012, title = "srs tool")

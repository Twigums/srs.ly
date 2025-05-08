from nicegui import ui
from nicegui.events import KeyEventArguments
from pyokaka import okaka # maybe consider romkan?
from houhou import SrsApp
import re
from rapidfuzz import process
import pandas as pd


# initialize the app
app = SrsApp()

# define the proper alphabet for review entry
alphabet = " abcdefghijklmnopqrstuvwxyz"

# define a few other global variables
correct_message = "✅"
incorrect_message = "❌"
text_buffer = ""
kana_output = ""

ui_port = 8080
ui_web_title = "SRS Tool"

# get keybinds
key_ignore_answer = app.keybinds["ignore_answer"]
key_add_as_valid_response = app.keybinds["add_as_valid_response"]
key_quit_after_current_set = app.keybinds["quit_after_current_set"].split(",")[-1]

"""
helper functions come first
"""

# load stats accordingly for the main page
def load_stats(grid):
    grid.clear()

    df_counts, df_ratio = app.get_review_stats()
    df_reviews = app.get_due_reviews()
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

# helper function to bfill, but for some reason there are funny "" or " " in the df?
# so this works better than bfill :(
def first_valid(row):
    for val in row:
        if isinstance(val, str):
            if val.strip():
                return val

        elif pd.notna(val):
            return val

    return None

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

    # main tab should be the default
    with ui.tab_panels(tabs, value = main_tab).classes("w-full"):

        # definitions for the main tab
        # we should show stats and refresh it automatically!
        with ui.tab_panel(main_tab):
            with ui.grid(columns = 2).classes("gap-4") as main_page_grid:
                load_stats(main_page_grid)
    
            ui.timer(interval = 60.0, callback = lambda: load_stats(main_page_grid))
            ui.button("Refresh Stats", color = "primary", on_click = lambda: load_stats(main_page_grid))

        # srs review tab to show review cards one by one
        with ui.tab_panel(review_tab):
            review_card = ui.card().classes("card-container")

            with review_card:

                # set up how the review card looks
                review_header = ui.label("Deck").classes("text-white")
                start_button = ui.button("Start Review", color = "primary", on_click = lambda: start_review())
                review_progress = ui.label("").classes("text-white")
                reading_display = ui.label("").classes("japanese-main-text text-center q-py-xl text-white")
                
                review_separator = ui.separator()
                
                user_romaji = ui.label("").classes("text-white")
                user_hiragana = ui.label("").classes("japanese-main-text text-white")
                user_alphabet = ui.label("").classes("main-text text-white")
    
                res_display = ui.label("").classes("japanese-main-text text-white")
                
                correct_reading_display = ui.label("").classes("japanese-main-text text-white")
                correct_meaning_display = ui.label("").classes("main-text text-white")

                review_progress.visible = False
                reading_display.visible = False
                review_separator.visible = False
                correct_reading_display.visible = False
                correct_meaning_display.visible = False
    
                item_dict = dict()

                """
                functions for the review card
                """

                # start review
                def start_review():
                    reviews = app.start_review_session()
                    
                    if not reviews:
                        review_header.text = "All done! 😋"
                        return
    
                    start_button.visible = False
                    reading_display.visible = True
                    review_separator.visible = True
    
                    update_review_display()

                    # keyboard to allow typing using our specified keys/keybinds
                    ui.keyboard(on_key = handle_key)

                # update the review display after each card
                def update_review_display():

                    # find the current item
                    current_item = app.get_current_item()

                    # if none, then we're done!
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

                    # otherwise, we have an item, so we should find what kind of item it is
                    review_type = current_item["review_type"]
                    card_type = current_item["card_type"]

                    # style the cards differently based on what the item is
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

                    # progress is defined as how many vocab has been completed over how many vocabs are due
                    review_progress.text = f"{app.current_completed} / {app.len_review_ids}"
                    review_progress.visible = True

                # "helper" function for keypresses
                def handle_key(e: KeyEventArguments):
                    global text_buffer, kana_output
    
                    key = e.key
                    key_str = str(key)
    
                    current_item = app.get_current_item()
                    card_type = current_item["card_type"]

                    # use "keydown"; otherwise we get 2 keys per press
                    if e.action.keydown:
                        match key:

                            # if the user clicks the enter button after the incorrect message is shown:
                            # they acknowledge they got the card incorrect
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

                            # if the user clicks the enter button while the text butter has something in it:
                            # the user is trying to submit their answer for checking
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

                            # if the user clicks the "ignore answer key" after the incorrect message is shown:
                            # they want us to acknowledge they made a mistake and would like to try again
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

                            # if the user clicks the "add as valid response" key after the incorrect message is shown:
                            # the user wants to add what they typed as an additional meaning and acknowledges they got the card correct
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

                            # if the user clicks the "quit after current set" key (with ctrl):
                            # the user wants to stop reviewing after the current set is completed
                            case app.key_quit_after_current_set if e.modifiers.ctrl:
                                ui.notify("Will quit after the remaining items are completed.")
                                app.stop_updating_review = True

                            # if the user clicks backspace:
                            # 1. if they're holding control, they want to remove the entire word
                            # 2. otherwise, they want to remove a character
                            case "Backspace":
                                if e.modifiers.ctrl:
                                    text_buffer = " ".join(text_buffer.split(" ")[:-1])
        
                                else:
                                    text_buffer = text_buffer[:-1]

                            # pyokaka's greedy algoirthm requires this roundabout
                            case "n" if text_buffer.endswith("n"):
                                match card_type:
                                    case "reading":

                                        # n' -> ん
                                        # nn -> っん
                                        text_buffer += "'"
    
                                    case "meaning":
                                        text_buffer += key_str.lower()

                            # if the user has clicked a character in our defined alphabet:
                            # add that character to the text buffer
                            case _ if key_str in alphabet:
                                text_buffer += key_str.lower()

                    # if the card type is reading, then we should show a kana output
                    # if the card type is meaning, then we should show the text buffer
                    match card_type:
                        case "reading":
                            kana_output = okaka.convert(text_buffer)
                            user_hiragana.text = kana_output
    
                        case "meaning":
                            user_hiragana.text = text_buffer
    
                    kana_output = okaka.convert(text_buffer)
                    user_romaji.text = text_buffer

                # function to process an answer and calls the app to save the information
                def process_answer(answer, item):
                    card_type = item["card_type"]
                    item_id = item["ID"]
                    answer_stripped = answer.strip()
                    lookup_readings = dict()

                    # keep track of progress for all items using a dictionary
                    if item_id not in item_dict:
                        item_dict[item_id] = []

                    # retrieve all valid readings and compare the typed answer to the valid readings
                    match card_type:

                        # reading cards should be strict, since a mistype of kana usually means a different word
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

                        # use fuzzy matching to score meanings
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

                    # if the score is over a certain threshold, then we mark it as correct
                    # otherwise, it's incorrect
                    if matching_score > app.match_score_threshold:
                        item_dict[item_id].append(1)
                        res_display.text = correct_message
                        app.current_reviews.pop(app.current_index)
    
                    else:
                        item_dict[item_id].append(0)
                        res_display.text = incorrect_message

                    # my way of marking if both the reading and meaning cards are marked as correct
                    # if so, then we should update the review item
                    # if the user gets both correct on the first try, the list would look like [1, 1]
                    # if they can't something wrong: [..., 1, ..., 1], where ... may be any length of 0s
                    if sum(item_dict[item_id]) == 2:
                        if len(item_dict[item_id]) == 2:
                            app.update_review_item(item_id, True)
    
                        else:
                            app.update_review_item(item_id, False)
    
                        del item_dict[item_id]
                        app.update_review_session()

        # add items tab
        with ui.tab_panel(add_tab):
            with ui.card().classes("card-container"):
                ui.label("Add New Items").classes("text-h4")

                # selection filter options
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
                    
                    search_button = ui.button("Search", color = "primary", on_click = lambda: update_search_results())

                # define containers to display items
                table_container = ui.element("div").classes("japanese-text w-full")
                items_separator = ui.separator()
                input_container = ui.column()
                
                add_button = ui.button("Add Selected Items", color = "green", on_click = lambda: add_selected_items())
                add_spinner = ui.spinner(size = "lg")

                add_button.visible = False
                add_spinner.visible = False

                # dictionary to store selected item information
                # this is important for sending information back to the app
                selected_items = dict()

                # updates the selection page every call
                # also resets the containers
                def update_search_results():
                    table_container.clear()
                    input_container.clear()
                    selected_items.clear()
                    add_button.visible = False

                    # sql query conditions to filter results
                    jlpt_condition = ",".join([str(val) for val in jlpt_levels.value])

                    # empty list to store dfs from kanji and vocab
                    list_dfs = []

                    # handle kanji
                    if "kanji" in item_type.value:
                        condition = f"k.JlptLevel IN ({jlpt_condition})"

                        df_kanji = app.discover_new_kanji(condition = condition)

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
                    if "vocab" in item_type.value:
                        condition = f"v.JlptLevel IN ({jlpt_condition})"
                        # if search_input.value:
                            # level_condition += f" AND (v.KanjiWriting LIKE '%{search_input.value}%' OR v.KanaWriting LIKE '%{search_input.value}%')"
                        df_vocab = app.discover_new_vocab(condition = condition)
                        
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
                        
                        with table_container:
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
                                    on_select = lambda e: render_inputs(e.selection),
                                    pagination = 100, # # of items to show on a page
                                ).classes("w-full vocab-table")


                # function to show selected rows as individual rows below table
                def render_inputs(selected):
                    input_container.clear()
                    selected_items.clear()

                    match len(selected):
                        case 0:
                            add_button.visible = False
                            items_separator.visible = False

                        # if an item is selected
                        case _:
                            add_button.visible = True
                            items_separator.visible = True

                            # display a row for each item
                            for i, item in enumerate(selected):
                                with input_container:
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
                                        readings_note_input = ui.input("Reading Note", placeholder = "remembering tips!")
                                        meanings_note_input = ui.input("Meaning Note", placeholder = "remembering tips!")

                                    # a separator makes everything more readable
                                    ui.separator().style("height: 0.1rem; width: 2rem;")

                                selected_items[i] = {
                                    "kanji": kanji_input,
                                    "readings": readings_input,
                                    "meanings": meanings_input,
                                    "reading_note": readings_note_input,
                                    "meaning_note": meanings_note_input,
                                    "type": item["type"],
                                }

                # function to send item information to the app
                def add_selected_items():
                    add_spinner.visible = True

                    for key in selected_items:
                        app.add_review_item(selected_items[key])

                    add_spinner.visible = False
                    update_search_results()
                    ui.notify("Successfully Added Items!")

# start serving the site
ui.run(port = ui_port, title = ui_web_title)
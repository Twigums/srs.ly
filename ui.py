from nicegui import ui
from nicegui.events import KeyEventArguments
from pyokaka import okaka
from houhou import SrsApp

app = SrsApp()

text_buffer = ""
kana_output = ""

@ui.page("/")
def index():
    ui.add_head_html("<link href='https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@400;700&display=swap' rel='stylesheet'>")
    ui.add_head_html("""
    <style>
        .japanese-text {
            font-family: 'Noto Sans JP', sans-serif;
            font-size: 2rem;
        }
        .main-text {
            font-family: 'Noto Sans', sans-serif;
            font-size: 2rem;
        }
        .card-container {
            max-width: 100rem;
            margin: 0 auto;
        }
        .stats-card {
            margin-bottom: 1rem;
        }

    </style>
    """)
    
    with ui.header().classes("bg-blue-500 text-white"):
        ui.label("SRS Tool").classes("text-h4 q-px-md")
    
    with ui.tabs().classes("w-full") as tabs:
        review_tab = ui.tab("Review")
        add_tab = ui.tab("Add Item")
        stats_tab = ui.tab("Statistics")

    # In the review tab section:
    with ui.tab_panel(review_tab):
        with ui.card().classes("card-container") as card:
            # Initialize display elements
            review_header = ui.label("Deck 1").classes("text-white")
            start_button = ui.button("Start Review", color = "primary", on_click=lambda: start_review())
            review_progress = ui.label('')
            review_progress.visible = False
            reading_display = ui.label("").classes("japanese-text text-center q-py-xl text-white")
            reading_display.visible = False
            
            separator = ui.separator()
            separator.visible = False
            
            user_romaji = ui.label("").classes("text-white")
            user_hiragana = ui.label("").classes("japanese-text text-white")
            user_alphabet = ui.label("").classes("main-text text-white")

            res_display = ui.label("").classes("main-text")
            
            correct_reading_display = ui.label("").classes("japanese-text text-white")
            correct_reading_display.visible = False

            correct_meaning_display = ui.label("").classes("main-text text-white")
            correct_meaning_display.visible = False

            def start_review():
                reviews = app.start_review_session()
                
                if not reviews:
                    review_header.text = "No items due for review!"
                    return

                start_button.visible = False
                reading_display.visible = True
                separator.visible = True

                update_review_display()
                ui.keyboard(on_key = handle_key)

            def update_review_display():
                current_item = app.get_current_item()

                if not current_item:
                    # Review session complete
                    reading_display.text = ""
                    start_button.visible = True
                    return
                
                review_type = current_item["review_type"]
                card_type = current_item["card_type"]
                
                if review_type == "kanji":
                    reading_display.text = current_item["AssociatedKanji"]
                    card.style("background-color: #2e67ff")

                elif review_type == "vocab":
                    reading_display.text = current_item["AssociatedVocab"]
                    card.style("background-color: #aa2eff")

                if card_type == "reading":
                    separator.style('border-top: 0.5rem solid #393939; margin: 0.75rem 0;')

                elif card_type == "meaning":
                    separator.style('border-top: 0.5rem solid #e4e4e4; margin: 0.75rem 0;')

                review_progress.text = f'Item {app.current_index + 1} of {len(app.current_reviews)}'

            def handle_key(e: KeyEventArguments):
                global text_buffer, kana_output

                alphabet = " abcdefghijklmnopqrstuvwxyz"
                key = e.key
                key_str = str(key)

                current_item = app.get_current_item()
                card_type = current_item["card_type"]

                if e.action.keydown:
                    if key == "Enter" and len(text_buffer) > 0:
                        process_answer(user_hiragana.text, current_item)

                        text_buffer = ""
                        kana_output = ""
                        user_romaji.text = ""
                        user_hiragana.text = ""
                        return

                    elif key == "Backspace":
                        if e.modifiers.ctrl:
                            text_buffer = " ".join(text_buffer.split(" ")[:-1])

                        else:
                            text_buffer = text_buffer[:-1]

                    elif key_str in alphabet:
                        text_buffer += key_str.lower()
                
                if card_type == "reading":
                    kana_output = okaka.convert(text_buffer)
                    user_hiragana.text = kana_output

                elif card_type == "meaning":
                    user_hiragana.text = text_buffer

                kana_output = okaka.convert(text_buffer)
                user_romaji.text = text_buffer

            item_dict = dict()

            """
            you need to find a way to not call update item until user confirms it because u want to be able to backspace to refresh your try
            """
            def process_answer(answer, item):
                card_type = item["card_type"]
                item_id = item["ID"]

                if item_id not in item_dict:
                    item_dict[item_id] = []
                
                if card_type == "reading":
                    valid_readings = item["Readings"].split(",")
                    correct_reading_display.text = str(valid_readings)
                    correct_reading_display.visible = True
                    correct_meaning_display.visible = False

                elif card_type == "meaning":
                    valid_readings = item["Meanings"].split(",")
                    correct_meaning_display.text = str(valid_readings)
                    correct_meaning_display.visible = True
                    correct_reading_display.visible = False

                if answer in valid_readings:                    
                    item_dict[item_id].append(1)
                    res_display.text = "✅"
                    app.current_reviews.pop(app.current_index)

                else:
                    item_dict[item_id].append(0)
                    res_display.text = "❌"


                if sum(item_dict[item_id]) == 2:
                    print(app.update_item(item_id, True))
                    del item_dict[item_id]
                    app.update_review_session()

                app.current_index += 1
        
                update_review_display()


ui.run(port = 7012, title = "abc")

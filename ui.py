from nicegui import ui
from nicegui.events import KeyEventArguments
from pyokaka import okaka
from houhou import SrsApp
import re
from rapidfuzz import process


app = SrsApp()

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

    with ui.tab_panel(review_tab):
        with ui.card().classes("card-container") as card:

            global text_buffer, kana_output
            text_buffer = ""
            kana_output = ""

            correct_message = "✅"
            incorrect_message = "❌"
            
            review_header = ui.label("Deck 1").classes("text-white")
            start_button = ui.button("Start Review", color = "primary", on_click = lambda: start_review())
            review_progress = ui.label("").classes("text-white")
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

            item_dict = dict()

            def start_review():
                reviews = app.start_review_session()
                
                if not reviews:
                    review_header.text = "All done! 😋"
                    return

                start_button.visible = False
                reading_display.visible = True
                separator.visible = True

                update_review_display()
                ui.keyboard(on_key = handle_key)

            def update_review_display():
                current_item = app.get_current_item()

                if not current_item:
                    reading_display.text = ""
                    start_button.visible = True
                    return
                
                review_type = current_item["review_type"]
                card_type = current_item["card_type"]

                match review_type:
                    case "kanji":
                        reading_display.text = current_item["AssociatedKanji"]
                        card.style("background-color: #2e67ff")

                    case "vocab":
                        reading_display.text = current_item["AssociatedVocab"]
                        card.style("background-color: #aa2eff")

                match card_type:
                    case "reading":
                        separator.style('border-top: 0.5rem solid #393939; margin: 0.75rem 0;')

                    case "meaning":
                        separator.style('border-top: 0.5rem solid #e4e4e4; margin: 0.75rem 0;')

                review_progress.text = f"{app.current_completed} / {app.len_review_ids}"
                review_progress.visible = True

            def handle_key(e: KeyEventArguments):
                global text_buffer, kana_output

                alphabet = " abcdefghijklmnopqrstuvwxyz"
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

                        case "Backspace" if res_display.text == incorrect_message:
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

                        case "Backspace":
                            if e.modifiers.ctrl:
                                text_buffer = " ".join(text_buffer.split(" ")[:-1])
    
                            else:
                                text_buffer = text_buffer[:-1]

                        case "n" if text_buffer.endswith("n"):
                            match card_type:
                                case "reading":
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
                        app.update_item(item_id, True)

                    else:
                        app.update_item(item_id, False)

                    del item_dict[item_id]
                    app.update_review_session()


ui.run(port = 7012, title = "abc")

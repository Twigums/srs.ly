import re

from nicegui import ui
from nicegui.events import KeyEventArguments
from pyokaka import okaka # maybe consider romkan?
from rapidfuzz import process


# define the proper alphabet for review entry
alphabet = " abcdefghijklmnopqrstuvwxyz0123456789!?-"

# define a few global variables
correct_message = "✅"
incorrect_message = "❌"

# buffer for review text entry
text_buffer = ""
kana_output = ""

# only enable keyboard input if this is False, otherwise we have a keyboard instance active already
keyboard_active = False

def review_tab_content(srs_app):
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
            reviews = srs_app.start_review_session()

            match reviews:
                case None:
                    ui.notify("DB not connected.")
                    return None

                case []:
                    review_header.text = "No reviews! 😋"
                    return None

                case _:
                    start_button.visible = False
                    reading_display.visible = True
                    review_separator.visible = True

                    update_review_display()

                    # keyboard to allow typing using our specified keys/keybinds
                    global keyboard_active
                    if not keyboard_active:
                        ui.keyboard(on_key = handle_key)
                        keyboard_active = True

        # update the review display after each card
        def update_review_display():

            # find the current item
            current_item = srs_app.get_current_item()

            # if none, then we're done!
            if not current_item:
                reading_display.text = ""
                res_display.text = ""
                review_header.visible = False
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
            review_progress.text = f"{srs_app.current_completed} / {srs_app.len_review_ids}"
            review_progress.visible = True

        # "helper" function for keypresses
        def handle_key(e: KeyEventArguments):
            global text_buffer, kana_output

            key = e.key
            key_str = str(key)

            current_item = srs_app.get_current_item()

            if not current_item:
                ui.notify("No current item!")

                return None
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
                        srs_app.current_index += 1

                        update_review_display()

                        return None

                    # if the user clicks the enter button while the text butter has something in it:
                    # the user is trying to submit their answer for checking
                    case "Enter" if len(text_buffer) > 0:
                        process_answer(user_hiragana.text, current_item)

                        if res_display.text != incorrect_message:
                            text_buffer = ""
                            kana_output = ""
                            user_romaji.text = ""
                            user_hiragana.text = ""
                            srs_app.current_index += 1

                            update_review_display()

                        return None

                    # if the user clicks the "ignore answer key" after the incorrect message is shown:
                    # they want us to acknowledge they made a mistake and would like to try again
                    case srs_app.key_ignore_answer if res_display.text == incorrect_message:
                        process_answer(user_hiragana.text, current_item)

                        res_display.text = ""
                        text_buffer = ""
                        kana_output = ""
                        user_romaji.text = ""
                        user_hiragana.text = ""
                        correct_reading_display.visible = False
                        correct_meaning_display.visible = False
                        srs_app.current_index += 1

                        update_review_display()

                        return None

                    # if the user clicks the "add as valid response" key after the incorrect message is shown:
                    # the user wants to add what they typed as an additional meaning and acknowledges they got the card correct
                    case srs_app.key_add_as_valid_response if len(text_buffer) > 0 and res_display.text == incorrect_message:
                        item_id = current_item["ID"]

                        srs_app.add_valid_response(user_hiragana.text, current_item)
                        srs_app.current_reviews.pop(srs_app.current_index)
                        item_dict[item_id].append(1)

                        # there has to be a better way of doing this
                        # i can't call a function since i dont think it would be able to delete the dictionary key?
                        # more testing is needed
                        if sum(item_dict[item_id]) == 2:
                            if len(item_dict[item_id]) == 2:
                                srs_app.update_review_item(item_id, True)

                            else:
                                srs_app.update_review_item(item_id, False)

                            del item_dict[item_id]
                            srs_app.update_review_session()

                        res_display.text = f"Added '{user_hiragana.text}' to {card_type}."

                        text_buffer = ""
                        kana_output = ""
                        user_romaji.text = ""
                        user_hiragana.text = ""
                        correct_reading_display.visible = False
                        correct_meaning_display.visible = False
                        srs_app.current_index += 1

                        update_review_display()

                        return None

                    # if the user clicks the "quit after current set" key (with ctrl):
                    # the user wants to stop reviewing after the current set is completed
                    case srs_app.key_quit_after_current_set if e.modifiers.ctrl:
                        ui.notify("Will quit after the remaining items are completed.")
                        srs_app.stop_updating_review = True

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
                        reading_lower = reading_stripped.lower()
                        remove_all_in_parentheses = re.sub(r"\s*\([^)]*\)\s*", "", reading_lower)
                        strip_parentheses = re.sub(r"[()]", "", reading_lower)

                        lookup_readings[strip_parentheses] = reading
                        lookup_readings[remove_all_in_parentheses] = reading

                    all_valid_readings = list(lookup_readings.keys())
                    matching_reading, matching_score, _ = process.extractOne(answer_stripped, all_valid_readings)

            # if the score is over a certain threshold, then we mark it as correct
            # otherwise, it's incorrect
            if matching_score > srs_app.match_score_threshold:
                item_dict[item_id].append(1)
                res_display.text = correct_message
                srs_app.current_reviews.pop(srs_app.current_index)

            else:
                item_dict[item_id].append(0)
                res_display.text = incorrect_message

            # my way of marking if both the reading and meaning cards are marked as correct
            # if so, then we should update the review item
            # if the user gets both correct on the first try, the list would look like [1, 1]
            # if they can't something wrong: [..., 1, ..., 1], where ... may be any length of 0s
            # a faster solution is storing a tuple (a, b)
            # if a = 2, then the user has completed both reviews
            # b is a counter for how many tries the user has taken
            if sum(item_dict[item_id]) == 2:
                if len(item_dict[item_id]) == 2:
                    srs_app.update_review_item(item_id, True)

                else:
                    srs_app.update_review_item(item_id, False)

                del item_dict[item_id]
                srs_app.update_review_session()
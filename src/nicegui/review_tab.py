import re

from nicegui import ui
from nicegui.events import KeyEventArguments
from pyokaka import okaka
from rapidfuzz import process, fuzz

from src.dataclasses import AppConfig

class ReviewTab(ui.element):
    def __init__(self, config: AppConfig):
        super().__init__()

        self.srs_app = config.srs_app
        self.key_ignore_answer = config.keybinds["ignore_answer"]
        self.key_add_as_valid_response = config.keybinds["add_as_valid_response"]
        self.key_quit_after_current_set = config.keybinds["quit_after_current_set"][-1]

        # define the proper alphabet for review entry
        self.alphabet = " ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789!?-"
 
        # define a few global variables
        self.correct_message = "✅"
        self.incorrect_message = "❌"

        # buffer for review text entry
        self.text_buffer = ""
        self.kana_output = ""

        # keyboard to allow typing using our specified keys/keybinds
        self.keyboard = ui.keyboard(on_key = self.handle_key)

        # contents
        self.review_card = ui.card().classes("card-container")

        with self.review_card:

            # set up how the review card looks
            self.review_header = ui.label("Deck").classes("text-white")
            self.start_button = ui.button("Start Review", color = "primary", on_click = lambda: self.start_review())
            self.review_progress = ui.label("").classes("text-white")
            self.reading_display = ui.label("").classes("japanese-main-text text-center q-py-xl text-white")

            self.review_separator = ui.separator()

            # bind the keyboard to whenever user romaji is visible
            self.user_romaji = ui.label("").classes("text-white") #.bind_visibility_to(self.keyboard, "active")
            self.user_hiragana = ui.label("").classes("japanese-main-text text-white")

            self.res_display = ui.label("").classes("japanese-main-text text-white")

            self.correct_reading_display = ui.label("").classes("japanese-main-text text-white")
            self.correct_meaning_display = ui.label("").classes("main-text text-white")

            if config.debug_mode == False:
                self.user_romaji.visible = False
                
            self.review_progress.visible = False
            self.reading_display.visible = False
            self.review_separator.visible = False
            self.correct_reading_display.visible = False
            self.correct_meaning_display.visible = False

    """
    functions for the review card
    """

    # start review
    def start_review(self) -> bool:
        reviews = self.srs_app.start_review_session()

        # initialize empty vars
        self.item_dict = dict()

        match reviews:
            case None:
                ui.notify("DB not connected.")

                return False

            case []:
                self.review_header.text = "No reviews! 😋"

                return False

            case _:
                self.review_header.visible = True
                self.start_button.visible = False
                self.reading_display.visible = True
                self.review_separator.visible = True

                self.update_review_display()

        return True

    # update the review display after each card
    def update_review_display(self) -> None:

        # find the current item
        self.current_item = self.srs_app.get_current_item()

        # if none, then we're done!
        if not self.current_item:
            self.reading_display.text = ""
            self.res_display.text = ""
            self.review_header.visible = False
            self.start_button.visible = True
            self.review_progress.visible = False
            self.reading_display.visible = False
            self.review_separator.visible = False
            self.correct_reading_display.visible = False
            self.correct_meaning_display.visible = False
            self.review_card.style("background-color: #26c826")

            return None

        # otherwise, we have an item, so we should find what kind of item it is
        review_type = self.current_item["review_type"]
        card_type = self.current_item["card_type"]

        # style the cards differently based on what the item is
        match review_type:
            case "kanji":
                self.reading_display.text = self.current_item["AssociatedKanji"]
                self.review_card.style("background-color: #2e67ff")

            case "vocab":
                self.reading_display.text = self.current_item["AssociatedVocab"]
                self.review_card.style("background-color: #aa2eff")

        match card_type:
            case "reading":
                self.review_separator.style("border-top: 0.5rem solid #393939; margin: 0.75rem 0;")

            case "meaning":
                self.review_separator.style("border-top: 0.5rem solid #e4e4e4; margin: 0.75rem 0;")

        # progress is defined as how many vocab has been completed over how many vocabs are due
        self.review_progress.text = f"{self.srs_app.current_completed} / {self.srs_app.len_review_ids}"
        self.review_progress.visible = True

        return None

    def clean_card(self) -> None:
        self.text_buffer = ""
        self.kana_output = ""
        self.user_romaji.text = ""
        self.user_hiragana.text = ""

        self.srs_app.current_index += 1
        self.update_review_display()

        return None

    # "helper" function for keypresses
    def handle_key(self, e: KeyEventArguments) -> str | None:
        key = e.key
        key_str = str(key)

        if not self.current_item:
            ui.notify("No current item!")

            return None

        card_type = self.current_item["card_type"]
        item_id = self.current_item["ID"]

        # use "keydown"; otherwise we get 2 keys per press
        if e.action.keydown:
            match key:

                # if the user clicks the enter button after the incorrect message is shown:
                # they acknowledge they got the card incorrect
                case "Enter" if self.res_display.text == self.incorrect_message:
                    self.process_answer(self.user_hiragana.text, will_submit = True)

                    self.res_display.text = ""
                    self.correct_reading_display.visible = False
                    self.correct_meaning_display.visible = False

                    self.clean_card()

                    return "acknowledged error"

                # if the user clicks the enter button while the text butter has something in it:
                # the user is trying to submit their answer for checking
                case "Enter" if len(self.text_buffer) > 0:
                    self.process_answer(self.user_hiragana.text, will_submit = False)

                    if self.res_display.text != self.incorrect_message:
                        self.clean_card()

                    return "submit"

                # if the user clicks the "ignore answer key" after the incorrect message is shown:
                # they acknowledge they made a mistake and would like to try again
                case self.key_ignore_answer if self.res_display.text == self.incorrect_message:

                    self.res_display.text = ""
                    self.correct_reading_display.visible = False
                    self.correct_meaning_display.visible = False

                    self.clean_card()

                    return "ignore result"

                # if the user clicks the "add as valid response" key after the incorrect message is shown:
                # the user wants to add what they typed as an additional meaning and acknowledges they got the card correct
                case self.key_add_as_valid_response if len(self.text_buffer) > 0 and self.res_display.text == self.incorrect_message:
                    self.srs_app.add_valid_response(self.user_hiragana.text, self.current_item)
                    self.srs_app.current_reviews.pop(self.srs_app.current_index)
                    self.item_dict[item_id].append(1)

                    # there has to be a better way of doing this
                    # i can't call a function since i dont think it would be able to delete the dictionary key?
                    # more testing is needed
                    if sum(self.item_dict[item_id]) == 2:
                        if len(self.item_dict[item_id]) == 2:
                            self.srs_app.update_review_item(item_id, True)

                        else:
                            self.srs_app.update_review_item(item_id, False)

                        del self.item_dict[item_id]
                        self.srs_app.update_review_session()

                    self.res_display.text = f"Added '{self.user_hiragana.text}' to {card_type}."

                    self.correct_reading_display.visible = False
                    self.correct_meaning_display.visible = False

                    self.clean_card()

                    return "add answer"

                # if the user clicks the "quit after current set" key (with ctrl):
                # the user wants to stop reviewing after the current set is completed
                case self.key_quit_after_current_set if e.modifiers.ctrl:
                    ui.notify("Will quit after the remaining items are completed.")
                    self.srs_app.stop_updating_review = True

                    res = "quit"

                # if the user clicks backspace:
                # 1. if they're holding control, they want to remove the entire word
                # 2. otherwise, they want to remove a character
                case "Backspace":
                    if e.modifiers.ctrl:
                        self.text_buffer = " ".join(self.text_buffer.split(" ")[:-1])

                        res = "delete word"

                    else:
                        match card_type:
                            case "reading":
                                current_length = len(self.kana_output)

                                while len(okaka.convert(self.text_buffer)) == current_length and current_length > 0:
                                    self.text_buffer = self.text_buffer[:-1]

                            case "meaning":
                                self.text_buffer = self.text_buffer[:-1]

                        res = "delete letter"

                # pyokaka's greedy algoirthm requires this roundabout
                case _ if key in ["n", "N"] and self.text_buffer.endswith("n") and (self.res_display.text != self.incorrect_message):
                    match card_type:
                        case "reading":

                            # n' -> ん
                            # nn -> っん
                            self.text_buffer += "'"

                        case "meaning":
                            self.text_buffer += key_str.lower()

                    res = "append kana n"                    

                # if the user has clicked a character in our defined alphabet:
                # add that character to the text buffer
                case _ if (key_str in self.alphabet) and (self.res_display.text != self.incorrect_message):
                    self.text_buffer += key_str.lower()

                    res = f"insert {key_str}"

                case _:
                    return None

            # if the card type is reading, then we should show a kana output
            # if the card type is meaning, then we should show the text buffer
            match card_type:
                case "reading":
                    self.kana_output = okaka.convert(self.text_buffer)
                    self.user_hiragana.text = self.kana_output

                case "meaning":
                    self.user_hiragana.text = self.text_buffer

            self.kana_output = okaka.convert(self.text_buffer)
            self.user_romaji.text = self.text_buffer

            # in the event of bugfixing/logging, printing res might be useful
            return res

        return None

    # function to process an answer and calls the app to save the information
    def process_answer(self, answer, will_submit) -> None:
        item_id = self.current_item["ID"]
        card_type = self.current_item["card_type"]

        answer_stripped = answer.strip()
        answer_lower = answer_stripped.lower()
        lookup_readings = dict()

        # keep track of progress for all items using a dictionary
        if item_id not in self.item_dict:
            self.item_dict[item_id] = []

        # retrieve all valid readings and compare the typed answer to the valid readings
        match card_type:

            # reading cards should be strict, since a mistype of kana usually means a different word
            case "reading":
                valid_readings = self.current_item["Readings"].split(",")
                self.correct_reading_display.text = str(valid_readings)
                self.correct_reading_display.visible = True
                self.correct_meaning_display.visible = False

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
                valid_readings = self.current_item["Meanings"].split(",")
                self.correct_meaning_display.text = str(valid_readings)
                self.correct_meaning_display.visible = True
                self.correct_reading_display.visible = False

                for reading in valid_readings:
                    reading_stripped = reading.strip()
                    reading_lower = reading_stripped.lower()
                    remove_all_in_parentheses = re.sub(r"\s*\([^)]*\)\s*", "", reading_lower)
                    strip_parentheses = re.sub(r"[()]", "", reading_lower)

                    lookup_readings[strip_parentheses] = reading
                    lookup_readings[remove_all_in_parentheses] = reading

                all_valid_readings = list(lookup_readings.keys())
                matching_reading, matching_score, _ = process.extractOne(answer_lower, all_valid_readings, scorer = fuzz.QRatio)

        self.correct_reading_display.text = str(valid_readings)
        self.correct_reading_display.visible = True
        self.correct_meaning_display.visible = False

        # if the score is over a certain threshold, then we mark it as correct
        # otherwise, it's incorrect
        to_append = 0
        if matching_score > self.srs_app.match_score_threshold:
            to_append = 1
            self.res_display.text = self.correct_message
            self.srs_app.current_reviews.pop(self.srs_app.current_index)

        else:
            self.res_display.text = self.incorrect_message

        if self.res_display.text == self.correct_message or will_submit:
            self.item_dict[item_id].append(to_append)
            
            # my way of marking if both the reading and meaning cards are marked as correct
            # if so, then we should update the review item
            # if the user gets both correct on the first try, the list would look like [1, 1]
            # if they can't something wrong: [..., 1, ..., 1], where ... may be any length of 0s
            # a faster solution is storing a tuple (a, b)
            # if a = 2, then the user has completed both reviews
            # b is a counter for how many tries the user has taken
            if sum(self.item_dict[item_id]) == 2:
                if len(self.item_dict[item_id]) == 2:
                    self.srs_app.update_review_item(item_id, True)
    
                else:
                    self.srs_app.update_review_item(item_id, False)
    
                del self.item_dict[item_id]
                self.srs_app.update_review_session()

        return None

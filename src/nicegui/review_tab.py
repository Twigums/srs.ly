import base64

from nicegui import app, run, ui
from nicegui.events import GenericEventArguments, KeyEventArguments
from pyokaka import okaka
from rapidfuzz import process, fuzz

from src.dataclasses import AppConfig
from src.utils import expand_meanings, spoken_to_hiragana, spoken_to_meaning
from src.review_storage import (
    save_review_state,
    load_review_state,
    clear_review_state,
    has_review_state,
)

# whisper language for each card type
VOICE_LANGUAGES = {"reading": "ja", "meaning": "en"}

# records a spoken answer and sends it back to python as base64 audio
# firefox has no speech recognition api, so the transcription happens server-side
VOICE_SCRIPT = """
<script>
window.srslyVoice = {
    recorder: null,
    timer: null,

    async start(maxSeconds) {
        // a clicked button keeps focus, and ui.keyboard ignores keys while a button is focused
        document.activeElement?.blur();

        if (this.recorder) return;
        if (!navigator.mediaDevices) {
            emitEvent("voice_error", {message: "The microphone needs HTTPS (or localhost)."});
            return;
        }

        let stream;
        try {
            stream = await navigator.mediaDevices.getUserMedia({audio: true});
        } catch (err) {
            emitEvent("voice_error", {message: `Microphone unavailable: ${err.name}`});
            return;
        }

        const chunks = [];
        const recorder = new MediaRecorder(stream);
        recorder.ondataavailable = (event) => chunks.push(event.data);
        recorder.onstop = () => {
            stream.getTracks().forEach((track) => track.stop());
            clearTimeout(this.timer);
            this.recorder = null;

            const reader = new FileReader();
            reader.onloadend = () => emitEvent("voice_audio", {audio: reader.result.split(",")[1]});
            reader.readAsDataURL(new Blob(chunks, {type: recorder.mimeType}));
        };

        this.recorder = recorder;
        recorder.start();
        this.timer = setTimeout(() => this.stop(), maxSeconds * 1000);
    },

    stop() {
        document.activeElement?.blur();

        if (this.recorder && this.recorder.state !== "inactive") this.recorder.stop();
    },
};
</script>
"""

class ReviewTab(ui.element):
    def __init__(self, config: AppConfig):
        super().__init__()

        self.srs_app = config.srs_app
        self.key_ignore_answer = config.keybinds["ignore_answer"]
        self.key_add_as_valid_response = config.keybinds["add_as_valid_response"]
        self.key_quit_after_current_set = config.keybinds["quit_after_current_set"][-1]
        self.key_voice_input = config.keybinds["voice_input"]

        # voice input: "idle" -> "recording" -> "transcribing" -> "idle"
        # voice_card remembers which card the recording is for
        self.transcriber = config.transcriber
        self.voice_max_record_seconds = config.voice_max_record_seconds
        self.voice_state = "idle"
        self.voice_card = None

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

            # record an answer instead of typing it; only shown while reviewing
            if self.transcriber:
                with ui.row().classes("items-center") as self.voice_row:
                    self.voice_button = ui.button(icon = "mic", on_click = self.toggle_voice).props("round flat color=white")
                    self.voice_status = ui.label("").classes("text-white")

                self.voice_row.bind_visibility_from(self.review_separator, "visible")

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

        if self.transcriber:
            ui.add_body_html(VOICE_SCRIPT)
            ui.on("voice_audio", self.handle_voice_audio)
            ui.on("voice_error", self.handle_voice_error)

        # Restore any in-progress session from per-user storage so that a
        # browser/connection refresh does not lose the user's place.
        if has_review_state(app.storage.user):
            self.item_dict = {}
            load_review_state(app.storage.user, self.srs_app, self.item_dict)
            self.review_header.visible = True
            self.start_button.visible = False
            self.reading_display.visible = True
            self.review_separator.visible = True
            self.update_review_display()

    """
    functions for the review card
    """

    # start review
    def start_review(self) -> bool:
        reviews = self.srs_app.start_review_session()

        # initialize empty vars
        self.item_dict = dict()

        # discard any previously saved session — this is a fresh start
        clear_review_state(app.storage.user)

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

            # session complete — remove saved state so the next load starts fresh
            clear_review_state(app.storage.user)

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

        # persist the current position so a refresh can resume here
        save_review_state(app.storage.user, self.srs_app, item_dict=self.item_dict)

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
                    self.srs_app.current_reviews.pop()
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

                    # current_index past the wrong card. clean_card() would increment it
                    # again, skipping the next card in the queue (issue #37)
                    self.text_buffer = ""
                    self.kana_output = ""
                    self.user_romaji.text = ""
                    self.user_hiragana.text = ""
                    self.update_review_display()

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

                # if the user clicks the voice input key:
                # start recording their answer, or stop and transcribe it if already recording
                case self.key_voice_input if self.transcriber:
                    res = self.toggle_voice()

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
                self.correct_reading_display.text = self.current_item["Readings"]
                self.correct_reading_display.visible = True
                self.correct_meaning_display.visible = False

                for reading in valid_readings:
                    reading_stripped = reading.strip()
                    lookup_readings[reading_stripped] = reading

                if answer_stripped in lookup_readings:
                    matching_score = 100
                    matching_reading = answer_stripped

                else:
                    matching_score = 0

            # use fuzzy matching to score meanings
            case "meaning":
                valid_readings = expand_meanings(self.current_item["Meanings"])
                self.correct_meaning_display.text = self.current_item["Meanings"]
                self.correct_meaning_display.visible = True
                self.correct_reading_display.visible = False

                for reading in valid_readings:
                    lookup_readings[reading.strip().lower()] = reading

                matching_reading, matching_score, _ = process.extractOne(answer_lower, lookup_readings.keys(), scorer = fuzz.QRatio)

        # if the score is over a certain threshold, then we mark it as correct
        # otherwise, it's incorrect
        current_review = self.srs_app.current_reviews.pop(self.srs_app.current_index)
        to_append = 0
        if matching_score > self.srs_app.match_score_threshold:
            to_append = 1
            self.res_display.text = self.correct_message

        else:
            self.srs_app.current_reviews.append(current_review)
            self.res_display.text = self.incorrect_message

        # only submit if we're ready to submit or if the user got it correct
        if to_append == 1 or will_submit:
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

        # persist item_dict changes so a refresh sees the latest answer progress
        save_review_state(app.storage.user, self.srs_app, item_dict=self.item_dict)

        return None

    """
    functions for voice input
    """

    # start recording an answer, or stop and send it off for transcription if already recording
    def toggle_voice(self) -> str | None:
        if not self.current_item or self.res_display.text == self.incorrect_message:
            return None

        match self.voice_state:
            case "idle":
                self.voice_state = "recording"
                self.voice_card = (self.current_item["ID"], self.current_item["card_type"])
                self.voice_status.text = f"Recording... press {self.key_voice_input} to stop."
                ui.run_javascript(f"srslyVoice.start({self.voice_max_record_seconds})")

                return "start recording"

            case "recording":
                ui.run_javascript("srslyVoice.stop()")

                return "stop recording"

        return None

    # a recording only applies to the card it was made for,
    # and only while the user can still type (not while acknowledging a wrong answer)
    def voice_card_is_current(self, voice_card: tuple | None) -> bool:
        if not self.current_item or self.res_display.text == self.incorrect_message:
            return False

        return voice_card == (self.current_item["ID"], self.current_item["card_type"])

    # transcribe a recorded answer and put it in the answer field
    # nothing is submitted here: the user checks the text, fixes it by typing, then presses enter as usual
    async def handle_voice_audio(self, e: GenericEventArguments) -> str | None:
        voice_card = self.voice_card
        self.voice_card = None

        if not self.voice_card_is_current(voice_card):
            self.voice_state = "idle"
            self.voice_status.text = ""

            return "stale recording"

        card_type = voice_card[1]
        audio = base64.b64decode(e.args["audio"])

        self.voice_state = "transcribing"
        self.voice_status.text = "Transcribing..."

        # run whisper off the event loop so the ui (and the discord bot) keep responding
        try:
            text = await run.io_bound(self.transcriber.transcribe, audio, VOICE_LANGUAGES[card_type])

        except Exception as err:
            ui.notify(f"Transcription failed: {err}")

            return "transcription failed"

        finally:
            self.voice_state = "idle"
            self.voice_status.text = ""

        # the user may have moved on while whisper was running
        if not self.voice_card_is_current(voice_card):
            return "stale recording"

        match card_type:
            case "reading":
                answer = spoken_to_hiragana(text)

            case "meaning":
                answer = spoken_to_meaning(text)

        if not answer:
            ui.notify("Didn't catch that, try again.")

            return "no speech"

        # replace what was typed; the buffers are set the same way typing fills them,
        # so backspace and further typing edit the transcription like any other answer
        self.text_buffer = answer
        self.kana_output = okaka.convert(answer)
        self.user_romaji.text = answer
        self.user_hiragana.text = answer

        return "transcribed"

    def handle_voice_error(self, e: GenericEventArguments) -> None:
        self.voice_state = "idle"
        self.voice_card = None
        self.voice_status.text = ""
        ui.notify(e.args["message"])

        return None

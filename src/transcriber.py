import io
import threading


class Transcriber:
    def __init__(self, model_size: str):
        self.model_size = model_size
        self.model = None

        # the startup task and the first review answer can both try to load the model
        self.lock = threading.Lock()

    # load the whisper model once (the first run also downloads it)
    # faster_whisper is imported here so it is only loaded when voice input is enabled
    def load(self) -> None:
        with self.lock:
            if self.model is None:
                from faster_whisper import WhisperModel

                self.model = WhisperModel(self.model_size, device = "cpu", compute_type = "int8")

        return None

    # transcribe one recorded answer
    # the language is forced since detecting it on a clip this short is unreliable,
    # and the vad filter drops silence that whisper would otherwise make up text for
    def transcribe(self, audio: bytes, language: str) -> str:
        self.load()

        segments, _ = self.model.transcribe(
            io.BytesIO(audio),
            language = language,
            vad_filter = True,
            condition_on_previous_text = False,
            without_timestamps = True,
        )

        return "".join(segment.text for segment in segments).strip()

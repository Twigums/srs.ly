import pandas as pd
import sqlite3
import random
import tomllib

from datetime import datetime, timedelta, timezone
from functools import wraps


# decorator to handle if db connection is not established
# returns None if no connection
def check_conn(f):

    @wraps(f)
    def wrapper(*args, **kwargs):
        self = args[0]

        if self.conn is None:
            print(f"{f.__name__} failed. DB conn is {self.conn}.")

            return None

        return f(*args, **kwargs)

    return wrapper

class SrsApp:
    def __init__(self):

        # config file is located here
        # saved as a toml file
        with open("config.toml", "rb") as f:
            config = tomllib.load(f)

        # set initial definitions from toml file
        self.max_reviews_at_once = config["max_reviews_at_once"]
        self.entries_before_commit = config["entries_before_commit"]
        self.match_score_threshold = config["match_score_threshold"]
        self.srs_interval = config["srs_interval"]
        self.path_to_srs_db = config["path_to_srs_db"]
        self.path_to_full_db = config["path_to_full_db"]

        # keybindings
        self.keybinds = config["keybinds"]
        self.key_ignore_answer = self.keybinds["ignore_answer"]
        self.key_add_as_valid_response = self.keybinds["add_as_valid_response"]
        self.key_quit_after_current_set = self.keybinds["quit_after_current_set"].split(",")[-1]

        # variables shared between app and ui
        self.id_srs_db = "srs_db"
        self.name_srs_table = self.id_srs_db + ".SrsEntrySet"
        self.conn = None
        self.cursor = None
        self.entries_without_commit = 0
        self.current_reviews = []
        self.current_index = 0
        self.current_completed = 0
        self.stop_updating_review = False
        self.due_review_ids = []
        self.len_review_ids = 0

    # initialize sql connection to db
    def init_db(self):
        try:
            self.conn = sqlite3.connect(self.path_to_full_db)

        except Exception:
            raise Exception

        self.cursor = self.conn.cursor()
        self.cursor.execute(f"ATTACH DATABASE '{self.path_to_srs_db}' AS {self.id_srs_db};")

        return None

    # buffer for committing
    # prevents many commits at the same time
    @check_conn
    def to_commit(self):
        self.entries_without_commit += 1

        if self.entries_without_commit >= self.entries_before_commit:
            self.conn.commit()
            self.entries_without_commit = 0

        return None

    # reset # of entries without commit, and then commit
    @check_conn
    def force_commit(self):
        self.entries_without_commit = 0
        self.conn.commit()

        return None

    # close db by commiting all changes then closing the connection
    @check_conn
    def close_db(self):
        self.force_commit()
        self.conn.close()

        self.conn = None
        self.cursor = None

        return None

    # retrieve counts and ratio from db
    @check_conn
    def get_review_stats(self):
        current_grade_col = "CurrentGrade"
        failure_col = "FailureCount"
        success_col = "SuccessCount"
        q_current_grade_count = f"""
                                SELECT 
                                    COUNT(*)
                                FROM {self.name_srs_table}
                                GROUP BY {current_grade_col};
                                """
        q_sucess_ratio = f"""
                         SELECT 
                             CASE
                             WHEN (SUM({failure_col}) + SUM({success_col})) = 0 THEN 0
                             ELSE SUM({success_col}) * 1.0 / (SUM({failure_col}) + SUM({success_col}))
                             END AS ratio
                         FROM srs_db.SrsEntrySet
                         """

        df_counts = pd.read_sql_query(q_current_grade_count, self.conn)
        df_ratio = pd.read_sql_query(q_sucess_ratio, self.conn)

        return df_counts, df_ratio

    # returns info on current item
    @check_conn
    def get_current_item(self):
        if len(self.current_reviews) == 0:
            return None

        if self.current_index >= len(self.current_reviews):
            self.current_index = 0

        return self.current_reviews[self.current_index]

    # returns df on review items that have their next review date timestamp less than the current time
    # that means that item is ready for review
    @check_conn
    def get_due_reviews(self) -> pd.core.frame.DataFrame:
        date_col = "NextAnswerDateISO"
        q = f"""
            SELECT * FROM {self.name_srs_table}
            WHERE {date_col} < current_timestamp;
            """

        df = pd.read_sql_query(q, self.conn)
        return df

    # returns df of all vocabs present in the user's srs review
    @check_conn
    def get_study_vocab(self) -> set:
        vocab_col = "AssociatedVocab"
        q = f"""
            SELECT {vocab_col} FROM {self.name_srs_table};
            """

        df = pd.read_sql_query(q, self.conn)

        all_vocabs = set(df[vocab_col].dropna())
        return all_vocabs

    # returns df of all kanji present in the user's srs review
    # this is a set of both their vocab and kanji
    # i should also blacklist all the hiragana and katakana, but it is what it is
    @check_conn
    def get_study_kanji(self) -> set:
        vocab_col, kanji_col = ("AssociatedVocab", "AssociatedKanji")
        q = f"""
            SELECT {vocab_col}, {kanji_col} FROM {self.name_srs_table}
            WHERE LENGTH({vocab_col}) = 1
            OR LENGTH({kanji_col}) = 1;
            """

        df = pd.read_sql_query(q, self.conn)

        vocab_kanjis = set(df[vocab_col].dropna())
        kanji_kanjis = set(df[kanji_col].dropna())

        all_kanjis = vocab_kanjis.union(kanji_kanjis)
        return all_kanjis

    # returns df of vocab that isn't present in our reviews given conditions
    # sort after using pd.sort_values to put nans at the end
    @check_conn
    def discover_new_vocab(self, condition: str = "v.JlptLevel IN (1, 2, 3, 4, 5)") -> pd.core.frame.DataFrame:
        vocab_col = "AssociatedVocab"
        q = f"""
            WITH v_except AS (
                SELECT * FROM VocabSet AS v
                WHERE {condition}
                AND NOT EXISTS (
                    SELECT 1 FROM {self.name_srs_table} AS srs
                    WHERE srs.{vocab_col} = v.KanjiWriting
                    )
                )
            SELECT * FROM v_except
            JOIN VocabEntityVocabMeaning AS v_link ON v_link.VocabEntity_ID = v_except.ID
            JOIN VocabMeaningSet AS v_meaning ON v_link.Meanings_ID = v_meaning.ID
            JOIN VocabMeaningVocabCategory as v_cat_link ON v_cat_link.VocabMeaningVocabCategory_VocabCategory_ID = v_meaning.ID
            JOIN VocabCategorySet as v_cat ON v_cat.ID = v_cat_link.Categories_ID;
            """

        df = pd.read_sql_query(q, self.conn)
        return df

    # returns df of kanji that isn't present in our reviews given conditions
    # sort after using pd.sort_values to put nans at the end
    @check_conn
    def discover_new_kanji(self, condition: str = "k.JpltLevel IN (1, 2, 3, 4, 5)") -> pd.core.frame.DataFrame:
        kanji_col = "AssociatedKanji"
        q = f"""
            WITH k_except AS (
                SELECT * FROM KanjiSet AS k
                WHERE {condition}
                AND NOT EXISTS (
                    SELECT 1 FROM {self.name_srs_table} AS srs
                    WHERE srs.{kanji_col} = k.Character
                    )
                )
            SELECT * FROM k_except as k
            JOIN KanjiMeaningSet AS k_meanings ON k_meanings.Kanji_ID = k.ID;
            """

        df = pd.read_sql_query(q, self.conn)
        return df

    # initialize the review session
    @check_conn
    def start_review_session(self):
        self.current_index = 0
        self.stop_updating_review = False

        # get due reviews
        df = self.get_due_reviews()

        if df.empty:
            return []

        # sort them by when they were due, so the user can complete the earliest ones first
        sorted_df = df.sort_values("NextAnswerDateISO", ascending = False)
        self.due_review_ids = sorted_df["ID"].tolist()
        self.len_review_ids = len(self.due_review_ids)

        current_ids = set()

        # makes sure that we add as many items to the review list without exceeding the max reviews defined
        while len(current_ids) < len(sorted_df) and len(current_ids) < self.max_reviews_at_once:
            current_id = self.due_review_ids.pop()
            current_ids.add(current_id)

        current_df = sorted_df[sorted_df["ID"].isin(current_ids)]
        items = current_df.to_dict("records")
        self.add_to_review(items)

        return self.current_reviews

    # if the user has not designated to stop reviewing, get another item and add it to the review list
    @check_conn
    def update_review_session(self):
        if not self.stop_updating_review:

            # adds one id
            id_col = "ID"
            current_id = self.due_review_ids.pop()
            q = f"""
                SELECT * FROM {self.name_srs_table}
                WHERE {id_col} = {current_id};
                """
    
            df = pd.read_sql_query(q, self.conn)
            item = df.to_dict("records")
            self.add_to_review(item)

        return None

    # defines an item and adds it to the review list
    @check_conn
    def add_to_review(self, items):
        for item in items:
            review_type = None
            current_item = None

            kanji_item = item.get("AssociatedKanji")
            vocab_item = item.get("AssociatedVocab")

            if kanji_item:
                review_type = "kanji"
                current_item = kanji_item

            elif vocab_item:
                review_type = "vocab"
                current_item = vocab_item

            # we need to make two cards: reading and meaning
            # they are defined as such
            reading_card = item.copy()
            reading_card["review_type"] = review_type
            reading_card["card_type"] = "reading"
            reading_card["prompt"] = current_item
            reading_card["expected_answer"] = reading_card["Readings"]
            self.current_reviews.append(reading_card)

            meaning_card = item.copy()
            meaning_card["review_type"] = review_type
            meaning_card["card_type"] = "meaning"
            meaning_card["prompt"] = current_item
            meaning_card["expected_answer"] = meaning_card["Meanings"]
            self.current_reviews.append(meaning_card)

        random.shuffle(self.current_reviews)

        return None

    # adds another valid meaning to the item in the db
    @check_conn
    def add_valid_response(self, user_input, item):
        id_col = "ID"
        card_type = item["card_type"]
        item_id = item["ID"]

        match card_type:
            case "reading":
                response_col = "Readings"

            case "meaning":
                response_col = "Meanings"

        q = f"""
            UPDATE {self.name_srs_table}
            SET
                {response_col} = ?
            WHERE {id_col} = {item_id};
            """

        valid_responses = item[response_col]
        valid_responses += f",{user_input}"

        self.conn.execute(q, (valid_responses,))
        self.to_commit()

        return None

    # adds an item from the vocab/kanji db to the srs review db
    @check_conn
    def add_review_item(self, item):
        q = f"""
            INSERT INTO {self.name_srs_table} (Meanings, Readings, CurrentGrade, FailureCount, SuccessCount, AssociatedVocab, AssociatedKanji, MeaningNote, ReadingNote, Tags, IsDeleted, ServerId, LastUpdateDateISO, CreationDateISO, NextAnswerDateISO)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """

        # utc current timestamp
        current_datetime = datetime.now(timezone.utc)
        next_answer_datetime = current_datetime + timedelta(hours = self.srs_interval["0"]["value"])

        # default definitions
        # timestamp as such for both readability and debugging
        meanings = item["meanings"].value
        readings = item["readings"].value
        current_grade = 0
        failure_count = 0
        success_count = 0
        associated_vocab = None
        associated_kanji = None
        meaning_note = item["meaning_note"].value
        reading_note = item["reading_note"].value
        tags = None
        is_deleted = 0
        server_id = None
        last_update_date = current_datetime.strftime("%Y-%m-%d %H:%M:%S")
        creation_date = current_datetime.strftime("%Y-%m-%d %H:%M:%S")
        next_answer_date = next_answer_datetime.strftime("%Y-%m-%d %H:%M:%S")

        match item["type"]:
            case "vocab":
                associated_vocab = item["kanji"].value

            case "kanji":
                associated_kanji = item["kanji"].value

        # big tuple...
        self.conn.execute(q, (meanings, readings, current_grade, failure_count, success_count, associated_vocab, associated_kanji, meaning_note, reading_note, tags, is_deleted, server_id, last_update_date, creation_date, next_answer_date))
        self.conn.commit()

        return None

    # after an answer has been processed, edit the item's status in the db
    @check_conn
    def update_review_item(self, item_id, res):
        id_col = "ID"
        q_retrieve_item = f"""
                          SELECT 
                              CurrentGrade,
                              FailureCount,
                              SuccessCount
                          FROM {self.name_srs_table}
                          WHERE {id_col} = {item_id};
                          """
        q_update_item = f"""
                        UPDATE {self.name_srs_table}
                        SET
                            CurrentGrade = ?,
                            FailureCount = ?,
                            SuccessCount = ?,
                            LastUpdateDateISO = current_timestamp,
                            NextAnswerDateISO = ?
                        WHERE {id_col} = {item_id};
                        """

        df = pd.read_sql_query(q_retrieve_item, self.conn)
        row = df.to_dict("records")[0]

        # utc current timestamp
        current_time = datetime.now(timezone.utc)

        # if the user got the item correct, increase the grade and success count
        # otherwise, opposite
        if res:
            row["CurrentGrade"] += 1
            row["SuccessCount"] += 1

        else:
            row["CurrentGrade"] = max(0, row["CurrentGrade"] - 1)
            row["FailureCount"] += 1

        current_grade_key = str(row["CurrentGrade"])
        current_grade_dict = self.srs_interval[current_grade_key]

        # if -1, then the user has proved that they know this item well enough to stop reviewing
        # otherwise, use the toml to determine when the next review date is
        match current_grade_dict:
            case -1:
                review_time = None

            case _:
                match current_grade_dict["unit"]:
                    case "hours":
                        review_datetime = current_time + timedelta(hours = current_grade_dict["value"])

                    case "days":
                        review_datetime = current_time + timedelta(days = current_grade_dict["value"])

                review_time = review_datetime.strftime("%Y-%m-%d %H:%M:%S")

        self.conn.execute(q_update_item, (row["CurrentGrade"], row["FailureCount"], row["SuccessCount"], review_time))
        self.current_completed += 1 # increment counter for frontend
        self.to_commit()

        return None

    # function to convert db from houhou
    # specifically, this just adds similar columns representing time but in iso format for readability
    @check_conn
    def convert_from_houhou(self) -> None:
        names_date_col = ["LastUpdateDate", "CreationDate", "NextAnswerDate", "SuspensionDate"]

        for name_col in names_date_col:
            name_iso_col = name_col + "ISO"
            q_create_col = f"ALTER TABLE {self.name_srs_table} ADD COLUMN {name_iso_col} TEXT DEFAULT current_timestamp);"
            q_update_col = f"""
                           UPDATE {self.name_srs_table}
                           SET {name_iso_col} = 
                               CASE 
                                   WHEN typeof({name_col}) = 'text' 
                                   AND {name_col} GLOB '20[0-9][0-9]-*' THEN 
                                       {name_col}

                                   WHEN typeof({name_col}) = 'integer' THEN
                                       datetime(({name_col} / 10000000) - 62135596800, 'unixepoch')

                                   ELSE NULL
                               END;
                           """

            try:
                self.conn.execute(q_create_col)
                self.conn.execute(q_update_col)

                self.conn.commit()

            # don't raise the error
            # most likely it's just saying the column exists if you run this function multiple times
            except Exception as e:
                print(f"{name_col}: {e}")
                continue

        return None

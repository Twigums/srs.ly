import pandas as pd
import os
import sqlite3
from datetime import datetime, timedelta, timezone
import random
import tomllib


class SrsApp:
    def __init__(self):
        with open("config.toml", "rb") as f:
            config = tomllib.load(f)

        self.max_reviews_at_once = config["max_reviews_at_once"]
        self.entries_before_commit = config["entries_before_commit"]
        self.match_score_threshold = config["match_score_threshold"]
        self.srs_interval = config["srs_interval"]
        path_to_srs_db = config["path_to_srs_db"]
        path_to_full_db = config["path_to_full_db"]

        # keybindings
        self.keybinds = config["keybinds"]
        self.key_ignore_answer = self.keybinds["ignore_answer"]
        self.key_add_as_valid_response = self.keybinds["add_as_valid_response"]
        self.key_quit_after_current_set = self.keybinds["quit_after_current_set"].split(",")[-1]

        self.id_srs_db = "srs_db"
        self.name_srs_table = self.id_srs_db + ".SrsEntrySet"
        self.entries_without_commit = 0
        self.current_reviews = []
        self.current_index = 0
        self.current_completed = 0
        self.due_review_ids = []
        self.len_review_ids = 0

        try:
            self.conn = sqlite3.connect(path_to_full_db)

        except Exception:
            raise Exception

        self.cursor = self.conn.cursor()
        self.cursor.execute(f"ATTACH DATABASE '{path_to_srs_db}' AS {self.id_srs_db};")

    def to_commit(self):
        self.entries_without_commit += 1
        
        if self.entries_without_commit >= self.entries_before_commit:
            self.conn.commit()
            self.entries_without_commit = 0

        return None

    def force_commit(self):
        self.entries_without_commit = 0
        self.conn.commit()

        return None
        
    def close_db(self):
        self.force_commit()
        self.conn.close()

        return None

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

        df_counts = pd.read_sql_query(q_current_grade_count, app.conn)
        df_ratio = pd.read_sql_query(q_sucess_ratio, app.conn)

        return df_counts, df_ratio

    def get_current_item(self):
        if len(self.current_reviews) == 0:
            return None

        if self.current_index >= len(self.current_reviews):
            self.current_index = 0

        return self.current_reviews[self.current_index]

    def get_due_reviews(self) -> pd.core.frame.DataFrame:
        date_col = "NextAnswerDateISO"
        q = f"""
            SELECT * FROM {self.name_srs_table}
            WHERE {date_col} < datetime('now');
            """
        
        df = pd.read_sql_query(q, self.conn)
        return df
        
    def get_study_vocab(self) -> set:
        vocab_col = "AssociatedVocab"
        q = f"""
            SELECT {vocab_col} FROM {self.name_srs_table};
            """
    
        df = pd.read_sql_query(q, self.conn)

        all_vocabs = set(df[vocab_col].dropna())
        return all_vocabs
    
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

    # sort after using pd.sort_values to put nans at the end
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
            JOIN VocabMeaningSet AS v_meaning ON v_link.Meanings_ID = v_meaning.ID;
            """

        df = pd.read_sql_query(q, self.conn)
        return df

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

    def start_review_session(self):
        self.current_index = 0
        self.end_review_early = False

        df = self.get_due_reviews()
        
        if df.empty:
            return []

        sorted_df = df.sort_values("NextAnswerDateISO", ascending = False)
        self.due_review_ids = sorted_df["ID"].tolist()
        self.len_review_ids = len(self.due_review_ids)

        current_ids = set()

        while len(current_ids) < len(sorted_df) and len(current_ids) < self.max_reviews_at_once:
            current_id = self.due_review_ids.pop()
            current_ids.add(current_id)
        
        current_df = sorted_df[sorted_df["ID"].isin(current_ids)]
        items = current_df.to_dict("records")
        self.add_to_review(items)
        
        return self.current_reviews

    def update_review_session(self):
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
                            LastUpdateDateISO = datetime('now'),
                            NextAnswerDateISO = ?
                        WHERE {id_col} = {item_id};
                        """

        df = pd.read_sql_query(q_retrieve_item, self.conn)
        row = df.to_dict("records")[0]

        current_time = datetime.now(timezone.utc)
        
        if res:
            row["CurrentGrade"] += 1
            row["SuccessCount"] += 1

        else:
            row["CurrentGrade"] = max(0, row["CurrentGrade"] - 1)
            row["FailureCount"] += 1

        current_grade_key = str(row["CurrentGrade"])
        current_grade_dict = self.srs_interval[current_grade_key]

        match current_grade_dict:
            case -1:
                review_time = None

            case _:
                match current_grade_dict["unit"]:
                    case "hours":
                        review_datetime = datetime.now(timezone.utc) + timedelta(hours = current_grade_dict["value"])

                    case "days":
                        review_datetime = datetime.now(timezone.utc) + timedelta(days = current_grade_dict["value"])

                review_time = review_datetime.strftime("%Y-%m-%d %H:%M:%S")

        self.conn.execute(q_update_item, (row["CurrentGrade"], row["FailureCount"], row["SuccessCount"], review_time))
        self.current_completed += 1
        self.to_commit()

        return None

    def convert_from_houhou(self) -> None:
        names_date_col = ["LastUpdateDate", "CreationDate", "NextAnswerDate", "SuspensionDate"]

        for name_col in names_date_col:
            name_iso_col = name_col + "ISO"
            q_create_col = f"ALTER TABLE {self.name_srs_table} ADD COLUMN {name_iso_col} TEXT;"
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

            except Exception as e:
                print(f"{name_col}: {e}")
                continue

        return None
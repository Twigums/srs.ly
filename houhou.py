import pandas as pd
import os
import sqlite3
from datetime import datetime, timedelta, timezone
import random


class SrsApp:
    def __init__(self, db_folder: str = "./db"):
        self.id_srs_db = "srs_db"
        self.name_srs_table = self.id_srs_db + ".SrsEntrySet"

        name_srs_db = "SrsDatabase.sqlite"
        name_full_db = "KanjiDatabase.sqlite"

        path_to_srs_db = os.path.join(db_folder, name_srs_db)
        path_to_full_db = os.path.join(db_folder, name_full_db)

        try:
            self.conn = sqlite3.connect(path_to_full_db)

        except Exception:
            raise Exception

        self.cursor = self.conn.cursor()
        self.cursor.execute(f"ATTACH DATABASE '{path_to_srs_db}' AS {self.id_srs_db};")

        self.max_reviews_at_once = 10

        # in days
        self.srs_interval = {
            0: 1 / 6,
            1: 1 / 3,
            2: 1,
            3: 3,
            4: 7,
            5: 14,
            6: 30,
            7: 120,
            8: None
        }

        self.current_reviews = []
        self.current_index = 0
        self.meaning_correct = None
        self.reading_correct = None
        self.due_review_ids = []
        
        # Stats
        self.review_count = 0
        
    def close_db(self):

        # commit changes
        self.conn.commit()
        self.conn.close()

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
        df = self.get_due_reviews()
        
        if df.empty:
            return []

        sorted_df = df.sort_values("NextAnswerDateISO", ascending = False)
        self.due_review_ids = sorted_df["ID"].tolist()

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

    def update_item(self, item_id, res):
        return f"updated {item_id} with {res}"

    def convert_from_houhou(self) -> None:
        names_date_col = ["LastUpdateDate", "CreationDate", "NextAnswerDate", "SuspensionDate"]
        name_table = self.id_srs_db + ".SrsEntrySet"

        for name_col in names_date_col:
            name_iso_col = name_col + "ISO"
            q_create_col = f"ALTER TABLE {name_table} ADD COLUMN {name_iso_col} TEXT;"
            q_update_col = f"""
                           UPDATE {name_table}
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


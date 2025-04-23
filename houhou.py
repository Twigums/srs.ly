import pandas as pd
import os
import sqlite3
from datetime import datetime, timedelta, timezone


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

        # Current review session state
        self.current_reviews = []
        self.current_index = 0
        self.showing_answer = False
        
        # Stats
        self.review_count = 0
        
    def close_db(self):

        # commit changes
        self.conn.commit()
        self.conn.close()

    def get_due_reviews(self) -> pd.core.frame.DataFrame:
        date_col = "NextAnswerDateISO"
        q = f"""
            SELECT *
            FROM {self.name_srs_table}
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

    def start_review_session(self, max_reviews_at_once: int = 10):
        """Initialize a review session with due items"""
        # Use your existing get_due_reviews function to fetch due items from SQLite
        df = self.get_due_reviews()
        
        if df.empty:
            return []
        
        # Sort by the next review date
        sorted_df = df.sort_values("NextAnswerDateISO")

        current_ids = set()

        i = 0
        while i < len(sorted_df) and len(current_ids) < max_reviews_at_once:
            current_ids.add(sorted_df.iloc[i]["ID"])
            i += 1
        
        # Filter the dataframe to only include selected items
        current_df = sorted_df[sorted_df["ID"].isin(current_ids)]
        
        # Convert to list of dictionaries for easier access
        self.current_reviews = current_df.to_dict("records")
        self.current_index = 0
        self.showing_answer = False
        self.review_count = 0
        
        # Determine the type of each item (kanji or vocab)
        for i, item in enumerate(self.current_reviews):
            if item.get("AssociatedKanji"):
                self.current_reviews[i]["review_type"] = "kanji"
            elif item.get('AssociatedVocab'):
                self.current_reviews[i]["review_type"] = "vocab"
            else:
                self.current_reviews[i]["review_type"] = None
        
        return self.current_reviews

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


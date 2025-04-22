import sqlite3
import pandas as pd

def init_connection(path_to_database):
    try:
        conn = sqlite3.connect(path_to_database)    
    except Exception as e:
        print(e)
        return False

    return conn

def get_studying_kanjis():
    col_query = f"SELECT AssociatedVocab, AssociatedKanji FROM srs_db.SrsEntrySet  \
                WHERE LENGTH(AssociatedVocab) = 1 \
                OR LENGTH(AssociatedKanji) = 1"
    
    df = pd.read_sql_query(col_query, conn)
    
    set1 = set(df["AssociatedVocab"].dropna())
    set2 = set(df["AssociatedKanji"].dropna())
    
    unioned = set1.union(set2)
    
    return unioned
import sqlite3

import polars as pl


def get_connection(db_path: str) -> sqlite3.Connection:
    return sqlite3.connect(db_path)

def load_kills(db_path: str, match_id: int) -> pl.DataFrame:
    with get_connection(db_path) as conn:
        query = f"SELECT * FROM kills WHERE match_id = {match_id}"
        return pl.read_database(query, conn)

def load_ticks(db_path: str, match_id: int) -> pl.DataFrame:
    with get_connection(db_path) as conn:
        query = f"SELECT * FROM ticks WHERE match_id = {match_id}"
        return pl.read_database(query, conn)

def load_smokes(db_path: str, match_id: int) -> pl.DataFrame:
    with get_connection(db_path) as conn:
        query = f"SELECT * FROM grenades WHERE nade_type = 'smoke' AND match_id = {match_id}"
        return pl.read_database(query, conn)

def load_shots(db_path: str, match_id: int) -> pl.DataFrame:
    with get_connection(db_path) as conn:
        query = f"SELECT * FROM weapon_fires WHERE match_id = {match_id}"
        return pl.read_database(query, conn)

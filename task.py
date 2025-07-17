import sqlite3

def remove_delisted_games():
    """ Delete 30 day old unlisted games from DB"""
    with sqlite3.connect("gamelist.db") as con:
        cur = con.cursor()
        cur.execute("""
                    DELETE FROM gamelist 
                    WHERE DATE(delist_date, '+30 days') <= DATE('now')
                 """)
        con.commit()
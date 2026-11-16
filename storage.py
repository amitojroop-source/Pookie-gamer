"""Server-scoped scores, with one result per session even on duplicate callbacks."""
from pathlib import Path
import sqlite3

class Scores:
    def __init__(self, path):
        if path != ':memory:': Path(path).parent.mkdir(parents=True,exist_ok=True)
        self.db=sqlite3.connect(path)
        self.db.row_factory=sqlite3.Row
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.execute('PRAGMA busy_timeout=5000')
        self.db.execute('''CREATE TABLE IF NOT EXISTS results (
            session_id TEXT PRIMARY KEY, guild_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL, game TEXT NOT NULL, outcome TEXT NOT NULL,
            points INTEGER NOT NULL, created_at TEXT DEFAULT CURRENT_TIMESTAMP)''')
        self.db.execute('CREATE INDEX IF NOT EXISTS results_server_user ON results(guild_id,user_id)')
        self.db.execute('CREATE TABLE IF NOT EXISTS game_settings (guild_id INTEGER PRIMARY KEY, channel_id INTEGER NOT NULL)')
        if 'second_channel_id' not in {r[1] for r in self.db.execute('PRAGMA table_info(game_settings)')}:
            self.db.execute('ALTER TABLE game_settings ADD COLUMN second_channel_id INTEGER')
        self.db.commit()

    def game_channel(self,guild):
        row=self.db.execute('SELECT channel_id FROM game_settings WHERE guild_id=?',(guild,)).fetchone()
        return row['channel_id'] if row else None

    def game_channels(self,guild):
        row=self.db.execute('SELECT channel_id, second_channel_id FROM game_settings WHERE guild_id=?',(guild,)).fetchone()
        return {c for c in row if c is not None} if row else set()

    def set_game_channel(self,guild,channel,second=None):
        with self.db:
            self.db.execute('INSERT INTO game_settings(guild_id,channel_id,second_channel_id) VALUES (?,?,?) ON CONFLICT(guild_id) DO UPDATE SET channel_id=excluded.channel_id,second_channel_id=excluded.second_channel_id',(guild,channel,second))

    def record(self,session,guild,user,game,outcome,points):
        with self.db:
            cur=self.db.execute('INSERT OR IGNORE INTO results(session_id,guild_id,user_id,game,outcome,points) VALUES (?,?,?,?,?,?)',(session,guild,user,game,outcome,max(0,points)))
        return cur.rowcount==1

    def stats(self,guild,user):
        return self.db.execute("SELECT COUNT(*) AS played, COALESCE(SUM(points),0) AS points, COALESCE(SUM(outcome='win'),0) AS wins, COALESCE(SUM(outcome='draw'),0) AS draws FROM results WHERE guild_id=? AND user_id=?",(guild,user)).fetchone()

    def leaderboard(self,guild):
        return self.db.execute("SELECT user_id, SUM(points) AS points, SUM(outcome='win') AS wins FROM results WHERE guild_id=? GROUP BY user_id ORDER BY points DESC,wins DESC,user_id ASC LIMIT 10",(guild,)).fetchall()

    def close(self): self.db.close()


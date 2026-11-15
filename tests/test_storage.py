import tempfile
from pathlib import Path
import unittest
from storage import Scores
class Persistence(unittest.TestCase):
    def test_reopen_duplicate_protection_and_guild_isolation(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=str(Path(tmp)/'scores.sqlite3');s=Scores(path)
            self.assertTrue(s.record('a',1,5,'wordle','win',40))
            self.assertFalse(s.record('a',1,5,'wordle','win',40))
            s.record('b',2,5,'wordle','win',60);s.record('c',1,6,'country','loss',0)
            s.close();s=Scores(path)
            self.assertEqual(s.stats(1,5)['points'],40);self.assertEqual(s.stats(1,5)['played'],1)
            self.assertEqual(s.stats(2,5)['points'],60);self.assertEqual(s.leaderboard(1)[0]['user_id'],5)
            self.assertEqual(s.stats(9,5)['points'],0);s.close()

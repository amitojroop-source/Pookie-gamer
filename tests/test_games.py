import random
import unittest
from engine import Game, wordle_marks, code_marks
from content import WORDS, COUNTRIES, TRIVIA, GAMES, EMOJI_RIDDLES

class GameRules(unittest.TestCase):
    def game(self,kind):return Game(kind,random.Random(7))
    def test_content_and_requested_game_list(self):
        self.assertEqual(len(GAMES),10)
        self.assertNotIn('tictactoe',GAMES);self.assertNotIn('rps',GAMES)
        self.assertTrue(all(len(w)==5 and w.isascii() and w.isalpha() for w in WORDS))
        self.assertEqual(len(WORDS),len(set(WORDS)))
        self.assertGreaterEqual(len(COUNTRIES),30);self.assertGreaterEqual(len(TRIVIA),25)
        self.assertGreaterEqual(len(EMOJI_RIDDLES),20)
    def test_wordle_duplicate_letter_accounting(self):
        self.assertEqual(wordle_marks('apple','allee'),'🟩🟨⬛⬛🟩')
        self.assertEqual(wordle_marks('apple','apple'),'🟩🟩🟩🟩🟩')
        self.assertEqual(wordle_marks('apple','ppppp'),'⬛🟩🟩⬛⬛')
    def test_wordle_win_and_finished_rejection(self):
        g=self.game('wordle');g.play(g.answer)
        self.assertTrue(g.done);self.assertEqual(g.points,60)
        with self.assertRaises(ValueError):g.play('apple')
    def test_wordle_invalid_and_duplicate_do_not_consume_turn(self):
        g=self.game('wordle');g.answer='apple'
        for invalid in ['a','12345','ééééé']:
            with self.assertRaises(ValueError):g.play(invalid)
        g.play('beach')
        with self.assertRaises(ValueError):g.play('beach')
        self.assertEqual(len(g.history),1)
    def test_wordle_loss(self):
        g=self.game('wordle');g.answer='apple'
        for value in ['beach','brain','chair','cloud','dance','dream']:g.play(value)
        self.assertEqual(g.outcome,'loss');self.assertIn('APPLE',g.text())
    def test_all_five_quiz_games_complete_and_score(self):
        for kind in ['country','trivia','scramble','math','emojiriddle']:
            with self.subTest(kind=kind):
                g=self.game(kind)
                for i in range(5):
                    g.play(g.answer)
                    if i<4:g.play('next')
                self.assertTrue(g.done);self.assertEqual(g.points,50);self.assertEqual(g.correct,5)
    def test_wrong_quiz_answers_and_next_button(self):
        g=self.game('country')
        for i in range(5):
            self.assertNotIn(g.answer,g.prompt)
            g.play(next(x for x in g.options if x!=g.answer))
            if i<4:
                with self.assertRaises(ValueError):g.play(g.answer)
                g.play('next')
        self.assertEqual(g.outcome,'loss');self.assertEqual(g.points,0)
    def test_scramble_attempt_limit_and_math_validation(self):
        g=self.game('scramble')
        for _ in range(3):g.play('zzzzz')
        self.assertTrue(g.waiting_next);self.assertEqual(g.correct,0)
        g=self.game('math')
        with self.assertRaises(ValueError):g.play('abc')
        self.assertEqual(g.attempts,0)
    def test_hangman_win_repeat_and_loss(self):
        g=self.game('hangman');g.answer='apple';g.play('p')
        with self.assertRaises(ValueError):g.play('p')
        for char in 'ale':g.play(char)
        self.assertEqual(g.outcome,'win')
        g=self.game('hangman');g.answer='apple'
        for char in 'bcdfgh':g.play(char)
        self.assertEqual(g.outcome,'loss')
    def test_number_bounds_hints_and_win(self):
        g=self.game('number');g.number=42
        for invalid in ['0','101','NaN','3.5','-1']:
            with self.assertRaises(ValueError):g.play(invalid)
        g.play('20');self.assertIn('higher',g.text())
        g.play('70');self.assertIn('lower',g.text())
        g.play('42');self.assertEqual(g.outcome,'win');self.assertEqual(g.attempts,3)
    def test_number_loss(self):
        g=self.game('number');g.number=100
        for i in range(1,8):g.play(str(i))
        self.assertEqual(g.outcome,'loss')
    def test_codebreaker_feedback_leading_zero_and_win(self):
        self.assertEqual(code_marks('0123','0324'),(2,1))
        self.assertEqual(code_marks('0123','3210'),(0,4))
        g=self.game('codebreaker');g.code='0123'
        for invalid in ['1123','123','abc4','12345']:
            with self.assertRaises(ValueError):g.play(invalid)
        g.play('0123');self.assertEqual(g.outcome,'win')
    def test_codebreaker_loss(self):
        g=self.game('codebreaker');g.code='0123'
        for value in ['4567','4568','4569','4578','4579','4589','4678','4679']:g.play(value)
        self.assertEqual(g.outcome,'loss')
    def test_memory_match_mismatch_and_hide(self):
        g=self.game('memory');g.cards=list('aabbccddeeff')
        g.play('0');g.play('2')
        with self.assertRaises(ValueError):g.play('1')
        g.hide();self.assertEqual(g.exposed,[])
        for a in range(0,12,2):g.play(str(a));g.play(str(a+1))
        self.assertEqual(g.outcome,'win');self.assertEqual(len(g.matched),12)
    def test_memory_turn_limit(self):
        g=self.game('memory');g.cards=list('aabbccddeeff')
        for i in range(18):
            g.play('0');g.play('2')
            if i<17:g.hide()
        self.assertEqual(g.outcome,'loss')
    def test_every_game_display_fits_discord(self):
        for kind in GAMES:self.assertLess(len(self.game(kind).text()),4096)

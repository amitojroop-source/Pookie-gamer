import unittest
from unittest.mock import AsyncMock
from types import SimpleNamespace as NS
from storage import Scores
from content import GAMES
from bot import GameView, Lobby, client, GuessModal
class GameUI(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):self.arcade=NS(scores=Scores(':memory:'),sessions={})
    async def asyncTearDown(self):
        for view in self.arcade.sessions.values():view.stop()
        self.arcade.scores.close()
    def interaction(self,user=10):
        return NS(guild_id=20,user=NS(id=user),response=NS(send_message=AsyncMock(),defer=AsyncMock(),is_done=lambda:True),followup=NS(send=AsyncMock()),edit_original_response=AsyncMock())
    def view(self,kind='wordle'):
        view=GameView(self.arcade,20,10,kind,'A player');view.message=NS(edit=AsyncMock())
        self.arcade.sessions[(20,10)]=view;return view
    async def test_all_game_views_and_lobby_serialize(self):
        for kind in GAMES:
            view=self.view(kind);self.assertLessEqual(len(view.children),25)
            self.assertTrue(view.to_components());self.assertLessEqual(len(view.embed().description),4096);view.stop()
        lobby=Lobby(self.arcade);self.assertTrue(lobby.is_persistent());self.assertEqual(len(lobby.children[0].options),10);lobby.stop()
    async def test_other_players_cannot_move(self):
        view=self.view();i=self.interaction(user=11);await view.move(i,view.game.answer)
        self.assertEqual(view.game.history,[]);self.assertFalse(i.response.defer.called)
    async def test_modal_win_records_score_once(self):
        view=self.view();i=self.interaction();modal=GuessModal(view);self.assertEqual(modal.revision,0)
        await view.move(i,view.game.answer,revision=0)
        self.assertEqual(self.arcade.scores.stats(20,10)['points'],60);self.assertNotIn((20,10),self.arcade.sessions)
        await view.move(i,view.game.answer,revision=0);self.assertEqual(self.arcade.scores.stats(20,10)['played'],1)
    async def test_stale_modal_cannot_consume_turn(self):
        view=self.view();view.revision=1;i=self.interaction();await view.move(i,'apple',revision=0)
        self.assertEqual(len(view.game.history),0);self.assertIn('earlier turn',i.followup.send.call_args.args[0])
    async def test_timeout_releases_slot_without_points(self):
        view=self.view();await view.on_timeout();self.assertNotIn((20,10),self.arcade.sessions)
        self.assertTrue(view.game.done);self.assertEqual(self.arcade.scores.stats(20,10)['points'],0)
        await view.on_timeout();self.assertEqual(self.arcade.scores.stats(20,10)['played'],1)
    async def test_memory_buttons_and_end_round(self):
        view=self.view('memory');view.game.cards=list('aabbccddeeff');i=self.interaction()
        await view.move(i,'0');await view.move(i,'2');self.assertTrue(any(b.label=='Hide cards' for b in view.children))
        await view.move(i,'hide');self.assertEqual(view.game.exposed,[])
        await view.move(i,'quit');self.assertEqual(view.game.outcome,'abandoned')
    async def test_registered_commands_public_and_no_secret_options(self):
        names={command.name for command in client.tree.get_commands()};self.assertEqual(len(names),16)
        self.assertTrue(set(GAMES)<=names)
        for command in client.tree.get_commands():
            self.assertIsNone(command.default_permissions);self.assertEqual(len(command.parameters),2 if command.name=='setgame' else 0)
    async def test_active_round_and_failed_send_guard(self):
        old_scores=client.scores;client.scores=self.arcade.scores;client.sessions.clear();client.starts.clear()
        first=self.interaction();first.user.display_name='Test';first.response.is_done=lambda:False
        first.original_response=AsyncMock(return_value=NS(edit=AsyncMock(),jump_url='https://discord.com/channels/20/1/2'))
        await client.start_game(first,'number')
        second=self.interaction();second.user.display_name='Test';await client.start_game(second,'wordle')
        self.assertEqual(len(client.sessions),1);self.assertEqual(client.sessions[(20,10)].game.kind,'number')
        await client.sessions[(20,10)].end('test end');client.starts.clear()
        first.response.send_message=AsyncMock(side_effect=RuntimeError('failed send'))
        with self.assertRaises(RuntimeError):await client.start_game(first,'wordle')
        self.assertEqual(client.sessions,{});client.scores=old_scores

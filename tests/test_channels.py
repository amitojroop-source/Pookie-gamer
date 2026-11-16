import tempfile,unittest
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock
from storage import Scores
from bot import client,setgame,GameView,games
class Channels(unittest.IsolatedAsyncioTestCase):
 async def asyncSetUp(self):
  self.old_info=client.application_info;client.application_info=AsyncMock(return_value=NS(team=None,owner=NS(id=7)));self.old=client.scores;client.scores=Scores(':memory:');client.sessions.clear()
 async def asyncTearDown(self):
  for v in list(client.sessions.values()):v.stop()
  client.sessions.clear();client.scores.close();client.scores=self.old;client.application_info=self.old_info
 def interaction(self,g=1,c=10,u=7):
  return NS(guild_id=g,channel_id=c,guild=NS(id=g,owner_id=7,me=object()),user=NS(id=u,display_name='Test'),response=NS(is_done=lambda:False,send_message=AsyncMock(),defer=AsyncMock()),followup=NS(send=AsyncMock()))
 def channel(self,g,c):
  return NS(id=c,guild=NS(id=g),mention=str(c),permissions_for=lambda m:NS(view_channel=True,send_messages=True,embed_links=True))
 async def test_owner_isolation_and_change(self):
  await setgame.callback(self.interaction(u=8),self.channel(1,10));self.assertIsNone(client.scores.game_channel(1))
  for g,c in [(1,10),(2,20),(1,11)]:await setgame.callback(self.interaction(g),self.channel(g,c))
  self.assertEqual(client.scores.game_channel(1),11);self.assertEqual(client.scores.game_channel(2),20)
 async def test_block_lobby_start_and_move(self):
  client.scores.set_game_channel(1,10);i=self.interaction(c=11)
  await games.callback(i);await client.start_game(i,'wordle');self.assertFalse(client.sessions)
  v=GameView(client,1,7,'wordle','Test');await v.move(i,v.game.answer);self.assertFalse(v.game.done);v.stop()
 async def test_end_old_rounds_only_in_this_server(self):
  for g,c in [(1,10),(2,20)]:
   v=GameView(client,g,7,'wordle','Test');v.message=NS(channel=NS(id=c),edit=AsyncMock());client.sessions[(g,7)]=v
  await setgame.callback(self.interaction(),self.channel(1,11))
  self.assertNotIn((1,7),client.sessions);self.assertIn((2,7),client.sessions)
 async def test_persistence(self):
  with tempfile.TemporaryDirectory() as tmp:
   p=tmp+'/db';s=Scores(p);s.set_game_channel(1,10);s.set_game_channel(2,20);s.close()
   s=Scores(p);self.assertEqual(s.game_channel(1),10);self.assertEqual(s.game_channel(2),20);s.close()
 async def test_two_channels_and_replacement(self):
  from bot import game_channel_allowed
  await setgame.callback(self.interaction(),self.channel(1,10),self.channel(1,11))
  self.assertEqual(client.scores.game_channels(1),{10,11})
  self.assertTrue(await game_channel_allowed(client,self.interaction(c=10)))
  self.assertTrue(await game_channel_allowed(client,self.interaction(c=11)))
  self.assertFalse(await game_channel_allowed(client,self.interaction(c=12)))
  await setgame.callback(self.interaction(),self.channel(1,12))
  self.assertEqual(client.scores.game_channels(1),{12})
  with tempfile.TemporaryDirectory() as tmp:
   p=tmp+'/db';s=Scores(p);s.set_game_channel(1,10,11);s.close();s=Scores(p)
   self.assertEqual(s.game_channels(1),{10,11});s.close()

"""Pookie Gamer: slash commands and native Discord game controls."""
import asyncio
import logging
import os
import time
import uuid
import discord
from discord import app_commands
from dotenv import load_dotenv
from content import GAMES
from engine import Game
from storage import Scores

log=logging.getLogger('pookie')
COLOR=0xB57BFF

async def private_reply(interaction,text):
    if interaction.response.is_done():
        await interaction.followup.send(text,ephemeral=True)
    else:
        await interaction.response.send_message(text,ephemeral=True)

class Arcade(discord.Client):
    def __init__(self):
        # Slash commands and components need no message content or members intent.
        super().__init__(intents=discord.Intents.default(),allowed_mentions=discord.AllowedMentions.none())
        self.tree=app_commands.CommandTree(self)
        self.sessions={}
        self.starts={}
        self.scores=None
        self.synced=set()
        self.sync_lock=asyncio.Lock()

    async def setup_hook(self):
        self.scores=Scores(os.getenv('DATABASE_PATH','data/pookie.sqlite3'))
        self.add_view(Lobby(self))

    async def sync_guild(self,guild):
        async with self.sync_lock:
            if guild.id in self.synced:return
            try:
                self.tree.copy_global_to(guild=guild)
                commands=await self.tree.sync(guild=guild)
                self.synced.add(guild.id)
                log.info('Registered %s commands in server %s',len(commands),guild.id)
            except discord.HTTPException:
                log.exception('Command sync failed in server %s; it will retry on reconnect',guild.id)

    async def on_ready(self):
        for guild in self.guilds: await self.sync_guild(guild)
        await self.change_presence(activity=discord.Game('/games • 10 games, everyone welcome'))
        log.info('Pookie Gamer is online in %s servers',len(self.guilds))

    async def on_guild_join(self,guild): await self.sync_guild(guild)

    async def close(self):
        # In-progress sessions end at restart. Completed scores remain in SQLite.
        for view in list(self.sessions.values()): view.stop()
        await super().close()
        if self.scores:self.scores.close()

    async def start_game(self,interaction,kind):
        if not interaction.guild_id:
            await private_reply(interaction,'Play inside a server using /games.');return
        key=(interaction.guild_id,interaction.user.id)
        if key in self.sessions:
            view=self.sessions[key]
            link=getattr(view.message,'jump_url',None)
            await private_reply(interaction,'You already have a round running. '+(f'[Open it]({link}). ' if link else '')+'Use /stopgame to end it.');return
        now=time.monotonic()
        if now-self.starts.get(key,0)<3:
            await private_reply(interaction,'Wait a moment before starting another game.');return
        if len(self.sessions)>=500:
            await private_reply(interaction,'The arcade is busy. Please try again in a moment.');return
        # Reserve before the first await, so simultaneous starts cannot overlap.
        view=GameView(self,interaction.guild_id,interaction.user.id,kind,interaction.user.display_name)
        self.sessions[key]=view
        self.starts[key]=now
        if len(self.starts)>2000:self.starts={k:v for k,v in self.starts.items() if now-v<60}
        try:
            await interaction.response.send_message(embed=view.embed(),view=view)
            view.message=await interaction.original_response()
        except Exception:
            if self.sessions.get(key) is view:self.sessions.pop(key,None)
            view.stop()
            raise

class MoveButton(discord.ui.Button):
    def __init__(self,game_view,value,label,*,row=None,style=discord.ButtonStyle.secondary,disabled=False):
        super().__init__(label=label,style=style,row=row,disabled=disabled)
        self.game_view=game_view;self.value=value
    async def callback(self,interaction): await self.game_view.move(interaction,self.value)

class GuessModal(discord.ui.Modal,title='Your answer'):
    answer=discord.ui.TextInput(label='Answer',placeholder='Type your guess here',min_length=1,max_length=40)
    def __init__(self,game_view):
        super().__init__(timeout=120)
        self.game_view=game_view
        self.revision=game_view.revision
    async def on_submit(self,interaction):
        await self.game_view.move(interaction,str(self.answer),revision=self.revision)
    async def on_error(self,interaction,error):
        log.error('Guess modal error',exc_info=(type(error),error,error.__traceback__))
        await private_reply(interaction,'Something went wrong. Try opening the answer box again.')

class GuessButton(discord.ui.Button):
    def __init__(self):super().__init__(label='Enter guess',emoji='✍️',style=discord.ButtonStyle.primary)
    async def callback(self,interaction):
        await interaction.response.send_modal(GuessModal(self.view))

class GameView(discord.ui.View):
    def __init__(self,client,guild_id,user_id,kind,display_name):
        super().__init__(timeout=180)
        self.client=client;self.guild_id=guild_id;self.user_id=user_id
        self.game=Game(kind);self.name=display_name;self.message=None
        self.session_id=uuid.uuid4().hex;self.lock=asyncio.Lock();self.revision=0
        self.recorded=False
        self.build_controls()

    async def interaction_check(self,interaction):
        if interaction.user.id!=self.user_id or interaction.guild_id!=self.guild_id:
            await private_reply(interaction,'This round belongs to another player. Start your own with /games!');return False
        if self.game.done:
            await private_reply(interaction,'This round has ended. Start another with /games.');return False
        return True

    def embed(self):
        emoji,title,_=GAMES[self.game.kind]
        embed=discord.Embed(title=f'{emoji} {title}',description=self.game.text(),color=0x43C59E if self.game.outcome=='win' else COLOR)
        embed.set_author(name=f'{self.name[:60]} • Pookie Gamer')
        embed.set_footer(text='Everyone can play • 3 minutes without a move ends the round • /games')
        return embed

    def build_controls(self):
        self.clear_items();g=self.game
        if g.done:
            # Preserve the final board, but disable it.
            if g.kind not in ('memory',):return
        if g.kind=='memory':
            for i,card in enumerate(g.cards):
                revealed=g.done or i in g.matched or i in g.exposed
                self.add_item(MoveButton(self,str(i),card if revealed else str(i+1),row=i//4,style=discord.ButtonStyle.success if i in g.matched else discord.ButtonStyle.secondary,disabled=g.done or i in g.matched or i in g.exposed or len(g.exposed)==2))
            if len(g.exposed)==2 and not g.done:self.add_item(MoveButton(self,'hide','Hide cards',row=3,style=discord.ButtonStyle.primary))
        elif g.waiting_next:self.add_item(MoveButton(self,'next','Next question →',style=discord.ButtonStyle.primary))
        elif g.options:
            for option in g.options:self.add_item(MoveButton(self,option,option,row=len(self.children)//2))
        else:self.add_item(GuessButton())
        if not g.done:self.add_item(MoveButton(self,'quit','End round',row=4,style=discord.ButtonStyle.danger))

    def save_result(self):
        if not self.recorded:
            self.client.scores.record(self.session_id,self.guild_id,self.user_id,self.game.kind,self.game.outcome,self.game.points)
            self.recorded=True
        key=(self.guild_id,self.user_id)
        if self.client.sessions.get(key) is self:self.client.sessions.pop(key,None)
        self.stop()

    async def move(self,interaction,value,revision=None):
        if not await self.interaction_check(interaction):return
        # Acknowledge before waiting on any concurrent callback or Discord edit.
        await interaction.response.defer()
        async with self.lock:
            if self.game.done:
                await private_reply(interaction,'This round has already ended.');return
            if revision is not None and revision!=self.revision:
                await private_reply(interaction,'That answer box belongs to an earlier turn. Open a new one.');return
            try:
                if value=='quit':self.game.finish('abandoned',0,'Round ended. Start something new with /games!')
                elif value=='hide':self.game.hide()
                else:self.game.play(value)
            except ValueError as exc:
                await private_reply(interaction,str(exc));return
            self.revision+=1
            if self.game.done:self.save_result()
            self.build_controls()
            # Modal submissions retain the triggering message; edit the bound game
            # message directly so slash /stopgame can use the same view too.
            try:
                if self.message:await self.message.edit(embed=self.embed(),view=self)
                else:await interaction.edit_original_response(embed=self.embed(),view=self)
            except discord.NotFound:
                if not self.game.done:
                    self.game.finish('abandoned',0,'Game message was deleted.');self.save_result()
            except discord.HTTPException:
                await private_reply(interaction,'Your move was saved, but Discord could not refresh the panel. Use /stopgame if needed.')

    async def end(self,reason):
        async with self.lock:
            if self.game.done:return
            self.game.finish('abandoned',0,reason);self.save_result();self.build_controls()
            if self.message:
                try:await self.message.edit(embed=self.embed(),view=self)
                except discord.HTTPException:pass

    async def on_timeout(self):await self.end('⌛ Round expired after 3 minutes without a move. Start again with /games.')

    async def on_error(self,interaction,error,item):
        log.error('Game interaction error',exc_info=(type(error),error,error.__traceback__))
        await private_reply(interaction,'Something went wrong with this move. Use /stopgame to reset your round if needed.')

class GameMenu(discord.ui.Select):
    def __init__(self,client):
        self.client=client
        super().__init__(placeholder='Choose your next game…',custom_id='pookie:arcade:v1',options=[discord.SelectOption(label=title,value=kind,emoji=emoji,description=description) for kind,(emoji,title,description) in GAMES.items()])
    async def callback(self,interaction):await self.client.start_game(interaction,self.values[0])

class Lobby(discord.ui.View):
    def __init__(self,client):super().__init__(timeout=None);self.add_item(GameMenu(client))
    async def on_error(self,interaction,error,item):
        log.error('Lobby error',exc_info=(type(error),error,error.__traceback__))
        await private_reply(interaction,'I could not start that game. Check my Send Messages and Embed Links permissions, then try again.')

client=Arcade()

@client.tree.command(name='games',description='Open the Pookie Gamer arcade — everyone can play!')
@app_commands.guild_only()
async def games(interaction:discord.Interaction):
    embed=discord.Embed(title='🎮 POOKIE GAMER',description='**Pick a game. Make your move. Climb the leaderboard.**\n\n'+'\n'.join(f'{emoji} **{title}** — {description}' for emoji,title,description in GAMES.values())+'\n\nEveryone can start their own round. Your buttons belong to you.\n🏆 `/leaderboard` · ⭐ `/stats` · 🛑 `/stopgame`',color=COLOR)
    embed.set_footer(text='10 games • No role required • No paid API • Scores saved per server')
    await interaction.response.send_message(embed=embed,view=Lobby(client))

# Direct commands as well as the menu. Factory avoids accidental slash options.
def game_command(kind):
    async def command(interaction:discord.Interaction):await client.start_game(interaction,kind)
    command.__name__=kind
    return app_commands.guild_only()(command)
for kind,(_,title,description) in GAMES.items():
    client.tree.command(name=kind,description=f'{title}: {description}')(game_command(kind))

@client.tree.command(name='stopgame',description='End your current round so you can start another game.')
@app_commands.guild_only()
async def stopgame(interaction:discord.Interaction):
    view=client.sessions.get((interaction.guild_id,interaction.user.id))
    if not view:await private_reply(interaction,'You have no active round. Choose one with /games.');return
    await interaction.response.defer(ephemeral=True)
    await view.end('Round ended by the player.')
    await interaction.followup.send('Round ended. Choose another game with /games.',ephemeral=True)

@client.tree.command(name='leaderboard',description='See this server’s top 10 players.')
@app_commands.guild_only()
async def leaderboard(interaction:discord.Interaction):
    rows=client.scores.leaderboard(interaction.guild_id)
    text='\n'.join(f'**{i}.** <@{r["user_id"]}> — **{r["points"]} pts** · {r["wins"]} wins' for i,r in enumerate(rows,1)) or 'No scores yet. Play a round with /games!'
    await interaction.response.send_message(embed=discord.Embed(title='🏆 Server Leaderboard',description=text,color=COLOR))

@client.tree.command(name='stats',description='See your points, wins and completed rounds in this server.')
@app_commands.guild_only()
async def stats(interaction:discord.Interaction):
    row=client.scores.stats(interaction.guild_id,interaction.user.id)
    await interaction.response.send_message(embed=discord.Embed(title='⭐ Your Player Card',description=f'**Points:** {row["points"]}\n**Wins:** {row["wins"]}\n**Draws:** {row["draws"]}\n**Finished/ended rounds:** {row["played"]}',color=COLOR),ephemeral=True)

@client.tree.command(name='help',description='How to play and use Pookie Gamer.')
@app_commands.guild_only()
async def help_command(interaction:discord.Interaction):
    await interaction.response.send_message(embed=discord.Embed(title='💜 Welcome to Pookie Gamer',description='Use **/games** and choose from 10 games, or use a game command directly.\n\n**Everyone can play** — there are no owner, Staff, or premium restrictions. Many players can play at once. Each player gets one active round per server.\n\nUse buttons for choices and boards; **Enter guess** opens a private answer box. Game progress is public in the channel.\n\n**Scoring:** each game displays its earned points. Country, Trivia, Emoji Riddles, Scramble and Math award 10 points per correct answer; 3/5 counts as a win. Faster wins earn more points in Wordle, Number, Codebreaker and Memory.\n\n**/stopgame** ends your round. Three minutes of inactivity expires it. Rounds end on bot restarts; saved scores remain when persistent storage is configured.\n\n**/leaderboard** shows server rankings. **/stats** shows your record.',color=COLOR),ephemeral=True)

@client.tree.error
async def command_error(interaction,error):
    if isinstance(error,app_commands.NoPrivateMessage):await private_reply(interaction,'Use this command in a server.');return
    log.error('Slash command error',exc_info=(type(error),error,error.__traceback__))
    await private_reply(interaction,'I could not complete that command. Please try again. If starting a game, check my Send Messages and Embed Links permissions.')

if __name__=='__main__':
    load_dotenv()
    token=os.getenv('DISCORD_BOT_TOKEN','').strip()
    if not token:raise SystemExit('Set DISCORD_BOT_TOKEN to the token for your NEW Pookie Gamer bot.')
    logging.basicConfig(level=logging.INFO,format='%(asctime)s %(levelname)s %(name)s: %(message)s')
    client.run(token)

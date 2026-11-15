# 🎮 Pookie Gamer

A Discord arcade with **10 playable games**, a violet interface, buttons, answer modals, server leaderboards, and SQLite score storage. Everyone can play: no Staff role, paid tier, AI service or API key is required.

## The arcade

| Command | Game | How it works |
|---|---|---|
| `/wordle` | Wordle-style word puzzle | Six guesses; green/yellow/black feedback handles duplicate letters. Any five ASCII letters are accepted; answers come from the included common-word bank. |
| `/country` | Guess the Country | Five flags and landmark clues, four choices each. |
| `/trivia` | Trivia | Five randomly sampled multiple-choice questions. |
| `/hangman` | Hangman | Guess individual letters; six misses ends the game. |
| `/scramble` | Word Scramble | Five scrambled words, three attempts each. |
| `/number` | Guess the Number | Find 1–100 with higher/lower clues in seven guesses. |
| `/math` | Math Challenge | Five addition, subtraction or multiplication problems. |
| `/emojiriddle` | Emoji Riddles | Guess five movie titles from emoji clues. |
| `/codebreaker` | Codebreaker | Eight guesses to crack four unique digits, with exact/misplaced clues. |
| `/memory` | Memory Match | Six pairs; up to 18 turns. Mismatches remain visible until you press Hide cards. |

`/games` opens a persistent game-selection menu. `/help`, `/stats`, `/leaderboard` and `/stopgame` complete the arcade.

Many members can play concurrently. Each member has one active round per server. Only the player who started a round can use its controls. Progress is public; answer entry and validation messages are private. Games use buttons and slash commands, not channel-message listeners.

## Set up your NEW Discord bot

1. Open the [Discord Developer Portal](https://discord.com/developers/applications), create an application named **Pookie Gamer**, and open **Bot**.
2. Get its bot token. Store it only as `DISCORD_BOT_TOKEN` in your host's private Variables. **Never paste it into GitHub or chat.** Do not use Lucius's token.
3. Under OAuth2 URL Generator, choose **bot** and **applications.commands**. Give the bot **View Channels**, **Send Messages**, and **Embed Links**, then use the generated invite link to add it to your server.
4. No privileged intents are required: Message Content, Server Members, and Presence can remain off.
5. Start the bot. It registers commands in each server on startup and when joining a server. Members need Discord's **Use Application Commands** channel permission.
6. Run `/games` or one of the ten game commands.

This repository does not create a Discord application or include a token. It becomes a live bot only after you provide a new bot token and deploy it.

## Deploy on Railway

Create a **new service** using this repository. The included Dockerfile and railway.json start `python bot.py` automatically. Add `DISCORD_BOT_TOKEN` in Railway Variables.

For saved scores across deployments, attach a persistent volume mounted at `/data` and set `DATABASE_PATH=/data/pookie.sqlite3`. The default local database is `data/pookie.sqlite3`; a container's local disk alone is not durable across deployments. Use **one replica**, as game sessions live in memory and SQLite is local to the volume.

This is a background Discord worker. No web domain, port, or HTTP health check is needed. Railway hosting may cost money; this code does not provision or purchase hosting.

## Run locally

Python 3.10 or newer:

```sh
python -m venv .venv
# Activate the virtual environment for your OS, then:
pip install -r requirements.txt
# Copy .env.example to .env and fill in your NEW bot token privately.
python bot.py
```

## Scores and limits

Scores are scoped to each server. Quiz games award 10 points per correct answer, with 3/5 considered a win. Wordle, Hangman, Number, Codebreaker and Memory award points based on attempts. Results are saved once per session, even if callbacks repeat. Abandoned and expired rounds award zero.

A game expires after three minutes without a component interaction. `/stopgame` releases your slot immediately. Restarting the bot ends in-progress rounds; completed scores remain in persistent storage. Existing arcade menus work again after restart, but old game buttons cannot resume their lost rounds. Start a new round with `/games`.

There is a three-second start cooldown per player and a maximum of 500 active rounds. Games are for fun, with no paid entry, gambling, cash payouts or prizes. Question banks are local and can be extended in `content.py`.

## Tests

```sh
python -m unittest discover -s tests -v
python -m compileall -q bot.py engine.py content.py storage.py
```

Tests use mock Discord interactions and temporary databases. They do not contact Discord or prove live bot connectivity. Live acceptance: start `/games` with two users; verify each can start a round but cannot play the other's controls, finish a game, check `/stats` and `/leaderboard`, restart the bot, and verify saved scores and the arcade menu.

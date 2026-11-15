"""Game rules independent of Discord, so every game can be tested offline."""
from collections import Counter
import random
from content import WORDS, COUNTRIES, TRIVIA, GAMES, EMOJI_RIDDLES


def wordle_marks(answer, guess):
    marks = ['⬛'] * 5
    remaining = Counter(a for a, g in zip(answer, guess) if a != g)
    for i, (a, g) in enumerate(zip(answer, guess)):
        if a == g:
            marks[i] = '🟩'
        elif remaining[g]:
            marks[i] = '🟨'
            remaining[g] -= 1
    return ''.join(marks)


def code_marks(answer, guess):
    exact=sum(a==g for a,g in zip(answer,guess))
    shared=sum((Counter(answer)&Counter(guess)).values())
    return exact, shared-exact


class Game:
    def __init__(self, kind, rng=None):
        if kind not in GAMES: raise ValueError('Unknown game')
        self.kind=kind; self.rng=rng or random.Random()
        self.done=False; self.outcome=None; self.points=0; self.notice=''; self.round=0; self.correct=0
        self.history=[]; self.guessed=set(); self.misses=0
        self.number=self.rng.randint(1,100); self.attempts=0
        self.code=''.join(self.rng.sample('0123456789',4))
        self.cards=list('🍓🍋🍇🍒🥝🍉')*2; self.rng.shuffle(self.cards)
        self.matched=set(); self.exposed=[]; self.turns=0
        self.answer=self.rng.choice(WORDS)
        self.questions=[]; self.options=[]; self.waiting_next=False
        if kind in ('country','trivia','scramble','math','emojiriddle'): self.make_questions(); self.load_question()

    def finish(self, outcome, points, notice):
        self.done=True; self.outcome=outcome; self.points=points; self.notice=notice

    def make_questions(self):
        if self.kind=='country':
            for name,flag,capital,clue in self.rng.sample(COUNTRIES,5):
                # Only flags and stable landmark clues are used; capitals are not queried.
                others=self.rng.sample([c[0] for c in COUNTRIES if c[0]!=name],3)
                self.questions.append((f'{flag}\n{clue}. Which country is it?',name,others))
        elif self.kind=='trivia': self.questions=self.rng.sample(TRIVIA,5)
        elif self.kind=='emojiriddle': self.questions=self.rng.sample(EMOJI_RIDDLES,5)
        elif self.kind=='scramble':
            for word in self.rng.sample(WORDS,5):
                letters=list(word)
                while ''.join(letters)==word: self.rng.shuffle(letters)
                self.questions.append((' '.join(letters).upper(),word,[]))
        else:
            for _ in range(5):
                a=self.rng.randint(2,20); b=self.rng.randint(2,12); op=self.rng.choice(['+','−','×'])
                value=a+b if op=='+' else a-b if op=='−' else a*b
                self.questions.append((f'{a} {op} {b} = ?',str(value),[]))

    def load_question(self):
        self.prompt,self.answer,distractors=self.questions[self.round]
        self.options=[self.answer,*distractors] if distractors else []
        self.rng.shuffle(self.options); self.attempts=0; self.waiting_next=False

    def next_question(self):
        if not self.waiting_next: raise ValueError('Answer this question first.')
        self.round+=1; self.notice=''; self.load_question()

    def quiz_answer(self, guess):
        if self.waiting_next: raise ValueError('Press Next question.')
        if self.kind=='math':
            try: guess=str(int(guess))
            except ValueError: raise ValueError('Enter a whole number, for example 24 or -3.')
        if self.kind=='scramble' and (len(guess)!=5 or not guess.isascii() or not guess.isalpha()):
            raise ValueError('Enter a five-letter word.')
        self.attempts+=1
        if guess.casefold()==self.answer.casefold():
            self.correct+=1; self.notice='✅ Correct!'
        elif self.kind=='scramble' and self.attempts<3:
            self.notice=f'Not quite. {3-self.attempts} tries left for this word.'; return
        else: self.notice=f'❌ The answer was **{self.answer}**.'
        if self.round==4:
            self.finish('win' if self.correct>=3 else 'loss',self.correct*10,f'{self.notice}\nFinished: **{self.correct}/5 correct**.')
        else: self.waiting_next=True

    def play(self, value):
        if self.done: raise ValueError('This game has finished.')
        value=value.strip().lower()
        if value=='next': self.next_question(); return
        if self.kind in ('country','trivia','scramble','math','emojiriddle'): self.quiz_answer(value); return
        if self.kind=='wordle':
            if len(value)!=5 or not value.isascii() or not value.isalpha(): raise ValueError('Enter exactly five English letters.')
            if any(g==value for g,_ in self.history): raise ValueError('You already tried that guess.')
            self.history.append((value,wordle_marks(self.answer,value)))
            if value==self.answer: self.finish('win',max(10,70-10*len(self.history)),'🎉 You found the word!')
            elif len(self.history)==6: self.finish('loss',0,f'The word was **{self.answer.upper()}**.')
        elif self.kind=='hangman':
            if len(value)!=1 or not value.isascii() or not value.isalpha(): raise ValueError('Enter one English letter.')
            if value in self.guessed: raise ValueError('You already tried that letter.')
            self.guessed.add(value)
            if value not in self.answer: self.misses+=1
            if set(self.answer)<=self.guessed: self.finish('win',max(10,60-self.misses*8),'🎉 Word rescued!')
            elif self.misses==6: self.finish('loss',0,f'The word was **{self.answer.upper()}**.')
        elif self.kind=='number':
            if not value.isascii() or not value.isdigit() or not 1<=int(value)<=100: raise ValueError('Enter a whole number from 1 to 100.')
            number=int(value)
            if number in self.guessed: raise ValueError('You already tried that number.')
            self.guessed.add(number); self.attempts+=1
            self.history.append(f'{number} → '+('correct' if number==self.number else 'go higher ↑' if number<self.number else 'go lower ↓'))
            if number==self.number: self.finish('win',max(10,80-self.attempts*10),'🎯 You found it!')
            elif self.attempts==7: self.finish('loss',0,f'The number was **{self.number}**.')
        elif self.kind=='codebreaker':
            if len(value)!=4 or not value.isascii() or not value.isdigit() or len(set(value))!=4:
                raise ValueError('Enter four different digits, such as 0123. Leading zero is allowed.')
            if value in self.guessed: raise ValueError('You already tried that code.')
            self.guessed.add(value); self.attempts+=1
            exact,misplaced=code_marks(self.code,value)
            self.history.append(f'`{value}` — **{exact} exact**, **{misplaced} misplaced')
            if exact==4:self.finish('win',max(10,90-self.attempts*10),'🔓 Code cracked!')
            elif self.attempts==8:self.finish('loss',0,f'The code was **{self.code}**.')
        elif self.kind=='memory': self.flip(value)

    def flip(self,value):
        try: cell=int(value)
        except ValueError: raise ValueError('Choose a card.')
        if len(self.exposed)==2: raise ValueError('Press Hide cards before your next turn.')
        if not 0<=cell<12 or cell in self.matched or cell in self.exposed: raise ValueError('Choose a hidden card.')
        self.exposed.append(cell)
        if len(self.exposed)==2:
            self.turns+=1
            if self.cards[self.exposed[0]]==self.cards[self.exposed[1]]:
                self.matched.update(self.exposed); self.exposed=[]; self.notice='✅ Match!'
            else: self.notice='Not a match. Remember these cards, then press Hide cards.'
            if len(self.matched)==12: self.finish('win',max(10,70-self.turns*2),'🎉 All pairs matched!')
            elif self.turns>=18: self.finish('loss',len(self.matched)*2,'Out of turns. Start another round!')

    def hide(self):
        if self.done or len(self.exposed)!=2: raise ValueError('There are no mismatched cards to hide.')
        self.exposed=[]; self.notice=''

    def text(self):
        if self.kind=='wordle':
            body='\n'.join(f'{marks}  `{guess.upper()}`' for guess,marks in self.history) or '⬛⬛⬛⬛⬛'
            body+=f'\n\n**{len(self.history)}/6 guesses** · 🟩 right spot · 🟨 wrong spot\nEnter any five English letters; the answer is a common word.'
        elif self.kind=='hangman':
            body=' '.join(c.upper() if c in self.guessed else '▰' for c in self.answer)
            body+=f'\n\n**Misses: {self.misses}/6**\nTried: '+(', '.join(sorted(self.guessed)).upper() or 'none')
        elif self.kind=='number': body=f'**Guess a number from 1 to 100.**\nAttempts: {self.attempts}/7\n\n'+'\n'.join(self.history)
        elif self.kind in ('country','trivia','scramble','math','emojiriddle'): body=f'**Round {self.round+1}/5** · Correct: {self.correct}\n\n{self.prompt}'
        elif self.kind=='codebreaker': body=f'**Find the four-digit code.** All four digits are different; it can start with 0.\nExact = right digit and position. Misplaced = right digit, wrong position.\n**Attempts: {self.attempts}/8**\n\n'+'\n'.join(self.history)
        else: body=f'**Pairs: {len(self.matched)//2}/6 · Turns: {self.turns}/18**\nFlip two cards to find a matching pair.'
        if self.notice: body+='\n\n'+self.notice
        if self.done: body+=f'\n\n**+{self.points} points** · Start another game with `/games`.'
        return body

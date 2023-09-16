import asyncio
import logging
import random
from pprint import pprint
import json
import discord
from discord.ext import commands, tasks


class CardCollection:
    def __init__(self):
        self.cards = []

    def append(self, card):
        self.cards.append(card)

    def pop(self):
        return self.cards.pop()

    def shuffle(self):
        random.shuffle(self.cards)

    def remove(self, card):
        self.cards.remove(card)

    def __len__(self):
        return len(self.cards)

    def __iter__(self):
        return iter(self.cards)

    def __contains__(self, item):
        return item in self.cards

    def __getitem__(self, item):
        return self.cards[item]

    def __setitem__(self, key, value):
        self.cards[key] = value

    def __delitem__(self, key):
        del self.cards[key]

    def clear(self):
        self.cards.clear()


class Card:
    def __init__(self, color, type):
        self.color = color
        self.overridenColor = None
        self.type = type

    def __str__(self):
        return f'{self.color} {self.type}' if self.overridenColor is None else f'{self.overridenColor} {self.type}'


class Player:
    def __init__(self, bot, id):
        self.bot = bot
        self.id = id
        self.name = self.bot.get_user(self.id).name
        self.hand = CardCollection()
        self.score = 0
        self.gameMSG = None

    async def send(self, message=None, embed=None, view=None):
        if self.gameMSG is None:
            self.gameMSG = await self.bot.get_user(self.id).send(message, embed=embed, view=view)
        else:
            await self.gameMSG.edit(message, embed=embed, view=view)
        return self.gameMSG

    async def delete(self):
        await self.gameMSG.delete()
        self.gameMSG = None

    def __str__(self):
        return f'{self.id}'


class Table:
    def __init__(self, players: list[int], bot: commands.AutoShardedBot):
        self.bot = bot
        self.logger = logging.getLogger('discord')
        self.deck = CardCollection()
        self.discard = CardCollection()
        self.players = [Player(self.bot, player) for player in players]
        random.shuffle(self.players)
        self.settings = {'maxStackSize': 7,
                         'startCards': 7,
                         'drawUntilPlayable': True}
        self.status = 'waiting'
        self.currentPlayerIndex = -1
        self.hasSkipped = False  # whether the current player has been skipped
        self.force_pickup = 0  # how many cards the next player has to pick up
        self.timer = 60  # how long the current player has to play a card before they are skipped
        # and kicked from the game

    @tasks.loop(seconds=10)
    async def update_gameMsg(self):
        if self.status == 'started':
            for player in self.players:
                embed, view = await self.createGameEmbedMessage(player)
                await player.send(embed=embed, view=view)

    async def setup(self):
        self.status = 'setup'
        for color in ['red', 'yellow', 'green', 'blue']:
            for i in range(10):
                self.deck.append(Card(color, i))
                if i != 0:
                    self.deck.append(Card(color, i))
            self.deck.append(Card(color, 'skip'))
            self.deck.append(Card(color, 'reverse'))
            self.deck.append(Card(color, '+2'))
        for i in range(4):
            self.deck.append(Card('black', 'wild'))
            self.deck.append(Card('black', 'wild+4'))
        self.deck.shuffle()
        for player in self.players:
            for i in range(self.settings['startCards']):
                player.hand.append(self.deck.pop())
        self.discard.append(self.deck.pop())
        self.status = 'ready'
        self.announce(
            f"Welcome to Uno! You are playing with {', '.join([str(player.name) for player in self.players])}!\nThe "
            f"game is setting up and will start soon.", delete_after=15)
        self.update_gameMsg.start()
        await asyncio.sleep(10)
        await self.start()

    async def start(self):
        if self.status == 'ready':
            self.status = 'started'
            random.shuffle(self.players)
            while self.discard[-1].color == 'black':
                self.discard.append(self.deck.pop())
            await self.tick({'type': 'start'})
            return True
        else:
            return False

    def announce(self, message=None, embed=None, delete_after=None):
        for player in self.players:
            self.bot.loop.create_task(self.bot.get_user(player.id).send(message, embed=embed,
                                                                        delete_after=delete_after))

    def canPlay(self, card):
        # A card is allowed to be played if it is the same color or type as the top card in the discard pile
        topCard = self.discard[-1]
        try:
            topCard.overridenColor
        except AttributeError:
            pass
        else:
            if topCard.overridenColor is not None and topCard.color == 'black':
                if topCard.overridenColor == card.color or topCard.type == card.type:
                    return True
                else:
                    return False
        if card.color != 'black':
            if topCard.color == card.color or topCard.type == card.type:
                return True
        elif card.color == 'black':
            return True
        else:
            return False

    def play(self, player, card):
        if self.canPlay(card):
            self.discard.append(card)
            player.hand.remove(card)
            return True
        else:
            return False

    async def tick(self, data):
        """Every time a player plays a card or draws a card, this function is called to check if the game has ended."""

        async def WildChoice(interaction: discord.Interaction):
            await interaction.response.defer()
            await interaction.delete_original_response()
            data = json.loads(interaction.data['custom_id'])
            color = data['data']['color']
            self.discard[-1].overridenColor = color

        if self.status == 'started':
            # Next player
            self.processed_topCard = False
            topCard = self.discard[-1]
            if topCard.color == 'black' and data['type'] != 'draw_card':
                if topCard.type == 'wild+4':
                    self.force_pickup += 4
                # if a wild card is played, send a message to the player asking them to choose a color
                view = discord.ui.View()
                for color in ['red', 'yellow', 'green', 'blue']:
                    button = discord.ui.Button(label=color.title(), style=discord.ButtonStyle.blurple,
                                               custom_id=json.dumps({'type': 'wild_choice', 'data': {
                                                   'color': color,
                                                   'player': self.players[self.currentPlayerIndex].id}}))
                    button.callback = WildChoice
                    view.add_item(button)
                await self.bot.get_user(self.players[self.currentPlayerIndex].id).send("Choose a color", view=view)
                while self.discard[-1].overridenColor is None:
                    await asyncio.sleep(1)
            self.currentPlayerIndex += 1
            if self.currentPlayerIndex >= len(self.players):
                self.currentPlayerIndex -= len(self.players)
            if not data['type'] == 'draw_card':
                # check top card for special cards
                if topCard.type == 'skip':
                    # skip the next player by adding 2 to the current player index
                    self.currentPlayerIndex += 1
                    if self.currentPlayerIndex >= len(self.players):
                        self.currentPlayerIndex -= len(self.players)
                    self.announce(f'{self.players[self.currentPlayerIndex - 1].name} has been skipped!',
                                  delete_after=10)
                elif topCard.type == 'reverse':
                    self.players.reverse()
                    self.currentPlayerIndex = self.players.index(self.players[self.currentPlayerIndex])
                    self.announce(f'The order of play has been reversed!', delete_after=10)
                    self.currentPlayerIndex += 1
                    if self.currentPlayerIndex >= len(self.players):
                        self.currentPlayerIndex -= len(self.players)
                elif topCard.type == '+2':
                    self.force_pickup += 2
                else:
                    self.timer = 60
                # check if the player has to pick up cards
                if self.force_pickup > 0:
                    print(f"Giving {self.force_pickup} cards to {self.players[self.currentPlayerIndex].name}")
                    for i in range(self.force_pickup):
                        self.players[self.currentPlayerIndex].hand.append(self.deck.pop())
                    self.force_pickup = 0
            for player in self.players:
                if len(player.hand) == 0 or player.score >= 500:
                    self.status = 'ended'
                    self.players.sort(key=lambda x: x.score, reverse=True)
                    self.winner = self.players[0]
                    print("Game ended")
                    self.announce(f'{self.winner.name} has won the game!\nThanks for playing!', delete_after=10)
                    self.update_gameMsg.stop()
                    self.cleanup()
                    return True
            return True
        else:
            return False

    def draw(self, player):
        if self.status == 'started':
            print(len(self.deck))
            if len(self.deck) <= 0:
                # reshuffle the discard pile into the deck, except for the top card
                topCard = self.discard[-1]
                self.deck = self.discard
                self.deck.shuffle()
                self.discard = CardCollection()
                self.discard.append(topCard)
                self.announce("The deck has been reshuffled!", delete_after=10)
            player.hand.append(self.deck.pop())
            return True
        else:
            return False

    async def createGameEmbedMessage(self, player) -> tuple[discord.Embed, discord.ui.View]:
        # Create an embed to display the game state to the player including their hand using discord emojis
        async def callback(interaction: discord.Interaction):
            await interaction.response.defer()
            player_to_play = json.loads(interaction.data['custom_id'])['data']['player']
            card_to_play = json.loads(interaction.data['custom_id'])['data']['card']['index']
            # Get more info about the player and card
            for player in self.players:
                if player.id == player_to_play:
                    player_to_play = player
                    break
            if self.canPlay(player_to_play.hand[card_to_play]):
                self.play(player_to_play, player_to_play.hand[card_to_play])
                await self.tick(json.loads(interaction.data['custom_id']))
                for player in self.players:
                    embed, view = await self.createGameEmbedMessage(player)
                    if player == player_to_play:
                        await interaction.edit_original_response(embed=embed, view=view)
                    else:
                        await player.send(embed=embed, view=view)
            else:

                await interaction.followup.send("You can't play this card!", delete_after=5)

        async def notYourTurn(interaction: discord.Interaction):
            await interaction.response.send_message("It's not your turn!", delete_after=5)
            return True

        async def drawcallback(interaction: discord.Interaction):
            await interaction.response.defer()
            player_to_play = json.loads(interaction.data['custom_id'])['data']['player']
            for player in self.players:
                if player.id == player_to_play:
                    player_to_play = player
                    break
            self.draw(player_to_play)
            await self.tick(json.loads(interaction.data['custom_id']))
            for player in self.players:
                embed, view = await self.createGameEmbedMessage(player)
                if player == player_to_play:
                    await interaction.edit_original_response(embed=embed, view=view)
                else:
                    await player.send(embed=embed, view=view)

        embed = discord.Embed(title=f'Uno!', description=f'Game stats:')
        embed.add_field(name='Players',
                        value=', '.join([f'{player.name} ({len(player.hand)})' if player != self.players[
                            self.currentPlayerIndex] else f'**{player.name} ({len(player.hand)})**' for player in
                                         self.players]))
        embed.add_field(name='Draw pile', value=f'{len(self.deck)} cards left')
        embed.add_field(name='Discard pile', value=f'{len(self.discard)} cards')
        # if the top card is a wild card, display the overriden color
        if self.discard[-1].overridenColor is None:
            embed.add_field(name='Top card', value=f"{self.convertCardtoName(self.discard[-1])} "
                                                   f"({str(self.discard[-1].color).title()} "
                                                   f"{str(self.discard[-1].type).title()})")
        else:
            embed.add_field(name='Top card', value=f"{self.convertCardtoName(self.discard[-1])} "
                                                   f"({str(self.discard[-1].overridenColor).title()} "
                                                   f"{str(self.discard[-1].type).title()})")
        view = discord.ui.View()
        # if it's the current player's turn, add a button to draw a card
        if player == self.players[self.currentPlayerIndex]:
            for i, card in enumerate(player.hand):
                if self.canPlay(card):
                    button = discord.ui.Button(emoji=self.convertCardtoName(card),
                                               label=f"{card.color} {card.type}".title(),
                                               custom_id=json.dumps({'type': 'play_card', 'data': {
                                                   'card': {'index': i},
                                                   'player': player.id}}), style=discord.ButtonStyle.green)
                else:
                    button = discord.ui.Button(emoji=self.convertCardtoName(card),
                                               label=f"{card.color} {card.type}".title(),
                                               custom_id=json.dumps({'type': 'play_card', 'data': {
                                                   'card': {'index': i},
                                                   'player': player.id}}), style=discord.ButtonStyle.red,
                                               disabled=True)
                button.callback = callback
                view.add_item(button)
            button = discord.ui.Button(emoji='🃏', label='Draw a card', custom_id=json.dumps({'type': 'draw_card',
                                                                                             'data': {
                                                                                                 'player': player.id}}),
                                       style=discord.ButtonStyle.blurple)
            button.callback = drawcallback
            view.add_item(button)
        else:
            for i, card in enumerate(player.hand):
                button = discord.ui.Button(emoji=self.convertCardtoName(card),
                                           label=f"{card.color} {card.type}".title(),
                                           custom_id=json.dumps({'type': 'play_card', 'data': {
                                               'card': {'index': i},
                                               'player': player.id}}), style=discord.ButtonStyle.gray, disabled=True)
                button.callback = notYourTurn
                view.add_item(button)
            button = discord.ui.Button(emoji='🃏', label='Draw a card', custom_id=json.dumps({'type': 'draw_card',
                                                                                             'data': {
                                                                                                 'player': player.id}}),
                                       style=discord.ButtonStyle.gray, disabled=True)
            button.callback = notYourTurn
            view.add_item(button)
        return embed, view

    def convertCardtoName(self, card):
        map = {"black wild": "<:blackwild:1144942824836571167>",
               "black wild+4": "<:blackplusfour:1144942822248685679>",
               "red 0": "<:red0:1144943495610650715>",
               "red 1": "<:red1:1144943497338699788>",
               "red 2": "<:red2:1144943499167412264>",
               "red 3": "<:red3:1144943501444915201>",
               "red 4": "<:red4:1144943503042957334>",
               "red 5": "<:red5:1144943505622450206>",
               "red 6": "<:red6:1151938864429154455>",
               "red 7": "<:red7:1144942889105899540>",
               "red 8": "<:red8:1144943508340359199>",
               "red 9": "<:red9:1144942892163551232>",
               "red skip": "<:redskip:1144943512270405662>",
               "red reverse": "<:redswap:1144943515063824424>",
               "red +2": "<:redplustwo:1151938865720983558>",
               "yellow 0": "<:yellow0:1151938869118373908>",
               "yellow 1": "<:yellow1:1151938871702081607>",
               "yellow 2": "<:yellow2:1144957924163198997>",
               "yellow 3": "<:yellow3:1144957927766097960>",
               "yellow 4": "<:yellow4:1144957928642719825>",
               "yellow 5": "<:yellow5:1144957930907639868>",
               "yellow 6": "<:yellow6:1144957932195299439>",
               "yellow 7": "<:yellow7:1144957934212755527>",
               "yellow 8": "<:yellow8:1144957936607703161>",
               "yellow 9": "<:yellow9:1144957938478370846>",
               "yellow skip": "<:yellowskip:1144957942379065364> ",
               "yellow reverse": "<:yellowswap:1144957943738020013>",
               "yellow +2": "<:yellowplustwo:1144957941099794452>",
               "green 0": "<:green0:1144943483531046932>",
               "green 1": "<:green1:1144942854267994122>",
               "green 2": "<:green2:1144943484801912862>",
               "green 3": "<:green3:1144942857875095592>",
               "green 4": "<:green4:1144943487410765855>",
               "green 5": "<:green5:1144942862786637884>",
               "green 6": "<:green6:1144942865429045328>",
               "green 7": "<:green7:1144943488992034866>",
               "green 8": "<:green8:1144942868331495445>",
               "green 9": "<:green9:1144943490355179602>",
               "green skip": "<:greenskip:1144943493534449684>",
               "green reverse": "<:greenswap:1144942876418113546>",
               "green +2": "<:greenplustwo:1144942871779221554>",
               "blue 0": "<:blue0:1144942826396852266>",
               "blue 1": "<:blue1:1144942827965526037>",
               "blue 2": "<:blue2:1144942830641500180>",
               "blue 3": "<:blue3:1144942832344383508>",
               "blue 4": "<:blue4:1144942835691425903>",
               "blue 5": "<:blue5:1144942837134270574>",
               "blue 6": "<:blue6:1144942839436955761>",
               "blue 7": "<:blue7:1144942841160798248>",
               "blue 8": "<:blue8:1144942843564134481>",
               "blue 9": "<:blue9:1144942844881154098>",
               "blue skip": "<:blueskip:1144942849322909718>",
               "blue reverse": "<:blueswap:1144942851550097478>",
               "blue +2": "<:blueplustwo:1144943480393711677>"}
        try:
            return map[f'{card.color} {card.type}']
        except KeyError:
            print(f'KeyError: {card.color} {card.type}')
            self.logger.error(f'KeyError: {card.color} {card.type}')
            return None

    def cleanup(self):
        """Cleanup the game after it has ended"""
        self.status = 'ended'
        self.players = []
        self.deck = CardCollection()
        self.discard = CardCollection()
        self.currentPlayerIndex = -1
        self.hasSkipped = False
        self.force_pickup = 0
        self.timer = 60
        self.update_gameMsg.stop()

import sqlite3
import os
import time
from endstone.plugin import Plugin
from endstone.event import event_handler, PlayerJoinEvent, PlayerDeathEvent, PlayerQuitEvent, BlockBreakEvent, BlockPlaceEvent
from endstone.command import Command, CommandSender
from endstone import ColorFormat, Player

class PlayerInfo(Plugin):
    api_version = "0.5"

    commands = {
        "playerinfo": {
            "description": "Shows basic player information.",
            "usages": ["/playerinfo [player: player]"],
        }
    }

    def __init__(self):
        super().__init__()
        self.db_file = None
        self.connection = None
        self.cursor = None
        self.last_update = {}

    def on_enable(self) -> None:
        self.logger.info("Enabled PlayerInfo plugin!")
        self.db_file = os.path.join(self.data_folder, "player_data.db")
        self.setup_database()
        self.register_events(self)

    def on_disable(self) -> None:
        self.logger.info("Disabled PlayerInfo plugin!")
        self._save_all_play_times()
        if self.connection:
            self.connection.close()

    def setup_database(self):
        os.makedirs(self.data_folder, exist_ok=True)
        self.connection = sqlite3.connect(self.db_file)
        self.cursor = self.connection.cursor()
        self.cursor.execute(""" 
            CREATE TABLE IF NOT EXISTS player_stats (
                name TEXT PRIMARY KEY,
                device TEXT,
                play_time INTEGER,
                deaths INTEGER,
                blocks_placed INTEGER,
                blocks_broken INTEGER
            )
        """)
        self.connection.commit()

    def get_player_data(self, player_name: str) -> dict:
        self.cursor.execute("SELECT * FROM player_stats WHERE name = ?", (player_name,))
        row = self.cursor.fetchone()
        if row:
            return {
                "name": row[0],
                "device": row[1],
                "play_time": row[2],
                "deaths": row[3],
                "blocks_placed": row[4],
                "blocks_broken": row[5]
            }
        return None

    def update_player_data(self, player_name: str, data: dict):
        self.cursor.execute(""" 
            INSERT OR REPLACE INTO player_stats (name, device, play_time, deaths, blocks_placed, blocks_broken)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            player_name,
            data.get("device", ""),
            data.get("play_time", 0),
            data.get("deaths", 0),
            data.get("blocks_placed", 0),
            data.get("blocks_broken", 0)
        ))
        self.connection.commit()

    def format_time(self, milliseconds: int) -> str:
        total_seconds = milliseconds // 1000
        days = total_seconds // 86400
        hours = (total_seconds % 86400) // 3600
        minutes = (total_seconds % 3600) // 60
        secs = total_seconds % 60
        return f"{days} days, {hours} hours, {minutes} mins, {secs} secs"

    def _save_all_play_times(self):
        current_time = int(time.time() * 1000)
        for player in self.server.online_players:
            if player.name in self.last_update:
                elapsed = current_time - self.last_update[player.name]
                data = self.get_player_data(player.name)
                if data:
                    data["play_time"] += elapsed
                    self.update_player_data(player.name, data)
        self.last_update.clear()

    def update_play_time(self, player_name: str):
        current_time = int(time.time() * 1000)
        if player_name in self.last_update:
            elapsed = current_time - self.last_update[player_name]
            data = self.get_player_data(player_name)
            if data:
                data["play_time"] += elapsed
                self.update_player_data(player_name, data)
        self.last_update[player_name] = current_time

    @event_handler
    def on_player_join(self, event: PlayerJoinEvent):
        player = event.player
        data = self.get_player_data(player.name)
        if not data:
            data = {
                "name": player.name,
                "device": player.device_os,
                "play_time": 0,
                "deaths": 0,
                "blocks_placed": 0,
                "blocks_broken": 0
            }
            self.update_player_data(player.name, data)
        self.last_update[player.name] = int(time.time() * 1000)

    @event_handler
    def on_player_death(self, event: PlayerDeathEvent):
        player = event.player
        self.update_play_time(player.name)

        data = self.get_player_data(player.name)
        if data:
            data["deaths"] += 1
            self.update_player_data(player.name, data)

    @event_handler
    def on_block_place(self, event: BlockPlaceEvent):
        player = event.player
        self.update_play_time(player.name)
        data = self.get_player_data(player.name)
        if data:
            data["blocks_placed"] += 1
            self.update_player_data(player.name, data)

    @event_handler
    def on_block_break(self, event: BlockBreakEvent):
        player = event.player
        self.update_play_time(player.name)
        data = self.get_player_data(player.name)
        if data:
            data["blocks_broken"] += 1
            self.update_player_data(player.name, data)

    @event_handler
    def on_player_quit(self, event: PlayerQuitEvent):
        player = event.player
        if player.name in self.last_update:
            self.update_play_time(player.name)
            del self.last_update[player.name]

    def on_command(self, sender: CommandSender, command: Command, args: list[str]) -> bool:
        if command.name == "playerinfo":
            if not isinstance(sender, Player):
                sender.send_error_message("This command can only be executed by a player")
                return False
            player_name = sender.name if len(args) == 0 else args[0]

            if player_name in self.last_update:
                self.update_play_time(player_name)

            data = self.get_player_data(player_name)
            if data:
                play_time_formatted = self.format_time(data["play_time"])
                sender.send_message(
                    f"{ColorFormat.AQUA}--- Player Info: {ColorFormat.DARK_AQUA}{data['name']} ---\n\n"
                    f"{ColorFormat.WHITE}Name: {ColorFormat.MATERIAL_AMETHYST}{data['name']}\n"
                    f"{ColorFormat.WHITE}Device: {ColorFormat.MATERIAL_AMETHYST}{data['device']}\n"
                    f"{ColorFormat.WHITE}Play Time: {ColorFormat.MATERIAL_AMETHYST}{play_time_formatted}\n"
                    f"{ColorFormat.WHITE}Deaths: {ColorFormat.MATERIAL_AMETHYST}{data['deaths']}\n"
                    f"{ColorFormat.WHITE}Blocks Placed: {ColorFormat.MATERIAL_AMETHYST}{data['blocks_placed']}\n"
                    f"{ColorFormat.WHITE}Blocks Broken: {ColorFormat.MATERIAL_AMETHYST}{data['blocks_broken']}\n"
                    f"{ColorFormat.WHITE}Ping: {ColorFormat.MATERIAL_AMETHYST}{sender.ping} ms"
                )
            else:
                sender.send_message(ColorFormat.RED + f"Player {player_name} not found.")

        return True

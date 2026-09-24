import random
import re
import threading
from collections import Counter

import supybot.callbacks as callbacks
import supybot.conf as conf
import supybot.ircmsgs as ircmsgs

from supybot.commands import wrap


class Shuffle(callbacks.Plugin):
    """A multiplayer Dutch longest-word game."""

    def __init__(self, irc):
        super().__init__(irc)

        self._words = set()
        self._words_by_length = {}
        self._load_words()

        self._lock = threading.Lock()
        self._round = None
        self._timer = None

    def _load_words(self):
        path = (
            conf.supybot.directories.plugins()
            + "/Shuffle/data/wordlist.txt"
        )

        with open(path, encoding="utf-8") as f:
            for line in f:
                word = line.strip().lower()

                if not re.fullmatch(r"[a-zà-ÿ]+", word):
                    continue

                if len(word) < 3:
                    continue

                self._words.add(word)
                self._words_by_length.setdefault(len(word), []).append(word)

    def _valid_word(self, word, letters):
        word = word.lower()

        if word not in self._words:
            return False

        return not (Counter(word) - Counter(letters))

    def _send(self, irc, channel, text):
        irc.queueMsg(ircmsgs.privmsg(channel, text))

    def _finish_round(self, irc):
        with self._lock:
            if self._round is None:
                return

            channel = self._round["channel"]
            attempts = self._round["attempts"]
            letters = self._round["letters"]

            self._round = None
            self._timer = None

        if not attempts:
            self._send(
                irc,
                channel,
                "⏰ Tijd! Niemand heeft een geldig woord gevonden."
            )
            return

        best_length = max(len(word) for word in attempts.values())

        winners = [
            (nick, word)
            for nick, word in attempts.items()
            if len(word) == best_length
        ]

        if len(winners) == 1:
            nick, word = winners[0]
            self._send(
                irc,
                channel,
                f"⏰ Tijd! 🏆 {nick} wint met {word.upper()} "
                f"({len(word)} letters)!"
            )
        else:
            results = ", ".join(
                f"{nick}: {word.upper()}"
                for nick, word in winners
            )
            self._send(
                irc,
                channel,
                f"⏰ Tijd! 🏆 Gelijkspel met {best_length} letters: "
                f"{results}"
            )

    def _start_timer(self, irc, seconds):
        self._timer = threading.Timer(
            seconds,
            self._finish_round,
            args=(irc,)
        )
        self._timer.daemon = True
        self._timer.start()

    def shuffle(self, irc, msg, args):
        """[status|stop]

        Start a new Shuffle round, show its status, or stop it.
        """

        channel = msg.channel

        if not channel:
            irc.error(
                "Dit commando kan alleen in een kanaal gebruikt worden."
            )
            return

        action = args[0].lower() if args else None

        if action == "status":
            self._status(irc, channel)
            return

        if action == "stop":
            self._stop(irc, channel)
            return

        if action is not None:
            irc.error("Gebruik: @shuffle [status|stop]")
            return

        with self._lock:
            if self._round is not None:
                irc.reply("Er loopt al een Shuffle-ronde.")
                return

            letter_count = self.registryValue("letterCount")
            candidates = self._words_by_length.get(letter_count, [])

            if not candidates:
                irc.error(
                    f"Geen woorden gevonden met {letter_count} letters."
                )
                return

            answer = random.choice(candidates)
            letters = list(answer)
            random.shuffle(letters)

            round_time = self.registryValue("roundTime")

            self._round = {
                "channel": channel,
                "letters": letters,
                "attempts": {},
                "answer": answer,
            }

            self._start_timer(irc, round_time)

        irc.reply(
            f"🔤 Letters: {' '.join(x.upper() for x in letters)}\n"
            f"⏱️ {round_time} seconden! Zoek het langste woord."
        )

    shuffle = wrap(shuffle)

    def _status(self, irc, channel):
        with self._lock:
            round_data = self._round

            if (
                round_data is None
                or round_data["channel"] != channel
            ):
                irc.reply("Er loopt momenteel geen Shuffle-ronde.")
                return

            attempts = dict(round_data["attempts"])
            letters = list(round_data["letters"])

        if not attempts:
            irc.reply(
                f"🔤 Letters: {' '.join(x.upper() for x in letters)}. "
                "Nog geen geldige pogingen."
            )
            return

        best_length = max(len(word) for word in attempts.values())

        best = [
            f"{nick}: {word.upper()}"
            for nick, word in attempts.items()
            if len(word) == best_length
        ]

        irc.reply(
            f"🔤 Beste score: {best_length} letters - "
            + ", ".join(best)
        )

    def _stop(self, irc, channel):
        with self._lock:
            if (
                self._round is None
                or self._round["channel"] != channel
            ):
                irc.reply("Er loopt momenteel geen Shuffle-ronde.")
                return

            if self._timer is not None:
                self._timer.cancel()
                self._timer = None

            attempts = self._round["attempts"]
            self._round = None

        if not attempts:
            irc.reply(
                "🛑 Shuffle gestopt. Niemand had een geldig woord."
            )
            return

        best_length = max(len(word) for word in attempts.values())

        winners = [
            (nick, word)
            for nick, word in attempts.items()
            if len(word) == best_length
        ]

        if len(winners) == 1:
            nick, word = winners[0]
            irc.reply(
                f"🛑 Shuffle gestopt. 🏆 {nick} wint met "
                f"{word.upper()} ({len(word)} letters)!"
            )
        else:
            results = ", ".join(
                f"{nick}: {word.upper()}"
                for nick, word in winners
            )
            irc.reply(
                f"🛑 Shuffle gestopt. Gelijkspel: {results}"
            )

    def doPrivmsg(self, irc, msg):
        if not msg.args or not msg.channel:
            return

        channel = msg.channel

        with self._lock:
            round_data = self._round

            if (
                round_data is None
                or round_data["channel"] != channel
            ):
                return

            letters = list(round_data["letters"])

        text = msg.args[1].strip().lower()

        if not re.fullmatch(r"[a-zà-ÿ]+", text):
            return

        if not self._valid_word(text, letters):
            return

        nick = msg.nick

        with self._lock:
            current = self._round

            if (
                current is None
                or current["channel"] != channel
            ):
                return

            previous = current["attempts"].get(nick)

            if previous is None or len(text) > len(previous):
                current["attempts"][nick] = text

                self._send(
                    irc,
                    channel,
                    f"✅ {nick}: {text.upper()} ({len(text)})"
                )


Class = Shuffle
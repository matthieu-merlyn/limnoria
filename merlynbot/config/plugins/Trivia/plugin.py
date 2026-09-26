###

# Copyright (c) 2010, quantumlemur
#
# Copyright (c) 2011, Valentin Lorentz
#
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
#   * Redistributions of source code must retain the above copyright notice,
#     this list of conditions, and the following disclaimer.
#
#   * Redistributions in binary form must reproduce the above copyright notice,
#     this list of conditions, and the following disclaimer in the
#     documentation and/or other materials provided with the distribution.
#   * Neither the name of the author nor the names of its contributors may
#     be used to endorse or promote products derived from this software without
#     specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.

###

import re
import os
import time
import math
import string
import random

import supybot.utils as utils
import supybot.ircdb as ircdb
from supybot.commands import *
import supybot.plugins as plugins
import supybot.ircmsgs as ircmsgs
import supybot.ircutils as ircutils
import supybot.schedule as schedule
import supybot.callbacks as callbacks
from supybot.i18n import PluginInternationalization, internationalizeDocstring

_ = PluginInternationalization('Trivia')


class Trivia(callbacks.Plugin):

    """Add the help for "@plugin help Trivia" here

    This should describe *how* to use this plugin."""

    threaded = True

    def __init__(self, irc):
        self.__parent = super(Trivia, self)
        self.__parent.__init__(irc)
        self.games = {}

        # Persistent all-time scores disabled for now.
        # self.scores = {}
        # self.scorefile = self.registryValue('scoreFile')
        # if not os.path.exists(self.scorefile):
        #     f = open(self.scorefile, 'w')
        #     f.close()
        # f = open(self.scorefile, 'r')
        # line = f.readline()
        # while line:
        #     (name, score) = line.split(' ')
        #     self.scores[name] = int(score.strip('\r\n'))
        #     line = f.readline()
        # f.close()

    def doPrivmsg(self, irc, msg):
        channel = ircutils.toLower(msg.args[0])

        if not irc.isChannel(channel):
            return

        if callbacks.addressed(irc.nick, msg):
            return

        if channel in self.games:
            self.games[channel].answer(msg)

    class Game:

        def __init__(self, irc, channel, num, plugin, language):
            self.rng = random.Random()
            self.rng.seed()
            self.registryValue = plugin.registryValue
            self.irc = irc
            self.channel = channel
            self.num = num
            self.numAsked = 0
            self.hints = 0
            self.hintusers = set()
            self.games = plugin.games

            # Persistent all-time scores disabled for now.
            # self.scores = plugin.scores
            # self.scorefile = plugin.scorefile

            self.language = language
            self.questionfile = os.path.join(
                os.path.dirname(self.registryValue('questionFile')),
                'questions_%s.txt' % language
            )

            self.total = num
            self.active = True
            self.questions = []
            self.roundscores = {}
            self.unanswered = 0

            f = open(self.questionfile, 'r', encoding='utf8')
            line = f.readline()

            while line:
                self.questions.append(line.strip('\n\r'))
                line = f.readline()

            f.close()

            if self.registryValue('randomize', channel):
                random.shuffle(self.questions)

            try:
                schedule.removeEvent('next_%s' % self.channel)
            except KeyError:
                pass

            self.newquestion()

        def newquestion(self):
            self.hintusers = set()

            inactiveShutoff = self.registryValue(
                'inactiveShutoff',
                self.channel
            )

            if self.num == 0:
                self.active = False

            elif self.unanswered > inactiveShutoff and inactiveShutoff >= 0:
                self.reply(_('Seems like no one\'s playing any more.'))
                self.active = False

            elif len(self.questions) == 0:
                self.reply(_('Oops!  I ran out of questions!'))
                self.active = False

            if not self.active:
                self.stop()
                return

            self.hints = 0
            self.num -= 1
            self.numAsked += 1

            q = self.questions.pop(len(self.questions) - 1)

            sep = self.registryValue('questionFileSeparator')

            self.q = q[:q.find(sep)]
            self.a = q[q.find(sep) + len(sep):].split(sep)

            color = self.registryValue('color', self.channel)

            self.reply(
                _('\x03%s#%d of %d: %s') %
                (color, self.numAsked, self.total, self.q)
            )

            def event():
                self.timedEvent()

            timeout = self.registryValue('timeout', self.channel)
            numHints = self.registryValue('numHints', self.channel)

            eventTime = time.time() + timeout / (numHints + 1)

            if self.active:
                schedule.addEvent(
                    event,
                    eventTime,
                    'next_%s' % self.channel
                )

        def stop(self):
            self.reply(_('Trivia stopping.'))
            self.active = False

            try:
                schedule.removeEvent('next_%s' % self.channel)
            except KeyError:
                pass

            scores = iter(self.roundscores.items())
            sorted = []

            for i in range(0, len(self.roundscores)):
                item = next(scores)
                sorted.append(item)

            def cmp(a, b):
                return b[1] - a[1]

            sorted.sort(key=lambda item: item[1], reverse=True)

            max = 3

            if len(sorted) < max:
                max = len(sorted)

            s = _('Top finishers: ')

            if max > 0:
                recipients = []
                maxp = sorted[0][1]

                for i in range(0, max):
                    item = sorted[i]
                    s = _('%s %s %s.') % (
                        s,
                        item[0],
                        item[1]
                    )

                self.reply(s)

            del self.games[self.channel]

        def timedEvent(self):
            if self.hints >= self.registryValue(
                'numHints',
                self.channel
            ):
                self.reply(
                    _('No one got the answer!  It was: %s') %
                    self.a[0]
                )

                self.unanswered += 1
                self.newquestion()

            else:
                self.hint()

        def hint(self):
            self.hints += 1

            ans = self.a[0]

            hintPercentage = self.registryValue(
                'hintPercentage',
                self.channel
            )

            divider = int(
                math.ceil(
                    len(ans) * hintPercentage * self.hints
                )
            )

            if divider == len(ans):
                divider -= 1

            show = ans[:divider]
            blank = ans[divider:]

            blankChar = self.registryValue(
                'blankChar',
                self.channel
            )

            blank = re.sub(r'\w', blankChar, blank)

            self.reply(_('HINT: %s%s') % (show, blank))

            def event():
                self.timedEvent()

            timeout = self.registryValue('timeout', self.channel)
            numHints = self.registryValue('numHints', self.channel)

            eventTime = time.time() + timeout / (numHints + 1)

            try:
                schedule.removeEvent('next_%s' % self.channel)
            except KeyError:
                pass

            if self.active:
                schedule.addEvent(
                    event,
                    eventTime,
                    'next_%s' % self.channel
                )

        def skip(self):
            self.reply(
                _("Question skipped. The answer was: %s") %
                self.a[0]
            )

            self.unanswered = 0

            try:
                schedule.removeEvent('next_%s' % self.channel)
            except KeyError:
                pass

            self.newquestion()

        def answer(self, msg):
            correct = False

            for ans in self.a:
                dist = self.DL(
                    ircutils.stripFormatting(
                        str.lower(msg.args[1])
                    ),
                    str.lower(ans)
                )

                flexibility = self.registryValue(
                    'flexibility',
                    self.channel
                )

                if dist <= len(ans) / flexibility:
                    correct = True

                # if self.registryValue('debug'):
                #     self.reply('Distance: %d' % dist)

            if correct:
                # Persistent all-time scoring disabled for now.
                # if not msg.nick in self.scores:
                #     self.scores[msg.nick] = 0
                # self.scores[msg.nick] += 1

                if msg.nick not in self.roundscores:
                    self.roundscores[msg.nick] = 0

                self.roundscores[msg.nick] += 1

                self.unanswered = 0

                self.reply(
                    _('%s got it!  The full answer was: %s. Points: %d') %
                    (
                        msg.nick,
                        self.a[0],
                        self.roundscores[msg.nick]
                    )
                )

                schedule.removeEvent(
                    'next_%s' % self.channel
                )

                # self.writeScores()

                self.newquestion()

        def reply(self, s):
            self.irc.queueMsg(
                ircmsgs.privmsg(self.channel, s)
            )

        def writeScores(self):
            f = open(self.scorefile, 'w')
            scores = iter(self.scores.items())

            for i in range(0, len(self.scores)):
                score = next(scores)
                f.write('%s %s\n' % (score[0], score[1]))

            f.close()

        def DL(self, seq1, seq2):
            oneago = None
            thisrow = list(range(1, len(seq2) + 1)) + [0]

            for x in range(len(seq1)):
                # Python lists wrap around for negative indices, so put the
                # leftmost column at the end of the list. This matches with
                # the zero-indexed strings and saves extra calculation.

                twoago, oneago, thisrow = (
                    oneago,
                    thisrow,
                    [0] * len(seq2) + [x + 1]
                )

                for y in range(len(seq2)):
                    delcost = oneago[y] + 1
                    addcost = thisrow[y - 1] + 1
                    subcost = oneago[y - 1] + (
                        seq1[x] != seq2[y]
                    )

                    thisrow[y] = min(
                        delcost,
                        addcost,
                        subcost
                    )

                    # This block deals with transpositions
                    if (
                        x > 0
                        and y > 0
                        and seq1[x] == seq2[y - 1]
                        and seq1[x - 1] == seq2[y]
                        and seq1[x] != seq2[y]
                    ):
                        thisrow[y] = min(
                            thisrow[y],
                            twoago[y - 2] + 1
                        )

            return thisrow[len(seq2) - 1]

    @internationalizeDocstring
    def start(self, irc, msg, args, channel, language, num):
        """[<channel>] [<language>] [<number of questions>]
        Starts a game of trivia. <channel> is only necessary if the message
        isn't sent in the channel itself. <language> can be 'en' or 'nl' and
        defaults to 'en'."""

        if language is None:
            language = 'en'
        else:
            language = language.lower()

        if language not in ('en', 'nl'):
            irc.error('Language must be "en" or "nl".')
            return

        if num == None:
            num = self.registryValue(
                'defaultRoundLength',
                channel
            )

        # elif num > 100:
        #     irc.reply('sorry, for now, you can\'t start games with more '
        #               'than 100 questions :(')
        #     num = 100

        channel = ircutils.toLower(channel)

        if channel in self.games:
            if not self.games[channel].active:
                del self.games[channel]

                try:
                    schedule.removeEvent('next_%s' % channel)
                except KeyError:
                    pass

                irc.reply(
                    _('Orphaned trivia game found and removed.')
                )

            else:
                self.games[channel].num += num
                self.games[channel].total += num

                irc.reply(
                    _('%d questions added to active game!') % num
                )

        else:
            self.games[channel] = self.Game(
                irc,
                channel,
                num,
                self,
                language
            )

        irc.noReply()

    start = wrap(
        start,
        [
            'channel',
            optional(('literal', ('en', 'nl'))),
            optional('positiveInt')
        ]
    )

    @internationalizeDocstring
    def hint(self, irc, msg, args, channel):
        """[<channel>]
        Invokes the next hint for the current question"""

        channel = ircutils.toLower(channel)

        if channel in self.games:
            game = self.games[channel]

            if msg.nick in game.hintusers:
                irc.reply(
                    _('You have already used your hint for this question.')
                )
                return

            game.hintusers.add(msg.nick)
            game.hint()

        else:
            irc.reply(
                _("Trivia is currently not active in this channel.")
            )

    hint = wrap(hint, ['channel'])

    @internationalizeDocstring
    def next(self, irc, msg, args, channel):
        """[<channel>]
        Moves onto the next question."""

        channel = ircutils.toLower(channel)

        if channel in self.games:
            self.games[channel].skip()

        else:
            irc.reply(
                _("Trivia is currently not active in this channel.")
            )

    next = wrap(next, ['channel'])

    @internationalizeDocstring
    def stop(self, irc, msg, args, channel):
        """[<channel>]
        Stops a running game of trivia. <channel> is only necessary if the
        message isn't sent in the channel itself."""

        channel = ircutils.toLower(channel)

        try:
            schedule.removeEvent('next_%s' % channel)
        except KeyError:
            irc.error(_('No trivia started'))

        if channel in self.games:
            if self.games[channel].active:
                self.games[channel].stop()

            else:
                del self.games[channel]
                irc.reply(_('Trivia stopped'))

        else:
            irc.noReply()

    stop = wrap(stop, ['channel'])


Class = Trivia


# vim:set shiftwidth=4 softtabstop=4 expandtab textwidth=79:
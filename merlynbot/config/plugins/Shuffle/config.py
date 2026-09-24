import supybot.conf as conf
import supybot.registry as registry


def configure(advanced):
    conf.registerPlugin('Shuffle', True)


Shuffle = conf.registerPlugin('Shuffle')


Shuffle.register(
    'roundTime',
    registry.PositiveInteger(
        60,
        _("Number of seconds each Shuffle round lasts.")
    )
)

Shuffle.register(
    'letterCount',
    registry.PositiveInteger(
        7,
        _("Number of letters in each Shuffle round.")
    )
)

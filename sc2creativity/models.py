import typing


class BuildEvent(typing.NamedTuple):
    target_name: str
    second: int


class ActionEvents(typing.NamedTuple):
    name: str
    all_event_times: typing.List[int]


class ActionRollup(typing.NamedTuple):
    name: str
    first_event_time: int
    event_weight: float


class ReplaySummary(typing.NamedTuple):
    self_race: str
    opponent_race: str
    actions: typing.List[ActionRollup]

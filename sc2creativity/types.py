import typing
import datetime


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


class ReplayPlayer(typing.NamedTuple):
    name: str
    race: str


class ReplaySummary(typing.NamedTuple):
    replay_id: str
    start_time: datetime.datetime
    real_duration_seconds: int

    self: ReplayPlayer
    opponent: ReplayPlayer

    actions: typing.List[ActionRollup]

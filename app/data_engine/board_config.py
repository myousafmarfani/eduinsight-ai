"""Extensible education-board configuration.

Boards do not share one grading system. Each board declares its grade bands, pass mark and
whether the percentage->grade mapping is fixed. Where a board's mapping is not a fixed public
table (e.g. Cambridge boundaries move every exam series), computed grades are flagged
*indicative* and a grade printed on the marksheet always takes precedence.

Add a board with `register_board(BoardConfig(...))`. The bands below should be checked against
the board's current notification before being relied upon.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class GradeBand:
    label: str
    min_percent: float


@dataclass(frozen=True)
class BoardConfig:
    key: str
    name: str
    country: str
    grade_bands: tuple[GradeBand, ...]  # sorted descending by min_percent
    pass_percentage: float
    fixed_scale: bool  # False => computed grades are only indicative
    notes: str = ""
    aliases: tuple[str, ...] = field(default_factory=tuple)


def _bands(*pairs: tuple[str, float]) -> tuple[GradeBand, ...]:
    return tuple(GradeBand(label, pct) for label, pct in sorted(pairs, key=lambda p: -p[1]))


_GENERIC_BANDS = _bands(("A", 80), ("B", 70), ("C", 60), ("D", 50), ("E", 40), ("F", 0))

_REGISTRY: dict[str, BoardConfig] = {}


def register_board(config: BoardConfig) -> None:
    """Register (or replace) a board configuration."""
    _REGISTRY[config.key.upper()] = config


register_board(BoardConfig(
    key="AKU-EB", name="AKU-EB (Aga Khan University Examination Board)", country="Pakistan",
    grade_bands=_bands(("A1", 90), ("A", 80), ("B", 70), ("C", 60), ("D", 50), ("E", 40), ("U", 0)),
    pass_percentage=40.0, fixed_scale=False,
    notes="Indicative bands. AKU-EB grade boundaries should be taken from the marksheet; enter the printed grade when you have it.",
    aliases=("AKUEB", "AKU EB"),
))
register_board(BoardConfig(
    key="CAMBRIDGE", name="Cambridge (IGCSE / O Level / A Level)", country="International",
    grade_bands=_bands(("A*", 90), ("A", 80), ("B", 70), ("C", 60), ("D", 50), ("E", 40), ("U", 0)),
    pass_percentage=40.0, fixed_scale=False,
    notes="Cambridge grade boundaries change every exam series and are set per component, so percentage-based grades are indicative only.",
    aliases=("CIE", "CAIE", "IGCSE", "O LEVEL", "A LEVEL"),
))
register_board(BoardConfig(
    key="FBISE", name="FBISE (Federal Board)", country="Pakistan",
    grade_bands=_bands(("A1", 90), ("A", 80), ("B", 70), ("C", 60), ("D", 50), ("E", 40), ("F", 0)),
    pass_percentage=33.0, fixed_scale=True,
    notes="Verify bands against the current FBISE notification.",
))
register_board(BoardConfig(
    key="PUNJAB", name="Punjab Board (BISE)", country="Pakistan",
    grade_bands=_bands(("A1", 80), ("A", 70), ("B", 60), ("C", 50), ("D", 40), ("E", 33), ("F", 0)),
    pass_percentage=33.0, fixed_scale=True,
    notes="Verify bands against your specific BISE's notification.",
    aliases=("PUNJAB BOARD", "BISE PUNJAB"),
))
register_board(BoardConfig(
    key="SINDH", name="Sindh Board (BSEK / BIEK / others)", country="Pakistan",
    grade_bands=_bands(("A1", 80), ("A", 70), ("B", 60), ("C", 50), ("D", 40), ("E", 33), ("F", 0)),
    pass_percentage=33.0, fixed_scale=True,
    notes="Verify bands against your specific Sindh board's notification.",
    aliases=("SINDH BOARD", "BSEK", "BIEK"),
))
register_board(BoardConfig(
    key="OTHER", name="Other board", country="Any",
    grade_bands=_GENERIC_BANDS, pass_percentage=40.0, fixed_scale=False,
    notes="Generic indicative bands. Enter your marksheet's printed grades for accuracy.",
))


def list_boards() -> list[BoardConfig]:
    """All registered boards (OTHER last)."""
    boards = sorted(_REGISTRY.values(), key=lambda b: (b.key == "OTHER", b.key))
    return boards


def get_board(board: str | None) -> BoardConfig:
    """Resolve a board by key, display name or alias; unknown boards map to OTHER."""
    if not board:
        return _REGISTRY["OTHER"]
    needle = board.strip().upper()
    if needle in _REGISTRY:
        return _REGISTRY[needle]
    for cfg in _REGISTRY.values():
        if needle == cfg.name.upper() or needle in (a.upper() for a in cfg.aliases):
            return cfg
    return _REGISTRY["OTHER"]


def grade_for_percentage(percentage: float, board: str | None) -> tuple[str, bool]:
    """Return (grade label, is_indicative) for a percentage under the board's bands."""
    cfg = get_board(board)
    for band in cfg.grade_bands:
        if percentage >= band.min_percent:
            return band.label, not cfg.fixed_scale
    return cfg.grade_bands[-1].label, not cfg.fixed_scale

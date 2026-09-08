"""Shared plumbing for the XML-based formats, TCX and GPX.

Both are edited as an lxml tree so that everything the tool does not understand
survives a load/save round trip. Elements are matched on their local name, which
keeps the code independent of the namespace prefixes a device happens to use.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable, Iterator, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime

from lxml import etree

from training_log_change.base import ActivityFormatError, TrackModifier

_TIMESTAMP = re.compile(
    r"^(?P<naive>\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2})"
    r"(?P<fraction>\.\d+)?"
    r"(?P<zone>Z|[+-]\d{2}:?\d{2})?$"
)


@dataclass(frozen=True)
class TimestampStyle:
    """How a timestamp was spelled in the file, so it can be written back the same.

    Devices are inconsistent -- Garmin writes ``...T10:00:00.000Z`` in TCX and
    ``...T10:00:00Z`` in GPX, and some exports carry a numeric offset instead of
    ``Z``. Keeping the original spelling per element means editing a file changes
    only the values that were asked for.
    """

    fractional: bool
    zone: str


def parse_timestamp(text: str | None) -> tuple[datetime, TimestampStyle] | None:
    """Parse an ISO 8601 timestamp, or return None if the text is not one.

    A timestamp without a zone is read as UTC so that arithmetic never mixes
    naive and aware datetimes; the missing zone is remembered in the style and
    the value is written back without one.
    """
    if text is None:
        return None
    match = _TIMESTAMP.match(text.strip())
    if match is None:
        return None
    zone = match["zone"] or ""
    moment = datetime.fromisoformat(
        f"{match['naive']}{match['fraction'] or ''}"
        f"{'+00:00' if zone in ('', 'Z') else zone}"
    )
    return moment, TimestampStyle(fractional=match["fraction"] is not None, zone=zone)


def format_timestamp(moment: datetime, style: TimestampStyle) -> str:
    """Render ``moment`` the way the file spelled timestamps of this element."""
    text = moment.strftime("%Y-%m-%dT%H:%M:%S")
    if style.fractional:
        text += f".{moment.microsecond // 1000:03d}"
    return text + style.zone


def format_number(value: float) -> str:
    """Render a number without the noise of binary floating point.

    ``5.5 * 1.1`` is ``6.050000000000001``; seven decimals is far beyond the
    precision any of these fields carries, and trailing zeros are dropped so
    whole numbers stay whole.
    """
    text = f"{value:.7f}".rstrip("0").rstrip(".")
    return text if text not in ("", "-0") else "0"


def parse_number(text: str | None) -> float | None:
    """Parse an element's numeric text, or return None if it is not a number."""
    if text is None:
        return None
    try:
        return float(text.strip())
    except ValueError:
        return None


def local_name(element: etree._Element) -> str:
    """The element's tag without its namespace."""
    tag = element.tag
    return tag.split("}")[-1] if isinstance(tag, str) else ""


@dataclass(frozen=True)
class TimeRef:
    """A place in the tree that holds a timestamp: element text or an attribute."""

    element: etree._Element
    attribute: str | None

    def read(self) -> str | None:
        if self.attribute is None:
            return self.element.text
        return self.element.get(self.attribute)

    def write(self, text: str) -> None:
        if self.attribute is None:
            self.element.text = text
        else:
            self.element.set(self.attribute, text)


class XmlTrackModifier(TrackModifier):
    """A :class:`TrackModifier` backed by an lxml tree."""

    #: Local names of elements whose text is a timestamp.
    TIME_ELEMENTS: frozenset[str] = frozenset()
    #: Local names of attributes that hold a timestamp.
    TIME_ATTRIBUTES: frozenset[str] = frozenset()
    #: Local name of the document element, used to reject the wrong format.
    ROOT_NAME = ""

    #: Entities declared inside the file are expanded; entities pointing outside
    #: it are not fetched, so an external one stays undefined and the file is
    #: rejected rather than absorbing whatever it targeted. This has been lxml's
    #: default since 5.0, which the dependency pin requires, and it is spelled
    #: out because both ways of getting it wrong are quiet. Resolving everything
    #: pulls the target of a `SYSTEM` entity straight into the output. Resolving
    #: nothing reads a value written as a reference as no value at all, so the
    #: sample is skipped while the lap summary above it is still repaired, and
    #: the file is left contradicting itself.
    PARSER = etree.XMLParser(
        # lxml-stubs still types resolve_entities as a bool, three years after
        # lxml 5.0 made "internal" the accepted value and the default.
        resolve_entities="internal",  # type: ignore[arg-type]
        no_network=True,
    )

    def __init__(self, file_path: str) -> None:
        try:
            self.tree = etree.parse(file_path, self.PARSER)
        except etree.XMLSyntaxError as exc:
            raise ActivityFormatError(
                f"{file_path} is not well-formed XML: {exc}"
            ) from exc
        self.root = self.tree.getroot()
        if local_name(self.root) != self.ROOT_NAME:
            raise ActivityFormatError(
                f"{file_path} has root element <{local_name(self.root)}>, "
                f"expected <{self.ROOT_NAME}>"
            )

    def save(self, file_path: str) -> None:
        self.tree.write(
            file_path,
            pretty_print=True,
            xml_declaration=True,
            encoding="UTF-8",
        )

    # -- timestamps ---------------------------------------------------------

    def _time_refs(self) -> Iterator[TimeRef]:
        for element in self.root.iter():
            if not isinstance(element.tag, str):
                continue
            if local_name(element) in self.TIME_ELEMENTS:
                yield TimeRef(element, None)
            for attribute in self.TIME_ATTRIBUTES:
                if element.get(attribute) is not None:
                    yield TimeRef(element, attribute)

    def start_time(self) -> datetime:
        """The earliest timestamp in the file."""
        moments = [
            parsed[0]
            for ref in self._time_refs()
            if (parsed := parse_timestamp(ref.read()))
        ]
        if not moments:
            raise ActivityFormatError("activity contains no timestamps")
        return min(moments)

    def _shift_times(self, transform: Callable[[datetime], datetime]) -> None:
        for ref in self._time_refs():
            parsed = parse_timestamp(ref.read())
            if parsed is None:
                continue
            moment, style = parsed
            shifted = transform(moment).astimezone(moment.tzinfo or UTC)
            ref.write(format_timestamp(shifted, style))

    def update_start_time(self, start_time: datetime) -> None:
        if start_time.tzinfo is None:
            start_time = start_time.replace(tzinfo=UTC)
        offset = start_time - self.start_time()
        self._shift_times(lambda moment: moment + offset)

    def _compress_times(self, multiplier: float) -> None:
        """Pull every timestamp towards the start of the activity."""
        start = self.start_time()
        self._shift_times(lambda moment: start + (moment - start) / multiplier)

    # -- numbers ------------------------------------------------------------

    def _scale_numbers(self, factors: Mapping[str, float]) -> None:
        """Multiply the text of every element named in ``factors`` by its factor."""
        for element in self.root.iter():
            if not isinstance(element.tag, str):
                continue
            factor = factors.get(local_name(element))
            value = parse_number(element.text) if factor is not None else None
            if factor is not None and value is not None:
                element.text = format_number(value * factor)


def value_holder(element: etree._Element) -> etree._Element:
    """The element actually holding the number.

    TCX wraps heart rate as ``<HeartRateBpm><Value>150</Value></HeartRateBpm>``
    while cadence and power carry their number directly, so unwrapping a single
    ``Value`` child lets both shapes be handled by the same code.
    """
    for child in element:
        if isinstance(child.tag, str) and local_name(child) == "Value":
            return child
    return element


def find_leaves(
    scope: etree._Element, names: Iterable[str], *, skip: str = ""
) -> Iterator[etree._Element]:
    """Yield the number-holding elements under ``scope`` matching ``names``.

    Subtrees rooted at an element called ``skip`` are not descended into, which
    is how lap summaries are scanned without also hitting the track points that
    a separate pass already handled.
    """
    wanted = frozenset(names)
    for child in scope:
        if not isinstance(child.tag, str):
            continue
        name = local_name(child)
        if skip and name == skip:
            continue
        if name in wanted:
            yield value_holder(child)
        else:
            yield from find_leaves(child, wanted, skip=skip)

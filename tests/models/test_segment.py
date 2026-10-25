"""Tests for :class:`kompy.Segment`, :class:`kompy.SegmentInformation` and :class:`kompy.AnnotatedSegment`."""

from __future__ import annotations

import pytest

from kompy import AnnotatedSegment, Segment, SegmentInformation
from kompy.constants import SegmentType


@pytest.fixture
def boundaries() -> SegmentInformation:
    return SegmentInformation(start_index_point=0, end_index_point=10)


def test_segment_with_valid_inputs(boundaries: SegmentInformation) -> None:
    segment = Segment(segment_type=SegmentType.MANUAL, segment_boundaries=boundaries, reference='reference123')

    assert segment.segment_type == SegmentType.MANUAL
    assert segment.segment_boundaries == boundaries
    assert segment.reference == 'reference123'


def test_segment_reference_is_optional(boundaries: SegmentInformation) -> None:
    assert Segment('Routed', boundaries).reference is None


def test_plain_string_type_becomes_enum_member(boundaries: SegmentInformation) -> None:
    segment = Segment('Routed', boundaries)

    assert segment.segment_type is SegmentType.ROUTED


def test_unknown_segment_type_is_kept_as_plain_string(boundaries: SegmentInformation) -> None:
    segment = Segment(segment_type='Imported', segment_boundaries=boundaries)

    assert segment.segment_type == 'Imported'


def test_segment_from_dict() -> None:
    segment = Segment.from_dict({'type': 'Routed', 'from': 0, 'to': 19, 'reference': 'hl:1'})

    assert segment == Segment(SegmentType.ROUTED, SegmentInformation(0, 19), 'hl:1')


@pytest.mark.parametrize('missing', ['type', 'from', 'to'])
def test_segment_from_dict_requires_keys(missing: str) -> None:
    payload = {'type': 'Routed', 'from': 0, 'to': 19}
    del payload[missing]

    with pytest.raises(KeyError):
        Segment.from_dict(payload)


def test_segment_information_from_dict() -> None:
    assert SegmentInformation.from_dict({'from': 691, 'to': 716}) == SegmentInformation(691, 716)


def test_annotated_segment_from_dict() -> None:
    segment = AnnotatedSegment.from_dict({'from': 0, 'to': 33, 'element': 'wt#way'})

    assert segment.element == 'wt#way'
    assert segment.segment_boundaries == SegmentInformation(0, 33)

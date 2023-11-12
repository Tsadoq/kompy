from typing import Optional

from kompy.constants import SegmentType


class SegmentInformation:

    def __init__(
        self,
        start_index_point: int,
        end_index_point: int,
    ):
        """
        Initialize the segment information.
        :param start_index_point: start index point
        :param end_index_point: end index point
        """
        self.start_index_point = start_index_point
        self.end_index_point = end_index_point


class Segment:
    def __init__(
        self,
        segment_type: str,
        segment_boundaries: SegmentInformation,
        reference: Optional[str] = None,
    ):
        """
        Initialize a segment.
        :param segment_type: Type of the segment.
        :param segment_boundaries: Boundaries of the segment as a SegmentInformation object.
        :param reference: Reference of the segment (optional).
        """
        if segment_type not in SegmentType.list_all():
            raise ValueError(f'Invalid segment type provided: {segment_type}. Please provide a valid segment type.')
        self.segment_type = segment_type
        self.segment_boundaries = segment_boundaries
        self.reference = reference

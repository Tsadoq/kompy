from typing import List, Optional


class SegmentInformation:
    def __init__(
        self,
        start_index_point: int,
        end_index_point: Optional[int] = None,
    ):
        """
        Initialize the segment information.
        :param start_index_point: Start index point of the segment.
        :param end_index_point: End index point of the segment (optional).
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


class SegmentType:
    ROUTED = 'Routed'
    MANUAL = 'Manual'

    @classmethod
    def list_all(cls) -> List[str]:
        """
        List all supported activities.
        :return: A list of all supported activities
        """
        return [
            getattr(cls, attr) for attr in dir(cls) if not attr.startswith('__') and not callable(getattr(cls, attr))
        ]

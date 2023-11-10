from typing import List, Optional

from pydantic import BaseModel, field_validator


class SegmentInformation(BaseModel):
    start_index_point: int
    end_index_point: Optional[int]


class Segment(BaseModel):
    segment_type: str
    reference: Optional[str]
    segment_boundaries: SegmentInformation

    @field_validator
    def check_segment_type(cls, segment_type):
        if segment_type not in SegmentType.list_all():
            raise ValueError(f'Invalid segment type provided: {segment_type}. Please provide a valid segment type.')


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

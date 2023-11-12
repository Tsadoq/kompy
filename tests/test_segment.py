import unittest

from kompy import (
    Segment,
    SegmentInformation,
)
from kompy.constants import SegmentType


class TestSegment(unittest.TestCase):

    def setUp(self):
        """
        Set up the Segment for the tests.
        """
        self.valid_segment_info = SegmentInformation(start_index_point=0, end_index_point=10)

    def test_initialization_with_valid_inputs(self):
        """
        Test initialization with valid inputs
        """
        segment = Segment(segment_type=SegmentType.MANUAL, segment_boundaries=self.valid_segment_info)
        self.assertIsInstance(segment, Segment)
        self.assertEqual(segment.segment_type, SegmentType.MANUAL)
        self.assertEqual(segment.segment_boundaries, self.valid_segment_info)

    def test_initialization_with_invalid_segment_type(self):
        """
        Test initialization with an invalid segment type
        """

        with self.assertRaises(ValueError):
            Segment(segment_type='invalid_segment_type', segment_boundaries=self.valid_segment_info)

    def test_segment_properties(self):
        """
        Test the properties of the Segment
        """
        segment = Segment(segment_type=SegmentType.MANUAL, segment_boundaries=self.valid_segment_info,
                          reference='reference123')
        self.assertEqual(segment.segment_type, SegmentType.MANUAL)
        self.assertEqual(segment.segment_boundaries, self.valid_segment_info)
        self.assertEqual(segment.reference, 'reference123')


if __name__ == '__main__':
    unittest.main()

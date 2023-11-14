import json
from unittest.mock import MagicMock

from requests import Response


def mock_response_builder(
    mock_get: MagicMock,
    mock_status_code: int,
    json_file_path: str,
) -> MagicMock:
    """
    Build a mock response for a given mock get object.
    :param mock_get: the mock get object
    :param mock_status_code: the status code to return
    :param json_file_path: the file containing the content of the response
    :return:
    """
    mock_response = Response()
    mock_response.status_code = mock_status_code,
    mock_response._content = json.dumps(
        json.loads(open(json_file_path).read())
    ).encode('utf-8')
    mock_get.return_value = mock_response
    return mock_get

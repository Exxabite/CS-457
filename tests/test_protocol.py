import struct
import unittest

from code.protocol import (
    FrameDecoder,
    MAX_FRAME_SIZE,
    ProtocolError,
    decode_message,
    encode_message,
)


class ProtocolTests(unittest.TestCase):
    def test_decodes_fragmented_and_coalesced_frames(self):
        first = encode_message("CONNECT", {})
        second = encode_message("STATE_CHANGE", {"row": 1, "column": 2})
        decoder = FrameDecoder()

        self.assertEqual(decoder.feed(first[:2]), [])
        self.assertEqual(decoder.feed(first[2:] + second[:3]), [first[4:]])
        self.assertEqual(decoder.feed(second[3:]), [second[4:]])

    def test_round_trips_json_message(self):
        framed = encode_message("STATE_CHANGE", {"row": 0, "column": 2})
        decoder = FrameDecoder()
        frame = decoder.feed(framed)[0]

        self.assertEqual(
            decode_message(frame),
            {"message": "STATE_CHANGE", "payload": {"row": 0, "column": 2}},
        )

    def test_rejects_invalid_coordinates(self):
        with self.assertRaises(ProtocolError):
            encode_message("STATE_CHANGE", {"row": 3, "column": 0})

    def test_rejects_unknown_message_type(self):
        with self.assertRaises(ProtocolError):
            decode_message(b'{"message":"MOVE","payload":{}}')

    def test_rejects_invalid_json(self):
        with self.assertRaises(ProtocolError):
            decode_message(b"not json")

    def test_rejects_zero_and_oversized_frames(self):
        with self.assertRaises(ProtocolError):
            FrameDecoder().feed(struct.pack("!I", 0))
        with self.assertRaises(ProtocolError):
            FrameDecoder().feed(struct.pack("!I", MAX_FRAME_SIZE + 1))


if __name__ == "__main__":
    unittest.main()

import socket
import sys
import unittest.mock
import tools.bridge.consumer as consumer

# Mock Hostname to MBP
with unittest.mock.patch("socket.gethostname", return_value="MBP-Pro-Max"):
    print("MOCK: Hostname -> MBP-Pro-Max")
    consumer.main()


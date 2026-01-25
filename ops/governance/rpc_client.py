import socket
import json
import os
import struct

class RPCClient:
    CLIENT_ID = "rpc_client"
    CLIENT_PATH = os.path.abspath(__file__)

    def __init__(self, sock_path="/Users/icmini/0luka/runtime/sock/gate_runner.sock"):
        self.sock_path = sock_path

    def call(self, cmd, **kwargs):
        if not os.path.exists(self.sock_path):
            return {"error": f"Socket not found at {self.sock_path}"}
            
        try:
            client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            client.connect(self.sock_path)
            
            request = {"cmd": cmd, **kwargs}
            request["client_id"] = self.CLIENT_ID
            request["client_path"] = self.CLIENT_PATH
            payload = json.dumps(request).encode()
            # Protocol v0.4: [LENGTH (4B)][PAYLOAD]
            msg = struct.pack('>I', len(payload)) + payload
            client.sendall(msg)
            
            # Read response length
            len_bytes = client.recv(4)
            if not len_bytes:
                return {"error": "No response from daemon"}
            
            resp_len = struct.unpack('>I', len_bytes)[0]
            
            # Read exact payload
            resp_data = b''
            while len(resp_data) < resp_len:
                chunk = client.recv(min(4096, resp_len - len(resp_data)))
                if not chunk: break
                resp_data += chunk
                
            return json.loads(resp_data.decode())
        except Exception as e:
            return {"error": str(e)}
        finally:
            client.close()

if __name__ == "__main__":
    import os
    client = RPCClient()
    # Test gate verification
    print(client.call("verify_gate", gate_id="gate.net.port"))

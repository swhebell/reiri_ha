import asyncio
import json
import logging
import websockets
import base64
from cryptography.hazmat.primitives.asymmetric import rsa, padding as asym_padding
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import padding as sym_padding

_LOGGER = logging.getLogger(__name__)

class ReiriClient:
    def __init__(self, ip, username, password, port=52001):
        self.ip = ip
        self.port = port
        self.username = username
        self.password = password
        self.uri = f"ws://{self.ip}:{self.port}/"
        self.websocket = None
        self.private_key = None
        self.public_key = None
        self.common_key = None
        self.iv = None
        self._lock = asyncio.Lock()

    async def connect(self):
        """Connect to the Reiri controller."""
        _LOGGER.debug(f"Connecting to {self.uri}")
        self.websocket = await websockets.connect(self.uri)
        await self._handshake()

    async def _handshake(self):
        """Perform RSA handshake to exchange keys."""
        # Generate RSA Key Pair
        self.private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
            backend=default_backend()
        )
        public_key = self.private_key.public_key()
        pem_pkcs1 = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.PKCS1
        ).decode('utf-8')

        # Send Public Key
        msg = [None, None, ["sys_info", pem_pkcs1]]
        await self.websocket.send(json.dumps(msg))

        # Receive Common Key
        while True:
            response = await asyncio.wait_for(self.websocket.recv(), timeout=10)
            data = json.loads(response)
            if isinstance(data, list) and len(data) > 2 and isinstance(data[2], list):
                cmd = data[2][0]
                payload = data[2][1]
                if cmd == "sys_info" and isinstance(payload, dict) and "common_key" in payload:
                    ciphertext = base64.b64decode(payload["common_key"])
                    self.common_key = self.private_key.decrypt(
                        ciphertext,
                        asym_padding.OAEP(
                            mgf=asym_padding.MGF1(algorithm=hashes.SHA1()),
                            algorithm=hashes.SHA1(),
                            label=None
                        )
                    )
                    self.iv = self.common_key
                    _LOGGER.debug("Handshake successful, common key received")
                    break

    async def login(self):
        """Login to the controller."""
        if not self.common_key:
            raise Exception("Not connected or handshake failed")

        payload = {
            "name": self.username,
            "passwd": self.password,
            "uuid": None
        }
        # The controller expects compact JSON
        login_data = json.dumps(payload).replace(" ", "")
        
        encrypted_payload = self._encrypt(login_data)
        msg = ["enc", None, ["login", encrypted_payload]]
        
        await self.websocket.send(json.dumps(msg))
        
        # Wait for login response
        while True:
            response = await asyncio.wait_for(self.websocket.recv(), timeout=10)
            if "login" in response:
                data = json.loads(response)
                if data[0] == "enc":
                    decrypted = self._decrypt(data[2][1])
                    resp_json = json.loads(decrypted)
                    if resp_json.get("result") == "OK":
                        _LOGGER.info("Login successful")
                        return True
                    else:
                        _LOGGER.error(f"Login failed: {resp_json}")
                        return False
                else:
                     # Should be encrypted, but handle plain just in case
                     _LOGGER.warning(f"Received plain login response: {response}")
                     return False

    async def ensure_connected(self):
        """Ensure that the connection is active and authenticated."""
        if self.websocket and self.websocket.close_code is None:
            return

        _LOGGER.info("Connection lost or not established. Reconnecting...")
        await self.close()
        
        try:
            await self.connect()
            if not await self.login():
                await self.close()
                raise Exception("Login failed during reconnection")
        except Exception as e:
            _LOGGER.error(f"Reconnection failed: {e}")
            await self.close()
            raise

    async def get_point_list(self):
        """Get the list of points (devices)."""
        async with self._lock:
            try:
                await self.ensure_connected()
                return await self._get_point_list_internal()
            except (websockets.exceptions.ConnectionClosed, BrokenPipeError):
                _LOGGER.warning("Connection closed during get_point_list. Retrying...")
                # Force close and retry once
                await self.close()
                await self.ensure_connected()
                return await self._get_point_list_internal()

    async def _get_point_list_internal(self):
        msg = ["enc", None, ["mplist"]]
        await self.websocket.send(json.dumps(msg))
        
        while True:
            response = await asyncio.wait_for(self.websocket.recv(), timeout=10)
            if "mplist" in response:
                data = json.loads(response)
                if data[0] == "enc":
                    decrypted = self._decrypt(data[2][1])
                    return json.loads(decrypted)
                return None

    async def operate(self, command):
        """Send an operation command."""
        async with self._lock:
            try:
                await self.ensure_connected()
                return await self._operate_internal(command)
            except (websockets.exceptions.ConnectionClosed, BrokenPipeError):
                _LOGGER.warning("Connection closed during operate. Retrying...")
                # Force close and retry once
                await self.close()
                await self.ensure_connected()
                return await self._operate_internal(command)

    async def _operate_internal(self, command):
        # command example: {"dtatcp1:1-00004": {"stat": "on"}}
        cmd_str = json.dumps(command).replace(" ", "")
        _LOGGER.info(f"Sending command: {cmd_str}")
        encrypted = self._encrypt(cmd_str)
        msg = ["enc", None, ["op", encrypted]]
        await self.websocket.send(json.dumps(msg))
        
        # Wait for response
        while True:
            response = await asyncio.wait_for(self.websocket.recv(), timeout=10)
            if "op" in response:
                data = json.loads(response)
                if data[0] == "enc":
                    decrypted = self._decrypt(data[2][1])
                    _LOGGER.info(f"Operate response: {decrypted}")
                    return json.loads(decrypted)
                return None

    def _encrypt(self, plaintext):
        """Encrypt data using AES-128-CBC."""
        cipher = Cipher(algorithms.AES(self.common_key), modes.CBC(self.iv), backend=default_backend())
        encryptor = cipher.encryptor()
        padder = sym_padding.PKCS7(128).padder()
        padded_data = padder.update(plaintext.encode('utf-8')) + padder.finalize()
        ciphertext = encryptor.update(padded_data) + encryptor.finalize()
        return ciphertext.hex()

    def _decrypt(self, hex_ciphertext):
        """Decrypt data using AES-128-CBC."""
        ciphertext = bytes.fromhex(hex_ciphertext)
        cipher = Cipher(algorithms.AES(self.common_key), modes.CBC(self.iv), backend=default_backend())
        decryptor = cipher.decryptor()
        padded_data = decryptor.update(ciphertext) + decryptor.finalize()
        unpadder = sym_padding.PKCS7(128).unpadder()
        plaintext = unpadder.update(padded_data) + unpadder.finalize()
        return plaintext.decode('utf-8')

    async def close(self):
        """Close the connection."""
        if self.websocket:
            try:
                await self.websocket.close()
            except Exception:
                pass
            self.websocket = None

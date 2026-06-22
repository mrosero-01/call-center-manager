import socket


class AmiClientError(RuntimeError):
    pass


class SocketAmiClient:
    """Cliente AMI minimo para ejecutar acciones contra Asterisk."""

    def __init__(self, host, port, username, password, timeout=5):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.timeout = timeout

    def db_put(self, family, key, value):
        self._run_logged_action(
            action_fields={
                "Action": "DBPut",
                "Family": family,
                "Key": key,
                "Val": value,
            },
            error_message="DBPut AMI fallido",
        )

    def command(self, command):
        return self._run_logged_action(
            action_fields={
                "Action": "Command",
                "Command": command,
            },
            error_message="Comando AMI fallido",
        )

    def _run_logged_action(self, action_fields, error_message):
        with socket.create_connection(
            (self.host, self.port),
            timeout=self.timeout,
        ) as connection:
            connection.settimeout(self.timeout)
            self._read_response(connection)
            self._send_action(
                connection,
                {
                    "Action": "Login",
                    "Username": self.username,
                    "Secret": self.password,
                    "Events": "off",
                },
            )
            self._ensure_success(self._read_response(connection), "Login AMI fallido")

            self._send_action(connection, action_fields)
            response = self._read_response(connection)
            self._ensure_success(response, error_message)

            self._send_action(connection, {"Action": "Logoff"})
            self._read_response(connection)

            return response

    def _send_action(self, connection, fields):
        payload = "".join(
            f"{name}: {value}\r\n"
            for name, value in fields.items()
        )
        connection.sendall(f"{payload}\r\n".encode("utf-8"))

    def _read_response(self, connection):
        chunks = []

        while True:
            chunk = connection.recv(4096)
            if not chunk:
                break

            chunks.append(chunk)

            if b"\r\n\r\n" in b"".join(chunks):
                break

        return b"".join(chunks).decode("utf-8", errors="replace")

    def _ensure_success(self, response, fallback_message):
        if "Response: Success" not in response:
            raise AmiClientError(f"{fallback_message}: {response.strip()}")

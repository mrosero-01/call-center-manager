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

    def db_del(self, family, key):
        self._run_logged_action(
            action_fields={
                "Action": "DBDel",
                "Family": family,
                "Key": key,
            },
            error_message="DBDel AMI fallido",
            allow_missing=True,
        )

    def run_database_actions(self, actions):
        self._run_logged_actions(actions)

    def command(self, command):
        return self._run_logged_action(
            action_fields={
                "Action": "Command",
                "Command": command,
            },
            error_message="Comando AMI fallido",
        )

    def _run_logged_action(self, action_fields, error_message, allow_missing=False):
        responses = self._run_logged_actions(
            [
                {
                    "fields": action_fields,
                    "error_message": error_message,
                    "allow_missing": allow_missing,
                }
            ]
        )

        return responses[0]

    def _run_logged_actions(self, actions):
        responses = []

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

            for action in actions:
                self._send_action(connection, action["fields"])
                response = self._read_response(connection)
                self._ensure_success(
                    response,
                    action["error_message"],
                    allow_missing=action.get("allow_missing", False),
                )
                responses.append(response)

            self._send_action(connection, {"Action": "Logoff"})
            self._read_response(connection)

            return responses

    def _send_action(self, connection, fields):
        payload = "".join(
            f"{name}: {value}\r\n"
            for name, value in fields.items()
        )
        connection.sendall(f"{payload}\r\n".encode("utf-8"))

    def _read_response(self, connection):
        chunks = []

        while True:
            try:
                chunk = connection.recv(4096)
            except socket.timeout:
                if chunks:
                    break
                raise

            if not chunk:
                break

            chunks.append(chunk)

            if b"\r\n\r\n" in b"".join(chunks):
                break

        return b"".join(chunks).decode("utf-8", errors="replace")

    def _ensure_success(self, response, fallback_message, allow_missing=False):
        if "Response: Success" not in response:
            if allow_missing and "not found" in response.lower():
                return

            raise AmiClientError(f"{fallback_message}: {response.strip()}")

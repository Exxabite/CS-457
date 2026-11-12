
import socket

HOST = "127.0.0.1"
PORT = 5000

client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)


def connect():
    client.connect((HOST, PORT))
    print(f"[+] Connected to server at {HOST}:{PORT}")


def send_message(message: str):
    """Send a string message to the server."""
    client.sendall(message.encode("utf-8"))


def disconnect():
    client.close()
    print("[-] Disconnected from server.")


if __name__ == "__main__":
    connect()

    try:
        # TEMPORARY INPUT LOOP:
        # Replace this loop with your actual application logic later.
        while True:
            message = input("> ")

            if message.lower() == "exit":
                break

            send_message(message)

    except KeyboardInterrupt:
        pass

    finally:
        disconnect()

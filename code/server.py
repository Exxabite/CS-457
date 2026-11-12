
import socket
import threading

HOST = "0.0.0.0"
PORT = 5000


def handle_client(client_socket, address):
    print(f"[+] Client connected: {address}")

    try:
        while True:
            data = client_socket.recv(1024)

            if not data:
                break

            message = data.decode("utf-8")
            print(f"[{address}] {message}")

    except ConnectionResetError:
        print(f"[-] Client disconnected unexpectedly: {address}")

    finally:
        client_socket.close()
        print(f"[-] Client disconnected: {address}")


def start_server():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    server.bind((HOST, PORT))
    server.listen()

    print(f"[*] Server listening on {HOST}:{PORT}")

    try:
        while True:
            client_socket, address = server.accept()

            # Handle each client in its own thread
            client_thread = threading.Thread(
                target=handle_client,
                args=(client_socket, address),
                daemon=True
            )

            client_thread.start()

    except KeyboardInterrupt:
        print("\n[*] Shutting down server.")

    finally:
        server.close()


if __name__ == "__main__":
    start_server()

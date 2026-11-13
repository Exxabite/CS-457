
import socket
import queue
import selectors
import struct

HOST = "0.0.0.0"
PORT = 5000
HEADER_SIZE = 4


def close_client(selector, clients, client_socket, address):
    try:
        selector.unregister(client_socket)
    except (KeyError, ValueError):
        pass

    clients.discard(client_socket)
    client_socket.close()
    print(f"[-] Client disconnected: {address}")


def start_server():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((HOST, PORT))
    server.listen()
    server.setblocking(False)

    selector = selectors.DefaultSelector()
    selector.register(server, selectors.EVENT_READ)
    clients = set()
    message_queue = queue.Queue()

    try:
        print(f"[*] Server listening on {HOST}:{PORT}")

        while True:
            for key, _ in selector.select():
                if key.fileobj is server:
                    while True:
                        try:
                            client_socket, address = server.accept()
                        except BlockingIOError:
                            break

                        client_socket.setblocking(False)
                        clients.add(client_socket)
                        selector.register(
                            client_socket,
                            selectors.EVENT_READ,
                            (address, bytearray())
                        )
                        print(f"[+] Client connected: {address}")
                    continue

                client_socket = key.fileobj
                address, buffer = key.data

                try:
                    data = client_socket.recv(4096)
                except ConnectionResetError:
                    print(f"[-] Client disconnected unexpectedly: {address}")
                    close_client(selector, clients, client_socket, address)
                    continue

                if not data:
                    close_client(selector, clients, client_socket, address)
                    continue

                buffer.extend(data)
                while len(buffer) >= HEADER_SIZE:
                    message_length = struct.unpack("!I", buffer[:HEADER_SIZE])[0]
                    frame_length = HEADER_SIZE + message_length
                    if len(buffer) < frame_length:
                        break

                    message = bytes(buffer[HEADER_SIZE:frame_length])
                    del buffer[:frame_length]
                    try:
                        decoded_message = message.decode("utf-8")
                    except UnicodeDecodeError:
                        print(f"[-] Invalid UTF-8 from client: {address}")
                        close_client(selector, clients, client_socket, address)
                        break

                    message_queue.put((address, decoded_message))

            while True:
                try:
                    address, message = message_queue.get_nowait()
                except queue.Empty:
                    break

                print(f"[{address}] {message}")

    except KeyboardInterrupt:
        print("\n[*] Shutting down server.")

    finally:
        for client_socket in clients:
            client_socket.close()
        selector.close()
        server.close()


if __name__ == "__main__":
    start_server()

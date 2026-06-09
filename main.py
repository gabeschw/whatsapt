
from client.db import connect, print_messages, recent_messages 


def main():
    conn = connect()
    print_messages(recent_messages(conn, 5))

if __name__ == "__main__":
    main()


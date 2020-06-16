import socket
import yaml
import logging
import os

debug_flag = False

class main:
    s = None

    # Main loop
    def main(self):
        T = tminal()
        s = T.connect_to_terminal()
        T.send_ping(self.get_sequence_id())
        T.send_payment_request(self.get_sequence_id())

    def get_sequence_id(self):
        sequence_id = None
        with open('.sequence_id', 'r') as file:
            read_data = file.readline()
            sequence_id = int(read_data)
        with open('.sequence_id', 'w') as file:
            file.write(str(sequence_id+1))
        return sequence_id

class tminal:
    net_STX = 0x02
    net_ETX = 0x03
    net_ENQ = 0x05
    net_ACK = 0x06
    net_DLE = 0x10
    net_NAK = 0x15
    # Comma is the field separator.
    net_FS = ","
    # Normal comma
    net_COMMA = 0x2C
    s = None

    terminal_configuration = None

    def __init__(self):
        self.read_configuration()
        

    def read_configuration(self):
        terminal_config_filename = 'config.terminal.yaml'
        if os.path.isfile(terminal_config_filename):
            with open(terminal_config_filename) as file:
                self.terminal_configuration = yaml.load(file, Loader=yaml.FullLoader)['terminal']

    def connect_to_terminal(self):
        logging.info("Connecting to Terminal...")
        self.s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.s.connect((self.terminal_configuration['ip'], self.terminal_configuration['port']))
        self.s.settimeout(30)
        return self.s

    def send_payment_request(self, sequence_id, purchase_amount="5.00"):
        status = False
        merchant_number = 1
        purchase_string = ''
        apd = ''
        session_id = ''
        server_id = ''
        txn_options='YYYNNN'
        # assemble message
        msg = (
               f"{str(sequence_id)}{self.net_FS}PUR{self.net_FS}{merchant_number}{self.net_FS}{str(purchase_amount)}{self.net_FS}"
               f"0.00{self.net_FS}{purchase_string}{self.net_FS}{txn_options}{self.net_FS}{apd}{self.net_FS}{session_id}{self.net_FS}{server_id}"
        )
        logging.debug(msg)
        logging.debug("".join("{:02x}".format(ord(c)) for c in msg))
        msgb = bytearray(msg, 'utf-8')
        full_msg = self.encodeMessage(msgb)
        logging.debug("FULL msg: " + str(full_msg))
        hextext = ''
        for b in full_msg:
            hextext += hex(b)[2:]
        logging.debug(hextext)

        # reconnect to terminal if necessary
        if not self.s:
            self.connect_to_terminal()

        # send
        logging.info("Sending PUR to the terminal...")
        self.s.send(full_msg)

        # check if the terminal has acknowledged...
        data = self.s.recv(1024)
        logging.info(data)
        if data == b'\x06':
            logging.info("Received an ACK from the terminal!")
            purchase_done = False
            while not purchase_done:
                # check for a reply ...
                data = self.s.recv(1024)
                logging.info("Data received: " + str(data))
                msg = self.parse_msg(data)
                print(msg)
                if msg[1] == "PUR":
                    print('msg 1 pur')
                    purchase_done = True
                elif msg[2] == "PUR":
                    print('msg 2 pur')
                    purchase_done = True
                elif msg[3] == "PUR":
                    print('msg 3 pur')
                    purchase_done = True
                # send ACK, if everything was fine
                logging.info("Sending ACK to the terminal.")
                self.send_ack()
        else:
            logging.error("No ACK received." + str(data))
        
        return status



    # Sends a "ping" to the terminal and checks for a reply.
    # POL operation    
    def send_ping(self, sequence_id):
        status = False
        # assemble message
        msg = f"{str(sequence_id)}{self.net_FS}POL{self.net_FS}1{self.net_FS}2.8{self.net_FS}{self.terminal_configuration['store_name']}{self.net_FS}1.2.34{self.net_FS}{self.net_FS}N{self.net_FS}{self.net_FS}N"
        logging.debug(msg)
        logging.debug("".join("{:02x}".format(ord(c)) for c in msg))
        msgb = bytearray(msg, 'utf-8')
        full_msg = self.encodeMessage(msgb)
        logging.debug("FULL msg: " + str(full_msg))
        hextext = ''
        for b in full_msg:
            hextext += hex(b)[2:]
        logging.debug(hextext)

        # reconnect to terminal if necessary
        if not self.s:
            self.connect_to_terminal()

        # send
        logging.info("Sending POL to the terminal...")
        self.s.send(full_msg)

        # check if the terminal has acknowledged...
        data = self.s.recv(1024)
        logging.info(data)
        if data == b'\x06':
            logging.info("Received an ACK from the terminal!")

            # check for a "pong" ...
            data = self.s.recv(1024)
            logging.info("Data received: " + str(data))
            msg = self.parse_msg(data)

            # send ACK, if everything was fine
            self.send_ack()
        else:
            logging.error("No ACK received." + str(data))
        
        return status

    def parse_msg(self, data):
        data = data.replace(b'\x02', b'')
        data = data.replace(b'\x03', b'')
        parts = str(data).split(self.net_FS)
        logging.info(parts)
        return parts

    # Sends an ACK message to the terminal
    def send_ack(self):
        self.s.send(self.create_ack_message())

    # creates an ACK message in byte format and returns it.
    def create_ack_message(self):
        net_ack_msg_byte = bytearray()
        net_ack_msg_byte.append(self.net_ACK)
        return net_ack_msg_byte

    # message format is described in the device / API documentation.
    # this is the same sequence of parts for all kinds of messages.
    def encodeMessage(self, msg):
        msg.append(self.net_ETX)
        net_LRC = self.generateLRC(msg);
        net_full_msg_binary = bytearray()
        net_full_msg_binary.append(self.net_STX)
        net_full_msg_binary.extend(msg)
        net_full_msg_binary.append(net_LRC)

        return net_full_msg_binary
    
    # The checksum is made by counting bytes; that's why the
    # message needs to be handed over as a bytearray.
    # No checksum no payments...
    def generateLRC(self, message):
        lrc = 0
        for b in message[0:]:
            lrc ^= b
        return lrc

logging.basicConfig(level=logging.DEBUG)
m = main()
m.main()
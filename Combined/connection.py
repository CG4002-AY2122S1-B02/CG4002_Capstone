# %%
# * Imports and initialization
import argparse
from time import sleep, time
from bluepy.btle import BTLEDisconnectError, DefaultDelegate, Peripheral
import struct
from crccheck.crc import Crc8
import logging
import Laptop_client


# * Packet Types
# For sending to Arduino
HELLO = 'H'
ACK = 'A'
RESET = 'R'
# Received from Arduino
DATA = b'D'
EMG = b'E'
TIMESTAMP = b'T'
POSITION = b'P'
LEFT_POS = b'L'
RIGHT_POS = b'R'


# * Bluetooth Data
BLE_SERVICE_UUID = "0000dfb0-0000-1000-8000-00805f9b34fb"
BLE_CHARACTERISTIC_UUID = "0000dfb1-0000-1000-8000-00805f9b34fb"
ACK_PACKET_SIZE = 6
BLE_PACKET_SIZE = 20
EMG_PACKET_SIZE = 10
DATA_PACKET_SIZE = 19
TIMESTAMP_PACKET_SIZE = 6
POSITION_PACKET_SIZE = 11


# * Mac Addresses of Bluno Beetles
BEETLE_1 = 'b0:b1:13:2d:b6:22' # Sanath
BEETLE_2 = 'b0:b1:13:2d:d3:58' # Joshua
BEETLE_3 = 'b0:b1:13:2d:b4:01' # Michael
EMG_BEETLE = '34:15:13:22:a1:23' # FOR EMG


# * Handshake status of Beetles
BEETLE_HANDSHAKE_STATUS = {
    BEETLE_1: False,
    BEETLE_2: False,
    BEETLE_3: False,
    EMG_BEETLE: False,
}

# * Requesting Reset status of Beetles
BEETLE_REQUEST_RESET_STATUS = {
    BEETLE_1: False,
    BEETLE_2: False,
    BEETLE_3: False,
    EMG_BEETLE: False,
}

# * For counting corrupted packets
BEETLE_CORRUPTION_NUM = {
    BEETLE_1: 0,
    BEETLE_2: 0,
    BEETLE_3: 0,
    EMG_BEETLE: 0,
}

# * For counting okay packets
BEETLE_OKAY_NUM = {
    BEETLE_1: 0,
    BEETLE_2: 0,
    BEETLE_3: 0,
    EMG_BEETLE: 0,
}

BEETLE_DANCER_ID = {
    '1': BEETLE_1,
    '2': BEETLE_2,
    '3': BEETLE_3,
    '4': EMG_BEETLE
}

USE_FAKE_DATA = False
laptop_client = Laptop_client
IS_NOT_LOCAL_TESTING = True
last_time_sync = 0


# * Delegate that is attached to each Beetle peripheral
class Delegate(DefaultDelegate):

    def __init__(self, mac_addr, dancer_id):
        DefaultDelegate.__init__(self)
        self.mac_addr = mac_addr
        self.dancer_id = dancer_id
        self.buffer = b''
        self.start_of_arduino_timestamp = 0

    # * Handles incoming packets from serial comms
    def handleNotification(self, cHandle, data):
        global last_time_sync

        # logging.info("#DEBUG#: Printing Raw Data here: %s. Length: %s" % (data, len(data)))

        self.buffer += data

        # Handshake completed. Handle data packets
        if (BEETLE_HANDSHAKE_STATUS[self.mac_addr]):

            # * Reads the first BLE packet
            raw_packet_data = self.buffer[0: BLE_PACKET_SIZE]

            # Received EMG Packet 4 bytes
            if (self.buffer[0] == ord(EMG) and len(self.buffer) >= BLE_PACKET_SIZE):  # * ASCII Code E (EMG)
                emg_packet_data = raw_packet_data[0: EMG_PACKET_SIZE]
                parsed_packet_data = struct.unpack(
                    '!cllc', emg_packet_data)

                if not self.checkCRC(EMG_PACKET_SIZE - 1):
                    logging.info(
                        "#DEBUG#: CRC Checksum doesn't match for %s." % self.mac_addr)
                    self.buffer = self.buffer[BLE_PACKET_SIZE:]
                    BEETLE_CORRUPTION_NUM[self.mac_addr] += 1
                    return
                    # BEETLE_REQUEST_RESET_STATUS[self.mac_addr] = True

                reformatted_data = self.formatDataForUltra96(parsed_packet_data)

                if (IS_NOT_LOCAL_TESTING):
                    laptop_client.send_data(reformatted_data)

                self.buffer = self.buffer[BLE_PACKET_SIZE:]

            # Received Data Packet 19 bytes
            elif (self.buffer[0] == ord(DATA) and len(self.buffer) >= BLE_PACKET_SIZE): # * ASCII Code D (DATA)
                data_packet_data = raw_packet_data[0: DATA_PACKET_SIZE]
                parsed_packet_data = struct.unpack(
                    '!chhhhhhcLc', data_packet_data)

                if not self.checkCRC(DATA_PACKET_SIZE - 1):
                    logging.info(
                        "#DEBUG#: CRC Checksum doesn't match for %s. Resetting..." % self.mac_addr)
                    self.buffer = self.buffer[BLE_PACKET_SIZE:]
                    BEETLE_CORRUPTION_NUM[self.mac_addr] += 1
                    # BEETLE_REQUEST_RESET_STATUS[self.mac_addr] = True
                    # return

                reformatted_data = self.formatDataForUltra96(parsed_packet_data)

                if (IS_NOT_LOCAL_TESTING):
                    laptop_client.send_data(reformatted_data)

                self.buffer = self.buffer[BLE_PACKET_SIZE:]

            # Received Timestamp packet 6 bytes
            # ! Currently unused
            elif (self.buffer[0] == ord(TIMESTAMP) and len(self.buffer) >= BLE_PACKET_SIZE):  # * ASCII Code T
                timestamp_packet_data = raw_packet_data[0: TIMESTAMP_PACKET_SIZE]
                parsed_packet_data = struct.unpack(
                    '!cLc', timestamp_packet_data)

                if not self.checkCRC(TIMESTAMP_PACKET_SIZE - 1):
                    logging.info(
                        "#DEBUG#: CRC Checksum doesn't match for %s. Resetting..." % self.mac_addr)
                    self.buffer = self.buffer[BLE_PACKET_SIZE:]
                    BEETLE_CORRUPTION_NUM[self.mac_addr] += 1
                    return
                    # BEETLE_REQUEST_RESET_STATUS[self.mac_addr] = True

                reformatted_data = self.formatDataForUltra96(parsed_packet_data)
                logging.info("#DEBUG#: Arduino Timestamp Packet %s" % reformatted_data)
                self.buffer = self.buffer[BLE_PACKET_SIZE:]

                # logging.info("Corruption stats for %s: %s" % (self.mac_addr, BEETLE_CORRUPTION_NUM[self.mac_addr]))
                # logging.info("Okay stats for %s: %s" % (self.mac_addr, BEETLE_OKAY_NUM[self.mac_addr]))

            # Recieved Position change packet 11 bytes
            elif (self.buffer[0] == ord(POSITION) and len(self.buffer) >= BLE_PACKET_SIZE): # * ASCII Code P
                position_packet_data = raw_packet_data[0:POSITION_PACKET_SIZE]
                parsed_packet_data = struct.unpack(
                    '!ccccccccccc', position_packet_data
                )

                if not self.checkCRC(POSITION_PACKET_SIZE - 1):
                    logging.info(
                        "#DEBUG#: CRC Checksum doesn't match for %s. Resetting..." % self.mac_addr)
                    self.buffer = self.buffer[BLE_PACKET_SIZE:]
                    BEETLE_CORRUPTION_NUM[self.mac_addr] += 1
                    # BEETLE_REQUEST_RESET_STATUS[self.mac_addr] = True
                    return

                reformatted_data = self.formatDataForUltra96(parsed_packet_data)

                if (IS_NOT_LOCAL_TESTING):
                    laptop_client.send_data(reformatted_data)
                self.buffer = self.buffer[BLE_PACKET_SIZE:]

            # Corrupted buffer. Move forward by one byte at a time
            else:
                logging.info("#DEBUG#: Corrupted! Buffer %s" % (self.buffer[0:BLE_PACKET_SIZE]))
                # BEETLE_REQUEST_RESET_STATUS[self.mac_addr] = True
                BEETLE_CORRUPTION_NUM[self.mac_addr] += 1
                self.buffer = self.buffer[BLE_PACKET_SIZE:]

        # Received ACK packet
        elif (self.buffer[0] == ord(ACK)):
            # 'A', Timestamp, CRC8
            parsed_packet_data = struct.unpack('!cLc', self.buffer[0:ACK_PACKET_SIZE])
            self.buffer = self.buffer[ACK_PACKET_SIZE:]
            self.start_of_arduino_timestamp = time() * 1000 - parsed_packet_data[1]
            BEETLE_HANDSHAKE_STATUS[self.mac_addr] = True
            logging.info('#DEBUG#: Received ACK packet from %s' %
                         self.mac_addr)

            last_time_sync = time()

            if (IS_NOT_LOCAL_TESTING):
                laptop_client.sync_clock()
        else:
            BEETLE_REQUEST_RESET_STATUS[self.mac_addr] = True

    # * Checks checksum by indicating the length of packet used to calculate checksum
    def checkCRC(self, length):
        calcChecksum = Crc8.calc(self.buffer[0: length])
        # logging.info("#DEBUG#: Calculated checksum: %s vs Received: %s" % (calcChecksum, self.buffer[length]))
        return calcChecksum == self.buffer[length]

    def formatDataForUltra96(self, parsed_data):
        BEETLE_OKAY_NUM[self.mac_addr] += 1
        packet_start = "#" + str(parsed_data[0], 'UTF-8') + "|" + str(self.dancer_id) + "|"

        if (parsed_data[0] == DATA):
            # Add start of dance + Timestamp + Accel & Gyro Data
            reformatted_data = packet_start + "|".join(map(str, parsed_data[1 : -3]))
            # ! current_epoch_timestamp = self.start_of_arduino_timestamp + parsed_data[8]
            current_epoch_timestamp = time()
            reformatted_data = reformatted_data + "|" + str(parsed_data[7], 'UTF-8') + "|" + str(current_epoch_timestamp) + "|"

        elif (parsed_data[0] == POSITION):
            # Left packet
            if LEFT_POS in parsed_data[1:10]:
                reformatted_data = packet_start + "L|"
            # Right packet
            elif RIGHT_POS in parsed_data[1:10]:
                reformatted_data = packet_start + "R|"

        else:
            reformatted_data = packet_start + "|".join(map(str, parsed_data[1 : -1])) + "|"

        logging.info("#DEBUG#: Formatted packet %s" % reformatted_data)
        return reformatted_data


class BeetleThread():

    def __init__(self, beetle_peripheral_object, dancer_id):

        self.beetle_periobj = beetle_peripheral_object
        self.dancer_id = dancer_id
        self.serial_service = self.beetle_periobj.getServiceByUUID(
            BLE_SERVICE_UUID)
        self.serial_characteristic = self.serial_service.getCharacteristics()[
            0]
        self.start_handshake()

    # * Initiate the start of handshake sequence with Beetle
    def start_handshake(self):
        logging.info("Starting handshake with %s" % self.beetle_periobj.addr)

        # While status is not true
        # Keep sending packet and keep track number of packets sent until response
        counter = 1
        try:
            while not BEETLE_HANDSHAKE_STATUS[self.beetle_periobj.addr]:
                # May throw BTLEException
                self.serial_characteristic.write(
                    bytes(HELLO, 'utf-8'), withResponse=False)
                logging.info("%s H packets sent to Beetle %s" %
                             (counter, self.beetle_periobj.addr))
                counter += 1

                # May be a case of faulty handshake.
                # Beetle think handshake has completed but laptop doesn't
                if counter % 5 == 0:
                    logging.info(
                        "Too many H packets sent. Arduino may be out of state. Resetting Beetle")
                    self.reset()

                # True if received packet from Beetle. Return ACK
                if self.beetle_periobj.waitForNotifications(3):
                    # logging.info("Successful connection with %s" %
                    #       self.beetle_periobj.addr)
                    # May throw BTLEEXcpetion
                    self.serial_characteristic.write(
                        bytes(ACK, 'utf-8'), withResponse=False)

            return True

        except BTLEDisconnectError:
            logging.info("Beetle %s disconnected. Attempt reconnection..." %
                         self.beetle_periobj.addr)
            self.reconnect()
            self.start_handshake()

    def reconnect(self):
        logging.info("Attempting reconnection with %s" %
                     self.beetle_periobj.addr)

        reconnection_external_packet = "#R|" + self.dancer_id + "|"

        if (IS_NOT_LOCAL_TESTING):
            laptop_client.send_data(reconnection_external_packet)

        try:
            self.beetle_periobj.disconnect()
            sleep(1)
            self.beetle_periobj.connect(self.beetle_periobj.addr)
            self.beetle_periobj.withDelegate(
                Delegate(self.beetle_periobj.addr, self.dancer_id))
            logging.info("Reconnection successful with %s" %
                         self.beetle_periobj.addr)
        except Exception as e:
            logging.info("#DEBUG#: Error reconnecting. Reason: %s" % e)
            self.reconnect()

    def reset(self):
        self.serial_characteristic.write(
            bytes(RESET, 'utf-8'), withResponse=False)
        logging.info("Resetting Beetle %s" % self.beetle_periobj.addr)
        BEETLE_HANDSHAKE_STATUS[self.beetle_periobj.addr] = False
        BEETLE_REQUEST_RESET_STATUS[self.beetle_periobj.addr] = False
        self.reconnect()

    # * Continues watching the Beetle and check request reset flag
    # * If request reset is true, reset Beetle and reinitiate handshake
    def run(self):
        global last_time_sync

        try:
            while True:
                # Break and reset
                if BEETLE_REQUEST_RESET_STATUS[self.beetle_periobj.addr]:
                    break

                if self.beetle_periobj.waitForNotifications(4) and not BEETLE_REQUEST_RESET_STATUS[self.beetle_periobj.addr]:
                    continue

            self.reset()
            self.start_handshake()
            self.run()
        except Exception as e:
            logging.info("#DEBUG#: Disconnection! Reason: %s" % e)
            self.reconnect()
            self.reset()
            self.start_handshake()
            self.run()

if __name__ == '__main__':

    parser = argparse.ArgumentParser(description = "Setup options")
    parser.add_argument('-f', '--fake-data', default = False, action='store_true', help = 'fake_data')
    parser.add_argument('-id', '--dancer-id', default = 1, help = 'dancer id')
    parser.add_argument('-e', '--emg', default = False, action='store_true', help = 'Toggle for EMG beetle')
    parser.add_argument('-l', '--local', default = False, action='store_true', help = 'For local testing')
    parser.add_argument('-p', '--port', default = 7000, help = 'port number')

    args = parser.parse_args()
    USE_FAKE_DATA = args.fake_data
    IS_NOT_LOCAL_TESTING = ~(args.local)
    IS_EMG_BEETLE = args.emg
    dancer_id = args.dancer_id
    port_number = int(args.port)

    # * Setup Logging
    logging.basicConfig(
        format="%(process)d %(message)s",
        level=logging.INFO
    )

    if (IS_NOT_LOCAL_TESTING):
        laptop_client = Laptop_client.main(dancer_id, port_number)

    if (USE_FAKE_DATA):
        laptop_client.manage_bluno_data()
    else:
        # * Change ALL_BEETLE_MAC to only include one dancer's Beetle
        if (IS_EMG_BEETLE):
            mac = BEETLE_DANCER_ID[4]
        else:
            mac = BEETLE_DANCER_ID[dancer_id]

        try:
            beetle = Peripheral(mac)
            beetle.withDelegate(Delegate(mac, dancer_id))
        except:
            sleep(10)
            beetle = Peripheral(mac)
            beetle.withDelegate(Delegate(mac, dancer_id))

        BeetleThread(beetle, dancer_id).run()


# %%

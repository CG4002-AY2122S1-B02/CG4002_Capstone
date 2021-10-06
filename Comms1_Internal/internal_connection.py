# %%
# * Imports and initialization
from time import sleep, time
from typing import Match
from bluepy.btle import BTLEDisconnectError, Scanner, DefaultDelegate, Peripheral
import struct
from crccheck.crc import Crc8
import logging
import os


# * Different Packet Types
HELLO = 'H'
ACK = 'A'
RESET = 'R'
DATA = 'D'
EMG = 'E'
START_DANCE = 'S'
TIMESTAMP = 'T'


# * Bluetooth Data
BLE_SERVICE_UUID = "0000dfb0-0000-1000-8000-00805f9b34fb"
BLE_CHARACTERISTIC_UUID = "0000dfb1-0000-1000-8000-00805f9b34fb"


# * Mac Addresses of Bluno Beetles
# BEETLE_1 = 'b0:b1:13:2d:b4:01'
BEETLE_2 = 'b0:b1:13:2d:b6:55'
BEETLE_3 = 'b0:b1:13:2d:b5:0d'
TEMP_BEETLE = 'b0:b1:13:2d:d4:ca'
ALL_BEETLE_MAC = [TEMP_BEETLE]


# * Handshake status of Beetles
BEETLE_HANDSHAKE_STATUS = {
    # BEETLE_1: False,
    BEETLE_2: False,
    BEETLE_3: False,
    TEMP_BEETLE: False
}

# * Requesting Reset status of Beetles
BEETLE_REQUEST_RESET_STATUS = {
    # BEETLE_1: False,
    BEETLE_2: False,
    BEETLE_3: False,
    TEMP_BEETLE: False
}

# ! FOR DEBUGGING AND LOGGING
BEETLE_CORRUPTION_NUM = {
    # BEETLE_1: 0,
    BEETLE_2: 0,
    BEETLE_3: 0,
    TEMP_BEETLE: 0
}

BEETLE_OKAY_NUM = {
    # BEETLE_1: 0,
    BEETLE_2: 0,
    BEETLE_3: 0,
    TEMP_BEETLE: 0
}

start = 0

# %%

# * Delegate that is attached to each Beetle peripheral
class Delegate(DefaultDelegate):

    def __init__(self, mac_addr):
        DefaultDelegate.__init__(self)
        self.mac_addr = mac_addr
        self.buffer = b''

    # * Handles incoming packets from serial comms
    def handleNotification(self, cHandle, data):
        # logging.info("#DEBUG#: Printing Raw Data here: %s. Length: %s" % (data, len(data)))

        self.buffer += data

        # Handshake completed. Handle data packets
        if (BEETLE_HANDSHAKE_STATUS[self.mac_addr]):

            raw_packet_data = self.buffer[0: 20]

            # Received EMG Packet 4 bytes
            if (self.buffer[0] == 69 and len(self.buffer) >= 20):  # * ASCII Code E (EMG)
                emg_packet_data = raw_packet_data[0: 4]
                parsed_packet_data = struct.unpack(
                    '!chc', emg_packet_data)

                if not self.checkCRC(3):
                    logging.info(
                        "#DEBUG#: CRC Checksum doesn't match for %s. Resetting..." % self.mac_addr)
                    self.buffer = b''
                    BEETLE_REQUEST_RESET_STATUS[self.mac_addr] = True
                    return

                self.sendDataToUltra96(parsed_packet_data)
                self.buffer = self.buffer[20:]

            # Received Data Packet 14 bytes
            # * ASCII Code D (DATA)
            elif (self.buffer[0] == 68 and len(self.buffer) >= 20):
                data_packet_data = raw_packet_data[0: 14]
                parsed_packet_data = struct.unpack(
                    '!chhhhhhc', data_packet_data)

                if not self.checkCRC(13):
                    logging.info(
                        "#DEBUG#: CRC Checksum doesn't match for %s. Resetting..." % self.mac_addr)
                    BEETLE_REQUEST_RESET_STATUS[self.mac_addr] = True
                    self.buffer = b''
                    return

                self.sendDataToUltra96(parsed_packet_data)
                self.buffer = self.buffer[20:]

            # Received Timestamp packet 6 bytes
            elif (self.buffer[0] == 84 and len(self.buffer) >= 20):  # * ASCII Code T
                timestamp_packet_data = raw_packet_data[0: 6]
                parsed_packet_data = struct.unpack(
                    '!cLc', timestamp_packet_data)

                if not self.checkCRC(5):
                    logging.info(
                        "#DEBUG#: CRC Checksum doesn't match for %s. Resetting..." % self.mac_addr)
                    BEETLE_REQUEST_RESET_STATUS[self.mac_addr] = True
                    self.buffer = b''
                    return

                self.sendDataToUltra96(parsed_packet_data)
                self.buffer = self.buffer[20:]

                logging.info("Corruption stats for %s: %s" % (self.mac_addr, BEETLE_CORRUPTION_NUM[self.mac_addr]))
                logging.info("Okay stats for %s: %s" % (self.mac_addr, BEETLE_OKAY_NUM[self.mac_addr]))

            # Corrupted buffer. Move forward by one byte at a time
            else:
                # logging.info("#DEBUG#: Corrupted! Buffer %s" % (self.buffer[0:20]))
                # BEETLE_REQUEST_RESET_STATUS[self.mac_addr] = True
                BEETLE_CORRUPTION_NUM[self.mac_addr] += 1
                self.buffer = self.buffer[20:]

        # Received ACK packet
        elif (self.buffer[0] == 65):
            # 'A', CRC8
            self.buffer = self.buffer[2:]
            BEETLE_HANDSHAKE_STATUS[self.mac_addr] = True
            logging.info('#DEBUG#: Received ACK packet from %s' %
                         self.mac_addr)

        else:
            BEETLE_REQUEST_RESET_STATUS[self.mac_addr] = True

    # * Checks checksum by indicating the length of packet used to calculate checksum
    def checkCRC(self, length):
        calcChecksum = Crc8.calc(self.buffer[0: length])
        # logging.info("#DEBUG#: Calculated checksum: %s vs Received: %s" % (calcChecksum, self.buffer[length]))
        return calcChecksum == self.buffer[length]

    # TODO Change this to external comms code in the future
    def sendDataToUltra96(self, data):
        BEETLE_OKAY_NUM[self.mac_addr] += 1
        logging.info("From %s: %s" % (self.mac_addr, data))


class BeetleThread():
    def __init__(self, beetle_peripheral_object):

        self.beetle_periobj = beetle_peripheral_object
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
                if counter % 20 == 0:
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
        try:
            self.beetle_periobj.disconnect()
            sleep(1)
            self.beetle_periobj.connect(self.beetle_periobj.addr)
            self.beetle_periobj.withDelegate(
                Delegate(self.beetle_periobj.addr))
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
        try:
            while True:
                # Break and reset
                if BEETLE_REQUEST_RESET_STATUS[self.beetle_periobj.addr]:
                    break

                if self.beetle_periobj.waitForNotifications(2) and not BEETLE_REQUEST_RESET_STATUS[self.beetle_periobj.addr]:
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


class Initialize:

    # * Utilize MAC address of Beetles and directly create connection with them
    def start_peripherals():
        created_beetle_peripherals = []
        for mac in ALL_BEETLE_MAC:
            try:
                # May throw BETLEException
                logging.info("#DEBUG# Attempting connection to %s" % mac)
                beetle = Peripheral(mac)
            except Exception as e:
                logging.info(
                    "#DEBUG#: Failed to create peripheral for %s. Exception: %s" % (mac, e))
                continue

            beetle.withDelegate(Delegate(mac))
            created_beetle_peripherals.append(beetle)
        return created_beetle_peripherals

    # ! DEPRE this was only used for testing
    # Returns a list of bluepy devices that match Beetle's MAC
    def scan():
        # Initialize scanner to hci0 interface (ensure this interface is bluetooth)
        scanner = Scanner(0)
        devices = scanner.scan(5)
        found_beetles = []
        for device in devices:
            if device.addr in ALL_BEETLE_MAC:
                found_beetles.append(device)
        logging.info('#DEBUG#: %s Beetle found!' % (len(found_beetles)))
        return found_beetles

    # ! DEPRE this was only used for testing
    # Devices are a list of ScanEntries that match Beetle's MAC
    # Returns a list of created Peripherals for Beetles
    def create_peripherals(devices):
        created_beetle_peripherals = []
        for dev in devices:
            try:
                # May throw BTLEException
                beetle = Peripheral(dev.addr)
            except:
                logging.info(
                    "#DEBUG#: Failed to create peripheral for %s. Retrying..." % dev.addr)
                beetle = Peripheral(dev.addr)

            beetle.setDelegate(Delegate(dev.addr))
            created_beetle_peripherals.append(beetle)
        return created_beetle_peripherals


# %%
# ! Actual main code
if __name__ == '__main__':
    # * Setup Logging
    logging.basicConfig(
        format="%(process)d %(message)s",
        level=logging.INFO
    )

    # beetle_peripherals = Initialize.start_peripherals()

    start = time()

    for mac in ALL_BEETLE_MAC:

        pid = os.fork()

        if pid > 0:
            logging.info("Spawning Child Process")
        else:
            logging.info("#DEBUG# Attempting connection to %s" % mac)
            try:
                # May throw BTLEException
                beetle = Peripheral(mac)
            except:
                logging.info(
                    "#DEBUG#: Failed to create peripheral for %s. Retrying once more." % mac)
                sleep(2)
                beetle = Peripheral(mac)
            beetle.withDelegate(Delegate(mac))
            BeetleThread(beetle).run()

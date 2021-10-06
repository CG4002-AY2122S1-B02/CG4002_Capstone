#include "CRC.h"
#include "CRC8.h"

// * Constants
#define BAUD_RATE 115200
#define SAMPLING_PERIOD 40 // 40ms, so 25Hz
#define EMG_SAMPLING_PERIOD 10 // 10ms, so 100Hz
#define TIMESTAMP_PERIOD 5000 // 5 seconds, so 0.2Hz
#define HELLO_PACKET 'H'
#define ACK_PACKET 'A'
#define RESET_PACKET 'R'
#define DATA_PACKET 'D'
#define EMG_PACKET 'E'
#define START_DANCE_PACKET 'S' // TODO yet to be implemented
#define TIMESTAMP 'T'

// * Time related global variables
unsigned long currentTime = 0;
unsigned long previousPacketTime = 0;
unsigned long previousEMGPacketTime = 0;
unsigned long previousTimestampPacketTime = 0;

// * Handshake status
bool handshakeStart = false;
bool handshakeEnd = false;

// * Data related global variables
int16_t accelX;
int16_t accelY;
int16_t accelZ;
int16_t rotX;
int16_t rotY;
int16_t rotZ;

int16_t emgData;

// * Buffer related
byte twoByteBuf[2];
byte fourByteBuf[4];

// * CRC Related
CRC8 crc;

// *   _    _      _                   ______
// * | |  | |    | |                 |  ____|
// * | |__| | ___| |_ __   ___ _ __  | |__ _   _ _ __   ___
// * |  __  |/ _ \ | '_ \ / _ \ '__| |  __| | | | '_ \ / __|
// * | |  | |  __/ | |_) |  __/ |    | |  | |_| | | | | (__
// * |_|  |_|\___|_| .__/ \___|_|    |_|   \__,_|_| |_|\___|
// *               | |
// *               |_|

// * Calculate CRC8 for checksum
uint8_t calcCRC8(uint8_t *data, int len) {
    return crc8(data, len);
}

// * Write 2 byte signed integer data to Serial (Little Endian!)
void writeIntToSerial(int16_t data) {
    twoByteBuf[1] = data & 255;
    twoByteBuf[0] = (data >> 8) & 255;
    Serial.write(twoByteBuf, sizeof(twoByteBuf));
    crc.add(twoByteBuf, sizeof(twoByteBuf));
}

// * Write 4 byte unsigned long (timestamp) to Serial
void writeLongToSerial(unsigned long data) {
    fourByteBuf[3] = data & 255;
    fourByteBuf[2] = (data >> 8) & 255;
    fourByteBuf[1] = (data >> 16) & 255;
    fourByteBuf[0] = (data >> 24) & 255;
    Serial.write(fourByteBuf, sizeof(fourByteBuf));
    crc.add(fourByteBuf, sizeof(fourByteBuf));
}

// * Reset Beetle Programmatically
void (* resetBeetle) (void) = 0;

// ? Read data from sensors (IN THE FUTURE)
// * Generate fake accelerometer and rotational data
void readData() {
    // ? Random generation of data
    accelX = random(-32768, 32767);
    accelY = random(-32768, 32767);
    accelZ = random(-32768, 32767);
    rotX = random(-32768, 32767);
    rotY = random(-32768, 32767);
    rotZ = random(-32768, 32767);
    // accelX = -6000;
    // accelY = 13880;
    // accelZ = -1380;
    // rotX = 915;
    // rotY = -68;
    // rotZ = -49;
}

// ? Read data from EMG sensors (IN THE FUTURE)
// * Generate fake EMG data
void readEMGData() {
    // ? Random generation of data
    emgData = random(0, 1023);
    // emgData = 200;
}

// *   _____ ______ _   _ _____    ______ _    _ _   _  _____
// *  / ____|  ____| \ | |  __ \  |  ____| |  | | \ | |/ ____|
// * | (___ | |__  |  \| | |  | | | |__  | |  | |  \| | |
// *  \___ \|  __| | . ` | |  | | |  __| | |  | | . ` | |
// *  ____) | |____| |\  | |__| | | |    | |__| | |\  | |____
// * |_____/|______|_| \_|_____/  |_|     \____/|_| \_|\_____|
//

// * Total 2 bytes currently
void sendACKPacket(char packetType) {

    // One byte packet type and add to CRC
    Serial.write(ACK_PACKET);
    crc.add(ACK_PACKET);

    Serial.write(crc.getCRC()); // One byte checksum

    crc.restart(); // Restart crc caclulation
}

// * Total 14 bytes currently + 6 byte paddings
void sendDataPacket() {

    // One byte packet type and add to CRC
    Serial.write(DATA_PACKET);
    crc.add(DATA_PACKET);

    // ! Remember to change this to actual reading of sensors data in the future
    readData();

    // 6 bytes accelerometer, 6 bytes rotational
    writeIntToSerial(accelX);
    writeIntToSerial(accelY);
    writeIntToSerial(accelZ);
    writeIntToSerial(rotX);
    writeIntToSerial(rotY);
    writeIntToSerial(rotZ);

    Serial.write(crc.getCRC()); // One byte checksum

    // Padding
    Serial.write(0);
    Serial.write(0);
    Serial.write(0);
    Serial.write(0);
    Serial.write(0);
    Serial.write(0);

    crc.restart();
}

// * Total 4 bytes + 16 bytes padding
void sendEMGPacket() {

    // One byte packet type and add to CRC
    Serial.write(EMG_PACKET);
    crc.add(EMG_PACKET);

    // ! Remember to change this to actual reading in the future
    readEMGData();

    // 2 bytes EMG data
    writeIntToSerial(emgData);

    Serial.write(crc.getCRC()); // One byte checksum

    // Padding
    Serial.write(0);
    Serial.write(0);
    Serial.write(0);
    Serial.write(0);
    Serial.write(0);
    Serial.write(0);
    Serial.write(0);
    Serial.write(0);
    Serial.write(0);
    Serial.write(0);
    Serial.write(0);
    Serial.write(0);
    Serial.write(0);
    Serial.write(0);
    Serial.write(0);
    Serial.write(0);

    crc.restart();
}

// * Total 6 bytes + 14 bytes padding
void sendTimestampPacket() {

    // One byte packet type and add to CRC
    Serial.write(TIMESTAMP);
    crc.add(TIMESTAMP);

    // 4 bytes timestamp data
    writeLongToSerial(currentTime);

    Serial.write(crc.getCRC()); // One byte checksum

    // Padding
    Serial.write(0);
    Serial.write(0);
    Serial.write(0);
    Serial.write(0);
    Serial.write(0);
    Serial.write(0);
    Serial.write(0);
    Serial.write(0);
    Serial.write(0);
    Serial.write(0);
    Serial.write(0);
    Serial.write(0);
    Serial.write(0);
    Serial.write(0);

    crc.restart();
}


// *                    _       _               ______
// *     /\           | |     (_)             |  ____|
// *    /  \   _ __ __| |_   _ _ _ __   ___   | |__ _   _ _ __   ___
// *   / /\ \ | '__/ _` | | | | | '_ \ / _ \  |  __| | | | '_ \ / __|
// *  / ____ \| | | (_| | |_| | | | | | (_) | | |  | |_| | | | | (__
// * /_/    \_\_|  \__,_|\__,_|_|_| |_|\___/  |_|   \__,_|_| |_|\___|

// * Initialization
void setup() {

    Serial.begin(BAUD_RATE);

    // ? Is this needed?
    currentTime = 0;
    previousPacketTime = 0;
    previousEMGPacketTime = 0;
    previousTimestampPacketTime = 0;
}

void loop() {
    if (Serial.available()) {
        byte packetType = Serial.read();

        switch (packetType) {
            case HELLO_PACKET:
                // Handshake starts from laptop. Reply handshake with ACK
                handshakeStart = true;
                handshakeEnd = false;
                sendACKPacket(ACK_PACKET);
                Serial.flush();
                break;
            case ACK_PACKET:
                // Received last ACK from laptop. Handshake complete
                if (handshakeStart) {
                    handshakeStart = false;
                    handshakeEnd = true;
                }
                break;
            case RESET_PACKET:
                resetBeetle();
                break;
        }
    }

    // Handshake completed
    if (handshakeEnd) {
        currentTime = millis();

        // Send EMG Packet Data
        if (currentTime - previousEMGPacketTime > EMG_SAMPLING_PERIOD) {
            readEMGData();
            sendEMGPacket();
            Serial.flush();
            previousEMGPacketTime = currentTime;
        }

        // Send sensor data
        if (currentTime - previousPacketTime > SAMPLING_PERIOD) {
            readData();
            sendDataPacket();
            Serial.flush();
            previousPacketTime = currentTime;
        }

        // Send timestamp packet for synchronisation
        if (currentTime - previousTimestampPacketTime > TIMESTAMP_PERIOD) {
            sendTimestampPacket();
            Serial.flush();
            previousTimestampPacketTime = currentTime;
        }

    }

}

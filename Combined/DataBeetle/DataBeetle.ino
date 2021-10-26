#include <Wire.h>
#include "I2Cdev.h"
#include "MPU6050_6Axis_MotionApps20.h"
#include "CRC.h"
#include "CRC8.h"

// * Constants
#define NUM_SAMPLES 10
#define START_MOVE_THRESHOLD 500
#define POS_MOVE_THRESHOLD 90
#define STOP_MOVE_THRESHOLD 70

#define BAUD_RATE 115200
#define SAMPLING_PERIOD 40 // 40ms, so 25Hz
#define EMG_SAMPLING_PERIOD 10 // 10ms, so 100Hz
#define TIMESTAMP_PERIOD 5000 // 5 seconds, so 0.2Hz
#define HELLO_PACKET 'H'
#define ACK_PACKET 'A'
#define RESET_PACKET 'R'
#define DATA_PACKET 'D'
#define EMG_PACKET 'E'
#define POS_PACKET 'P'
#define START_DANCE_PACKET 'S'
#define NORMAL_DANCE_PACKET 'N'
#define TIMESTAMP 'T'

// * Time related global variables
unsigned long currentTime = 0;
unsigned long previousPacketTime = 0;
unsigned long previousTimestampPacketTime = 0;

// * Handshake status
bool handshakeStart = false;
bool handshakeEnd = false;

// * MPU related variables
MPU6050 mpu;
// MPU control/status variables
bool dmpReady = false;          // set true if DMP init was successful
uint8_t devStatus;              // return status after each device operation (0 = success, !0 = error)
uint16_t packetSize;            // expected DMP packet size (default is 42 bytes)
uint16_t fifoCount;             // count of all bytes currently in FIFO
uint8_t fifoBuffer[64];         // FIFO storage buffer

// * Orientation / Motion variables
Quaternion q;                   // [w, x, y, z]         quaternion container
VectorInt16 aa;                 // [x, y, z]            accel sensor measurements (includes gravity)
VectorInt16 aaReal;             // [x, y, z]            gravity-free accel sensor measurements
VectorFloat gravity;            // [x, y, z]            gravity vector
float ypr[3];                   // [yaw, pitch, roll]   yaw/pitch/roll container and gravity vector

int16_t AccX[NUM_SAMPLES];      // Stores NUM_SAMPLES number of the most recent real acceleration values in X axis. Acts like a window
int16_t AccY[NUM_SAMPLES];      // Stores NUM_SAMPLES number of the most recent real acceleration values in Y axis. Acts like a window
int16_t AccZ[NUM_SAMPLES];      // Stores NUM_SAMPLES number of the most recent real acceleration values in Z axis. Acts like a window
int curr_frame = 0;             // Used to indicate which frame of the window we are going to be placing the values in
bool fullWindow = false;
double prevWindowAvgX = 0;
double prevWindowAvgY = 0;
double prevWindowAvgZ = 0;

bool firstWindowDone = false;
bool detectedDanceMovement = false;
bool detectedPosMovement = false;
bool firstDancePacket = false;
int32_t lastDetectedMoveTime;

double windowDiffMin = -1e9, windowDiffMax = 1e9;
int32_t minTime, maxTime;

// * Data related global variables
int16_t accelX;
int16_t accelY;
int16_t accelZ;
int16_t rotX;
int16_t rotY;
int16_t rotZ;

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

// * Function to check for FIFO buffer
void checkFIFO() {
    mpu.resetFIFO();
    fifoCount = mpu.getFIFOCount();
    while (fifoCount < packetSize) fifoCount = mpu.getFIFOCount();
    mpu.getFIFOBytes(fifoBuffer, packetSize);
}


// * Function to calibrate MPU offset
void calibrateMPUOffset() {
    // BLE 1
    mpu.setXAccelOffset(271);
    mpu.setYAccelOffset(1047);
    mpu.setZAccelOffset(1071);
    mpu.setXGyroOffset(50);
    mpu.setYGyroOffset(54);
    mpu.setZGyroOffset(29);

    // BLE 2
//        mpu.setXAccelOffset(-3114);
//        mpu.setYAccelOffset(745);
//        mpu.setZAccelOffset(1368);
//        mpu.setXGyroOffset(32);
//        mpu.setYGyroOffset(158);
//        mpu.setZGyroOffset(-14);

    // BLE 3
//         mpu.setXAccelOffset(785);
//         mpu.setYAccelOffset(-481);
//         mpu.setZAccelOffset(905);
//         mpu.setXGyroOffset(2);
//         mpu.setYGyroOffset(-22);
//         mpu.setZGyroOffset(-85);

}

/*
    * Function that reads sensor data values
    Function to get acceleration values in X, Y and Z axis store them in accX, accY and accZ arrays
    We will only be getting the raw values from aaReal. In order to convert it to m/s^2,
    we will have to divide the values by 8192, then multiply by g = 9.80665 m/s^2
    acceleration sensitivity is +/-2g, hence values will be 0-8192 will represent 1g and -8192-0 represents -1g
*/
void getAccValues() {
    mpu.dmpGetQuaternion(&q, fifoBuffer);
    mpu.dmpGetAccel(&aa, fifoBuffer);
    mpu.dmpGetGravity(&gravity, &q);
    mpu.dmpGetLinearAccel(&aaReal, &aa, &gravity);
    mpu.dmpGetYawPitchRoll(ypr, &q, &gravity);

    AccX[curr_frame] = aaReal.x;
    AccY[curr_frame] = aaReal.y;
    AccZ[curr_frame] = aaReal.z;

    accelX = aaReal.x;
    accelY = aaReal.y;
    accelZ = aaReal.z;

    rotX = (int) (ypr[0] * 10000);
    rotY = (int) (ypr[1] * 10000);
    rotZ = (int) (ypr[2] * 10000);

    // Replace the oldest value with the newest value in the next loop
    curr_frame = (curr_frame + 1) % 10;
}

// * Detect start of dance move or change position
void detectStartMoveOrPosition() {
    // once curr_frame hits NUM_SAMPLES-1 (hit window size) for the first time, then can start to perform sliding window
    if (!fullWindow && curr_frame == NUM_SAMPLES - 1) fullWindow = true;

    // find average of current window and compare to previous window
    if (fullWindow) {
        double totalAccX = 0;
        double totalAccY = 0;
        double totalAccZ = 0;
        for (int i = 0; i < NUM_SAMPLES; i++) {
            totalAccX += AccX[i];
            totalAccY += AccY[i];
            totalAccZ += AccZ[i];
        }

        double currWindowAvgX = totalAccX / (double)NUM_SAMPLES;
        double currWindowAvgY = totalAccY / (double)NUM_SAMPLES;
        double currWindowAvgZ = totalAccZ / (double)NUM_SAMPLES;

        // only need to calculate difference between previous and current window average after we have taken the first window
        if (firstWindowDone) {
            double windowDiffX = currWindowAvgX - prevWindowAvgX;
            double windowDiffY = currWindowAvgY - prevWindowAvgY;
            double windowDiffZ = currWindowAvgZ - prevWindowAvgZ;

            // ? Maybe add separate logic for positional move threshold
            if (!detectedDanceMovement && (abs(windowDiffX) > START_MOVE_THRESHOLD || abs(windowDiffY) > START_MOVE_THRESHOLD || abs(windowDiffZ) > START_MOVE_THRESHOLD)) {
                firstDancePacket = true;
                detectedDanceMovement = true;
                lastDetectedMoveTime = micros();
            }
            else if (!detectedDanceMovement && !detectedPosMovement && (abs(windowDiffX) < POS_MOVE_THRESHOLD && abs(windowDiffY) < 200 && abs(windowDiffZ) > POS_MOVE_THRESHOLD)){
                detectedPosMovement = true;
                lastDetectedMoveTime = micros();
            }

            // if difference between current window and previous windows has been somewhat 0 (not much movement detected)
            // for about 1.5 seconds, then we will deem it that the user has stopped moving
            if (detectedDanceMovement) {
                detectedPosMovement = false;
                if (abs(windowDiffX) > STOP_MOVE_THRESHOLD || abs(windowDiffY) > STOP_MOVE_THRESHOLD || abs(windowDiffZ) > STOP_MOVE_THRESHOLD) lastDetectedMoveTime = micros();
                else if (micros() - lastDetectedMoveTime > 1500000) detectedDanceMovement = false;
            }
            else if (detectedPosMovement)
            {
                if (windowDiffZ < windowDiffMin)
                {
                    windowDiffMin = windowDiffZ;
                    minTime = millis();
                }
                if (windowDiffZ > windowDiffMax)
                {
                    windowDiffMax = windowDiffZ;
                    maxTime = millis();
                }
                

                if (abs(windowDiffZ) > STOP_MOVE_THRESHOLD) lastDetectedMoveTime = micros();
                else if (micros() - lastDetectedMoveTime > 1000000)
                {
                    if (maxTime > minTime)
                        sendPosPacket(1);
                    else
                        sendPosPacket(0);

                    windowDiffMin = 1e9;
                    windowDiffMax = -1e9;
                    maxTime = millis();
                    minTime = millis();
                    detectedPosMovement = false;
                }
            }
        }

        // replace values for the next loop
        prevWindowAvgX = currWindowAvgX;
        prevWindowAvgY = currWindowAvgY;
        prevWindowAvgZ = currWindowAvgZ;
        firstWindowDone = true;
    }
}

// *   _____
// *  / ____|
// * | |     ___  _ __ ___  _ __ ___  ___
// * | |    / _ \| '_ ` _ \| '_ ` _ \/ __|
// * | |___| (_) | | | | | | | | | | \__
// *  \_____\___/|_| |_| |_|_| |_| |_|___/

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

// * Write 4 byte float to Serial
void writeFloatToSerial(float data) {
    byte* buf = (byte *) &data;
    Serial.write(buf, 4);
}

// * Pad BLE packet with 0s so that it is 20 bytes long
void padPacket(int length) {
    for (int i = 0; i < length; i++) {
        Serial.write(0);
    }
}

// * Reset Beetle Programmatically
void (* resetBeetle) (void) = 0;

// *   _____ ______ _   _ _____    ______ _    _ _   _  _____
// *  / ____|  ____| \ | |  __ \  |  ____| |  | | \ | |/ ____|
// * | (___ | |__  |  \| | |  | | | |__  | |  | |  \| | |
// *  \___ \|  __| | . ` | |  | | |  __| | |  | | . ` | |
// *  ____) | |____| |\  | |__| | | |    | |__| | |\  | |____
// * |_____/|______|_| \_|_____/  |_|     \____/|_| \_|\_____|
//

// * Total 11 bytes with 9 bytes padding
void sendPosPacket(int isLeft) {

    // One byte packet type and add to CRC
    Serial.write(POS_PACKET);
    crc.add(POS_PACKET);

    // One byte char repeated 9 times (1 == left, 0 == right)
    for (int i = 0; i < 9; i++) {
        if (isLeft) {
            Serial.write('L');
            crc.add('L');
        } else {
            Serial.write('R');
            crc.add('R');
        }
    }

    Serial.write(crc.getCRC());
    crc.restart();

    padPacket(9);

    Serial.flush();
}

// * Total 6 bytes currently
void sendACKPacket() {

    // One byte packet type and add to CRC
    Serial.write(ACK_PACKET);
    crc.add(ACK_PACKET);

    // 4 bytes timestamp data
    writeLongToSerial(currentTime);

    Serial.write(crc.getCRC()); // One byte checksum

    crc.restart(); // Restart crc caclulation
}

// * Total 19 bytes currently + 1 byte paddings
void sendDataPacket() {

    // One byte packet type and add to CRC
    Serial.write(DATA_PACKET);
    crc.add(DATA_PACKET);

    // 6 bytes accelerometer, 6 bytes rotational (YPR)
    writeIntToSerial(accelX);
    writeIntToSerial(accelY);
    writeIntToSerial(accelZ);
    writeIntToSerial(rotX);
    writeIntToSerial(rotY);
    writeIntToSerial(rotZ);

    // 1 byte for start dance or normal dance packet
    if (firstDancePacket) {
        firstDancePacket = false;
        Serial.write(START_DANCE_PACKET);
        crc.add(START_DANCE_PACKET);
    } else {
        Serial.write(NORMAL_DANCE_PACKET);
        crc.add(NORMAL_DANCE_PACKET);
    }

    // 4 bytes timestamp data
    writeLongToSerial(currentTime);

    Serial.write(crc.getCRC()); // One byte checksum

    padPacket(1);

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
    padPacket(14);

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
    // join I2C bus (I2Cdev library doesn't do this automatically)
#if I2CDEV_IMPLEMENTATION == I2CDEV_ARDUINO_WIRE
    Wire.begin();
    Wire.setClock(400000); // 400kHz I2C clock. Comment this line if having compilation difficulties
#elif I2CDEV_IMPLEMENTATION == I2CDEV_BUILTIN_FASTWIRE
    Fastwire::setup(400, true);
#endif

    Serial.begin(BAUD_RATE);

    // Initialise the device
    // initially set gyro sensitivity to +/-250deg/s, and acceleration to +/-2g --> mpu6050.cpp line 58
    mpu.initialize();

    // Initialise DMP
    // set sampling rate to 200 Hz and gyro sensitivity to +/-2000deg/s --> mpu6050_6Axis_MotionApps20.h lines 324 and 333
    // Digital Low-Pass Filter (DLPF) with bandwidth of 42Hz --> mpu6050_6Axis_MotionApps20.h lines 330
    devStatus = mpu.dmpInitialize();

    // set sampling rate to 1000/(1+49) = 20Hz, BLE cannot support very high rates
    mpu.setRate(49);

    // Offset MPU
    calibrateMPUOffset();

    // Check DMP initialized correctly (returns 0 if so)
    if (devStatus == 0) {
        // turn on the DMP, now that it's ready
        mpu.setDMPEnabled(true);
        dmpReady = true;

        // get expected DMP packet size for later comparison
        packetSize = mpu.dmpGetFIFOPacketSize();
    }

    // Delay 3 seconds to let IMU stabilise
    delay(3000);

    currentTime = 0;
    previousPacketTime = 0;
    previousTimestampPacketTime = 0;
}

void loop() {
    checkFIFO();

    if (Serial.available()) {
        byte packetType = Serial.read();

        switch (packetType) {
            case HELLO_PACKET:
                // Handshake starts from laptop. Reply handshake with ACK
                handshakeStart = true;
                handshakeEnd = false;
                sendACKPacket();
                Serial.flush();
                break;
            case ACK_PACKET:
                // Received last ACK from laptop. Handshake complete
                Serial.flush();
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

    getAccValues();
    detectStartMoveOrPosition();

    // Handshake completed
    if (handshakeEnd && detectedDanceMovement) {
        currentTime = millis();

        // Send sensor data
        if (currentTime - previousPacketTime > SAMPLING_PERIOD) {
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

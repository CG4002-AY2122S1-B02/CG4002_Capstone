#include <Wire.h>
#include "I2Cdev.h"
#include "MPU6050_6Axis_MotionApps20.h"

#define NUM_SAMPLES 10
#define START_MOVE_THRESHOLD 500
#define STOP_MOVE_THRESHOLD 70

MPU6050 mpu;

// MPU control/status variables
bool dmpReady = false;          // set true if DMP init was successful
uint8_t devStatus;              // return status after each device operation (0 = success, !0 = error)
uint16_t packetSize;            // expected DMP packet size (default is 42 bytes)
uint16_t fifoCount;             // count of all bytes currently in FIFO
uint8_t fifoBuffer[64];         // FIFO storage buffer

// Orientation / Motion variables
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
bool detectedMovement = false;
int32_t lastDetectedMoveTime;

// ================================================
// ==                 Functions                  ==
// ================================================

/*
     Function to check for FIFO buffer
*/
void checkFIFO() {
    mpu.resetFIFO();
    fifoCount = mpu.getFIFOCount();
    while (fifoCount < packetSize) fifoCount = mpu.getFIFOCount();
    mpu.getFIFOBytes(fifoBuffer, packetSize);
}

/*
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

    //    Serial.print("with gravity: ");
    //    Serial.print(aa.x);
    //    Serial.print(" ");
    //    Serial.print(aa.y);
    //    Serial.print(" ");
    //    Serial.println(aa.z);
    //
    //    Serial.print("gravity: ");
    //    Serial.print(gravity.x);
    //    Serial.print(" ");
    //    Serial.print(gravity.y);
    //    Serial.print(" ");
    //    Serial.println(gravity.z);
    //
    //    Serial.print("without gravity: ");
    //    Serial.print(aaReal.x);
    //    Serial.print(" ");
    //    Serial.print(aaReal.y);
    //    Serial.print(" ");
    //    Serial.println(aaReal.z);
    //    Serial.println();

    // Replace the oldest value with the newest value in the next loop
    curr_frame = (curr_frame + 1) % 10;
}

/*
     Function to calibrate MPU offset
*/
void calibrateMPUOffset() {
    // BLE 1
    mpu.setXAccelOffset(271);
    mpu.setYAccelOffset(1047);
    mpu.setZAccelOffset(1071);
    mpu.setXGyroOffset(50);
    mpu.setYGyroOffset(54);
    mpu.setZGyroOffset(29);

    // BLE 2
//        mpu.setXAccelOffset(-3553);
//        mpu.setYAccelOffset(599);
//        mpu.setZAccelOffset(1346);
//        mpu.setXGyroOffset(34);
//        mpu.setYGyroOffset(161);
//        mpu.setZGyroOffset(-12);

    // BLE 3
//        mpu.setXAccelOffset(579);
//        mpu.setYAccelOffset(-201);
//        mpu.setZAccelOffset(863);
//        mpu.setXGyroOffset(18);
//        mpu.setYGyroOffset(-43);
//        mpu.setZGyroOffset(-80);

}

/*
     Function to detect start of move
*/
void detectStartMove() {
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
            Serial.print(windowDiffX);
            Serial.print(" ");
            Serial.print(windowDiffY);
            Serial.print(" ");
            Serial.println(windowDiffZ);

            if (!detectedMovement && (abs(windowDiffX) > START_MOVE_THRESHOLD || abs(windowDiffY) > START_MOVE_THRESHOLD || abs(windowDiffZ) > START_MOVE_THRESHOLD)) {
                detectedMovement = true;
                lastDetectedMoveTime = micros();
            }

            // if difference between current window and previous windows has been somewhat 0 (not much movement detected)
            // for about 1.5 seconds, then we will deem it that the user has stopped moving
            if (detectedMovement) {
                if (abs(windowDiffX) > STOP_MOVE_THRESHOLD || abs(windowDiffY) > STOP_MOVE_THRESHOLD || abs(windowDiffZ) > STOP_MOVE_THRESHOLD) lastDetectedMoveTime = micros();
                else if (micros() - lastDetectedMoveTime > 1500000) detectedMovement = false;
            }
        }

        // replace values for the next loop
        prevWindowAvgX = currWindowAvgX;
        prevWindowAvgY = currWindowAvgY;
        prevWindowAvgZ = currWindowAvgZ;
        firstWindowDone = true;
    }
}

// ================================================
// ==                    Setup                   ==
// ================================================

void setup() {
    // join I2C bus (I2Cdev library doesn't do this automatically)
#if I2CDEV_IMPLEMENTATION == I2CDEV_ARDUINO_WIRE
    Wire.begin();
    Wire.setClock(400000); // 400kHz I2C clock. Comment this line if having compilation difficulties
#elif I2CDEV_IMPLEMENTATION == I2CDEV_BUILTIN_FASTWIRE
    Fastwire::setup(400, true);
#endif

    Serial.begin(115200);

    // Initialise the device
    // initially set gyro sensitivity to +/-250deg/s, and acceleration to +/-2g --> mpu6050.cpp line 58
    mpu.initialize();
    //    Serial.println(mpu.testConnection() ? "MPU6050 connection successful" : "MPU6050 connection failed");

    // Initialise DMP
    // set sampling rate to 200 Hz and gyro sensitivity to +/-2000deg/s --> mpu6050_6Axis_MotionApps20.h lines 324 and 333
    // Digital Low-Pass Filter (DLPF) with bandwidth of 42Hz --> mpu6050_6Axis_MotionApps20.h lines 330
    devStatus = mpu.dmpInitialize();

    // set sampling rate to 1000/(1+49) = 20Hz, BLE cannot support very high rates
    mpu.setRate(49);

    // Offset MPU
    calibrateMPUOffset();

    // make sure it worked (returns 0 if so)
    if (devStatus == 0) {
        // turn on the DMP, now that it's ready
        //        Serial.println(F("Enabling DMP..."));
        mpu.setDMPEnabled(true);
        dmpReady = true;

        // get expected DMP packet size for later comparison
        packetSize = mpu.dmpGetFIFOPacketSize();
    } else {
        // ERROR!
        // 1 = initial memory load failed
        // 2 = DMP configuration updates failed
        // (if it's going to break, usually the code will be 1)
        Serial.print(F("DMP Initialization failed (code "));
        Serial.print(devStatus);
        Serial.println(F(")"));
    }

    //    Serial.println("Done setting up");

    // delay by 3 seconds to let IMU stabilise
    delay(4000);
    //    Serial.println("Done stabilising");
    Serial.println("X,Y,Z");
}

// ================================================
// ==                Main Loop                   ==
// ================================================

void loop() {
    checkFIFO();
    getAccValues();
    detectStartMove();
    if (detectedMovement) Serial.println("Detected");
    else Serial.println("Not detected");
}

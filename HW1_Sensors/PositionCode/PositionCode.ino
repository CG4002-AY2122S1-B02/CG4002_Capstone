#include <Wire.h>
#include "I2Cdev.h"
#include "MPU6050_6Axis_MotionApps20.h"

// * Constants
#define NUM_SAMPLES 10
#define START_MOVE_THRESHOLD 100
#define STOP_MOVE_THRESHOLD 70

#define BAUD_RATE 115200

// * MPU related variables
MPU6050 mpu;
// MPU control/status variables
bool dmpReady = false;  // set true if DMP init was successful
uint8_t devStatus;      // return status after each device operation (0 = success, !0 = error)
uint16_t packetSize;    // expected DMP packet size (default is 42 bytes)
uint16_t fifoCount;     // count of all bytes currently in FIFO
uint8_t fifoBuffer[64]; // FIFO storage buffer

// * Orientation / Motion variables
Quaternion q;        // [w, x, y, z]         quaternion container
VectorInt16 aa;      // [x, y, z]            accel sensor measurements (includes gravity)
VectorInt16 aaReal;  // [x, y, z]            gravity-free accel sensor measurements
VectorFloat gravity; // [x, y, z]            gravity vector
float ypr[3];        // [yaw, pitch, roll]   yaw/pitch/roll container and gravity vector

int16_t AccX[NUM_SAMPLES]; // Stores NUM_SAMPLES number of the most recent real acceleration values in X axis. Acts like a window
int16_t AccY[NUM_SAMPLES]; // Stores NUM_SAMPLES number of the most recent real acceleration values in Y axis. Acts like a window
int16_t AccZ[NUM_SAMPLES]; // Stores NUM_SAMPLES number of the most recent real acceleration values in Z axis. Acts like a window
int curr_frame = 0;        // Used to indicate which frame of the window we are going to be placing the values in
bool fullWindow = false;
double prevWindowAvgX = 0;
double prevWindowAvgY = 0;
double prevWindowAvgZ = 0;

bool firstWindowDone = false;
bool detectedMovement = false;
int32_t lastDetectedMoveTime, firstDetectedMoveTime;

double windowDiffMin = -1e9, windowDiffMax = 1e9;
int32_t minTime, maxTime;

int currPosition = 2;
int left = 0, right = 0;

// *   _    _      _                   ______
// * | |  | |    | |                 |  ____|
// * | |__| | ___| |_ __   ___ _ __  | |__ _   _ _ __   ___
// * |  __  |/ _ \ | '_ \ / _ \ '__| |  __| | | | '_ \ / __|
// * | |  | |  __/ | |_) |  __/ |    | |  | |_| | | | | (__
// * |_|  |_|\___|_| .__/ \___|_|    |_|   \__,_|_| |_|\___|
// *               | |
// *               |_|

// * Function to check for FIFO buffer
void checkFIFO()
{
    mpu.resetFIFO();
    fifoCount = mpu.getFIFOCount();
    while (fifoCount < packetSize)
        fifoCount = mpu.getFIFOCount();
    mpu.getFIFOBytes(fifoBuffer, packetSize);
}

// * Function to calibrate MPU offset
void calibrateMPUOffset()
{
    // BLE 1
    mpu.setXAccelOffset(505);
    mpu.setYAccelOffset(972);
    mpu.setZAccelOffset(1078);
    mpu.setXGyroOffset(20);
    mpu.setYGyroOffset(26);
    mpu.setZGyroOffset(30);

    // BLE 2
    //        mpu.setXAccelOffset(-3114);
    //        mpu.setYAccelOffset(745);
    //        mpu.setZAccelOffset(1368);
    //        mpu.setXGyroOffset(32);
    //        mpu.setYGyroOffset(158);
    //        mpu.setZGyroOffset(-14);

    // BLE 3
    //        mpu.setXAccelOffset(785);
    //        mpu.setYAccelOffset(-481);
    //        mpu.setZAccelOffset(905);
    //        mpu.setXGyroOffset(2);
    //        mpu.setYGyroOffset(-22);
    //        mpu.setZGyroOffset(-85);
}

/*
      Function that reads sensor data values
    Function to get acceleration values in X, Y and Z axis store them in accX, accY and accZ arrays
    We will only be getting the raw values from aaReal. In order to convert it to m/s^2,
    we will have to divide the values by 8192, then multiply by g = 9.80665 m/s^2
    acceleration sensitivity is +/-2g, hence values will be 0-8192 will represent 1g and -8192-0 represents -1g
*/
void getAccValues()
{
    mpu.dmpGetQuaternion(&q, fifoBuffer);
    mpu.dmpGetAccel(&aa, fifoBuffer);
    mpu.dmpGetGravity(&gravity, &q);
    mpu.dmpGetLinearAccel(&aaReal, &aa, &gravity);
    mpu.dmpGetYawPitchRoll(ypr, &q, &gravity);

    AccX[curr_frame] = aaReal.x;
    AccY[curr_frame] = aaReal.y;
    AccZ[curr_frame] = aaReal.z;

    //    accelX = aaReal.x;
    //    accelY = aaReal.y;
    //    accelZ = aaReal.z;

    //    Serial.print(aaReal.x);
    //    Serial.print(" ");
    //    Serial.print(aaReal.y);
    //    Serial.print(" ");
    //    Serial.println(aaReal.z);

    //    rotX = ypr[0];
    //    rotY = ypr[1];
    //    rotZ = ypr[2];

    // Replace the oldest value with the newest value in the next loop
    curr_frame = (curr_frame + 1) % 10;
}

void setup()
{
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
    if (devStatus == 0)
    {
        // turn on the DMP, now that it's ready
        mpu.setDMPEnabled(true);
        dmpReady = true;

        // get expected DMP packet size for later comparisoL
        packetSize = mpu.dmpGetFIFOPacketSize();
    }

    // Delay 3 seconds to let IMU stabilise
    delay(4000);
    Serial.println("X,Y,Z");
}

// * Detect motion and check for position
void detectMotion()
{
    // once curr_frame hits NUM_SAMPLES-1 (hit window size) for the first time, then can start to perform sliding window
    if (!fullWindow && curr_frame == NUM_SAMPLES - 1)
        fullWindow = true;

    // find average of current window and compare to previous window
    if (fullWindow)
    {
        double totalAccX = 0;
        double totalAccY = 0;
        double totalAccZ = 0;
        for (int i = 0; i < NUM_SAMPLES; i++)
        {
            totalAccX += AccX[i];
            totalAccY += AccY[i];
            totalAccZ += AccZ[i];
        }

        double currWindowAvgX = totalAccX / (double)NUM_SAMPLES;
        double currWindowAvgY = totalAccY / (double)NUM_SAMPLES;
        double currWindowAvgZ = totalAccZ / (double)NUM_SAMPLES;

        // only need to calculate difference between previous and current window average after we have taken the first window
        if (firstWindowDone)
        {
            double windowDiffX = currWindowAvgX - prevWindowAvgX;
            double windowDiffY = currWindowAvgY - prevWindowAvgY;
            double windowDiffZ = currWindowAvgZ - prevWindowAvgZ;

            //            Serial.print(windowDiffX);
            //          Serial.print(" ");
            //          Serial.print(windowDiffY);
            //          Serial.print(" ");
            Serial.println(windowDiffZ);

            if (!detectedMovement && (abs(windowDiffZ) > START_MOVE_THRESHOLD))
            {
                detectedMovement = true;
                firstDetectedMoveTime = micros();
                lastDetectedMoveTime = micros();
            }

            // if difference between current window and previous windows has been somewhat 0 (not much movement detected)
            // for about 1.5 seconds, then we will deem it that the user has stopped moving
            if (detectedMovement)
            {
                if (windowDiffZ < windowDiffMin)
                {
                    windowDiffMin = windowDiffZ;
                    minTime = millis();
                }
                else if (windowDiffZ > windowDiffMax)
                {
                    windowDiffMax = windowDiffZ;
                    maxTime = millis();
                }

                // positive direction is left, negative direction is right
                if (windowDiffZ > STOP_MOVE_THRESHOLD)
                    left++;
                else if (windowDiffZ < -STOP_MOVE_THRESHOLD)
                    right++;

                if (abs(windowDiffZ) > STOP_MOVE_THRESHOLD)
                {
                    lastDetectedMoveTime = micros();

                    //          if (lastDetectedMoveTime - firstDetectedMoveTime > 800000) {
                    //            if(maxTime > minTime) Serial.println("moved left");
                    //            else Serial.println("moved right");
                    //          }
                }
                else if (micros() - lastDetectedMoveTime > 1000000)
                {
                    if (maxTime > minTime)
                        Serial.println("moved left");
                    else
                        Serial.println("moved right");

                    windowDiffMin = 1e9;
                    windowDiffMax = -1e9;
                    maxTime = millis();
                    minTime = millis();
                    detectedMovement = false;
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

void loop()
{
    checkFIFO();

    getAccValues();
    detectMotion();
}

#include "CRC.h"
#include "CRC8.h"
#include "arduinoFFT.h"

// * Constants
#define SAMPLING_FREQ 1024 // use power of 2 also, get more whole numbers
#define WINDOW_SIZE 128    // Must be power of 2

#define BAUD_RATE 115200
#define SAMPLING_PERIOD 40 // 40ms, so 25Hz
#define EMG_SAMPLING_PERIOD 10 // 10ms, so 100Hz
#define TIMESTAMP_PERIOD 5000 // 5 seconds, so 0.2Hz
#define HELLO_PACKET 'H'
#define ACK_PACKET 'A'
#define RESET_PACKET 'R'
#define EMG_PACKET 'E'

unsigned long currentTime = 0;

// * Handshake status
bool handshakeStart = false;
bool handshakeEnd = false;

// * EMG related global variables
arduinoFFT FFT = arduinoFFT();
uint32_t interval_us; // sampling interval in microsecond based on the required sampling frequency
uint32_t prevMicros = 0;
double vReal[WINDOW_SIZE];
double vImag[WINDOW_SIZE];

double MeanAbsValue;
double RootMeanSqValue;
double MeanFreq;
double MedianFreq;
int16_t emgData;

// * Buffer related
byte twoByteBuf[2];
byte fourByteBuf[4];

// * CRC Related
CRC8 crc;


// *   _____ ______ _   _ _____    ______ _    _ _   _  _____
// *  / ____|  ____| \ | |  __ \  |  ____| |  | | \ | |/ ____|
// * | (___ | |__  |  \| | |  | | | |__  | |  | |  \| | |
// *  \___ \|  __| | . ` | |  | | |  __| | |  | | . ` | |
// *  ____) | |____| |\  | |__| | | |    | |__| | |\  | |____
// * |_____/|______|_| \_|_____/  |_|     \____/|_| \_|\_____|
//

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

// * Total 8 bytes + 12 bytes padding
// * MeanAbsValue (2 bytes) and RootMeanSqValue (2 bytes) and MedianFreq (2 bytes)
void sendEMGPacket() {
    int convertedMeanAbsValue = (int) (MeanAbsValue);
    int convertedRootMeanSqValue = (int) (RootMeanSqValue);
    int convertedMedianFreq = (int) (MedianFreq);

    // One byte packet type and add to CRC
    Serial.write(EMG_PACKET);
    crc.add(EMG_PACKET);

    // 6 bytes EMG data
    writeIntToSerial(convertedMeanAbsValue);
    writeIntToSerial(convertedRootMeanSqValue);
    writeIntToSerial(convertedMedianFreq);

    Serial.write(crc.getCRC()); // One byte checksum

    // Padding
    padPacket(12);

    crc.restart();

    Serial.flush();
}

// *   _    _      _                   ______
// * | |  | |    | |                 |  ____|
// * | |__| | ___| |_ __   ___ _ __  | |__ _   _ _ __   ___
// * |  __  |/ _ \ | '_ \ / _ \ '__| |  __| | | | '_ \ / __|
// * | |  | |  __/ | |_) |  __/ |    | |  | |_| | | | | (__
// * |_|  |_|\___|_| .__/ \___|_|    |_|   \__,_|_| |_|\___|
// *               | |
// *               |_|

// * Function to collect values into window for analysis
// * Also calculate the Mean Absolute Value (MAV) and Root Mean Square(RMS) in the function
void collectData() {
    double totalAbsValue = 0;
    double totalSqValue = 0;

    for (int i = 0; i < WINDOW_SIZE; ) {
        // only collect one value after 1ms, hence making the sampling frequency 1kHz
        // micros() used instead of millis() as it gives more precise values
        if (micros() - prevMicros > interval_us) {
            double sensorValue = analogRead(A3);
//            double voltage = sensorValue * (5.0 / 1023.0);
            vReal[i] = sensorValue;
            vImag[i] = 0;

            totalAbsValue += abs(sensorValue);
            totalSqValue += sq(sensorValue);

            // only add to i after 1 interval has passed since we are reading every interval
            i++;

            prevMicros = micros();
        }
    }

    MeanAbsValue = totalAbsValue / (double) WINDOW_SIZE;
    RootMeanSqValue = sqrt(totalSqValue / (double)WINDOW_SIZE);
}

// * Function to convert time domain to frequency domain using FFT
// * and retrieve Mean Frequency (MNF) and Median Frequency (MDF)
void calculateFFT() {
    FFT.Windowing(vReal, WINDOW_SIZE, FFT_WIN_TYP_HAMMING, FFT_FORWARD);
    FFT.Compute(vReal, vImag, WINDOW_SIZE, FFT_FORWARD);
    FFT.ComplexToMagnitude(vReal, vImag, WINDOW_SIZE);

    double totalPSD = 0;
    double totalFreqPSD = 0;

    // Take half the samples only due to Nyquist-Shannon Sampling Theorem,
    // we can only detect frequencies up to half the sampling frequency
    // frequencies have been divided into their separate distinct bins from 0 to WINDOW_SIZE/2
    for (int i = 0; i < WINDOW_SIZE / 2; i++) {
        // vReal^2 will give us the PSD for that frequency bin
        double currPSD = sq(vReal[i]);
        totalPSD += currPSD;
        double currFreq = (i * (double)SAMPLING_FREQ) / (double)WINDOW_SIZE;
        totalFreqPSD += (currFreq * currPSD);
    }

    // ! meanFreq and medianFreq currently not used yet
    double meanFreq = totalFreqPSD / totalPSD;
    meanFreq -= 1;
    meanFreq *= 100;

    double medianFreq = totalPSD / 2.0;
    // scale the median frequency down
    medianFreq = medianFreq /= 1000000.0;
    MedianFreq = medianFreq;
}

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

// * Write 4 byte long to Serial
void writeLongToSerial(long data) {
    fourByteBuf[3] = data & 255;
    fourByteBuf[2] = (data >> 8) & 255;
    fourByteBuf[1] = (data >> 16) & 255;
    fourByteBuf[0] = (data >> 24) & 255;
    Serial.write(fourByteBuf, sizeof(fourByteBuf));
    crc.add(fourByteBuf, sizeof(fourByteBuf));
}

// * Reset Beetle Programmatically
void (* resetBeetle) (void) = 0;

// * Pad BLE packet with 0s so that it is 20 bytes long
void padPacket(int length) {
    for (int i = 0; i < length; i++) {
        Serial.write(0);
    }
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
}

void loop() {
    currentTime = millis();
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

        collectData();
        calculateFFT();
        sendEMGPacket();

    }

}

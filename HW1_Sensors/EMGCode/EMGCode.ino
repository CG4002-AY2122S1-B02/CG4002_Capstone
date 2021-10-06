/*
    Recommended sampling frequency is 1000Hz, hence time interval is 1ms = 1000microseconds
    Window size for smoothening/filtering is generally between 100ms - 300ms

    https://www.ncbi.nlm.nih.gov/pmc/articles/PMC6679263/

    Features extracted using EMG to detect muscle fatigue:
    - Mean Absolute Value (MAV)
    - Root Mean Square (RMS)
    - Mean Frequency (MEF)
    - Median Frequency (MDF)

    Since analog samples are in time domain, we will need to convert them to frequency domain to find MNF and MDF
    We can use the Fast Fourier Transform (FFT) algorithm to convert to Discrete Fourier Transform (DFT)
    FFT computes in O(NlogN) instead of normal DFT at O(N^2)

    https://www.norwegiancreations.com/2017/08/what-is-fft-and-how-can-you-implement-it-on-an-arduino/
*/
#include "arduinoFFT.h"

#define SAMPLING_FREQ 1024      // use power of 2 also, get more whole numbers
#define WINDOW_SIZE 128         // Must be power of 2

arduinoFFT FFT = arduinoFFT();

uint32_t interval_us;           // sampling interval in microsecond based on the required sampling frequency
uint32_t prevMicros = 0;
double vReal[WINDOW_SIZE];
double vImag[WINDOW_SIZE];

// ================================================
// ==                 Functions                  ==
// ================================================

/*
    Function to collect values into window for analysis
    We also calculate the Mean Absolute Value (MAV) and Root Mean Square(RMS) in the function
*/
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

    double MeanAbsValue = totalAbsValue / (double) WINDOW_SIZE;
    double RootMeanSqValue = sqrt(totalSqValue / (double)WINDOW_SIZE);

//    Serial.println(MeanAbsValue);
//    Serial.print(" ");
//    Serial.println(RootMeanSqValue);
//    Serial.print(" ");
}

/*
    Function to convert time domain to frequency domain using FFT and retrieve Mean Frequency (MNF)
    and Median Frequency (MDF)
*/
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

    double meanFreq = totalFreqPSD / totalPSD;
    meanFreq -= 1;
    meanFreq *= 100;
    
    double medianFreq = totalPSD / 2.0;
    // scale the median frequency down
    medianFreq = medianFreq /= 1000000.0;

//    Serial.println(meanFreq);
//    Serial.print(" ");
    Serial.println(medianFreq);
    
}

// ================================================
// ==                    Setup                   ==
// ================================================
void setup() {
    Serial.begin(115200);
    interval_us = round(1000000 * (1.0 / SAMPLING_FREQ));

//    Serial.println("MAV,RMS,MNF,MDF");
}

// ================================================
// ==                Main Loop                   ==
// ================================================
void loop() {
    collectData();
    calculateFFT();
}

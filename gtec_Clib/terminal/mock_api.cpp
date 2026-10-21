// Test-only simulated DLL. Never link this into the hardware executable.
#include "unicorn.h"
#include <cstring>
#include <thread>
#include <chrono>
#include <cstdlib>
#include <string>
static bool acquiring = false;
static uint32_t counter = 0;
#ifdef UNICORN_SESSION_TEST
static constexpr int channelCount = 11;
#else
static constexpr int channelCount = 4;
#endif
float UNICORN_GetApiVersion() { return 1; }
const char* UNICORN_GetLastErrorText() { return "simulated error"; }
int UNICORN_GetBluetoothAdapterInfo(UNICORN_BLUETOOTH_ADAPTER_INFO* b) { *b = {}; return 0; }
int UNICORN_GetAvailableDevices(UNICORN_DEVICE_SERIAL* d, uint32_t* n, BOOL) {
    if (d) std::strcpy(d[0], "MOCK"); *n = 1; return 0;
}
int UNICORN_OpenDevice(const char*, UNICORN_HANDLE* h) { *h = 1; return 0; }
int UNICORN_CloseDevice(UNICORN_HANDLE* h) { *h = 0; return 0; }
int UNICORN_StartAcquisition(UNICORN_HANDLE, BOOL) { acquiring = true; counter = 0; return 0; }
int UNICORN_StopAcquisition(UNICORN_HANDLE) { acquiring = false; return 0; }
int UNICORN_GetConfiguration(UNICORN_HANDLE, UNICORN_AMPLIFIER_CONFIGURATION* c) {
    *c = {};
    const char* names[] = {"EEG 1", "Counter", "Battery Level", "Validation Indicator"};
    for (int i = 0; i < channelCount; ++i) {
#ifdef UNICORN_SESSION_TEST
        std::string name = i < 8 ? "EEG "+std::to_string(i+1) : names[i-7];
        std::strcpy(c->Channels[i].name, name.c_str());
        std::strcpy(c->Channels[i].unit, i < 8 ? "uV" : "count");
#else
        std::strcpy(c->Channels[i].name, names[i]);
#endif
        c->Channels[i].enabled = TRUE;
    }
    if (std::getenv("UNICORN_MOCK_MISSING_CHANNEL")) c->Channels[0].enabled = FALSE;
    return 0;
}
int UNICORN_SetConfiguration(UNICORN_HANDLE, UNICORN_AMPLIFIER_CONFIGURATION*) { return 0; }
int UNICORN_GetNumberOfAcquiredChannels(UNICORN_HANDLE, uint32_t* n) { *n = channelCount; return 0; }
int UNICORN_GetChannelIndex(UNICORN_HANDLE, const char* name, uint32_t* index) {
    UNICORN_AMPLIFIER_CONFIGURATION c{}; UNICORN_GetConfiguration(1, &c);
    for (uint32_t i = 0; i < channelCount; ++i) if (!std::strcmp(name, c.Channels[i].name)) { *index = i; return 0; }
    return 1;
}
int UNICORN_GetData(UNICORN_HANDLE, uint32_t scans, float* data, uint32_t length) {
    if (!acquiring || length < scans*channelCount*sizeof(float)) return 1;
    std::this_thread::sleep_for(std::chrono::milliseconds(scans*4));
    if (std::getenv("UNICORN_MOCK_FAIL")) return UNICORN_ERROR_CONNECTION_PROBLEM;
    for (uint32_t s = 0; s < scans; ++s) {
        for (int i = 0; i < channelCount-3; ++i) data[s*channelCount+i] = 1.5f;
        data[s*channelCount+channelCount-3] = float(counter++);
        data[s*channelCount+channelCount-2] = 80; data[s*channelCount+channelCount-1] = 1;
    }
    return 0;
}
int UNICORN_GetDeviceInformation(UNICORN_HANDLE, UNICORN_DEVICE_INFORMATION* d) { *d = {}; std::strcpy(d->serial,"MOCK"); return 0; }
int UNICORN_SetDigitalOutputs(UNICORN_HANDLE, uint8_t) { return 0; }
int UNICORN_GetDigitalOutputs(UNICORN_HANDLE, uint8_t* value) { *value = 0; return 0; }

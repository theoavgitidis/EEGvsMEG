#include "unicorn.h"
#ifdef _WIN32
#define NOMINMAX
#include <windows.h>
#endif
#include <iostream>
#include <sstream>
#include <string>
#include <vector>
#include <fstream>
#include <iomanip>
#include <stdexcept>
#include <memory>

static void check(int code) {
    if (code != UNICORN_ERROR_SUCCESS) {
        const char* error = UNICORN_GetLastErrorText();
        throw std::runtime_error("API error " + std::to_string(code) + ": " + (error ? error : "no text"));
    }
}
#include "recorder.h"
#include "experiments.h"
static void help() {
    std::cout <<
        "NewExp NAME | GoToExp NAME | ListExp | Where\n"
        "version | error | bluetooth | scan paired|unpaired\n"
        "open SERIAL | close | info | config | channels | index CHANNEL NAME\n"
        "enable CONFIG_INDEX 0|1   (indices 0..16; acquisition stopped)\n"
        "start real|test | read SCANS [CSV_NAME] | stop\n"
        "record SECONDS CSV_NAME [real|test] (0 = until stop)\n"
        "mark LABEL | status (background recorder)\n"
        "outputs | outputs VALUE (0..255) | help | quit\n"
        "read accepts 1..2500 scans; CSV filenames stay in the active experiment; existing files are refused.\n"
        "Pair the headset in Windows or Unicorn Suite before opening it.\n";
}
int main() {
#ifdef _WIN32
    SetConsoleCP(CP_UTF8); SetConsoleOutputCP(CP_UTF8);
#endif
    Experiments experiments;
    UNICORN_HANDLE handle = 0;
    bool opened = false, acquiring = false;
    Recorder recorder;
    auto stop = [&]() { recorder.stop(); if (acquiring) { check(UNICORN_StopAcquisition(handle)); acquiring = false; } };
    auto close = [&]() { if (opened) { stop(); check(UNICORN_CloseDevice(&handle)); opened = false; } };
    std::cout << "Unicorn API terminal (250 Hz). Type help for commands.\n";
    help();
    std::string line;
    while (std::cout << experiments.prompt() && std::getline(std::cin, line)) {
        try {
            std::istringstream in(line);
            std::string cmd; in >> cmd;
            if (cmd.empty()) continue;
            std::transform(cmd.begin(), cmd.end(), cmd.begin(), [](unsigned char c) { return char(std::tolower(c)); });
            if (cmd == "where") { experiments.where(); continue; }
            if (cmd == "listexp") { experiments.list(); continue; }
            if (cmd == "newexp" || cmd == "gotoexp") {
                if (acquiring || recorder.active()) throw std::runtime_error("Stop acquisition before changing experiments.");
                experiments.select(in, cmd == "newexp"); continue;
            }
            if (cmd == "quit" || cmd == "exit") break;
            if (cmd == "help") { help(); continue; }
            if (cmd == "status") { recorder.status(); continue; }
            if (cmd == "mark") {
                std::string label; std::getline(in >> std::ws, label);
                if (label.empty()) throw std::runtime_error("Use mark LABEL");
                recorder.mark(label); continue;
            }
            if (recorder.active() && cmd != "stop" && cmd != "close")
                throw std::runtime_error("Background recording active. Use mark, status, stop, close, help or quit.");
            if (!recorder.active()) recorder.stop(); // join completed timed recordings
            if (cmd == "version") { std::cout << UNICORN_GetApiVersion() << '\n'; continue; }
            if (cmd == "error") {
                const char* text = UNICORN_GetLastErrorText();
                std::cout << (text ? text : "No error text") << '\n'; continue;
            }
            if (cmd == "bluetooth") {
                UNICORN_BLUETOOTH_ADAPTER_INFO b{};
                check(UNICORN_GetBluetoothAdapterInfo(&b));
                std::cout << "Name: " << b.name << "\nManufacturer: " << b.manufacturer
                    << "\nRecommended: " << b.isRecommendedDevice << "\nProblem: " << b.hasProblem << '\n';
                continue;
            }
            if (cmd == "scan") {
                std::string mode; in >> mode;
                if (mode != "paired" && mode != "unpaired") throw std::runtime_error("Use scan paired|unpaired");
                uint32_t count = 0;
                BOOL paired = mode == "paired" ? TRUE : FALSE;
                check(UNICORN_GetAvailableDevices(nullptr, &count, paired));
                if (!count) { std::cout << "No devices found.\n"; continue; }
                std::unique_ptr<UNICORN_DEVICE_SERIAL[]> devices(new UNICORN_DEVICE_SERIAL[count]{});
                check(UNICORN_GetAvailableDevices(devices.get(), &count, paired));
                for (uint32_t i = 0; i < count; ++i) std::cout << devices[i] << '\n';
                continue;
            }
            if (cmd == "open") {
                if (opened) throw std::runtime_error("Close the current device first.");
                std::string serial; in >> serial;
                if (serial.empty()) throw std::runtime_error("Use open SERIAL");
                check(UNICORN_OpenDevice(serial.c_str(), &handle)); opened = true;
                std::cout << "Connected.\n"; continue;
            }
            if (!opened) throw std::runtime_error("Open a device first (or use help).");
            if (cmd == "close") { close(); std::cout << "Disconnected.\n"; }
            else if (cmd == "info") {
                UNICORN_DEVICE_INFORMATION d{}; check(UNICORN_GetDeviceInformation(handle, &d));
                std::cout << "Serial: " << d.serial << "\nFirmware: " << d.firmwareVersion
                    << "\nDevice version: " << d.deviceVersion << "\nEEG channels: " << d.numberOfEegChannels << '\n';
                std::cout << "PCB:"; for (auto x : d.pcbVersion) std::cout << ' ' << unsigned(x);
                std::cout << "\nEnclosure:"; for (auto x : d.enclosureVersion) std::cout << ' ' << unsigned(x);
                std::cout << '\n';
            } else if (cmd == "config" || cmd == "enable") {
                UNICORN_AMPLIFIER_CONFIGURATION c{}; check(UNICORN_GetConfiguration(handle, &c));
                if (cmd == "enable") {
                    int index, value;
                    if (!(in >> index >> value) || index < 0 || index >= UNICORN_TOTAL_CHANNELS_COUNT || (value != 0 && value != 1))
                        throw std::runtime_error("Use enable CONFIG_INDEX 0|1 (index 0..16)");
                    if (acquiring) throw std::runtime_error("Stop acquisition before changing configuration.");
                    c.Channels[index].enabled = value;
                    check(UNICORN_SetConfiguration(handle, &c));
                    check(UNICORN_GetConfiguration(handle, &c));
                }
                for (int i = 0; i < UNICORN_TOTAL_CHANNELS_COUNT; ++i) {
                    const auto& ch = c.Channels[i];
                    std::cout << i << ": " << ch.name << " [" << ch.unit << "] range "
                        << ch.range[0] << ".." << ch.range[1] << " enabled=" << ch.enabled << '\n';
                }
            } else if (cmd == "channels") {
                uint32_t n = 0; check(UNICORN_GetNumberOfAcquiredChannels(handle, &n)); std::cout << n << '\n';
            } else if (cmd == "index") {
                std::string name; std::getline(in >> std::ws, name);
                if (name.empty()) throw std::runtime_error("Use index CHANNEL NAME");
                uint32_t index = 0; check(UNICORN_GetChannelIndex(handle, name.c_str(), &index)); std::cout << index << '\n';
            } else if (cmd == "record") {
                double seconds; std::string path, mode = "real";
                if (!(in >> seconds >> std::quoted(path, '"', '\0')) || !std::isfinite(seconds) || seconds < 0 || seconds > 86400 || path.empty())
                    throw std::runtime_error("Use record SECONDS CSV_NAME [real|test], 0..86400 seconds");
                in >> mode;
                if (mode != "real" && mode != "test") throw std::runtime_error("Mode must be real or test.");
                if (acquiring) throw std::runtime_error("Stop manual acquisition first.");
                uint64_t target = seconds == 0 ? 0 : uint64_t(std::ceil(seconds * UNICORN_SAMPLING_RATE));
                auto destination = experiments.output(path);
                recorder.start(handle, destination, target, mode == "test");
                path = destination.u8string();
                std::cout << "Background recording started: " << path << " (events: " << path << ".events.csv).\n";
            } else if (cmd == "start") {
                std::string mode; in >> mode;
                if (mode != "real" && mode != "test") throw std::runtime_error("Use start real|test");
                if (acquiring) throw std::runtime_error("Already acquiring.");
                experiments.require();
                check(UNICORN_StartAcquisition(handle, mode == "test" ? TRUE : FALSE)); acquiring = true;
                std::cout << "Started. Read promptly: the API buffer can overflow while waiting for commands.\n";
            } else if (cmd == "stop") { stop(); std::cout << "Stopped.\n"; }
            else if (cmd == "read") {
                int scans; std::string path;
                if (!(in >> scans) || scans < 1 || scans > 2500) throw std::runtime_error("Use read SCANS [CSV_NAME], 1..2500");
                if (!acquiring) throw std::runtime_error("Start acquisition first.");
                in >> std::ws;
                if (!in.eof() && !(in >> std::quoted(path, '"', '\0')))
                    throw std::runtime_error("Use read SCANS [CSV_NAME]; close quoted filenames.");
                uint32_t n = 0; check(UNICORN_GetNumberOfAcquiredChannels(handle, &n));
                if (!n || n > UNICORN_TOTAL_CHANNELS_COUNT) throw std::runtime_error("Unexpected channel count.");
                uint32_t floats = uint32_t(scans) * n;
                // Vendor example passes bytes, header says floats. Reserve enough for
                // either interpretation while passing the vendor example's byte count.
                uint32_t length = floats * sizeof(float);
                std::vector<float> data(length);
                std::ofstream file;
                if (!path.empty()) { file.open(experiments.output(path)); if (!file) throw std::runtime_error("Cannot open CSV file."); }
                check(UNICORN_GetData(handle, uint32_t(scans), data.data(), length));
                if (file) {
                    UNICORN_AMPLIFIER_CONFIGURATION c{}; check(UNICORN_GetConfiguration(handle, &c));
                    std::vector<std::string> names(n);
                    for (const auto& ch : c.Channels) if (ch.enabled) {
                        uint32_t index = 0; check(UNICORN_GetChannelIndex(handle, ch.name, &index));
                        if (index >= n) throw std::runtime_error("Unexpected channel index.");
                        names[index] = ch.name;
                    }
                    for (uint32_t j = 0; j < n; ++j) file << (j ? "," : "") << names[j];
                    file << '\n' << std::setprecision(9);
                }
                for (int s = 0; s < scans; ++s) {
                    if (s < 5) {
                        std::cout << "Scan " << s << ':';
                        for (uint32_t j = 0; j < n; ++j) std::cout << ' ' << data[s*n+j];
                        std::cout << '\n';
                    }
                    if (file) { for (uint32_t j = 0; j < n; ++j) file << (j ? "," : "") << data[s*n+j]; file << '\n'; }
                }
                if (file.is_open()) { file.flush(); if (!file) throw std::runtime_error("CSV write failed."); }
                std::cout << "Read " << scans << " scans, " << n << " channels.\n";
            } else if (cmd == "outputs") {
                in >> std::ws;
                if (!in.eof()) {
                    int value;
                    if (!(in >> value) || value < 0 || value > 255) throw std::runtime_error("Use outputs VALUE, 0..255");
                    check(UNICORN_SetDigitalOutputs(handle, uint8_t(value)));
                }
                uint8_t value = 0; check(UNICORN_GetDigitalOutputs(handle, &value)); std::cout << unsigned(value) << '\n';
            } else throw std::runtime_error("Unknown command. Type help.");
        } catch (const std::exception& e) { std::cerr << e.what() << '\n'; }
    }
    try { close(); } catch (const std::exception& e) { std::cerr << "Cleanup: " << e.what() << '\n'; return 1; }
    return 0;
}

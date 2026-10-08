#pragma once
#include <atomic>
#include <chrono>
#include <cmath>
#include <filesystem>
#include <mutex>
#include <thread>

// The worker exclusively owns API calls while recording. Terminal commands
// use cached status and a separate event file; they never touch the DLL.
class Recorder {
    std::thread worker;
    std::atomic<bool> cancel{false}, running{false};
    mutable std::mutex mutex;
    uint64_t samples = 0, discontinuities = 0;
    float battery = 0, validation = 0;
    bool hasBattery = false, hasValidation = false;
    std::string failure;
    std::ofstream events;
    std::chrono::steady_clock::time_point origin;
    static double utc() {
        return std::chrono::duration<double>(std::chrono::system_clock::now().time_since_epoch()).count();
    }
    double elapsed() const {
        return std::chrono::duration<double>(std::chrono::steady_clock::now()-origin).count();
    }
    static std::string csv(std::string text) {
        std::string out = "\"";
        for (char c : text) { if (c == '"') out += '"'; out += c; }
        return out + '"';
    }
public:
    ~Recorder() { stop(); }
    bool active() const { return running.load(); }
    void stop() {
        cancel = true;
        if (worker.joinable()) worker.join();
        if (events.is_open()) { events.flush(); events.close(); }
    }
    void status() const {
        std::lock_guard<std::mutex> lock(mutex);
        std::cout << "Recording: " << running << " samples=" << samples
            << " nominal_seconds=" << samples / double(UNICORN_SAMPLING_RATE)
            << " counter_discontinuities=" << discontinuities;
        if (hasBattery) std::cout << " battery=" << battery;
        if (hasValidation) std::cout << " validation=" << validation;
        if (!failure.empty()) std::cout << " error=" << failure;
        std::cout << '\n';
    }
    void mark(const std::string& label) {
        std::lock_guard<std::mutex> lock(mutex);
        if (!running) throw std::runtime_error("No background recording is active.");
        events << std::setprecision(17) << utc() << ',' << elapsed() << ',' << samples << ',' << csv(label) << '\n';
        events.flush();
        if (!events) throw std::runtime_error("Event log write failed.");
    }
    void start(UNICORN_HANDLE handle, const std::string& path, uint64_t target, bool test) {
        stop();
        if (std::filesystem::exists(path) || std::filesystem::exists(path + ".events.csv"))
            throw std::runtime_error("Recording files already exist; choose a new path.");
        uint32_t n = 0; check(UNICORN_GetNumberOfAcquiredChannels(handle, &n));
        if (!n || n > UNICORN_TOTAL_CHANNELS_COUNT) throw std::runtime_error("Unexpected channel count.");
        UNICORN_AMPLIFIER_CONFIGURATION config{}; check(UNICORN_GetConfiguration(handle, &config));
        std::vector<std::string> names(n);
        int counterIndex = -1, batteryIndex = -1, validationIndex = -1;
        for (const auto& ch : config.Channels) if (ch.enabled) {
            uint32_t index = 0; check(UNICORN_GetChannelIndex(handle, ch.name, &index));
            if (index >= n) throw std::runtime_error("Unexpected channel index.");
            names[index] = ch.name;
            if (std::string(ch.name) == "Counter") counterIndex = int(index);
            if (std::string(ch.name) == "Battery Level") batteryIndex = int(index);
            if (std::string(ch.name) == "Validation Indicator") validationIndex = int(index);
        }
        std::ofstream data(path);
        if (!data) throw std::runtime_error("Cannot create recording file.");
        events.open(path + ".events.csv");
        if (!events) throw std::runtime_error("Cannot create event log.");
        data << "sample_index,nominal_time_s,host_read_utc_s";
        for (const auto& name : names) data << ',' << csv(name);
        data << '\n' << std::setprecision(17);
        events << "host_utc_s,elapsed_s,samples_received,label\n";
        data.flush(); events.flush();
        if (!data || !events) throw std::runtime_error("Cannot write recording headers.");
        { std::lock_guard<std::mutex> lock(mutex);
          samples = discontinuities = 0; failure.clear(); hasBattery = hasValidation = false; }
        origin = std::chrono::steady_clock::now();
        check(UNICORN_StartAcquisition(handle, test ? TRUE : FALSE));
        cancel = false; running = true;
        try {
            worker = std::thread([this, handle, target, n, counterIndex, batteryIndex, validationIndex,
                                  data = std::move(data)]() mutable {
                uint64_t total = 0;
                float previous = 0; bool havePrevious = false;
                auto lastFlush = std::chrono::steady_clock::now();
                try {
                    while (!cancel && (!target || total < target)) {
                        uint32_t scans = 25;
                        if (target && target-total < scans) scans = uint32_t(target-total);
                        const uint32_t length = scans * n * sizeof(float);
                        std::vector<float> buffer(length); // accommodates vendor length ambiguity
                        check(UNICORN_GetData(handle, scans, buffer.data(), length));
                        double received = utc(); uint64_t gaps = 0;
                        for (uint32_t s = 0; s < scans; ++s) {
                            const float* row = buffer.data() + s*n;
                            if (counterIndex >= 0) {
                                float current = row[counterIndex];
                                if (havePrevious && current != previous + 1) ++gaps;
                                previous = current; havePrevious = true;
                            }
                            data << total << ',' << total/double(UNICORN_SAMPLING_RATE) << ',' << received;
                            for (uint32_t j = 0; j < n; ++j) data << ',' << row[j];
                            data << '\n'; ++total;
                        }
                        if (std::chrono::steady_clock::now()-lastFlush >= std::chrono::seconds(1)) {
                            data.flush(); lastFlush = std::chrono::steady_clock::now();
                        }
                        if (!data) throw std::runtime_error("Recording write failed.");
                        { std::lock_guard<std::mutex> lock(mutex);
                          samples = total; discontinuities += gaps;
                          if (batteryIndex >= 0) { battery = buffer[(scans-1)*n+batteryIndex]; hasBattery = true; }
                          if (validationIndex >= 0) { validation = buffer[(scans-1)*n+validationIndex]; hasValidation = true; } }
                    }
                    data.flush();
                    if (!data) throw std::runtime_error("Recording flush failed.");
                } catch (const std::exception& e) {
                    std::lock_guard<std::mutex> lock(mutex); failure = e.what();
                }
                try { check(UNICORN_StopAcquisition(handle)); }
                catch (const std::exception& e) {
                    std::lock_guard<std::mutex> lock(mutex); failure += std::string(" Stop: ") + e.what();
                }
                running = false;
            });
        } catch (...) { running = false; UNICORN_StopAcquisition(handle); throw; }
    }
};

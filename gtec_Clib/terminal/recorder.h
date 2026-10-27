#pragma once
#include <atomic>
#include <chrono>
#include <cmath>
#include <filesystem>
#include <mutex>
#include <thread>
#include <condition_variable>
#include <cstdlib>
#include "worker_process.h"

// The worker exclusively owns API calls while recording. Terminal commands
// use cached status and a separate event file; they never touch the DLL.
class Recorder {
    WorkerProcess child;
    std::thread worker;
    std::atomic<bool> cancel{false}, running{false};
    mutable std::mutex mutex;
    uint64_t samples = 0, discontinuities = 0;
    float battery = 0, validation = 0;
    bool hasBattery = false, hasValidation = false;
    std::string failure;
    std::ofstream events;
    bool extendedEvents = false;
    bool oscar = false, ready = false, done = false;
    uint64_t cleanedSamples = 0;
    int delaySamples = 0;
    std::condition_variable startup;
    std::chrono::steady_clock::time_point lastStatus;
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
    struct Snapshot { bool running; uint64_t samples, discontinuities; std::string failure; bool oscar; uint64_t cleanedSamples; int delaySamples; };
    Snapshot snapshot() const {
        std::lock_guard<std::mutex> lock(mutex);
        if (oscar && running && std::chrono::steady_clock::now()-lastStatus > std::chrono::seconds(6))
            return {false,samples,discontinuities,"OSCAR worker status timed out.",oscar,cleanedSamples,delaySamples};
        return {running.load(), samples, discontinuities, failure, oscar, cleanedSamples, delaySamples};
    }
    struct Context {
        std::string source = "manual", run, condition, phase, reason;
        int block = 0, trial = 0, attempt = 0, startNumber = 0;
        double planned = 0, actual = 0;
    };
    void stop() {
        cancel = true;
        if (child.active()) {
            child.requestStop();
            if (!child.wait(8000)) {
                { std::lock_guard<std::mutex> lock(mutex); failure = "OSCAR worker shutdown timed out."; }
                child.kill(); child.wait(1000);
            }
            if (!child.successful()) { std::lock_guard<std::mutex> lock(mutex); if (failure.empty()) failure="OSCAR worker returned a nonzero exit code."; }
        }
        if (worker.joinable()) worker.join();
        child.dispose();
        if (events.is_open()) { events.flush(); events.close(); }
    }
    void status() const {
        std::lock_guard<std::mutex> lock(mutex);
        std::cout << "Recording: " << running << " samples=" << samples
            << " nominal_seconds=" << samples / double(UNICORN_SAMPLING_RATE)
            << " counter_discontinuities=" << discontinuities;
        std::cout << " processing=" << (oscar ? "OSCAR" : "RAW");
        if (oscar) std::cout << " oscar_samples=" << cleanedSamples << " oscar_delay_samples=" << delaySamples;
        if (hasBattery) std::cout << " battery=" << battery;
        if (hasValidation) std::cout << " validation=" << validation;
        if (!failure.empty()) std::cout << " error=" << failure;
        std::cout << '\n';
    }
    void mark(const std::string& label) { mark(label, Context{}); }
    void mark(const std::string& label, const Context& context, bool finalEvent = false) {
        std::lock_guard<std::mutex> lock(mutex);
        if (!running && !(finalEvent && events.is_open())) throw std::runtime_error("No background recording is active.");
        events << std::setprecision(17) << utc() << ',' << elapsed() << ',' << samples << ',' << csv(label);
        if (extendedEvents) events << ',' << csv(context.source) << ',' << csv(context.run)
            << ',' << context.block << ',' << context.trial << ',' << context.attempt
            << ',' << csv(context.condition) << ',' << csv(context.phase) << ',' << context.planned
            << ',' << context.actual << ',' << csv(context.reason) << ',' << context.startNumber << ',' << (context.startNumber ? 7 : 0);
        events << '\n';
        events.flush();
        if (!events) throw std::runtime_error("Event log write failed.");
    }
    void start(UNICORN_HANDLE handle, const std::filesystem::path& path, uint64_t target, bool test, bool extended = false) {
        stop();
        oscar = false; cleanedSamples = 0; delaySamples = 0;
        extendedEvents = extended;
        auto eventPath = path; eventPath += ".events.csv";
        if (std::filesystem::exists(path) || std::filesystem::exists(eventPath))
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
        events.open(eventPath);
        if (!events) throw std::runtime_error("Cannot create event log.");
        data << "sample_index,nominal_time_s,host_read_utc_s";
        for (const auto& name : names) data << ',' << csv(name);
        data << '\n' << std::setprecision(17);
        events << "host_utc_s,elapsed_s,samples_received,label";
        if (extendedEvents) events << ",source,run,block,trial,attempt,condition,phase,planned_elapsed_s,actual_session_elapsed_s,reason,start_number,subtract";
        events << '\n';
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
    void startOscar(const std::string& serial, const std::filesystem::path& path) {
        stop();
        for (const auto& suffix : {"", ".events.csv", ".oscar.csv", ".processing.json", ".device.json", ".worker.log"}) {
            auto candidate=path; candidate+=suffix;
            if (std::filesystem::exists(candidate)) throw std::runtime_error("Recording files already exist; choose a new path.");
        }
        std::filesystem::path script;
#ifdef _WIN32
        if (auto value=_wgetenv(L"EEG_OSCAR_WORKER")) script=value;
#else
        if (auto value=std::getenv("EEG_OSCAR_WORKER")) script=std::filesystem::u8path(value);
#endif
#ifdef EEG_OSCAR_WORKER
        else script=std::filesystem::u8path(EEG_OSCAR_WORKER);
#else
        else script=std::filesystem::path("acquisition")/"oscar_worker.py";
#endif
        if (!std::filesystem::is_regular_file(script)) throw std::runtime_error("OSCAR worker missing; set EEG_OSCAR_WORKER to acquisition/oscar_worker.py.");
        std::string python="python";
#ifdef _WIN32
        if (auto value=_wgetenv(L"EEG_OSCAR_PYTHON")) python=std::filesystem::path(value).u8string();
#else
        if (auto value=std::getenv("EEG_OSCAR_PYTHON")) python=value;
#endif
        auto eventPath=path; eventPath+=".events.csv";
        events.open(eventPath);
        if (!events) throw std::runtime_error("Cannot create event log.");
        events << "host_utc_s,elapsed_s,samples_received,label,source,run,block,trial,attempt,condition,phase,planned_elapsed_s,actual_session_elapsed_s,reason,start_number,subtract\n";
        events.flush();
        if (!events) throw std::runtime_error("Cannot write event log header.");
        {
            std::lock_guard<std::mutex> lock(mutex);
            samples=discontinuities=cleanedSamples=0; failure.clear(); ready=done=false; oscar=true;
            delaySamples=0; hasBattery=hasValidation=false; extendedEvents=true;
            lastStatus=std::chrono::steady_clock::now();
        }
        origin=std::chrono::steady_clock::now(); cancel=false;
        child.start(python,script,serial,path);
        worker=std::thread([this]() {
            try {
                std::string line;
                while (child.line(line)) {
                    std::lock_guard<std::mutex> lock(mutex);
                    std::istringstream input(line); std::string type; input>>type;
                    lastStatus=std::chrono::steady_clock::now();
                    if (type == "READY") {
                        int version=0, delay=0; std::string extra;
                        if (!(input>>version>>delay) || version != 1 || delay <= 0 || ready || (input>>extra)) throw std::runtime_error("Invalid OSCAR READY protocol.");
                        ready=true; delaySamples=delay; running=true; startup.notify_all();
                    } else if (type == "SAMPLES") {
                        uint64_t raw=0, clean=0; std::string extra;
                        if (!(input>>raw>>clean) || raw < samples || clean < cleanedSamples || clean > raw || (input>>extra)) throw std::runtime_error("Invalid OSCAR sample counters.");
                        samples=raw; cleanedSamples=clean;
                    } else if (type == "DONE") { done=true; }
                    else if (type == "ERROR") { std::getline(input>>std::ws,failure); if (failure.empty()) failure="OSCAR worker failed."; running=false; startup.notify_all(); }
                    else throw std::runtime_error("Unknown OSCAR worker protocol message.");
                }
                std::lock_guard<std::mutex> lock(mutex);
                if (!done && failure.empty()) failure="OSCAR worker exited without confirmed file finalization. Check .worker.log.";
            } catch (const std::exception& e) {
                std::lock_guard<std::mutex> lock(mutex); failure=e.what();
            }
            { std::lock_guard<std::mutex> lock(mutex); running=false; startup.notify_all(); }
        });
        std::unique_lock<std::mutex> lock(mutex);
        bool signaled=startup.wait_for(lock,std::chrono::seconds(35),[&]() { return ready || !failure.empty(); });
        if (!signaled || !ready || !failure.empty() || !running) {
            std::string error=failure.empty() ? "OSCAR startup failed or timed out." : failure;
            lock.unlock(); stop(); throw std::runtime_error(error);
        }
    }
};

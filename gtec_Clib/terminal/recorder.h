#pragma once
#include <atomic>
#include <chrono>
#include <cmath>
#include <filesystem>
#include <fstream>
#include <mutex>
#include <thread>
#include <condition_variable>
#include <cstdlib>
#include "worker_process.h"

// The worker exclusively owns API calls while recording. Terminal commands
// use cached status and a separate event file; they never touch the DLL.
class Recorder {
    WorkerProcess child;
    std::thread worker, readinessWorker;
    std::atomic<bool> cancel{false}, running{false};
    mutable std::mutex mutex;
    uint64_t samples = 0, discontinuities = 0;
    float battery = 0, validation = 0;
    bool hasBattery = false, hasValidation = false;
    std::string failure;
    std::ofstream events;
    std::ofstream startupLog;
    bool extendedEvents = false;
    bool oscar = false, ready = false, done = false, workerExited = false;
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
    // Caller holds mutex once reader/monitor threads have started. No stdout diagnostics.
    void trace(const std::string& message) {
        if (startupLog.is_open()) { startupLog << std::fixed << std::setprecision(6) << elapsed() << ' ' << message << '\n'; startupLog.flush(); }
    }
    static int readyDelay(std::istream& input) {
        std::string type, extra; int version=0, delay=0;
        if (!(input>>type>>version>>delay) || type != "READY" || version != 1 || delay <= 0 || (input>>extra))
            throw std::runtime_error("Invalid OSCAR readiness confirmation (expected READY 1 <positive delay>).");
        return delay;
    }
    void acceptReady(int delay, const std::string& source) {
        trace("observed_ready source="+source+" delay="+std::to_string(delay));
        if (ready && delaySamples != delay) throw std::runtime_error("Conflicting OSCAR readiness confirmation from "+source+".");
        if (!ready && (workerExited || done)) throw std::runtime_error("OSCAR readiness arrived after worker finalization.");
        if (!failure.empty()) return;
        if (!ready && !cancel) {
            ready=true; delaySamples=delay; running=true;
            // A file confirmation is a new status observation, even after a long initialization.
            lastStatus=std::chrono::steady_clock::now();
            trace("readiness_accepted source="+source);
        }
        startup.notify_all();
    }
    void failOscar(const std::string& error) {
        if (failure.empty()) failure=error;
        running=false; trace("failure="+failure); startup.notify_all();
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
        int block = 0, trial = 0, attempt = 0, startNumber = 0, subtract = 0;
        std::string protocolVersion, mode, bodyPart, side, movementVersion, language, wordLetter;
        double planned = 0, actual = 0;
    };
    void stop() {
        cancel = true;
        startup.notify_all();
        if (child.active()) {
            child.requestStop();
            if (!child.wait(8000)) {
                { std::lock_guard<std::mutex> lock(mutex); failure = "OSCAR worker shutdown timed out."; }
                child.kill(); child.wait(1000);
            }
            if (!child.successful()) { std::lock_guard<std::mutex> lock(mutex); if (failure.empty()) failure="OSCAR worker returned a nonzero exit code."; }
        }
        if (worker.joinable()) worker.join();
        if (readinessWorker.joinable()) readinessWorker.join();
        child.dispose();
        if (events.is_open()) { events.flush(); events.close(); }
        if (startupLog.is_open()) { trace("stopped"); startupLog.close(); }
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
            << ',' << context.actual << ',' << csv(context.reason) << ',' << context.startNumber << ',' << context.subtract
            << ',' << csv(context.protocolVersion) << ',' << csv(context.mode) << ',' << csv(context.bodyPart)
            << ',' << csv(context.side) << ',' << csv(context.movementVersion) << ',' << csv(context.language) << ',' << csv(context.wordLetter);
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
        if (extendedEvents) events << ",source,run,block,trial,attempt,condition,phase,planned_elapsed_s,actual_session_elapsed_s,reason,start_number,subtract,protocol_version,mode,body_part,side,movement_version,language,word_letter";
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
        for (const auto& suffix : {"", ".events.csv", ".oscar.csv", ".processing.json", ".device.json", ".worker.log", ".startup.log", ".ready", ".ready.tmp"}) {
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
        script=std::filesystem::absolute(script);
        std::string python="python";
#ifdef _WIN32
        if (auto value=_wgetenv(L"EEG_OSCAR_PYTHON")) python=std::filesystem::path(value).u8string();
#else
        if (auto value=std::getenv("EEG_OSCAR_PYTHON")) python=value;
#endif
        auto eventPath=path; eventPath+=".events.csv";
        events.open(eventPath);
        if (!events) throw std::runtime_error("Cannot create event log.");
        events << "host_utc_s,elapsed_s,samples_received,label,source,run,block,trial,attempt,condition,phase,planned_elapsed_s,actual_session_elapsed_s,reason,start_number,subtract,protocol_version,mode,body_part,side,movement_version,language,word_letter\n";
        events.flush();
        if (!events) throw std::runtime_error("Cannot write event log header.");
        {
            std::lock_guard<std::mutex> lock(mutex);
            samples=discontinuities=cleanedSamples=0; failure.clear(); ready=done=workerExited=false; oscar=true;
            delaySamples=0; hasBattery=hasValidation=false; extendedEvents=true;
            lastStatus=std::chrono::steady_clock::now();
        }
        origin=std::chrono::steady_clock::now(); cancel=false;
        auto outputPath=std::filesystem::absolute(path);
        auto readyPath=outputPath; readyPath += ".ready";
        auto logPath=outputPath; logPath += ".startup.log";
        startupLog.open(logPath);
        if (!startupLog) throw std::runtime_error("Cannot create OSCAR startup log.");
        trace(std::string("controller=oscar-startup-v2 build=")+__DATE__+" "+__TIME__);
        trace("executable="+WorkerProcess::executablePath());
        trace("python="+python); trace("worker="+script.u8string()); trace("ready_path="+readyPath.u8string());
        try {
            child.start(python,script,serial,outputPath);
            trace("worker_pid="+std::to_string(child.id()));
            worker=std::thread([this]() {
                try {
                    std::string line;
                    while (child.line(line)) {
                        std::lock_guard<std::mutex> lock(mutex);
                        std::istringstream input(line); std::string type; input>>type;
                        lastStatus=std::chrono::steady_clock::now();
                        if (type == "READY") {
                            std::istringstream confirmation(line);
                            acceptReady(readyDelay(confirmation),"stdout");
                        } else if (type == "SAMPLES") {
                            uint64_t raw=0, clean=0; std::string extra;
                            if (!(input>>raw>>clean) || raw < samples || clean < cleanedSamples || clean > raw || (input>>extra)) throw std::runtime_error("Invalid OSCAR sample counters.");
                            if (!samples) trace("first_samples raw="+std::to_string(raw)+" clean="+std::to_string(clean));
                            samples=raw; cleanedSamples=clean;
                        } else if (type == "DONE") {
                            std::string extra;
                            if (input>>extra) throw std::runtime_error("Invalid OSCAR DONE protocol.");
                            if (!ready) throw std::runtime_error("OSCAR worker finalized before readiness.");
                            if (!cancel) throw std::runtime_error("OSCAR worker finalized before requested stop.");
                            done=true; trace("observed_done");
                        }
                        else if (type == "ERROR") { std::string error; std::getline(input>>std::ws,error); failOscar(error.empty() ? "OSCAR worker failed." : error); }
                        else throw std::runtime_error("Unknown OSCAR worker protocol message.");
                    }
                    std::lock_guard<std::mutex> lock(mutex);
                    if (!done && failure.empty()) failOscar("OSCAR worker exited without confirmed file finalization. Check .worker.log.");
                } catch (const std::exception& e) {
                    std::lock_guard<std::mutex> lock(mutex); failOscar(e.what());
                }
                { std::lock_guard<std::mutex> lock(mutex); workerExited=true; running=false; trace("stdout_closed"); startup.notify_all(); }
            });
            // Keep checking after stdout READY: the file may arrive later. A separate
            // monitor also keeps file readiness independent of a blocking pipe read.
            readinessWorker=std::thread([this,readyPath]() {
                try {
                    size_t polls=0; bool finishing=false;
                    { std::lock_guard<std::mutex> lock(mutex); trace("ready_monitor_started"); }
                    while (true) {
                        ++polls;
                        std::error_code error;
                        bool exists=std::filesystem::exists(readyPath,error);
                        if (error) throw std::runtime_error("Cannot inspect OSCAR readiness file: "+error.message());
                        if (exists) {
                            std::string contents;
                            {
                                // Close before remove; Windows does not guarantee delete-sharing.
                                std::ifstream confirmation(readyPath,std::ios::binary);
                                if (!confirmation) throw std::runtime_error("Cannot open OSCAR readiness file.");
                                char buffer[256]; confirmation.read(buffer,sizeof(buffer));
                                contents.assign(buffer,size_t(confirmation.gcount()));
                                if (confirmation.bad()) throw std::runtime_error("Cannot read OSCAR readiness file.");
                                if (!confirmation.eof()) throw std::runtime_error("Invalid OSCAR readiness confirmation: content exceeds limit.");
                            }
                            std::unique_lock<std::mutex> lock(mutex);
                            trace("ready_file_observed checks="+std::to_string(polls)+" bytes="+std::to_string(contents.size()));
                            if (contents.empty() || contents.back() != '\n') throw std::runtime_error("Invalid OSCAR readiness confirmation: incomplete line.");
                            contents.pop_back();
                            if (!contents.empty() && contents.back() == '\r') contents.pop_back();
                            if (contents.find_first_of("\r\n") != std::string::npos) throw std::runtime_error("Invalid OSCAR readiness confirmation: expected exactly one line.");
                            std::istringstream confirmation(contents);
                            acceptReady(readyDelay(confirmation),"file");
                            bool removed=std::filesystem::remove(readyPath,error);
                            trace("ready_file_removed="+std::to_string(removed)+" error="+error.message());
                            // Valid confirmations are consumed once. Malformed/conflicting
                            // files remain as evidence; a removal failure is logged explicitly.
                            return;
                        }
                        std::unique_lock<std::mutex> lock(mutex);
                        if (polls == 1) trace("ready_file_absent");
                        if (finishing) { trace("ready_monitor_ended checks="+std::to_string(polls)); return; }
                        startup.wait_for(lock,std::chrono::milliseconds(100),[this]() { return workerExited || !failure.empty(); });
                        // One final file check after pipe closure/error catches a
                        // matching confirmation published just before shutdown.
                        finishing=workerExited || !failure.empty();
                    }
                } catch (const std::exception& e) {
                    std::lock_guard<std::mutex> lock(mutex); failOscar(e.what());
                }
            });
            std::unique_lock<std::mutex> lock(mutex);
            auto timeout=std::chrono::milliseconds(120000);
#ifdef UNICORN_SESSION_TEST
            if (auto value=std::getenv("UNICORN_OSCAR_STARTUP_TIMEOUT_MS")) timeout=std::chrono::milliseconds(std::stoul(value));
#endif
            bool signaled=startup.wait_for(lock,timeout,[this]() { return ready || workerExited || !failure.empty(); });
            if (!signaled || !ready || !failure.empty() || !running) {
                if (failure.empty()) failOscar(!signaled ? "OSCAR startup timed out without an accepted readiness confirmation. Check .startup.log and .worker.log." : "OSCAR worker stopped during startup. Check .startup.log and .worker.log.");
                trace("startup_rejected ready="+std::to_string(ready)+" raw="+std::to_string(samples)+" clean="+std::to_string(cleanedSamples));
                // stop() joins the stdout thread, which needs this mutex to process
                // the worker's final protocol messages after STOP.
                lock.unlock();
                throw std::runtime_error(failure);
            }
            trace("startup_return_running");
        } catch (const std::exception& e) {
            { std::lock_guard<std::mutex> lock(mutex); failOscar(e.what()); }
            stop(); throw;
        }
    }
};

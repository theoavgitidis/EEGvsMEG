#pragma once
#include "session_plan.h"
#include <chrono>
#include <ctime>
#include <filesystem>
#include <fstream>
#include <mutex>
#include <thread>
#include <atomic>
#include <cstdlib>
#include <functional>

class Session {
    Recorder& recorder;
    Cues& cues;
    mutable std::mutex mutex;
    std::thread worker;
    std::unique_ptr<session::Timeline> timeline;
    std::string state = "idle", reason, id, startedUtc, endedUtc, configJson;
    std::filesystem::path dataPath, reservation;
    std::chrono::steady_clock::time_point epoch;
    double speed = 1, endedAt = 0;
    std::string shown;
    std::vector<int> runOrder{0,1};
    bool oscarRequested = false;
    struct TimingDeviation {};
    bool checkingTransition = false;
    double transitionTarget = 0;
    void checkTransitionTime() const {
        if (checkingTransition && now()-transitionTarget > 0.25*speed) throw TimingDeviation{};
    }
    template<class Operation> void transition(double target, Operation operation) {
        transitionTarget = target; checkingTransition = true;
        try {
            operation();
            if (!timeline->completed) checkTransitionTime();
            checkingTransition = false;
        } catch (const TimingDeviation&) {
            checkingTransition = false;
            reason = "timing_deviation_over_250ms";
            // End the visible task before any more synchronous logging.
            if (cues.active()) display("PAUSE");
            event("timing_deviation",timeline->phase(),timeline->attempt,now(),timeline->deadline);
            if (!timeline->paused) pauseLocked(reason);
            else { state = "paused"; saveMetadata(); }
        } catch (...) { checkingTransition = false; throw; }
    }
    static std::filesystem::path appended(std::filesystem::path path, const char* suffix) { path += suffix; return path; }
    std::filesystem::path companion(const char* suffix) const { return appended(dataPath,suffix); }
    static std::string quote(const std::string& value) {
        std::ostringstream out; out << '"';
        for (unsigned char c : value) {
            if (c == '"' || c == '\\') out << '\\' << c;
            else if (c < 32) out << "\\u" << std::hex << std::setw(4) << std::setfill('0') << int(c) << std::dec;
            else out << c;
        }
        out << '"'; return out.str();
    }
    static std::string cell(const std::string& value) {
        std::string out = "\""; for (char c : value) { if (c == '"') out += '"'; out += c; } return out+'"';
    }
    static std::string date(bool local, const char* pattern) {
        auto now = std::time(nullptr); std::tm value{};
#ifdef _WIN32
        if (local) localtime_s(&value,&now); else gmtime_s(&value,&now);
#else
        if (local) localtime_r(&now,&value); else gmtime_r(&now,&value);
#endif
        std::ostringstream out; out << std::put_time(&value,pattern); return out.str();
    }
    double now() const { return std::chrono::duration<double>(std::chrono::steady_clock::now()-epoch).count()*speed; }
    void display(const std::string& text) {
        if (shown != text) { cues.show(text); shown = text; }
    }
    static void taskContext(Recorder::Context& c, const session::Phase& p) {
        c.protocolVersion = session::protocolVersion; c.startNumber = p.startNumber; c.subtract = p.subtract; c.wordLetter = p.wordLetter;
        if (auto spec = p.task()) {
            c.mode = spec->mode; c.bodyPart = spec->bodyPart; c.side = spec->side;
            c.movementVersion = spec->mode == "cognitive" ? "" : session::movementVersion;
            c.language = spec->mode == "cognitive" ? "de" : "";
        }
    }
    void event(const std::string& type, const session::Phase& p, int attempt, double at, double deadline) {
        checkTransitionTime();
        // Paint first; cue/task events below then describe software-confirmed display delivery.
        if (type == "phase_start") display(p.cue(p.duration));
        checkTransitionTime();
        Recorder::Context c; c.source = "automatic"; c.run = p.run; c.block = p.block;
        c.trial = p.trial; c.attempt = attempt; c.startNumber = p.startNumber; c.condition = p.condition; c.phase = p.stage;
        c.actual = std::max(at,now())-timeline->started; c.planned = deadline-p.duration-timeline->started;
        if (type == "phase_end" || type == "task_offset" || type == "rest_end" || type == "trial_end" || type == "baseline_end" || type == "break_end" || type == "block_end" || type == "run_end" || type == "session_end") c.planned += p.duration;
        c.reason = reason; taskContext(c,p);
        recorder.mark(type,c,type == "session_error" || type == "session_abort" || type == "trial_invalidated");
        checkTransitionTime();
    }
    void saveMetadata() {
        auto snap = recorder.snapshot();
        auto destination = companion(".session.json");
        auto temporary = appended(destination,".tmp");
        std::ofstream out(temporary);
        if (!out) throw std::runtime_error("Cannot write session metadata.");
        double elapsed = state == "running" || state == "paused" ? now() : endedAt;
        out << "{\n  \"session_id\": " << quote(id)
            << ",\n  \"participant_id\": " << quote(dataPath.parent_path().filename().u8string())
            << ",\n  \"protocol_version\": " << quote(session::protocolVersion)
            << ",\n  \"seed\": " << timeline->plan.seed
            << ",\n  \"state\": " << quote(state) << ",\n  \"reason\": " << quote(reason)
            << ",\n  \"started_utc\": " << quote(startedUtc) << ",\n  \"ended_utc\": " << quote(endedUtc)
            << ",\n  \"local_timezone\": " << quote(date(true,"%Z %z"))
            << ",\n  \"schema_version\": 2"
            << ",\n  \"movement_version\": " << quote(session::movementVersion)
            << ",\n  \"task_language\": \"de\""
            << ",\n  \"subtraction_policy\": \"single subtraction; minuend 60..199; subtrahend 12..59; unique pairs\""
            << ",\n  \"word_letter_pool\": \"BDFGHKLMNRST\""
            << ",\n  \"order\": [" << quote(session::runNames()[runOrder[0]])
            << ',' << quote(session::runNames()[runOrder[1]]) << ']'
            << ",\n  \"planned_trials\": " << timeline->plan.trials()
            << ",\n  \"planned_seconds\": " << timeline->plan.duration() << ",\n  \"elapsed_seconds\": " << elapsed
            << ",\n  \"unplanned_pause_seconds\": " << timeline->pausedSeconds + (timeline->paused ? elapsed-timeline->pauseStarted : 0)
            << ",\n  \"completed_trials\": " << timeline->completedTrials
            << ",\n  \"completed_trials_by_run\": {\"Motorik\":" << timeline->completedByRun["Motorik"]
            << ",\"Imagery\":" << timeline->completedByRun["Imagery"] << '}'
            << ",\n  \"invalid_attempts\": " << timeline->invalid
            << ",\n  \"repetitions\": " << timeline->repeats
            << ",\n  \"samples\": " << snap.samples << ",\n  \"counter_discontinuities\": " << snap.discontinuities
            << ",\n  \"sampling_rate_hz\": " << UNICORN_SAMPLING_RATE
            << ",\n  \"processing_mode\": " << quote(oscarRequested ? "oscar" : "raw")
            << ",\n  \"default_signal\": " << quote(oscarRequested ? "oscar" : "raw")
            << ",\n  \"oscar_file\": " << (oscarRequested ? quote(dataPath.filename().u8string()+".oscar.csv") : "null")
            << ",\n  \"processing_file\": " << (oscarRequested ? quote(dataPath.filename().u8string()+".processing.json") : "null")
            << ",\n  \"oscar_samples\": " << snap.cleanedSamples
            << ",\n  \"oscar_delay_samples\": " << snap.delaySamples
            << ",\n  \"event_position_method\": " << quote(oscarRequested ? "latest raw sample count from worker status; approximate (40 ms status interval plus queue/IPC/scheduling latency)" : "latest raw sample count from C API read; approximate")
            << ",\n  \"test_clock_speed\": " << speed
            << ",\n  \"eeg_file\": " << quote(dataPath.filename().u8string())
            << ",\n  \"event_file\": " << quote(dataPath.filename().u8string()+".events.csv")
            << ",\n  \"plan_file\": " << quote(dataPath.filename().u8string()+".plan.csv")
            << ",\n  \"device\": " << configJson << "\n}\n";
        out.flush(); if (!out) throw std::runtime_error("Session metadata write failed."); out.close();
#ifdef _WIN32
        if (!MoveFileExW(temporary.c_str(),destination.c_str(),MOVEFILE_REPLACE_EXISTING | MOVEFILE_WRITE_THROUGH))
            throw std::runtime_error("Session metadata replacement failed.");
#else
        std::filesystem::rename(temporary,destination);
#endif
    }
    void finish(const std::string& finalState, const std::string& why) {
        state = finalState; reason = why; endedAt = now(); endedUtc = date(false,"%Y-%m-%dT%H:%M:%SZ");
        timeline->running = false;
        // A vendor read, event flush, or join can block. Stop instructing the
        // participant before starting that cleanup, even if it cannot finish yet.
        try { if (cues.active()) display("PAUSE"); }
        catch (const std::exception& e) { reason += std::string("; display: ")+e.what(); }
        try {
            if (finalState != "completed" && !timeline->paused && timeline->phase().isTrial()) {
                ++timeline->invalid;
                event("trial_invalidated",timeline->phase(),timeline->attempt,endedAt,timeline->deadline);
            }
            if (finalState != "completed")
                event(finalState == "failed" ? "session_error" : "session_abort",timeline->phase(),timeline->attempt,endedAt,timeline->deadline);
        } catch (const std::exception& e) { reason += std::string("; event: ")+e.what(); state = "failed"; }
        recorder.stop();
        auto failure = recorder.snapshot().failure;
        if (!failure.empty()) { state = "failed"; reason += "; recorder: "+failure; }
        try { if (cues.active()) display(state == "completed" ? "SITZUNG BEENDET" : "PAUSE"); }
        catch (const std::exception& e) { reason += std::string("; display: ")+e.what(); }
        try { saveMetadata(); } catch (const std::exception& e) { state = "failed"; reason += std::string("; metadata: ")+e.what(); }
        if (!reservation.empty()) { std::error_code ec; std::filesystem::remove(reservation,ec); reservation.clear(); }
    }
    void pauseLocked(const std::string& why) {
        reason = why;
        if (cues.active()) display("PAUSE");
        timeline->pause(now()); state = "paused"; saveMetadata();
    }
public:
    Session(Recorder& r, Cues& c) : recorder(r), cues(c) {}
    ~Session() { try { stop("program shutdown"); } catch (...) {} if (worker.joinable()) worker.join(); }
    bool active() const { std::lock_guard<std::mutex> lock(mutex); return state == "running" || state == "paused"; }
#ifdef UNICORN_SESSION_TEST
    void testJump(double seconds) {
        std::lock_guard<std::mutex> lock(mutex);
        epoch -= std::chrono::duration_cast<std::chrono::steady_clock::duration>(std::chrono::duration<double>(seconds/speed));
    }
    void testNextBoundary() {
        std::lock_guard<std::mutex> lock(mutex);
        epoch -= std::chrono::duration_cast<std::chrono::steady_clock::duration>(std::chrono::duration<double>((timeline->deadline-now())/speed));
    }
#endif
    void setOrder(const std::vector<int>& order) {
        std::lock_guard<std::mutex> lock(mutex);
        if (state == "running" || state == "paused" || recorder.active()) throw std::runtime_error("Stop acquisition before changing run order.");
        auto check = order; std::sort(check.begin(),check.end());
        if (check != std::vector<int>{0,1}) throw std::runtime_error("Specify each run once: motorik imagery (or imagery motorik).");
        runOrder = order;
    }
    void start(UNICORN_HANDLE handle, Experiments& experiments, bool useOscar = false,
               std::function<void()> releaseDevice = {}) {
        if (active()) throw std::runtime_error("A session is already active.");
        if (worker.joinable()) worker.join();
        std::lock_guard<std::mutex> lock(mutex);
        if (recorder.active()) throw std::runtime_error("Stop background recording before starting a session.");
        experiments.require();
        oscarRequested = useOscar;
        UNICORN_AMPLIFIER_CONFIGURATION config{}; check(UNICORN_GetConfiguration(handle,&config));
        UNICORN_DEVICE_INFORMATION device{}; check(UNICORN_GetDeviceInformation(handle,&device));
        for (int i = 1; i <= 8; ++i) {
            bool found = false; auto name = "EEG "+std::to_string(i);
            for (const auto& channel : config.Channels) if (channel.enabled && name == channel.name) found = true;
            if (!found) throw std::runtime_error("Session requires enabled channel "+name+". Check config.");
        }
        std::ostringstream configuration;
        configuration << "{\"serial\":" << quote(device.serial) << ",\"firmware\":" << quote(device.firmwareVersion)
            << ",\"api_version\":" << UNICORN_GetApiVersion() << ",\"channels\":[";
        bool first = true;
        for (const auto& channel : config.Channels) {
            if (!first) configuration << ','; first = false;
            configuration << "{\"name\":" << quote(channel.name) << ",\"unit\":" << quote(channel.unit)
                << ",\"enabled\":" << (channel.enabled ? "true" : "false") << '}';
        }
        configuration << "]}"; configJson = configuration.str();
        uint32_t seed = std::random_device{}();
#ifdef UNICORN_SESSION_TEST
        if (auto value = std::getenv("UNICORN_SESSION_SEED")) seed = uint32_t(std::stoul(value));
        if (auto value = std::getenv("UNICORN_SESSION_SPEED")) speed = std::stod(value);
        if (!std::isfinite(speed) || speed <= 0) throw std::runtime_error("Invalid test clock speed.");
#endif
        timeline = std::make_unique<session::Timeline>(session::makePlan(seed,runOrder),
            [this](const std::string& type,const session::Phase& p,int attempt,double at,double deadline) { event(type,p,attempt,at,deadline); });
        // Reserve a unique directory-independent stem. CLI serializes starts in this process.
        std::string base = "session_"+date(true,"%Y%m%d_%H%M%S");
        for (int suffix = 0;; ++suffix) {
            id = base+(suffix ? "_"+std::to_string(suffix) : "");
            try { dataPath = experiments.output(id+".csv"); }
            catch (const std::runtime_error& e) {
                if (std::string(e.what()).find("already exist") == std::string::npos || suffix > 10000) throw;
                continue;
            }
            if (std::filesystem::exists(companion(".plan.csv")) || std::filesystem::exists(companion(".session.json"))) continue;
            auto candidate = companion(".reserve");
            if (!std::filesystem::create_directory(candidate)) continue; // atomic reservation across CLI processes
            // Another starter may have finished creating files between the existence check and reservation.
            if (std::filesystem::exists(dataPath) || std::filesystem::exists(companion(".events.csv")) ||
                std::filesystem::exists(companion(".plan.csv")) || std::filesystem::exists(companion(".session.json"))) {
                std::filesystem::remove(candidate); continue;
            }
            reservation = candidate; break;
        }
        state = "preparing"; reason.clear(); shown.clear(); endedUtc.clear(); endedAt = 0;
        epoch = std::chrono::steady_clock::now(); startedUtc = date(false,"%Y-%m-%dT%H:%M:%SZ");
        try {
            std::ofstream plan(companion(".plan.csv"));
            plan << "session_id,phase_index,planned_start_s,run,block,trial,condition,phase,duration_s,start_number,subtract,protocol_version,seed,mode,body_part,side,movement_version,language,word_letter,next_run\n";
            double planned = 0;
            for (size_t i = 0; i < timeline->plan.phases.size(); ++i) {
                const auto& p = timeline->plan.phases[i];
                plan << cell(id) << ',' << i << ',' << planned << ',' << cell(p.run) << ',' << p.block << ',' << p.trial
                    << ',' << cell(p.condition) << ',' << cell(p.stage) << ',' << p.duration << ',';
                if (p.startNumber) plan << p.startNumber;
                plan << ','; if (p.subtract) plan << p.subtract;
                Recorder::Context context; taskContext(context,p);
                plan << ',' << cell(session::protocolVersion) << ',' << seed << ',' << cell(context.mode) << ',' << cell(context.bodyPart)
                    << ',' << cell(context.side) << ',' << cell(context.movementVersion) << ',' << cell(context.language) << ',' << cell(p.wordLetter)
                    << ',' << cell(p.nextRun) << '\n'; planned += p.duration;
            }
            plan.flush(); if (!plan) throw std::runtime_error("Cannot write session plan."); plan.close();
            saveMetadata();
            cues.open(); cues.fullscreenOn();
            display("AUFNAHME WIRD VORBEREITET");
            if (oscarRequested) {
                if (!releaseDevice) throw std::runtime_error("OSCAR requires exclusive device handoff.");
                releaseDevice();
                recorder.startOscar(device.serial,dataPath);
                std::ifstream actual(companion(".device.json"));
                if (!actual) throw std::runtime_error("OSCAR device metadata missing.");
                configJson.assign(std::istreambuf_iterator<char>(actual),std::istreambuf_iterator<char>());
                if (configJson.empty()) throw std::runtime_error("OSCAR device metadata empty.");
            } else recorder.start(handle,dataPath,0,false,true);
            epoch = std::chrono::steady_clock::now(); startedUtc = date(false,"%Y-%m-%dT%H:%M:%SZ");
            state = "running"; transition(0,[&]() { timeline->start(0); }); saveMetadata();
            std::filesystem::remove(reservation); reservation.clear();
            worker = std::thread([this]() {
                while (true) {
                    {
                        std::lock_guard<std::mutex> lock(mutex);
                        if (state != "running" && state != "paused") break;
                        try {
                            auto snapshot = recorder.snapshot();
                            if (!snapshot.running) throw std::runtime_error(snapshot.failure.empty() ? "Recording ended unexpectedly." : snapshot.failure);
                            if (!cues.active() && state == "running") {
                                reason = "participant_window_closed";
                                event("participant_window_closed",timeline->phase(),timeline->attempt,now(),timeline->deadline);
                                pauseLocked(reason);
                            }
                            if (state == "running") {
                                double at = now();
                                // The same deadline covers exit logging, painting and entry
                                // logging. Checking only before advance misses blocking callbacks.
                                if (at >= timeline->deadline)
                                    transition(timeline->deadline,[&]() { timeline->advance(at); });
                                if (timeline->completed) { finish("completed",""); break; }
                                if (state == "running")
                                    display(timeline->phase().cue(timeline->phaseRemaining(now())));
                            }
                        } catch (const std::exception& e) { finish("failed",e.what()); break; }
                    }
                    std::this_thread::sleep_for(std::chrono::milliseconds(5));
                }
            });
        } catch (const std::exception& e) { finish("failed",std::string("start failed: ")+e.what()); throw; }
    }
    void pause() {
        std::lock_guard<std::mutex> lock(mutex);
        if (state != "running") throw std::runtime_error("No running session to pause.");
        try { pauseLocked("operator"); } catch (const std::exception& e) { finish("failed",e.what()); throw; }
    }
    void resume() {
        std::lock_guard<std::mutex> lock(mutex);
        if (state != "paused") throw std::runtime_error("Session is not paused.");
        if (!recorder.active()) { finish("failed","Recording ended while paused."); throw std::runtime_error(reason); }
        // A failed reopen leaves the session paused.
        cues.open(); cues.fullscreenOn(); shown.clear();
        try {
            double at = now(); state = "running";
            transition(at,[&]() {
                timeline->resume(at);
                display(timeline->phase().cue(timeline->phaseRemaining(now())));
            });
            if (state == "running") reason.clear();
            saveMetadata();
        }
        catch (const std::exception& e) { finish("failed",e.what()); throw; }
    }
    void stop(const std::string& why) {
        { std::lock_guard<std::mutex> lock(mutex); if (state == "running" || state == "paused") finish("aborted",why); }
        if (worker.joinable()) worker.join();
    }
    void mark(const std::string& label) {
        std::lock_guard<std::mutex> lock(mutex);
        if (state != "running" && state != "paused") throw std::runtime_error("No active session.");
        Recorder::Context c; const auto& p = timeline->phase(); c.run = p.run; c.block = p.block; c.trial = p.trial;
        c.attempt = timeline->attempt; c.startNumber = p.startNumber; c.condition = p.condition; c.phase = p.stage;
        c.actual = now()-timeline->started; c.planned = timeline->deadline-p.duration-timeline->started; taskContext(c,p);
        try { recorder.mark(label,c); } catch (const std::exception& e) { finish("failed",e.what()); throw; }
    }
    std::vector<std::string> lines() const {
        std::lock_guard<std::mutex> lock(mutex);
        if (!timeline) return {};
        double at = state == "running" || state == "paused" ? now() : endedAt; const auto& p = timeline->phase();
        std::string trials = p.isTrial() ? "Trial "+std::to_string(p.trial)+"/"+std::to_string(p.total)+" | Versuch "+std::to_string(timeline->attempt) : "kein Aufgaben-Trial";
        int blocks = session::blocksPerRun;
        return {"SITZUNG "+id+" | "+state+" | REST "+session::clockText(timeline->remaining(at))+" | VERSTRICHEN "+session::clockText(state == "running" || state == "paused" ? at : endedAt),
            p.run+" : "+p.instruction()+" : "+trials,
            "Block "+std::to_string(p.block)+"/"+std::to_string(p.block ? blocks : 0)+" | "+p.stage+" Rest "+session::clockText(timeline->phaseRemaining(at))+" | Aufnahme "+(recorder.active() ? "AKTIV" : "STOPP")+" | "+(oscarRequested ? "OSCAR" : "RAW"),
            "Datei: "+dataPath.u8string()+" | abgeschlossen "+std::to_string(timeline->completedTrials)+"/"+std::to_string(timeline->plan.trials())+" | Wiederholungen "+std::to_string(timeline->repeats)+(reason.empty() ? "" : " | "+reason)};
    }
};

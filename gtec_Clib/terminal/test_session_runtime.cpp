// Regression tests with the real recorder and controllably slow I/O/UI adapters.
#include "unicorn.h"
#ifdef _WIN32
#define NOMINMAX
#include <windows.h>
#endif
#include <cassert>
#include <condition_variable>
#include <fstream>
#include <iostream>
#include <iomanip>
#include <memory>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>
static void check(int code) { if (code) throw std::runtime_error("Mock API error"); }
#include "recorder.h"
#include "experiments.h"

class TestRecorder : public Recorder {
    std::mutex hookMutex;
    std::condition_variable changed;
    std::string delayedLabel, delayedPhase;
    bool blockStop = false, stopEntered = false, releaseStop = false;
public:
    void delayOnce(const std::string& label, const std::string& phase) {
        std::lock_guard<std::mutex> lock(hookMutex); delayedLabel = label; delayedPhase = phase;
    }
    void mark(const std::string& label, const Context& context, bool finalEvent = false) {
        bool delay = false;
        {
            std::lock_guard<std::mutex> lock(hookMutex);
            if (label == delayedLabel && context.phase == delayedPhase) {
                delay = true; delayedLabel.clear();
            }
        }
        Recorder::mark(label,context,finalEvent);
        if (delay) std::this_thread::sleep_for(std::chrono::milliseconds(400));
    }
    void armBlockingStop() { std::lock_guard<std::mutex> lock(hookMutex); blockStop = true; }
    void waitForBlockedStop() {
        std::unique_lock<std::mutex> lock(hookMutex);
        assert(changed.wait_for(lock,std::chrono::seconds(3),[&]() { return stopEntered; }));
    }
    void unblockStop() { std::lock_guard<std::mutex> lock(hookMutex); releaseStop = true; changed.notify_all(); }
    void stop() {
        {
            std::unique_lock<std::mutex> lock(hookMutex);
            if (blockStop) {
                stopEntered = true; changed.notify_all();
                changed.wait(lock,[&]() { return releaseStop; });
            }
        }
        Recorder::stop();
    }
};
class Cues {
    std::atomic<bool> opened{false}, slowTask{false};
    mutable std::mutex mutex;
    std::string text;
public:
    bool active() const { return opened; }
    void open() { opened = true; }
    void close() { opened = false; }
    void fullscreenOn() {}
    void delayNextTask() { slowTask = true; }
    std::string current() const { std::lock_guard<std::mutex> lock(mutex); return text; }
    void show(const std::string& value) {
        if ((value == "HAND LINKS" || value == "HAND RECHTS" || value == "FUSS LINKS" || value == "FUSS RECHTS") && slowTask.exchange(false))
            std::this_thread::sleep_for(std::chrono::milliseconds(400));
        std::lock_guard<std::mutex> lock(mutex); text = value;
    }
};
#define Recorder TestRecorder
#include "session.h"
#undef Recorder

template<class Predicate> void waitFor(Predicate predicate) {
    auto deadline = std::chrono::steady_clock::now()+std::chrono::seconds(3);
    while (!predicate()) {
        assert(std::chrono::steady_clock::now() < deadline);
        std::this_thread::sleep_for(std::chrono::milliseconds(5));
    }
}
std::string status(Session& s) {
    std::string text; for (const auto& line : s.lines()) text += line+'\n'; return text;
}
void nextPhase(Session& s, const std::string& phase) {
    s.testNextBoundary(); waitFor([&]() { return status(s).find(" | "+phase+" Rest") != std::string::npos; });
}
int main() {
    for (const std::string scenario : {"slow-display", "slow-exit-event", "slow-trial-end", "blocked-stop"}) {
        TestRecorder recorder; Cues cues; Session s(recorder,cues); Experiments experiments;
        std::istringstream name(scenario); experiments.select(name,true);
        s.start(1,experiments);
        nextPhase(s,"prepare");
        if (scenario == "slow-display") cues.delayNextTask();
        if (scenario == "slow-exit-event") recorder.delayOnce("phase_end","prepare");
        if (scenario == "slow-display" || scenario == "slow-exit-event") {
            s.testNextBoundary();
            waitFor([&]() { return status(s).find(" | paused |") != std::string::npos; });
            assert(cues.current() == "PAUSE");
            assert(status(s).find("abgeschlossen 0/168") != std::string::npos);
            assert(status(s).find("timing_deviation_over_250ms") != std::string::npos);
            s.resume();
            assert(status(s).find("prepare Rest") != std::string::npos);
            assert(status(s).find("Versuch 2") != std::string::npos);
            nextPhase(s,"task");
            assert(status(s).find(" | running |") != std::string::npos);
        } else if (scenario == "slow-trial-end") {
            nextPhase(s,"task"); nextPhase(s,"rest");
            recorder.delayOnce("trial_end","rest");
            s.testNextBoundary();
            waitFor([&]() { return status(s).find(" | paused |") != std::string::npos; });
            assert(status(s).find("abgeschlossen 0/168") != std::string::npos);
            s.resume(); assert(status(s).find("Trial 1/64 | Versuch 2") != std::string::npos);
            nextPhase(s,"task"); nextPhase(s,"rest"); nextPhase(s,"prepare");
            assert(status(s).find("abgeschlossen 1/168") != std::string::npos);
        } else {
            nextPhase(s,"task");
            assert(cues.current() != "PAUSE");
            recorder.armBlockingStop();
            std::thread abort([&]() { s.stop("operator stop"); });
            recorder.waitForBlockedStop();
            // Assert while the recorder is still blocked, not after cleanup.
            assert(cues.current() == "PAUSE");
            recorder.unblockStop(); abort.join();
        }
        s.stop("test complete");
        std::cout << "PASS: " << scenario << '\n';
    }
}

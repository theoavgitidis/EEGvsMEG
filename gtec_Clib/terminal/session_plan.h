#pragma once
#include <algorithm>
#include <cmath>
#include <functional>
#include <iomanip>
#include <numeric>
#include <map>
#include <random>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

namespace session {
constexpr const char* protocolVersion = "eeg-session-1.0";
inline std::string clockText(double seconds) {
    int n = int(std::ceil(std::max(0.0, seconds)));
    std::ostringstream out; out << n/60 << ':' << std::setw(2) << std::setfill('0') << n%60; return out.str();
}
struct Phase {
    std::string run, stage, condition;
    int block = 0, trial = 0, total = 0, startNumber = 0;
    double duration = 0;
    bool isTrial() const { return trial > 0; }
    std::string cue(double remaining = 0) const {
        if (stage == "break") return "PAUSE\n" + clockText(remaining);
        if (stage == "prepare") return run == "Kognitiv" ? "READY" : "+";
        if (stage != "task") return "+";
        if (condition == "arms") return "ARME HEBEN";
        if (condition == "legs") return "BEINE HEBEN";
        if (condition == "blink") return "BLINZELN";
        if (condition == "imagine_arms") return "ARME VORSTELLEN";
        if (condition == "imagine_legs") return "BEINE VORSTELLEN";
        return std::to_string(startNumber) + " − 7\nFORTLAUFEND";
    }
    std::string instruction() const {
        if (stage == "baseline") return "ruhig sitzen, Kreuz ansehen";
        if (stage == "break") return "PAUSE";
        if (stage == "rest") return "ERHOLUNG – ruhig sitzen, Kreuz ansehen";
        if (stage == "prepare") return run == "Kognitiv" ? "READY – noch nicht rechnen" : "Kreuz ansehen";
        if (condition == "arms") return "ARME HEBEN – einmal anheben und ablegen";
        if (condition == "legs") return "BEINE HEBEN – einmal anheben und absetzen";
        if (condition == "blink") return "BLINZELN – zweimal";
        if (condition == "imagine_arms") return "ARME VORSTELLEN – ohne Bewegung";
        if (condition == "imagine_legs") return "BEINE VORSTELLEN – ohne Bewegung";
        return "ab " + std::to_string(startNumber) + " fortlaufend 7 abziehen";
    }
};
struct Plan {
    uint32_t seed;
    std::vector<Phase> phases;
    double duration() const { double n = 0; for (const auto& p : phases) n += p.duration; return n; }
};
inline Plan makePlan(uint32_t seed, const std::vector<int>& order = {0,1,2}) {
    auto sorted = order; std::sort(sorted.begin(), sorted.end());
    if (sorted != std::vector<int>{0,1,2}) throw std::runtime_error("Run order must contain Motorik, Imagery, Kognitiv once each.");
    Plan plan{seed, {}}; std::mt19937 rng(seed);
    auto baseline = [&](const char* name) { plan.phases.push_back({name, "baseline", "baseline", 0,0,0,0,60}); };
    baseline("Anfangsbaseline");
    std::vector<int> numbers(600); std::iota(numbers.begin(), numbers.end(), 300);
    std::shuffle(numbers.begin(), numbers.end(), rng); // 300..899, unique, remains positive under normal pilot pace
    const std::vector<std::string> runs = {"Motorik", "Imagery", "Kognitiv"};
    for (int position = 0; position < 3; ++position) {
        int run = order[position];
        int blocks = run == 2 ? 3 : 4, perClass = run == 2 ? 4 : 5;
        std::vector<std::string> conditions = run == 0 ? std::vector<std::string>{"arms","legs","blink"}
            : run == 1 ? std::vector<std::string>{"imagine_arms","imagine_legs"} : std::vector<std::string>{"mental_arithmetic"};
        std::vector<std::vector<int>> rests;
        for (size_t c = 0; c < conditions.size(); ++c) {
            std::vector<int> values;
            int base = run == 2 ? 15 : 6, count = run == 2 ? 3 : 5;
            for (int i = 0; i < count; ++i) values.push_back(base);
            for (int i = 0; i < count*2; ++i) values.push_back(base+1);
            for (int i = 0; i < count; ++i) values.push_back(base+2);
            std::shuffle(values.begin(), values.end(), rng); rests.push_back(values);
        }
        std::vector<int> used(conditions.size(), 0); int trial = 0;
        std::vector<int> history;
        for (int block = 1; block <= blocks; ++block) {
            std::vector<int> order;
            for (int c = 0; c < int(conditions.size()); ++c)
                for (int i = 0; i < perClass; ++i) order.push_back(c);
            // Rejection sampling preserves exact block counts and checks across block boundaries.
            bool valid = false;
            for (int attempt = 0; attempt < 100000 && !valid; ++attempt) {
                std::shuffle(order.begin(), order.end(), rng); auto check = history; valid = true;
                for (int c : order) {
                    if (run != 2 && check.size() >= 2 && check.back() == c && check[check.size()-2] == c) { valid = false; break; }
                    check.push_back(c);
                }
            }
            if (!valid) throw std::runtime_error("Could not generate balanced trial order.");
            for (int c : order) {
                history.push_back(c); ++trial;
                int number = run == 2 ? numbers[trial-1] : 0;
                int rest = rests[c][used[c]++];
                for (const auto& step : std::vector<std::pair<std::string,double>>{{"prepare",2},{"task",run == 2 ? 10.0 : 4.0},{"rest",double(rest)}})
                    plan.phases.push_back({runs[run],step.first,conditions[c],block,trial,
                        blocks*perClass*int(conditions.size()),number,step.second});
            }
            if (block < blocks) plan.phases.push_back({runs[run],"break","block_break",block,0,0,0,45});
        }
        if (position < 2) plan.phases.push_back({runs[run],"break","run_break",0,0,0,0,90});
    }
    baseline("Endbaseline");
    if (plan.duration() != 2296) throw std::runtime_error("Invalid session duration.");
    return plan;
}

// Pure timeline: caller supplies monotonic seconds. No sleeping or device/UI access.
class Timeline {
public:
    using Event = std::function<void(const std::string&, const Phase&, int, double, double)>;
    Plan plan;
    size_t index = 0;
    int attempt = 1, repeats = 0, invalid = 0, completedTrials = 0;
    bool running = false, paused = false, completed = false;
    double deadline = 0, pausedRemaining = 0, started = 0, pauseStarted = 0, pausedSeconds = 0;
    Event event;
    std::map<std::string,int> completedByRun;
    explicit Timeline(Plan value, Event callback) : plan(std::move(value)), event(std::move(callback)) {}
    const Phase& phase() const { return plan.phases.at(index); }
    void emit(const std::string& type, double now) { event(type, phase(), attempt, now, deadline); }
    void enter(double now) {
        const auto& p = phase();
        if (p.stage == "baseline") emit("baseline_start",now);
        if (p.stage == "break") emit("break_start",now);
        if (p.stage == "prepare") {
            if (p.trial == 1 && attempt == 1) emit("run_start",now);
            bool blockFirst = index == 0 || plan.phases[index-1].block != p.block || plan.phases[index-1].run != p.run || plan.phases[index-1].stage == "break";
            if (blockFirst && attempt == 1) emit("block_start",now);
            emit("trial_start",now);
        }
        emit("phase_start",now);
        if (p.stage == "task") { emit("cue_onset",now); emit("task_onset",now); }
    }
    void start(double now) { running = true; started = now; deadline = now+phase().duration; emit("session_start",now); enter(now); }
    double phaseRemaining(double now) const { return paused ? pausedRemaining : std::max(0.0,deadline-now); }
    double remaining(double now) const {
        if (completed) return 0;
        double value = phaseRemaining(now);
        for (size_t i = index+1; i < plan.phases.size(); ++i) value += plan.phases[i].duration;
        return value;
    }
    // Advance only one visible phase at a time. Runtime rejects large lateness before calling.
    bool advance(double now) {
        if (!running || paused || now < deadline) return false;
        const auto p = phase();
        emit("phase_end",now);
        if (p.stage == "task") emit("task_offset",now);
        if (p.stage == "baseline") emit("baseline_end",now);
        if (p.stage == "break") emit("break_end",now);
        if (p.stage == "rest") {
            emit("rest_end",now); emit("trial_end",now);
            bool lastBlock = index+1 >= plan.phases.size() || plan.phases[index+1].block != p.block || plan.phases[index+1].run != p.run || plan.phases[index+1].stage == "break";
            if (lastBlock) emit("block_end",now);
            bool lastRun = index+1 >= plan.phases.size() || plan.phases[index+1].run != p.run || plan.phases[index+1].condition == "run_break";
            if (lastRun) emit("run_end",now);
            // Only commit a valid trial after all potentially blocking exit
            // callbacks succeed; a timing exception must leave it repeatable.
            ++completedTrials; ++completedByRun[p.run];
        }
        if (index+1 == plan.phases.size()) {
            emit("session_end",now); completed = true; running = false; return true;
        }
        ++index; attempt = 1;
        // Preserve attempt number through prepare/task/rest of a repeated trial.
        if (p.isTrial() && phase().isTrial() && p.trial == phase().trial && p.run == phase().run) attempt = previousAttempt;
        else previousAttempt = 1;
        deadline += phase().duration; enter(now); return true;
    }
    void pause(double now) {
        if (!running || paused) throw std::runtime_error("No running session to pause.");
        pausedRemaining = std::max(0.0,deadline-now); pauseStarted = now; paused = true;
        if (phase().isTrial()) ++invalid;
        emit("pause_start",now);
        if (phase().isTrial()) emit("trial_invalidated",now);
        else if (phase().stage == "baseline") emit("baseline_invalidated",now);
    }
    void resume(double now) {
        if (!running || !paused) throw std::runtime_error("Session is not paused.");
        emit("pause_end",now); pausedSeconds += now-pauseStarted;
        if (phase().isTrial()) {
            auto trial = phase().trial; auto run = phase().run;
            while (index > 0 && plan.phases[index-1].trial == trial && plan.phases[index-1].run == run) --index;
            ++attempt; previousAttempt = attempt; ++repeats;
            deadline = now+phase().duration; paused = false; emit("trial_repeat",now); enter(now);
        } else if (phase().stage == "baseline") {
            ++attempt; deadline = now+phase().duration; paused = false; enter(now);
        } else { deadline = now+pausedRemaining; paused = false; emit("phase_resume",now); }
    }
private:
    int previousAttempt = 1;
};
} // namespace session

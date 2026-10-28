#pragma once
#include <algorithm>
#include <cmath>
#include <cstdint>
#include <functional>
#include <iomanip>
#include <numeric>
#include <map>
#include <random>
#include <sstream>
#include <stdexcept>
#include <string>
#include <tuple>
#include <vector>

namespace session {
constexpr const char* protocolVersion = "eeg-session-2.0";
constexpr const char* movementVersion = "fist-ankle-dorsiflexion-v1";
constexpr int plannedSeconds = 2704, plannedTrials = 168, blocksPerRun = 4;
inline const std::vector<std::string>& runNames() {
    static const std::vector<std::string> names{"Motorik", "Imagery"}; return names;
}
inline std::string clockText(double seconds) {
    int n = int(std::ceil(std::max(0.0, seconds)));
    std::ostringstream out; out << n/60 << ':' << std::setw(2) << std::setfill('0') << n%60; return out.str();
}
struct Condition {
    std::string label, cue, instruction, mode, bodyPart, side;
    int perBlock, taskSeconds;
};
inline const std::vector<Condition>& conditions(int run) {
    static const std::vector<Condition> motor{
        {"me_hand_left","HAND LINKS","linke Faust locker schliessen und oeffnen; ca. 2 Zyklen","motor_execution","hand","left",4,4},
        {"me_hand_right","HAND RECHTS","rechte Faust locker schliessen und oeffnen; ca. 2 Zyklen","motor_execution","hand","right",4,4},
        {"me_foot_left","FUSS LINKS","linken Vorfuss heben/senken; Ferse auflegen; ca. 2 Zyklen","motor_execution","foot","left",4,4},
        {"me_foot_right","FUSS RECHTS","rechten Vorfuss heben/senken; Ferse auflegen; ca. 2 Zyklen","motor_execution","foot","right",4,4}};
    static const std::vector<Condition> mental{
        {"mi_hand_left","HAND LINKS","linke Faustbewegung fuehlen und vorstellen; ohne Bewegung","motor_imagery","hand","left",4,4},
        {"mi_hand_right","HAND RECHTS","rechte Faustbewegung fuehlen und vorstellen; ohne Bewegung","motor_imagery","hand","right",4,4},
        {"mi_foot_left","FUSS LINKS","linkes Vorfussheben fuehlen und vorstellen; ohne Bewegung","motor_imagery","foot","left",4,4},
        {"mi_foot_right","FUSS RECHTS","rechtes Vorfussheben fuehlen und vorstellen; ohne Bewegung","motor_imagery","foot","right",4,4},
        {"mi_hands_bilateral","BEIDE HAENDE","beide Faustbewegungen gleichzeitig vorstellen; ohne Bewegung","motor_imagery","hand","bilateral",3,5},
        {"mi_feet_bilateral","BEIDE FUESSE","beide Vorfuesse gleichzeitig heben/senken vorstellen; ohne Bewegung","motor_imagery","foot","bilateral",3,5},
        {"word_generation","","ein deutsches Wort zum Buchstaben still finden; nicht sprechen","cognitive","","",2,5},
        {"mental_subtraction_single","","einmal still subtrahieren und Ergebnis pruefen","cognitive","","",2,5}};
    if (run == 0) return motor;
    if (run == 1) return mental;
    throw std::runtime_error("Unknown session run.");
}
inline const Condition* definition(const std::string& label) {
    for (int run : {0,1}) for (const auto& item : conditions(run)) if (item.label == label) return &item;
    return nullptr;
}
struct Phase {
    std::string run, stage, condition;
    int block = 0, trial = 0, total = 0, startNumber = 0;
    double duration = 0;
    int subtract = 0;
    std::string wordLetter, nextRun;
    bool isTrial() const { return trial > 0; }
    const Condition* task() const { return definition(condition); }
    std::string cue(double remaining = 0) const {
        if (stage == "break") return "PAUSE\n" + clockText(remaining) + "\nDANACH: " +
            (nextRun == "Motorik" ? "BEWEGEN" : "VORSTELLEN / DENKAUFGABEN");
        if (stage != "task") return "+";
        if (condition == "word_generation") return "WORT MIT " + wordLetter;
        if (condition == "mental_subtraction_single") return std::to_string(startNumber) + " − " + std::to_string(subtract) + "\nEINMAL RECHNEN";
        if (auto value = task()) return value->cue;
        throw std::runtime_error("Unknown task cue: " + condition);
    }
    std::string instruction() const {
        if (stage == "baseline") return "ruhig sitzen, Kreuz ansehen";
        if (stage == "break") return "PAUSE; danach " + nextRun;
        if (stage == "rest") return "ERHOLUNG – ruhig sitzen, Kreuz ansehen";
        if (stage == "prepare") return "Kreuz ansehen";
        if (auto value = task()) return value->instruction;
        throw std::runtime_error("Unknown task instruction: " + condition);
    }
};
struct Plan {
    uint32_t seed;
    std::vector<Phase> phases;
    double duration() const { double n = 0; for (const auto& p : phases) n += p.duration; return n; }
    int trials() const { return int(std::count_if(phases.begin(),phases.end(),[](const Phase& p) { return p.stage == "task"; })); }
    void validate() const {
        if (duration() != plannedSeconds || trials() != plannedTrials || phases.size() != 513)
            throw std::runtime_error("Invalid session totals.");
        std::map<std::pair<std::string,int>,double> durations;
        std::map<std::pair<std::string,int>,std::map<std::string,int>> counts;
        std::map<std::tuple<std::string,int,std::string>,std::vector<int>> rests;
        int baselines = 0, blockBreaks = 0, runBreaks = 0;
        for (size_t i = 0; i < phases.size(); ++i) {
            const auto& p = phases[i];
            if (p.stage == "baseline") { ++baselines; if (p.duration != 60) throw std::runtime_error("Invalid baseline."); continue; }
            if (p.stage == "break") {
                if (p.condition == "block_break" && p.duration == 45) ++blockBreaks;
                else if (p.condition == "run_break" && p.duration == 90) ++runBreaks;
                else throw std::runtime_error("Invalid break.");
                continue;
            }
            auto spec = p.task();
            if (!spec || p.block < 1 || p.block > 4 || p.trial < 1 || p.total != (p.run == "Motorik" ? 64 : 104))
                throw std::runtime_error("Invalid trial context.");
            durations[{p.run,p.block}] += p.duration;
            if (p.stage == "prepare") {
                ++counts[{p.run,p.block}][p.condition];
                if (p.duration != 2 || i+2 >= phases.size()) throw std::runtime_error("Invalid preparation.");
                const auto& task = phases[i+1]; const auto& rest = phases[i+2];
                if (task.stage != "task" || rest.stage != "rest" || task.run != p.run || rest.run != p.run ||
                    task.trial != p.trial || rest.trial != p.trial || task.condition != p.condition || rest.condition != p.condition ||
                    task.startNumber != p.startNumber || rest.startNumber != p.startNumber ||
                    task.subtract != p.subtract || rest.subtract != p.subtract || task.wordLetter != p.wordLetter || rest.wordLetter != p.wordLetter)
                    throw std::runtime_error("Invalid trial phase linkage.");
            } else if (p.stage == "task") {
                if (p.duration != spec->taskSeconds) throw std::runtime_error("Invalid task duration.");
                if (p.condition == "mental_subtraction_single" && (p.startNumber < 60 || p.startNumber > 199 || p.subtract < 12 || p.subtract > 59 || p.startNumber <= p.subtract))
                    throw std::runtime_error("Invalid subtraction.");
                if (p.condition == "word_generation" && p.wordLetter.size() != 1) throw std::runtime_error("Invalid letter.");
            } else if (p.stage == "rest") rests[{p.run,p.block,p.condition}].push_back(int(p.duration));
            else throw std::runtime_error("Invalid trial stage.");
        }
        if (baselines != 2 || blockBreaks != 6 || runBreaks != 1) throw std::runtime_error("Invalid baseline/break counts.");
        for (int run : {0,1}) for (int block = 1; block <= 4; ++block) {
            auto key = std::make_pair(runNames()[run],block);
            if (durations[key] != (run == 0 ? 208 : 348) || counts[key].size() != conditions(run).size()) throw std::runtime_error("Invalid block totals.");
            for (const auto& spec : conditions(run)) {
                if (counts[key][spec.label] != spec.perBlock) throw std::runtime_error("Invalid block balance.");
                auto values = rests[{key.first,block,spec.label}]; std::sort(values.begin(),values.end());
                if ((spec.perBlock == 4 && values != std::vector<int>{6,7,7,8}) ||
                    (spec.perBlock == 3 && values != std::vector<int>{6,7,8}) ||
                    (spec.perBlock == 2 && values != std::vector<int>{6,8} && values != std::vector<int>{7,7}))
                    throw std::runtime_error("Invalid rest balance.");
            }
        }
    }
};
inline Plan makePlan(uint32_t seed, const std::vector<int>& order = {0,1}) {
    auto sorted = order; std::sort(sorted.begin(), sorted.end());
    if (sorted != std::vector<int>{0,1}) throw std::runtime_error("Specify each run once: motorik imagery (or imagery motorik).");
    Plan plan{seed, {}}; std::mt19937 rng(seed);
    auto baseline = [&](const char* name) { Phase p; p.run=name; p.stage="baseline"; p.condition="baseline"; p.duration=60; plan.phases.push_back(p); };
    baseline("Anfangsbaseline");
    std::string letters = "BDFGHKLMNRST"; std::shuffle(letters.begin(),letters.end(),rng); int usedLetters=0;
    std::vector<std::pair<int,int>> numbers;
    for (int a=60; a<=199; ++a) for (int b=12; b<=59; ++b) numbers.emplace_back(a,b);
    std::shuffle(numbers.begin(),numbers.end(),rng); int usedNumbers=0;
    for (size_t position = 0; position < order.size(); ++position) {
        int run = order[position]; const auto& specs=conditions(run);
        std::vector<std::vector<int>> cognitiveBlocks(specs.size(),std::vector<int>{0,0,1,1});
        for (auto& values : cognitiveBlocks) std::shuffle(values.begin(),values.end(),rng);
        int trial=0; std::vector<int> history;
        for (int block=1; block<=4; ++block) {
            std::vector<int> sequence; std::vector<std::vector<int>> rests;
            for (int c=0; c<int(specs.size()); ++c) {
                for (int i=0; i<specs[c].perBlock; ++i) sequence.push_back(c);
                std::vector<int> values = specs[c].perBlock == 4 ? std::vector<int>{6,7,7,8} :
                    specs[c].perBlock == 3 ? std::vector<int>{6,7,8} :
                    cognitiveBlocks[c][block-1] ? std::vector<int>{7,7} : std::vector<int>{6,8};
                std::shuffle(values.begin(),values.end(),rng); rests.push_back(values);
            }
            bool valid=false;
            for (int attempt=0; attempt<100000 && !valid; ++attempt) {
                std::shuffle(sequence.begin(),sequence.end(),rng); auto check=history; valid=true;
                for (int c : sequence) {
                    if (check.size()>=2 && check.back()==c && check[check.size()-2]==c) { valid=false; break; }
                    check.push_back(c);
                }
            }
            if (!valid) throw std::runtime_error("Could not generate balanced trial order.");
            std::vector<int> used(specs.size(),0);
            for (int c : sequence) {
                history.push_back(c); ++trial;
                Phase p; p.run=runNames()[run]; p.condition=specs[c].label; p.block=block; p.trial=trial; p.total=run==0 ? 64 : 104;
                if (p.condition=="word_generation") p.wordLetter=letters.substr(usedLetters++,1);
                if (p.condition=="mental_subtraction_single") { auto pair=numbers.at(usedNumbers++); p.startNumber=pair.first; p.subtract=pair.second; }
                int rest=rests[c][used[c]++];
                for (const auto& step : std::vector<std::pair<std::string,double>>{{"prepare",2},{"task",double(specs[c].taskSeconds)},{"rest",double(rest)}}) {
                    p.stage=step.first; p.duration=step.second; plan.phases.push_back(p);
                }
            }
            if (block<4) { Phase p; p.run=runNames()[run]; p.stage="break"; p.condition="block_break"; p.block=block; p.duration=45; p.nextRun=p.run; plan.phases.push_back(p); }
        }
        if (position+1<order.size()) { Phase p; p.run=runNames()[run]; p.stage="break"; p.condition="run_break"; p.duration=90; p.nextRun=runNames()[order[position+1]]; plan.phases.push_back(p); }
    }
    baseline("Endbaseline"); plan.validate(); return plan;
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

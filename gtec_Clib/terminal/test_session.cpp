#include "session_plan.h"
#include <cassert>
#include <iostream>
#include <map>
#include <set>
#include <tuple>

int main() {
    for (unsigned seed = 0; seed < 250; ++seed) {
        auto plan = session::makePlan(seed), again = session::makePlan(seed);
        assert(plan.duration() == 2296 && plan.phases.size() == 348);
        std::map<std::string,int> counts;
        std::map<std::pair<std::string,int>,int> rests;
        std::map<std::pair<std::string,int>,int> blocks;
        int baselines = 0, blockBreaks = 0, runBreaks = 0;
        std::set<int> numbers;
        std::vector<std::string> history;
        std::string lastRun;
        for (size_t i = 0; i < plan.phases.size(); ++i) {
            const auto& p = plan.phases[i]; const auto& q = again.phases[i];
            assert(p.condition == q.condition && p.duration == q.duration && p.startNumber == q.startNumber);
            if (p.stage == "baseline") { ++baselines; assert(p.duration == 60 && p.cue() == "+"); }
            if (p.stage == "break") {
                if (p.condition == "block_break") { ++blockBreaks; assert(p.duration == 45 && p.cue(45) == "PAUSE\n0:45"); }
                else { ++runBreaks; assert(p.duration == 90 && p.cue(90) == "PAUSE\n1:30"); }
            }
            if (p.stage == "prepare") {
                ++counts[p.condition]; ++blocks[{p.run,p.block}];
                if (lastRun != p.run) history.clear(); lastRun = p.run;
                if (p.run != "Kognitiv" && history.size() >= 2) assert(!(history.back() == p.condition && history[history.size()-2] == p.condition));
                history.push_back(p.condition);
                assert(p.duration == 2 && p.cue() == (p.run == "Kognitiv" ? "READY" : "+"));
                if (p.run == "Kognitiv") { assert(p.startNumber >= 300 && p.startNumber < 900); numbers.insert(p.startNumber); }
            }
            if (p.stage == "task") {
                assert(p.duration == (p.run == "Kognitiv" ? 10 : 4));
                assert(p.cue().find("STOPP") == std::string::npos);
                if (p.run == "Kognitiv") assert(p.cue().find("FORTLAUFEND") != std::string::npos);
            }
            if (p.stage == "rest") { ++rests[{p.condition,int(p.duration)}]; assert(p.cue() == "+"); }
        }
        assert(baselines == 2 && blockBreaks == 8 && runBreaks == 2 && numbers.size() == 12);
        for (auto condition : {"arms","legs","blink","imagine_arms","imagine_legs"}) {
            assert(counts[condition] == 20);
            for (int rest = 6; rest <= 8; ++rest) assert((rests[{condition,rest}] == (rest == 7 ? 10 : 5)));
        }
        assert(counts["mental_arithmetic"] == 12);
        for (int rest = 15; rest <= 17; ++rest) assert((rests[{"mental_arithmetic",rest}] == (rest == 16 ? 6 : 3)));
        for (auto item : blocks) assert(item.second == (item.first.first == "Motorik" ? 15 : item.first.first == "Imagery" ? 10 : 4));
    }
    std::vector<int> order{0,1,2};
    do {
        auto plan = session::makePlan(7,order); std::vector<std::string> seen;
        for (const auto& p : plan.phases) if (p.stage == "prepare" && p.trial == 1) seen.push_back(p.run);
        assert(plan.duration() == 2296 && seen.size() == 3);
        for (size_t i = 0; i < 3; ++i) assert(seen[i] == (std::vector<std::string>{"Motorik","Imagery","Kognitiv"}[order[i]]));
    } while (std::next_permutation(order.begin(),order.end()));
    try { session::makePlan(1,{0,0,1}); assert(false); } catch (const std::runtime_error&) {}
    std::vector<std::tuple<std::string,int,int>> events;
    auto callback = [&](const std::string& name,const session::Phase& p,int attempt,double,double) { events.emplace_back(name,p.trial,attempt); };
    session::Timeline t(session::makePlan(42),callback);
    t.start(100); assert(t.remaining(100) == 2296);
    // Initial baseline restarts entirely, pause freezes planned clock.
    t.pause(110); assert(t.remaining(200) == 2286);
    t.resume(210); assert(t.remaining(210) == 2296);
    assert(t.phaseRemaining(210) == 60 && t.attempt == 2);
    t.advance(270); assert(t.phase().stage == "prepare" && t.phase().trial == 1);
    t.advance(272); assert(t.phase().stage == "task");
    auto condition = t.phase().condition;
    t.pause(273); double remaining = t.remaining(273);
    assert(t.remaining(900) == remaining && t.invalid == 1);
    t.resume(300); assert(t.phase().stage == "prepare" && t.phase().condition == condition && t.attempt == 2);
    assert(t.remaining(300) == remaining+3);
    t.advance(302); assert(t.attempt == 2);
    t.advance(306); assert(t.phase().stage == "rest" && t.attempt == 2);
    t.pause(307); t.resume(400); assert(t.attempt == 3 && t.phase().stage == "prepare");
    assert(t.invalid == 2 && t.repeats == 2);
    t.pause(401); t.resume(410); assert(t.attempt == 4);
    // Finish using simulated deadlines, exercise pause in planned break.
    bool pausedBreak = false;
    while (t.running) {
        if (!pausedBreak && t.phase().stage == "break") {
            double at = t.deadline-10; t.pause(at); assert(t.phaseRemaining(at+100) == 10);
            t.resume(at+100); assert(t.phaseRemaining(at+100) == 10); pausedBreak = true;
        }
        t.advance(t.deadline);
    }
    assert(t.completed && t.remaining(t.deadline) == 0 && t.completedTrials == 112);
    assert(pausedBreak);
    std::map<std::string,int> totals;
    for (auto e : events) ++totals[std::get<0>(e)];
    assert(totals["trial_end"] == 112 && totals["run_start"] == 3 && totals["run_end"] == 3);
    assert(totals["block_start"] == 11 && totals["block_end"] == 11);
    assert(totals["trial_invalidated"] == 3 && totals["trial_repeat"] == 3);
    assert(totals["session_end"] == 1);
    try { t.resume(0); assert(false); } catch (const std::runtime_error&) {}
    // Distinct display cues and stable countdown rounding.
    assert(session::clockText(2296) == "38:16" && session::clockText(.01) == "0:01" && session::clockText(-1) == "0:00");
    std::cout << "PASS: 250 seeds, balanced plans, 2296 seconds, cues, timeline, pauses, repeats, attempt IDs, event boundaries\n";
}

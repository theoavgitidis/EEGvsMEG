#include "session_plan.h"
#include <cassert>
#include <iostream>
#include <map>
#include <set>
#include <tuple>

int main() {
    for (unsigned seed=0; seed<250; ++seed) for (const auto& order : std::vector<std::vector<int>>{{0,1},{1,0}}) {
        auto plan=session::makePlan(seed,order), again=session::makePlan(seed,order);
        assert(plan.duration()==2704 && plan.trials()==168 && plan.phases.size()==513);
        std::map<std::string,int> counts;
        std::map<std::pair<std::string,int>,int> rests;
        std::map<std::pair<std::string,int>,double> blockDurations;
        int baselines=0, blockBreaks=0, runBreaks=0;
        std::set<std::pair<int,int>> numbers; std::set<std::string> letters;
        std::vector<std::string> history, seenRuns; std::string lastRun;
        for (size_t i=0; i<plan.phases.size(); ++i) {
            const auto& p=plan.phases[i]; const auto& q=again.phases[i];
            assert(p.run==q.run && p.condition==q.condition && p.duration==q.duration && p.startNumber==q.startNumber && p.subtract==q.subtract && p.wordLetter==q.wordLetter);
            if (p.stage=="baseline") { ++baselines; assert(p.duration==60 && p.cue()=="+"); }
            if (p.stage=="break") {
                if (p.condition=="block_break") { ++blockBreaks; assert(p.duration==45 && p.cue(45).find("PAUSE\n0:45")==0); }
                else { ++runBreaks; assert(p.duration==90 && p.nextRun==session::runNames()[order[1]]); }
            }
            if (p.isTrial()) blockDurations[{p.run,p.block}]+=p.duration;
            if (p.stage=="prepare") {
                ++counts[p.condition];
                if (lastRun!=p.run) { history.clear(); seenRuns.push_back(p.run); }
                lastRun=p.run;
                if (history.size()>=2) assert(!(history.back()==p.condition && history[history.size()-2]==p.condition));
                history.push_back(p.condition);
                assert(p.duration==2 && p.cue()=="+");
                if (p.condition=="mental_subtraction_single") {
                    assert(p.startNumber>=60 && p.startNumber<=199 && p.subtract>=12 && p.subtract<=59 && p.startNumber>p.subtract);
                    numbers.insert({p.startNumber,p.subtract});
                }
                if (p.condition=="word_generation") { assert(p.wordLetter.size()==1); letters.insert(p.wordLetter); }
            }
            if (p.stage=="task") {
                assert(p.duration==p.task()->taskSeconds && p.cue().find("STOPP")==std::string::npos && !p.instruction().empty());
                if (p.condition=="word_generation") assert(p.cue()=="WORT MIT "+p.wordLetter);
                if (p.condition=="mental_subtraction_single") assert(p.cue().find(std::to_string(p.startNumber)+" − "+std::to_string(p.subtract))==0);
            }
            if (p.stage=="rest") { ++rests[{p.condition,int(p.duration)}]; assert(p.cue()=="+"); }
        }
        assert(baselines==2 && blockBreaks==6 && runBreaks==1 && numbers.size()==8 && letters.size()==8);
        assert(seenRuns==std::vector<std::string>({session::runNames()[order[0]],session::runNames()[order[1]]}));
        for (int run : {0,1}) for (const auto& spec : session::conditions(run)) {
            assert(counts[spec.label]==4*spec.perBlock);
            auto expected=spec.perBlock==4 ? std::vector<int>{4,8,4} : spec.perBlock==3 ? std::vector<int>{4,4,4} : std::vector<int>{2,4,2};
            for (int rest=6; rest<=8; ++rest) assert((rests[{spec.label,rest}]==expected[rest-6]));
        }
        for (const auto& item : blockDurations) assert(item.second==(item.first.first=="Motorik" ? 208 : 348));
    }
    for (const auto& invalid : std::vector<std::vector<int>>{{},{0},{0,0},{0,1,2},{2,1}}) {
        try { session::makePlan(1,invalid); assert(false); } catch (const std::runtime_error&) {}
    }
    auto corrupt=session::makePlan(1); corrupt.phases[2].duration=5;
    try { corrupt.validate(); assert(false); } catch (const std::runtime_error&) {}
    // Every new condition repeats with exactly the same payload after interruption.
    for (const auto& spec : session::conditions(1)) for (const std::string stage : {"prepare","task","rest"}) {
        session::Timeline repeat(session::makePlan(7,{1,0}),[](const std::string&,const session::Phase&,int,double,double){});
        repeat.start(0);
        while (repeat.phase().condition!=spec.label || repeat.phase().stage!=stage) repeat.advance(repeat.deadline);
        auto original=repeat.phase(); double at=repeat.deadline-.5;
        repeat.pause(at); repeat.resume(at+100);
        assert(repeat.phase().stage=="prepare" && repeat.attempt==2);
        assert(repeat.phase().condition==original.condition && repeat.phase().trial==original.trial && repeat.phase().startNumber==original.startNumber && repeat.phase().subtract==original.subtract && repeat.phase().wordLetter==original.wordLetter);
    }
    assert(session::conditions(0)[0].cue==session::conditions(1)[0].cue);
    assert(session::conditions(0)[2].cue==session::conditions(1)[2].cue);
    std::vector<std::tuple<std::string,int,int>> events;
    auto callback = [&](const std::string& name,const session::Phase& p,int attempt,double,double) { events.emplace_back(name,p.trial,attempt); };
    session::Timeline t(session::makePlan(42),callback);
    t.start(100); assert(t.remaining(100) == 2704);
    // Initial baseline restarts entirely, pause freezes planned clock.
    t.pause(110); assert(t.remaining(200) == 2694);
    t.resume(210); assert(t.remaining(210) == 2704);
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
    assert(t.completed && t.remaining(t.deadline) == 0 && t.completedTrials == 168);
    assert(pausedBreak);
    std::map<std::string,int> totals;
    for (auto e : events) ++totals[std::get<0>(e)];
    assert(totals["trial_end"] == 168 && totals["run_start"] == 2 && totals["run_end"] == 2);
    assert(totals["block_start"] == 8 && totals["block_end"] == 8);
    assert(totals["trial_invalidated"] == 3 && totals["trial_repeat"] == 3);
    assert(totals["session_end"] == 1);
    try { t.resume(0); assert(false); } catch (const std::runtime_error&) {}
    // Distinct display cues and stable countdown rounding.
    assert(session::clockText(2704) == "45:04" && session::clockText(.01) == "0:01" && session::clockText(-1) == "0:00");
    std::cout << "PASS: 250 seeds, balanced plans, 2704 seconds, cues, timeline, pauses, repeats, attempt IDs, event boundaries\n";
}

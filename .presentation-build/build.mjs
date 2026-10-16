import fs from 'node:fs/promises';
import {Presentation, PresentationFile} from '@oai/artifact-tool';
import {finalizePresentation} from '/Users/theoa/.codex/plugins/cache/openai-primary-runtime/presentations/26.1013.11914/skills/presentations/container_tools/artifact_tool_utils.mjs';
const root='/Users/theoa/Desktop/Projects/EEGvsMEG';
const skill='/Users/theoa/.codex/plugins/cache/openai-primary-runtime/presentations/26.1013.11914/skills/presentations';
const p=Presentation.create({slideSize:{width:1280,height:720}});
const navy='#142B3B', teal='#087F83', gray='#435563', paper='#F6F5F0';
function txt(s,text,x,y,w,h,size=28,color=navy,bold=false){const t=s.shapes.add({geometry:'textbox',position:{left:x,top:y,width:w,height:h},fill:'none',line:{fill:'none',width:0}});t.text=text;t.text.style={fontFamily:'Aptos',fontSize:size,color,bold};return t;}
function slide(title,number){const s=p.slides.add();s.background.fill=paper;txt(s,title,72,55,1136,100,46,navy,true);txt(s,String(number).padStart(2,'0'),1150,653,60,30,18,gray);return s;}
function row(s,label,body,y){txt(s,label,74,y,315,65,29,teal,true);txt(s,body,418,y,775,85,28,navy);}
function notes(s,text,sources){s.speakerNotes.text=text+'\n\nProject sources:\n'+sources.map(a=>root+'/'+a).join('\n');}
let s=slide('EEG vs MEG',1);
txt(s,'Implementation progress',74,235,1100,80,58,navy,true);
txt(s,'EEG acquisition and experiment preparation',76,341,1080,60,32,gray);
txt(s,'Theodoros Avgitidis\n15 October 2026',76,530,1000,80,25,teal);
notes(s,'This project investigates which motor and cognitive tasks a practical EEG setup can distinguish, with MEG task paradigms as a reference. The current implementation supports recording and inspection. A completed EEG–MEG performance comparison is not established by the project files.',['docs/planned-experiments.md','docs/Einwilligungserklaerung_EEG-Studie.html','gtec_Clib/terminal/README.md']);
s=slide('Project aim and current scope',2);
txt(s,'Which tasks can we distinguish with EEG?',74,179,1110,80,39,teal,true);
row(s,'Research aim','Compare actual movement, imagined movement and mental tasks.',300);
row(s,'Implemented','Record EEG, present instructions, label tasks and inspect signals.',412);
row(s,'Next research stage','Collect pilot data and evaluate task classification and MEG comparability.',524);
notes(s,'The earlier study plan references MEGBCI2020 and includes word generation. The newer protocol dated 13 October focuses the pilot on movement, imagery, blinking and serial subtraction. Treat the latest protocol as the current pilot proposal. No classifier, MEG processing pipeline or microcontroller control implementation appears in the inspected project.',['docs/planned-experiments.md','docs/experiment-protocol.md','analysis/view_eeg.py','gtec_Clib/terminal/main.cpp']);
s=slide('EEG connection and recording',3);
row(s,'Device setup','Find and connect the Unicorn headset. Inspect device details and select channels.',186);
row(s,'Recording modes','Capture short checks or continuous sessions, with an optional automatic stop.',306);
row(s,'Saved data','Export channel values and timing information to CSV at 250 samples per second.',426);
row(s,'Session monitoring','Check sample counts, recording errors and available device status indicators.',546);
notes(s,'The terminal covers the supplied Unicorn API: version and error information, Bluetooth adapter information, paired/unpaired discovery, open/close, device information, channel configuration and index lookup, acquisition, data export, and optional digital output read/write. Digital outputs depend on device support. Production acquisition requires 64-bit Windows, the vendor DLL, Bluetooth and a compatible headset. Background recording reads blocks continuously and reports counter discontinuities plus battery and validation values if enabled. These values do not constitute a validated signal-quality score.',['gtec_Clib/terminal/main.cpp','gtec_Clib/terminal/recorder.h','gtec_Clib/terminal/README.md']);
s=slide('Experiment organisation and task instructions',4);
row(s,'Experiment folders','Create, select and list experiments. Keep EEG files and task labels together.',183);
row(s,'Participant display','Show movement, subtraction or custom instructions in a separate Windows window.',300);
row(s,'Task markers','Log task labels during recording and update the participant display.',417);
row(s,'Data protection','Prevent accidental overwrites and experiment changes during acquisition.',534);
notes(s,'The participant window supports a fixation cross, German hand/leg instructions, parameterised serial subtraction, arbitrary text and fullscreen mode. Marker labels can contain spaces and quotes. Markers use host timing and received sample counts. They indicate command processing and approximate sample positions, not exact stimulus onset or precise EEG–MEG synchronisation. Cues and timing are operator-driven. An automated trial scheduler is not implemented. Experiment names support Unicode and spaces, with checks against invalid names and paths.',['gtec_Clib/terminal/cues.h','gtec_Clib/terminal/experiments.h','gtec_Clib/terminal/recorder.h','gtec_Clib/terminal/main.cpp']);
s=slide('Signal inspection and software checks',5);
row(s,'EEG viewer','Open recorded channels and task markers in MNE for visual inspection.',182);
row(s,'Display options','View signal traces or frequency spectra. Apply optional display filtering.',299);
row(s,'Input checks','Check units, sample numbering and invalid values. Warn about counter gaps.',416);
row(s,'Software testing','Simulated-device tests pass for recording, markers, file safeguards and failure handling.',533);
notes(s,'The viewer accepts EEG 1–8 columns, asks explicitly for the recorded unit and converts values to volts for MNE. It imports event positions approximately from samples_received / 250. Optional filtering uses a 50 Hz notch and 0.5–30 Hz bandpass on a copy, preserving the CSV. It provides Welch frequency spectra. It does not implement artifact correction, feature extraction or classification. The hardware-free integration suite passed on 15 October 2026 in this workspace. It covers Unicode experiment names, path validation, switching guards, manual export, timed recording, CSV quoting, exclusive API access, overwrite prevention, continuous stop and simulated connection failure. This does not verify Bluetooth or real headset behaviour.',['analysis/view_eeg.py','gtec_Clib/terminal/test_recorder.py','gtec_Clib/terminal/mock_api.cpp']);
s=slide('Study materials and proposed pilot',6);
txt(s,'Prepared documentation',74,178,495,55,32,teal,true);
txt(s,'German operating guide\nHeadset and software summary\nParticipant information and consent\nTask descriptions and pilot protocol',74,260,510,290,28);
txt(s,'Latest pilot proposal',662,178,545,55,32,teal,true);
txt(s,'Actual arm and leg movement, blinking\nImagined arm and leg movement\nSilent serial subtraction\nBaseline recordings and recovery periods',662,260,545,290,28);
txt(s,'112 task trials · About 29 minutes of measurement, or 38 minutes including planned breaks',74,596,1115,65,25,gray);
notes(s,'The 13 October protocol is a proposed design, not an implemented automatic experiment. It specifies 60 physical-movement/blink trials, 40 imagery trials and 12 arithmetic trials, plus 60-second opening and closing baselines. Measurement totals 29:16 including within-trial recovery. Additional breaks total 9 minutes, giving 38:16 before setup, instruction and practice. The proposal specifies balanced task counts, randomisation constraints, saved seeds, trial lists and counterbalanced run orders. These remain protocol requirements rather than coded scheduler features. Word generation appears in earlier planning and is absent from the latest pilot. The participant information and consent document is prepared material, not evidence of institutional approval.',['docs/experiment-protocol.md','docs/planned-experiments.md','docs/plannedExperiments/README.md','docs/manual/unicorn-hybrid-black-and-suite-summary.md','docs/Einwilligungserklaerung_EEG-Studie.html','gtec_Clib/terminal/VERWENDUNG.md']);
s=slide('Remaining work and next steps',7);
row(s,'Pilot validation','Confirm headset behaviour, recording stability and instruction timing with participants.',181);
row(s,'Experiment automation','Implement the proposed trial sequence, randomisation and planned timing.',298);
row(s,'Scientific analysis','Define artifact handling and evaluate classifiers on held-out trials or blocks.',415);
row(s,'EEG–MEG comparison','Choose comparable tasks and evaluation measures, then assess performance.',532);
notes(s,'The implemented tools provide a foundation for acquisition and visual inspection. They do not establish classification accuracy, validated neural effects or MEG equivalence. Physical movement and blinking can introduce muscle, movement and eye signals, so interpretation needs appropriate artifact handling. The protocol recommends keeping segments from the same trial together during evaluation and holding out entire participants for claims about new people. Precise synchronisation requires additional validation and potentially external timing hardware. Microcontroller control remains an application aim in the consent material, with no implementation found in the current project.',['docs/experiment-protocol.md','docs/Einwilligungserklaerung_EEG-Studie.html','gtec_Clib/terminal/README.md','analysis/view_eeg.py']);
for(let i=0;i<p.slides.items.length;i++){const png=await p.export({slide:p.slides.items[i],format:'png',scale:1});await fs.writeFile(root+'/.presentation-build/slide-'+(i+1)+'.png',new Uint8Array(await png.arrayBuffer()));}
await (await PresentationFile.exportPptx(p)).save(root+'/.presentation-build/draft.pptx');
await finalizePresentation({workspaceDir:root,candidatePath:root+'/.presentation-build/draft.pptx',finalPath:root+'/presentations/EEGvsMEG_Progress.pptx',pythonExecutable:'/Users/theoa/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3',integrityValidatorPath:skill+'/container_tools/inspect_presentation_package_integrity.py',layoutValidatorPath:skill+'/container_tools/inspect_presentation_layout_geometry.py',layoutArgs:['--expected-slide-size-emu','12192000,6858000','--validate-heading-fit'],fontPolicy:{basis:'design',families:['Aptos']},verifyArtifactToolImport:true,receiptPath:root+'/.presentation-build/validation.json'});
console.log('DONE');

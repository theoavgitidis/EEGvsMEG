#pragma once
#include <functional>
#include <iostream>
#include <string>
#include <vector>
#ifdef _WIN32
#include <conio.h>
#endif

// Console editing and rendering share this thread; session workers never print.
class Console {
public:
    bool read(const std::string& prompt, std::string& line,
              const std::function<std::vector<std::string>()>& status) {
#ifdef _WIN32
        HANDLE input = GetStdHandle(STD_INPUT_HANDLE), output = GetStdHandle(STD_OUTPUT_HANDLE);
        DWORD mode = 0, outMode = 0;
        if (GetConsoleMode(input,&mode) && GetConsoleMode(output,&outMode)
                && SetConsoleMode(output,outMode | ENABLE_VIRTUAL_TERMINAL_PROCESSING)) {
            auto wide = [](const std::string& text) {
                int size = MultiByteToWideChar(CP_UTF8,0,text.data(),int(text.size()),nullptr,0);
                std::wstring result(size,L' '); MultiByteToWideChar(CP_UTF8,0,text.data(),int(text.size()),result.data(),size); return result;
            };
            auto write = [&](const std::wstring& text) { DWORD written; WriteConsoleW(output,text.data(),DWORD(text.size()),&written,nullptr); };
            std::wstring edit; int drawn = 0; auto last = std::chrono::steady_clock::time_point{};
            while (true) {
                if (std::chrono::steady_clock::now()-last >= std::chrono::milliseconds(100)) {
                    auto rows = status(); rows.push_back(prompt);
                    CONSOLE_SCREEN_BUFFER_INFO info{}; GetConsoleScreenBufferInfo(output,&info);
                    int width = std::max(20,int(info.srWindow.Right-info.srWindow.Left));
                    if (drawn) write(L"\r\x1b["+std::to_wstring(drawn)+L"A");
                    for (size_t i = 0; i < rows.size(); ++i) {
                        auto text = wide(rows[i]);
                        if (i+1 == rows.size()) text += edit;
                        if (int(text.size()) > width) text = text.substr(text.size()-width);
                        write(L"\r\x1b[2K"+text+(i+1 == rows.size() ? L"" : L"\n"));
                    }
                    drawn = int(rows.size())-1; last = std::chrono::steady_clock::now();
                }
                if (_kbhit()) {
                    wchar_t c = wchar_t(_getwch());
                    if (c == 0 || c == 224) { _getwch(); continue; }
                    if (c == 26 || c == 4) { write(L"\n"); return false; }
                    if (c == L'\r') {
                        write(L"\n");
                        int n = WideCharToMultiByte(CP_UTF8,0,edit.data(),int(edit.size()),nullptr,0,nullptr,nullptr);
                        line.assign(n,' '); WideCharToMultiByte(CP_UTF8,0,edit.data(),int(edit.size()),line.data(),n,nullptr,nullptr);
                        return true;
                    }
                    if (c == L'\b') { if (!edit.empty()) edit.pop_back(); }
                    else if (c >= L' ') edit += c;
                    last = {};
                }
                std::this_thread::sleep_for(std::chrono::milliseconds(10));
            }
        }
#endif
        (void)status;
        std::cout << prompt << std::flush;
        return bool(std::getline(std::cin,line));
    }
};

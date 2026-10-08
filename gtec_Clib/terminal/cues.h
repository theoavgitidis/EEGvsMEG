#pragma once
#include <string>
#include <stdexcept>
#ifdef _WIN32
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>
#include <thread>
#include <mutex>
#include <condition_variable>
#include <atomic>

class Cues {
    std::thread ui;
    std::atomic<HWND> window{nullptr};
    std::mutex mutex;
    std::condition_variable ready;
    bool initialized = false;
    std::wstring text = L"+";
    bool fullscreen = false;
    RECT previous{};
    static constexpr UINT displayMessage = WM_APP + 1;
    static LRESULT CALLBACK procedure(HWND hwnd, UINT message, WPARAM w, LPARAM l) {
        auto* self = reinterpret_cast<Cues*>(GetWindowLongPtrW(hwnd, GWLP_USERDATA));
        if (message == WM_NCCREATE) {
            self = static_cast<Cues*>(reinterpret_cast<CREATESTRUCTW*>(l)->lpCreateParams);
            SetWindowLongPtrW(hwnd, GWLP_USERDATA, reinterpret_cast<LONG_PTR>(self));
        }
        if (!self) return DefWindowProcW(hwnd, message, w, l);
        if (message == displayMessage) {
            self->text = *reinterpret_cast<const std::wstring*>(l);
            InvalidateRect(hwnd, nullptr, TRUE);
            UpdateWindow(hwnd); // marker is logged after this synchronous paint request
            return 0;
        }
        if (message == WM_KEYDOWN && w == VK_F11) {
            self->fullscreen = !self->fullscreen;
            if (self->fullscreen) {
                GetWindowRect(hwnd, &self->previous);
                MONITORINFO monitor{sizeof(MONITORINFO)};
                GetMonitorInfoW(MonitorFromWindow(hwnd, MONITOR_DEFAULTTONEAREST), &monitor);
                SetWindowLongPtrW(hwnd, GWL_STYLE, WS_POPUP | WS_VISIBLE);
                const auto& r = monitor.rcMonitor;
                SetWindowPos(hwnd, HWND_TOP, r.left, r.top, r.right-r.left, r.bottom-r.top, SWP_FRAMECHANGED);
            } else {
                SetWindowLongPtrW(hwnd, GWL_STYLE, WS_OVERLAPPEDWINDOW | WS_VISIBLE);
                const auto& r = self->previous;
                SetWindowPos(hwnd, nullptr, r.left, r.top, r.right-r.left, r.bottom-r.top, SWP_FRAMECHANGED | SWP_NOZORDER);
            }
            return 0;
        }
        if (message == WM_KEYDOWN && w == VK_ESCAPE) {
            if (self->fullscreen) SendMessageW(hwnd, WM_KEYDOWN, VK_F11, 0);
            return 0;
        }
        if (message == WM_PAINT) {
            PAINTSTRUCT paint{}; HDC dc = BeginPaint(hwnd, &paint);
            RECT r; GetClientRect(hwnd, &r);
            FillRect(dc, &r, static_cast<HBRUSH>(GetStockObject(BLACK_BRUSH)));
            SetBkMode(dc, TRANSPARENT); SetTextColor(dc, RGB(255,255,255));
            HFONT font = CreateFontW(-48, 0, 0, 0, FW_NORMAL, FALSE, FALSE, FALSE,
                DEFAULT_CHARSET, OUT_DEFAULT_PRECIS, CLIP_DEFAULT_PRECIS, CLEARTYPE_QUALITY,
                DEFAULT_PITCH, L"Segoe UI");
            auto old = SelectObject(dc, font);
            RECT measured{0,0,r.right-80,0};
            DrawTextW(dc, self->text.c_str(), -1, &measured, DT_CENTER | DT_WORDBREAK | DT_CALCRECT | DT_NOPREFIX);
            RECT area{40, (r.bottom-(measured.bottom-measured.top))/2, r.right-40, r.bottom};
            DrawTextW(dc, self->text.c_str(), -1, &area, DT_CENTER | DT_WORDBREAK | DT_NOPREFIX);
            SelectObject(dc, old); DeleteObject(font); EndPaint(hwnd, &paint);
            return 0;
        }
        if (message == WM_DESTROY) { self->window = nullptr; PostQuitMessage(0); return 0; }
        return DefWindowProcW(hwnd, message, w, l);
    }
public:
    ~Cues() { close(); }
    bool active() const { return window.load() != nullptr; }
    void open() {
        if (active()) return;
        close(); initialized = false; fullscreen = false; text = L"+";
        ui = std::thread([this]() {
            WNDCLASSW cls{}; cls.lpfnWndProc = procedure; cls.style = CS_HREDRAW | CS_VREDRAW;
            cls.hInstance = GetModuleHandleW(nullptr); cls.lpszClassName = L"UnicornParticipantCues";
            cls.hCursor = LoadCursor(nullptr, IDC_ARROW);
            RegisterClassW(&cls);
            HWND hwnd = CreateWindowExW(0, cls.lpszClassName, L"Unicorn - Teilnehmer", WS_OVERLAPPEDWINDOW,
                CW_USEDEFAULT, CW_USEDEFAULT, 1000, 700, nullptr, nullptr, cls.hInstance, this);
            if (hwnd) { ShowWindow(hwnd, SW_SHOW); UpdateWindow(hwnd); }
            { std::lock_guard<std::mutex> lock(mutex); window = hwnd; initialized = true; }
            ready.notify_one();
            if (hwnd) { MSG msg{}; while (GetMessageW(&msg, nullptr, 0, 0) > 0) { TranslateMessage(&msg); DispatchMessageW(&msg); } }
        });
        std::unique_lock<std::mutex> lock(mutex);
        ready.wait(lock, [this] { return initialized; });
        if (!active()) throw std::runtime_error("Could not create participant window.");
    }
    void close() {
        if (auto hwnd = window.load()) PostMessageW(hwnd, WM_CLOSE, 0, 0);
        if (ui.joinable()) ui.join();
    }
    void show(const std::string& value) {
        auto hwnd = window.load();
        if (!hwnd) throw std::runtime_error("Open the participant window with cue open first.");
        int size = MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, value.data(), int(value.size()), nullptr, 0);
        if (!size) throw std::runtime_error("Cue text must be UTF-8.");
        std::wstring converted(size, L' ');
        MultiByteToWideChar(CP_UTF8, 0, value.data(), int(value.size()), converted.data(), size);
        SendMessageW(hwnd, displayMessage, 0, reinterpret_cast<LPARAM>(&converted));
        if (!IsWindow(hwnd)) throw std::runtime_error("Participant window was closed; cue was not confirmed.");
    }
};
#else
class Cues {
public:
    bool active() const { return false; }
    void open() { throw std::runtime_error("Participant window requires Windows."); }
    void close() {}
    void show(const std::string&) { throw std::runtime_error("Participant window requires Windows."); }
};
#endif

inline std::string cueForMarker(const std::string& label) {
    if (label == "rest" || label == "baseline" || label == "fixation") return "+";
    if (label == "hands" || label == "hands_up") return "Hände hochheben";
    if (label == "hands_down") return "Hände senken";
    if (label == "imagine_hands") return "Stelle dir vor, deine Hände hochzuheben";
    return label;
}

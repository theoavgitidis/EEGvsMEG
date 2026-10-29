#pragma once
#include <filesystem>
#include <string>
#include <stdexcept>
#include <chrono>
#include <thread>
#include <vector>
#include <fstream>
#ifdef _WIN32
#include <windows.h>
#else
#include <cerrno>
#include <fcntl.h>
#include <signal.h>
#include <sys/wait.h>
#include <unistd.h>
#endif

// No shell, no command substitution. A worker has exclusive ownership of its
// pipes and is stopped before they are disposed. stderr is a session artifact.
class WorkerProcess {
    bool exitOk = false;
#ifdef _WIN32
    HANDLE process = nullptr, input = nullptr, output = nullptr;
    static std::wstring wide(const std::string& s) {
        if (s.empty()) return {};
        int n = MultiByteToWideChar(CP_UTF8,MB_ERR_INVALID_CHARS,s.data(),int(s.size()),nullptr,0);
        if (!n) throw std::runtime_error("Invalid UTF-8 worker argument.");
        std::wstring out(n,L'\0'); MultiByteToWideChar(CP_UTF8,MB_ERR_INVALID_CHARS,s.data(),int(s.size()),out.data(),n); return out;
    }
    static std::wstring quoted(const std::wstring& s) {
        std::wstring out = L"\""; size_t slashes = 0;
        for (wchar_t c : s) {
            if (c == L'\\') { ++slashes; continue; }
            out.append(c == L'"' ? slashes*2+1 : slashes,L'\\'); slashes = 0; out += c;
        }
        out.append(slashes*2,L'\\'); return out+L'"';
    }
    static std::pair<std::filesystem::path,std::filesystem::path> interpreter(const std::string& configured) {
        auto executable=std::filesystem::u8path(configured);
        auto root=executable.parent_path().parent_path();
        std::ifstream input(root/"pyvenv.cfg");
        std::string line, home;
        while (std::getline(input,line)) if (line.rfind("home = ",0)==0) { home=line.substr(7); break; }
        auto packages=root/"Lib"/"site-packages";
        auto base=home.empty() ? std::filesystem::path{} : std::filesystem::u8path(home)/"python.exe";
        if (std::filesystem::is_regular_file(base) && std::filesystem::is_directory(packages)) return {base,packages};
        return {executable,{}};
    }
#else
    pid_t process = -1;
    int input = -1, output = -1;
#endif
public:
    unsigned long id() const {
#ifdef _WIN32
        return process ? GetProcessId(process) : 0;
#else
        return process > 0 ? static_cast<unsigned long>(process) : 0;
#endif
    }
    static std::string executablePath() {
#ifdef _WIN32
        std::wstring path(32768,L'\0');
        auto size=GetModuleFileNameW(nullptr,path.data(),DWORD(path.size()));
        if (size && size < path.size()) { path.resize(size); return std::filesystem::path(path).u8string(); }
#endif
        return "unavailable on this platform";
    }
    bool successful() const { return exitOk; }
    bool active() const {
#ifdef _WIN32
        return process != nullptr;
#else
        return process > 0;
#endif
    }
    ~WorkerProcess() { dispose(); }
    void start(const std::string& python, const std::filesystem::path& script,
               const std::string& serial, const std::filesystem::path& path) {
        if (active()) throw std::runtime_error("Worker is already allocated.");
        exitOk=false;
        auto logPath = path; logPath += ".worker.log";
#ifdef _WIN32
        SECURITY_ATTRIBUTES sa{sizeof(sa),nullptr,TRUE};
        HANDLE childInput=nullptr, childOutput=nullptr;
        if (!CreatePipe(&childInput,&input,&sa,0) || !CreatePipe(&output,&childOutput,&sa,0)) {
            if (childInput) CloseHandle(childInput); if (childOutput) CloseHandle(childOutput);
            dispose(); throw std::runtime_error("Cannot create worker pipes.");
        }
        SetHandleInformation(input,HANDLE_FLAG_INHERIT,0); SetHandleInformation(output,HANDLE_FLAG_INHERIT,0);
        HANDLE log = CreateFileW(logPath.c_str(),GENERIC_WRITE,FILE_SHARE_READ,&sa,CREATE_NEW,FILE_ATTRIBUTE_NORMAL,nullptr);
        if (log == INVALID_HANDLE_VALUE) { CloseHandle(childInput); CloseHandle(childOutput); dispose(); throw std::runtime_error("Cannot create worker log."); }
        SIZE_T attributeSize=0;
        InitializeProcThreadAttributeList(nullptr,1,0,&attributeSize);
        std::vector<unsigned char> attributeStorage(attributeSize);
        auto attributes=reinterpret_cast<LPPROC_THREAD_ATTRIBUTE_LIST>(attributeStorage.data());
        if (!InitializeProcThreadAttributeList(attributes,1,0,&attributeSize)) {
            CloseHandle(childInput); CloseHandle(childOutput); CloseHandle(log); dispose();
            throw std::runtime_error("Cannot initialize OSCAR worker handle list.");
        }
        HANDLE inherited[] = {childInput,childOutput,log};
        if (!UpdateProcThreadAttribute(attributes,0,PROC_THREAD_ATTRIBUTE_HANDLE_LIST,
                                       inherited,sizeof(inherited),nullptr,nullptr)) {
            DeleteProcThreadAttributeList(attributes);
            CloseHandle(childInput); CloseHandle(childOutput); CloseHandle(log); dispose();
            throw std::runtime_error("Cannot restrict OSCAR worker handle inheritance.");
        }
        STARTUPINFOEXW si{}; si.StartupInfo.cb=sizeof(si); si.StartupInfo.dwFlags=STARTF_USESTDHANDLES;
        si.StartupInfo.hStdInput=childInput; si.StartupInfo.hStdOutput=childOutput; si.StartupInfo.hStdError=log;
        si.lpAttributeList=attributes;
        auto [childPython,packages]=interpreter(python);
        std::wstring previousPythonPath;
        bool hadPythonPath=false;
        if (!packages.empty()) {
            DWORD size=GetEnvironmentVariableW(L"PYTHONPATH",nullptr,0);
            hadPythonPath=size != 0;
            if (hadPythonPath) { previousPythonPath.resize(size); GetEnvironmentVariableW(L"PYTHONPATH",previousPythonPath.data(),size); previousPythonPath.pop_back(); }
            auto pythonPath=packages.wstring();
            if (hadPythonPath) pythonPath+=L";"+previousPythonPath;
            if (!SetEnvironmentVariableW(L"PYTHONPATH",pythonPath.c_str())) throw std::runtime_error("Cannot configure OSCAR Python package path.");
        }
        PROCESS_INFORMATION pi{};
        std::wstring command=quoted(childPython.wstring())+L" -u "+quoted(script.wstring())+L" --serial "+quoted(wide(serial))+L" --output "+quoted(path.wstring());
        BOOL ok=CreateProcessW(nullptr,command.data(),nullptr,nullptr,TRUE,CREATE_NO_WINDOW|EXTENDED_STARTUPINFO_PRESENT,
                               nullptr,nullptr,&si.StartupInfo,&pi);
        if (!packages.empty()) SetEnvironmentVariableW(L"PYTHONPATH",hadPythonPath ? previousPythonPath.c_str() : nullptr);
        DeleteProcThreadAttributeList(attributes);
        CloseHandle(childInput); CloseHandle(childOutput); CloseHandle(log);
        if (!ok) { dispose(); throw std::runtime_error("Cannot launch OSCAR Python; set EEG_OSCAR_PYTHON to its executable path."); }
        process=pi.hProcess; CloseHandle(pi.hThread);
#else
        int a[2],b[2];
        if (pipe(a)) throw std::runtime_error("Cannot create worker stdin pipe.");
        if (pipe(b)) { ::close(a[0]); ::close(a[1]); throw std::runtime_error("Cannot create worker stdout pipe."); }
        int log=::open(logPath.c_str(),O_WRONLY|O_CREAT|O_EXCL,0600);
        if (log < 0) { for (int fd : {a[0],a[1],b[0],b[1]}) ::close(fd); throw std::runtime_error("Cannot create worker log."); }
        process=fork();
        if (process == 0) {
            dup2(a[0],STDIN_FILENO); dup2(b[1],STDOUT_FILENO); dup2(log,STDERR_FILENO);
            for (int fd : {a[0],a[1],b[0],b[1],log}) ::close(fd);
            execlp(python.c_str(),python.c_str(),"-u",script.c_str(),"--serial",serial.c_str(),"--output",path.c_str(),static_cast<char*>(nullptr));
            _exit(127);
        }
        ::close(a[0]); ::close(b[1]); ::close(log);
        if (process < 0) { ::close(a[1]); ::close(b[0]); throw std::runtime_error("Cannot launch worker."); }
        input=a[1]; output=b[0];
        // EPIPE is an ordinary child failure, never a reason to kill the CLI.
        signal(SIGPIPE,SIG_IGN);
#endif
    }
    bool line(std::string& result) {
        result.clear(); char ch;
        while (result.size() < 8192) {
#ifdef _WIN32
            DWORD n=0;
            if (!ReadFile(output,&ch,1,&n,nullptr)) {
                auto error=GetLastError();
                if (error != ERROR_BROKEN_PIPE) throw std::runtime_error("OSCAR stdout read failed; Windows error="+std::to_string(error));
            }
#else
            ssize_t n=::read(output,&ch,1); if (n < 0 && errno == EINTR) continue;
            if (n < 0) throw std::runtime_error("OSCAR stdout read failed; errno="+std::to_string(errno));
#endif
            if (n == 0) {
                if (!result.empty()) throw std::runtime_error("OSCAR stdout ended with an unterminated protocol line.");
                return false;
            }
            if (ch == '\n') return true;
            if (ch != '\r') result += ch;
        }
        throw std::runtime_error("Worker protocol line exceeds limit.");
    }
    void requestStop() {
#ifdef _WIN32
        if (input) { DWORD n=0; WriteFile(input,"STOP\n",5,&n,nullptr); CloseHandle(input); input=nullptr; }
#else
        if (input >= 0) { auto ignored=::write(input,"STOP\n",5); (void)ignored; ::close(input); input=-1; }
#endif
    }
    // Only the controller calls wait; reader never reaps concurrently.
    bool wait(unsigned milliseconds) {
        if (!active()) return true;
#ifdef _WIN32
        if (WaitForSingleObject(process,milliseconds) != WAIT_OBJECT_0) return false;
        DWORD code=1; GetExitCodeProcess(process,&code); exitOk=code == 0; return true;
#else
        auto deadline=std::chrono::steady_clock::now()+std::chrono::milliseconds(milliseconds);
        do {
            int status=0; auto done=waitpid(process,&status,WNOHANG);
            if (done == process) { exitOk=WIFEXITED(status) && WEXITSTATUS(status) == 0; process=-1; return true; }
            if (done < 0 && errno == ECHILD) { process=-1; return true; }
            std::this_thread::sleep_for(std::chrono::milliseconds(10));
        } while (std::chrono::steady_clock::now() < deadline);
        return false;
#endif
    }
    void kill() {
#ifdef _WIN32
        if (process) TerminateProcess(process,1);
#else
        if (process > 0) ::kill(process,SIGKILL);
#endif
    }
    void dispose() {
        if (active()) { requestStop(); if (!wait(200)) { kill(); wait(1000); } }
#ifdef _WIN32
        if (process) CloseHandle(process); if (input) CloseHandle(input); if (output) CloseHandle(output);
        process=nullptr; input=nullptr; output=nullptr;
#else
        if (input >= 0) ::close(input); if (output >= 0) ::close(output);
        process=-1; input=output=-1;
#endif
    }
};

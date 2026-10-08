#pragma once
#include <algorithm>
#include <cctype>
#include <filesystem>
#include <iomanip>
#include <iostream>
#include <stdexcept>
#include <vector>

class Experiments {
    std::filesystem::path base = std::filesystem::u8path(RECORDINGS_ROOT), current;
    static void validate(const std::string& name) {
        if (name.empty() || name == "." || name == ".." || name.back() == '.' || name.back() == ' ' ||
            name.find_first_of("<>:\"/\\|?*") != std::string::npos ||
            std::any_of(name.begin(), name.end(), [](unsigned char c) { return c < 32; }))
            throw std::runtime_error("Invalid Windows name; use a name without paths or special characters.");
        std::string stem = name.substr(0, name.find('.'));
        std::transform(stem.begin(), stem.end(), stem.begin(), [](unsigned char c) { return char(std::toupper(c)); });
        if (stem == "CON" || stem == "PRN" || stem == "AUX" || stem == "NUL" ||
            (stem.size() == 4 && (stem.substr(0, 3) == "COM" || stem.substr(0, 3) == "LPT") && stem[3] >= '1' && stem[3] <= '9'))
            throw std::runtime_error("Reserved Windows name.");
    }
    void verify() const {
        if (current.empty()) throw std::runtime_error("Select an experiment first: NewExp or GoToExp.");
        if (!std::filesystem::is_directory(current) || std::filesystem::is_symlink(current) ||
            std::filesystem::canonical(current).parent_path() != std::filesystem::canonical(base))
            throw std::runtime_error("Experiment folder is missing or outside recordings.");
    }
public:
    std::string prompt() const { return "[" + (current.empty() ? std::string("Kein Versuch ausgewählt") : current.filename().u8string()) + "] > "; }
    void where() const { std::cout << "Speicherort: " << (current.empty() ? base : current).u8string() << '\n'; }
    void select(std::istream& in, bool create) {
        std::string name, extra;
        if (!(in >> std::quoted(name, '"', '\0')) || (in >> extra)) throw std::runtime_error("Use NewExp \"NAME\" or GoToExp \"NAME\".");
        validate(name);
        auto folder = base / std::filesystem::u8path(name);
        if (create) {
            std::filesystem::create_directories(base);
            if (!std::filesystem::create_directory(folder)) throw std::runtime_error("Experiment already exists; use GoToExp.");
        }
        if (!std::filesystem::is_directory(folder) || std::filesystem::is_symlink(folder) ||
            std::filesystem::canonical(folder).parent_path() != std::filesystem::canonical(base))
            throw std::runtime_error("Experiment not found or outside recordings.");
        current = folder;
        where();
    }
    void list() const {
        if (!std::filesystem::exists(base)) { std::cout << "No experiments yet.\n"; return; }
        std::vector<std::string> names;
        for (const auto& entry : std::filesystem::directory_iterator(base))
            if (entry.is_directory() && !entry.is_symlink() && std::filesystem::canonical(entry.path()).parent_path() == std::filesystem::canonical(base))
                names.push_back(entry.path().filename().u8string());
        std::sort(names.begin(), names.end());
        for (const auto& name : names) std::cout << ((!current.empty() && current.filename().u8string() == name) ? "* " : "  ") << name << '\n';
    }
    void require() const { verify(); }
    std::filesystem::path output(const std::string& name) const {
        verify(); validate(name);
        auto path = current / std::filesystem::u8path(name);
        auto events = path; events += ".events.csv";
        if (std::filesystem::exists(path) || std::filesystem::exists(events))
            throw std::runtime_error("Recording files already exist; choose a new filename.");
        return path;
    }
};

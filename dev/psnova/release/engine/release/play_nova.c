/* Done by Codex. Start the installed Nova runtime with its portable player directory.
 *
 * Support reports and updates: every start, launch failure and exit is recorded in NovaData\Player\launch.json (the one before it
 * in launch.prev.json), with no file paths in it. A launch failure or an abnormal exit offers to create a support report (it runs
 * Setup Phantasy Star Nova.exe --export-report); a normal quit stays silent and starts a quiet, hidden update check that Setup's
 * own once-a-day limit throttles. NOVA_LAUNCHER_QUIET=1 turns off the dialogs and the background check (for test scripts). */
#include <windows.h>
#include <stdio.h>
#include <string.h>
#include <wchar.h>

enum { PATH_CAP = 4096, INSTALL_ID_LENGTH = 24 };

static const wchar_t *title = L"Phantasy Star Nova Recomp";
static const wchar_t *modules[] = {
    L"libc.img", L"libgxm_es4.img", L"libgpu_es4.img",
    L"libscemp4.img", L"libsceavplayer.img"
};

/* where the launch record goes, set once the release folder is known; empty until then */
static wchar_t record_path[PATH_CAP], record_previous[PATH_CAP], release_root[PATH_CAP];
static char build_id[INSTALL_ID_LENGTH + 1], started_at[32];

static int quiet(void) {
    wchar_t value[4];
    return GetEnvironmentVariableW(L"NOVA_LAUNCHER_QUIET", value, 4) && value[0] == L'1';
}

static void utc_now(char *out, size_t size) {
    SYSTEMTIME t;
    GetSystemTime(&t);
    snprintf(out, size, "%04u-%02u-%02uT%02u:%02u:%02uZ", t.wYear, t.wMonth, t.wDay, t.wHour, t.wMinute, t.wSecond);
}

/* One small JSON object, written to a temporary file and moved over the record so a reader never sees half of it. The message is
 * one of this program's own fixed sentences with an error number: it holds no path. */
static void write_record(const char *state, DWORD pid, int has_exit, DWORD exit_code, const char *message) {
    if (!record_path[0]) return;
    char ended[32] = "", text[1024];
    if (has_exit || !strcmp(state, "launch-failed")) utc_now(ended, sizeof ended);
    int n = snprintf(text, sizeof text,
                     "{\n  \"schema\": 1,\n  \"state\": \"%s\",\n  \"build\": \"%s\",\n  \"started\": \"%s\",\n  \"pid\": %lu",
                     state, build_id, started_at, (unsigned long)pid);
    if (ended[0]) n += snprintf(text + n, sizeof text - n, ",\n  \"ended\": \"%s\"", ended);
    if (has_exit) n += snprintf(text + n, sizeof text - n, ",\n  \"exit_code\": %lu", (unsigned long)exit_code);
    if (message && *message) n += snprintf(text + n, sizeof text - n, ",\n  \"message\": \"%s\"", message);
    snprintf(text + n, sizeof text - n, "\n}\n");
    wchar_t temporary[PATH_CAP];
    swprintf(temporary, PATH_CAP, L"%ls.tmp", record_path);
    HANDLE file = CreateFileW(temporary, GENERIC_WRITE, 0, NULL, CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, NULL);
    if (file == INVALID_HANDLE_VALUE) return;
    DWORD written;
    BOOL ok = WriteFile(file, text, (DWORD)strlen(text), &written, NULL);
    CloseHandle(file);
    if (ok) MoveFileExW(temporary, record_path, MOVEFILE_REPLACE_EXISTING);
    else DeleteFileW(temporary);
}

/* The same Setup program the player already runs does the export, with no console. */
static void start_report(void) {
    wchar_t setup[PATH_CAP], command[PATH_CAP + 64];
    swprintf(setup, PATH_CAP, L"%ls\\Setup Phantasy Star Nova.exe", release_root);
    swprintf(command, PATH_CAP + 64, L"\"%ls\" --export-report", setup);
    STARTUPINFOW startup = {0};
    startup.cb = sizeof startup;
    PROCESS_INFORMATION process;
    if (CreateProcessW(setup, command, NULL, NULL, FALSE, 0, NULL, release_root, &startup, &process)) {
        CloseHandle(process.hThread);
        CloseHandle(process.hProcess);
    } else {
        MessageBoxW(NULL, L"Setup Phantasy Star Nova.exe was not found next to this program. Run it and choose Export support report.",
                    title, MB_OK | MB_ICONINFORMATION);
    }
}

static void offer_report(const wchar_t *message) {
    if (quiet()) return;
    wchar_t text[1024];
    swprintf(text, sizeof text / sizeof *text,
             L"%ls\n\nCreate a support report now? It is a ZIP in NovaData\\Reports with no saves, game files or file paths. "
             L"Nothing is sent: you choose whether to share it. You can also open Setup Phantasy Star Nova.exe and choose "
             L"Export support report.", message);
    if (MessageBoxW(NULL, text, title, MB_YESNO | MB_ICONERROR) == IDYES) start_report();
}

static int fail(const wchar_t *message) {
    if (!quiet()) MessageBoxW(NULL, message, title, MB_OK | MB_ICONERROR);
    return 1;
}

/* a launch failure: recorded, then the dialog with the export offer */
static int launch_fail(const char *tag, const wchar_t *message) {
    write_record("launch-failed", 0, 0, 0, tag);
    offer_report(message);
    return 1;
}

static int join_path(wchar_t *out, size_t size, const wchar_t *base, const wchar_t *tail) {
    int written = swprintf(out, size, L"%ls\\%ls", base, tail);
    return written >= 0 && (size_t)written < size;
}

static int read_hex(const wchar_t *filename, unsigned int minimum, unsigned int maximum,
                    int lowercase, wchar_t *out) {
    char bytes[32];
    DWORD amount = 0;
    HANDLE file = CreateFileW(filename, GENERIC_READ,
                              FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE,
                              NULL, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, NULL);
    if (file == INVALID_HANDLE_VALUE) return 0;
    BOOL read_ok = ReadFile(file, bytes, sizeof bytes, &amount, NULL);
    CloseHandle(file);
    if (!read_ok || !amount || amount == sizeof bytes) return 0;
    if (bytes[amount - 1] == '\n') amount--;
    if (amount && bytes[amount - 1] == '\r') amount--;
    if (amount < minimum || amount > maximum) return 0;
    for (DWORD index = 0; index < amount; index++) {
        char c = bytes[index];
        if ((c < '0' || c > '9') && (c < 'a' || c > 'f') &&
            (lowercase || c < 'A' || c > 'F')) return 0;
        out[index] = c;
    }
    out[amount] = 0;
    return 1;
}

static BOOL exists_file(const wchar_t *path) {
    DWORD attributes = GetFileAttributesW(path);
    return attributes != INVALID_FILE_ATTRIBUTES && !(attributes & FILE_ATTRIBUTE_DIRECTORY);
}

static BOOL set_default(const wchar_t *name, const wchar_t *value) {
    wchar_t old[2];
    if (GetEnvironmentVariableW(name, old, 2)) return TRUE;
    return SetEnvironmentVariableW(name, value);
}

/* After a normal quit: the bundled Python runs Setup's own throttled check, hidden. Setup decides whether updates are on. */
static void start_background_check(void) {
    if (quiet()) return;
    wchar_t python[PATH_CAP], command[PATH_CAP * 2 + 128];
    swprintf(python, PATH_CAP, L"%ls\\engine\\python\\python.exe", release_root);
    swprintf(command, sizeof command / sizeof *command,
             L"\"%ls\" -E -s -B -X utf8 \"%ls\\setup.py\" --check-updates --quiet", python, release_root);
    STARTUPINFOW startup = {0};
    startup.cb = sizeof startup;
    PROCESS_INFORMATION process;
    if (exists_file(python) &&
        CreateProcessW(python, command, NULL, NULL, FALSE, CREATE_NO_WINDOW | DETACHED_PROCESS, NULL, release_root, &startup, &process)) {
        CloseHandle(process.hThread);
        CloseHandle(process.hProcess);
    }
}

int WINAPI wWinMain(HINSTANCE instance, HINSTANCE previous, PWSTR command_line, int show) {
    (void)instance;
    (void)previous;
    (void)command_line;
    (void)show;
    wchar_t root[PATH_CAP], player[PATH_CAP], path[PATH_CAP], game[PATH_CAP];
    wchar_t log_path[PATH_CAP], previous_log[PATH_CAP];
    wchar_t generation[INSTALL_ID_LENGTH + 1], entry[9];
    wchar_t relative[160], image[184], filesystem[184], images[1100] = L"";
    wchar_t arguments[PATH_CAP + 240];
    DWORD root_length = GetModuleFileNameW(NULL, root, PATH_CAP);
    if (!root_length || root_length >= PATH_CAP) return fail(L"Unable to find the release folder.");
    wchar_t *slash = wcsrchr(root, L'\\');
    if (!slash) return fail(L"Unable to find the release folder.");
    *slash = 0;
    wcscpy(release_root, root);
    utc_now(started_at, sizeof started_at);

    /* the launch record lives in the player folder; before the first setup there is no NovaData to put it in */
    if (join_path(player, PATH_CAP, root, L"NovaData\\Player") && join_path(path, PATH_CAP, root, L"NovaData")) {
        DWORD attributes = GetFileAttributesW(path);
        if (attributes != INVALID_FILE_ATTRIBUTES && (attributes & FILE_ATTRIBUTE_DIRECTORY)) {
            CreateDirectoryW(player, NULL);
            join_path(record_path, PATH_CAP, player, L"launch.json");
            join_path(record_previous, PATH_CAP, player, L"launch.prev.json");
        }
    }

    if (!join_path(path, PATH_CAP, root, L"NovaData\\current.txt") ||
        !read_hex(path, INSTALL_ID_LENGTH, INSTALL_ID_LENGTH, 1, generation))
        return launch_fail("no-build",
                           L"No complete installation was found. Run Setup Phantasy Star Nova.exe first.");
    for (int i = 0; i < INSTALL_ID_LENGTH; i++) build_id[i] = (char)generation[i];
    build_id[INSTALL_ID_LENGTH] = 0;

    swprintf(relative, sizeof relative / sizeof *relative,
             L"../installs/%ls/library/decrypted/PCSG00351/recomp", generation);
    if (!join_path(path, PATH_CAP, player, relative) ||
        !join_path(game, PATH_CAP, path, L"game_host.exe") || !exists_file(game))
        return launch_fail("missing-game-executable",
                           L"The installed game executable is missing. Run Setup Phantasy Star Nova.exe to repair it.");

    wchar_t game_dir[PATH_CAP];
    wcscpy(game_dir, path);
    if (!join_path(path, PATH_CAP, game_dir, L"entry.txt") || !read_hex(path, 1, 8, 0, entry) ||
        !join_path(path, PATH_CAP, game_dir, L"game.img") || !exists_file(path) ||
        !join_path(path, PATH_CAP, game_dir, L"SDL3.dll") || !exists_file(path))
        return launch_fail("incomplete-game-data",
                           L"The installed game data is incomplete. Run Setup Phantasy Star Nova.exe to repair it.");

    for (size_t i = 0; i < sizeof modules / sizeof *modules; i++) {
        if (!join_path(path, PATH_CAP, game_dir, modules[i]) || !exists_file(path))
            return launch_fail("missing-runtime-module",
                               L"An installed Vita runtime module is missing. Run Setup Phantasy Star Nova.exe to repair it.");
        size_t used = wcslen(images);
        swprintf(images + used, sizeof images / sizeof *images - used, L"%ls%ls/%ls",
                 i ? L"," : L"", relative, modules[i]);
    }
    swprintf(image, sizeof image / sizeof *image, L"%ls/game.img", relative);
    swprintf(filesystem, sizeof filesystem / sizeof *filesystem, L"%ls/fs", relative);

    if (!SetEnvironmentVariableW(L"RECOMP_MODULES", images) ||
        !SetEnvironmentVariableW(L"RECOMP_FS", filesystem) ||
        !SetEnvironmentVariableW(L"RECOMP_SAVE_ROOT", L".") ||
        !SetEnvironmentVariableW(L"RECOMP_SETTINGS", L"./settings.ini") ||
        !SetEnvironmentVariableW(L"RECOMP_TITLE", L"PCSG00351") ||
        !SetEnvironmentVariableW(L"RECOMP_GAME_NAME", L"Phantasy Star Nova") ||
        !set_default(L"RECOMP_LOG", L"0") ||
        !set_default(L"RECOMP_HITCH_LOG", L"50") ||
        !set_default(L"RECOMP_STALL_PROF", L"150") ||
        !set_default(L"RECOMP_GPU_FENCE_STATS", L"1") ||
        !set_default(L"RECOMP_WAIT_STATS", L"120") ||
        !set_default(L"RECOMP_METRICS", L"1") ||
        !set_default(L"RECOMP_PSN_FPS_TRACE", L"1"))
        return launch_fail("environment", L"Windows could not configure the game process.");

    if (!join_path(path, PATH_CAP, player, L"playing.lock") ||
        !join_path(log_path, PATH_CAP, player, L"session.log") ||
        !join_path(previous_log, PATH_CAP, player, L"session.prev.log"))
        return launch_fail("path-too-long", L"The release folder path is too long.");

    /* A second launch, or a setup that is switching builds, holds the lock: a short wait covers a setup's switch. */
    HANDLE lock = INVALID_HANDLE_VALUE;
    DWORD lock_error = 0;
    for (int attempt = 0; attempt < 12; attempt++) {
        lock = CreateFileW(path, GENERIC_WRITE, 0, NULL, OPEN_ALWAYS, FILE_ATTRIBUTE_NORMAL, NULL);
        if (lock != INVALID_HANDLE_VALUE) break;
        lock_error = GetLastError();
        if (lock_error != ERROR_SHARING_VIOLATION) break;
        Sleep(250);
    }
    if (lock == INVALID_HANDLE_VALUE)
        return fail(lock_error == ERROR_SHARING_VIOLATION ?
                    L"Phantasy Star Nova is already running from this folder, or Setup is updating it. Close it and try again." :
                    L"Unable to open the player folder for writing.");

    if (record_path[0]) MoveFileExW(record_path, record_previous, MOVEFILE_REPLACE_EXISTING);
    write_record("starting", 0, 0, 0, NULL);
    if (join_path(path, PATH_CAP, player, L"captures")) CreateDirectoryW(path, NULL);
    MoveFileExW(log_path, previous_log, MOVEFILE_REPLACE_EXISTING);
    SECURITY_ATTRIBUTES inheritable = {sizeof inheritable, NULL, TRUE};
    HANDLE log = CreateFileW(log_path, GENERIC_WRITE, FILE_SHARE_READ, &inheritable,
                             CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, NULL);
    HANDLE input = CreateFileW(L"NUL", GENERIC_READ, FILE_SHARE_READ | FILE_SHARE_WRITE,
                               &inheritable, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, NULL);
    if (log == INVALID_HANDLE_VALUE || input == INVALID_HANDLE_VALUE) {
        if (log != INVALID_HANDLE_VALUE) CloseHandle(log);
        if (input != INVALID_HANDLE_VALUE) CloseHandle(input);
        CloseHandle(lock);
        write_record("launch-failed", 0, 0, 0, "session-log");
        offer_report(L"Unable to create the session log in NovaData\\Player.");
        return 1;
    }

    swprintf(arguments, sizeof arguments / sizeof *arguments, L"\"%ls\" \"%ls\" %ls 100000000000",
             game, image, entry);
    STARTUPINFOW startup = {0};
    startup.cb = sizeof startup;
    startup.dwFlags = STARTF_USESTDHANDLES;
    startup.hStdInput = input;
    startup.hStdOutput = log;
    startup.hStdError = log;
    PROCESS_INFORMATION process;
    BOOL started = CreateProcessW(game, arguments, NULL, NULL, TRUE, CREATE_NO_WINDOW,
                                  NULL, player, &startup, &process);
    DWORD error = GetLastError();
    CloseHandle(input);
    CloseHandle(log);
    if (!started) {
        CloseHandle(lock);
        char tag[64];
        snprintf(tag, sizeof tag, "windows-could-not-start-the-game-error-%lu", (unsigned long)error);
        write_record("launch-failed", 0, 0, 0, tag);
        wchar_t message[320];
        swprintf(message, sizeof message / sizeof *message,
                 L"Windows could not start the installed game (error %lu). Run setup to repair it, and check whether Windows blocked the locally built executable.",
                 error);
        offer_report(message);
        return 1;
    }
    write_record("running", process.dwProcessId, 0, 0, NULL);
    CloseHandle(process.hThread);
    WaitForSingleObject(process.hProcess, INFINITE);
    DWORD status = 1;
    GetExitCodeProcess(process.hProcess, &status);
    CloseHandle(process.hProcess);
    write_record("exited", process.dwProcessId, 1, status, NULL);
    CloseHandle(lock);
    if (status == 0) {
        start_background_check();
    } else {
        wchar_t message[320];
        if (status >= 0xC0000000u)
            swprintf(message, sizeof message / sizeof *message,
                     L"Phantasy Star Nova stopped unexpectedly (Windows exception 0x%08lX).", (unsigned long)status);
        else
            swprintf(message, sizeof message / sizeof *message,
                     L"Phantasy Star Nova closed unexpectedly (exit code %lu).", (unsigned long)status);
        offer_report(message);
    }
    return (int)status;
}

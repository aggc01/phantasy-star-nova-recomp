/* Done by Codex. Start the installed Nova runtime with its portable player directory. */
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

static int fail(const wchar_t *message) {
    MessageBoxW(NULL, message, title, MB_OK | MB_ICONERROR);
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

    if (!join_path(path, PATH_CAP, root, L"NovaData\\current.txt") ||
        !read_hex(path, INSTALL_ID_LENGTH, INSTALL_ID_LENGTH, 1, generation))
        return fail(L"No complete installation was found. Run Setup Phantasy Star Nova.exe first.");

    swprintf(relative, sizeof relative / sizeof *relative,
             L"../installs/%ls/library/decrypted/PCSG00351/recomp", generation);
    if (!join_path(player, PATH_CAP, root, L"NovaData\\Player") ||
        !join_path(path, PATH_CAP, player, relative) ||
        !join_path(game, PATH_CAP, path, L"game_host.exe") || !exists_file(game))
        return fail(L"The installed game executable is missing. Run Setup Phantasy Star Nova.exe to repair it.");

    wchar_t game_dir[PATH_CAP];
    wcscpy(game_dir, path);
    if (!join_path(path, PATH_CAP, game_dir, L"entry.txt") || !read_hex(path, 1, 8, 0, entry) ||
        !join_path(path, PATH_CAP, game_dir, L"game.img") || !exists_file(path) ||
        !join_path(path, PATH_CAP, game_dir, L"SDL3.dll") || !exists_file(path))
        return fail(L"The installed game data is incomplete. Run Setup Phantasy Star Nova.exe to repair it.");

    for (size_t i = 0; i < sizeof modules / sizeof *modules; i++) {
        if (!join_path(path, PATH_CAP, game_dir, modules[i]) || !exists_file(path))
            return fail(L"An installed Vita runtime module is missing. Run Setup Phantasy Star Nova.exe to repair it.");
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
        return fail(L"Windows could not configure the game process.");

    if (!join_path(path, PATH_CAP, player, L"playing.lock") ||
        !join_path(log_path, PATH_CAP, player, L"session.log") ||
        !join_path(previous_log, PATH_CAP, player, L"session.prev.log"))
        return fail(L"The release folder path is too long.");

    HANDLE lock = CreateFileW(path, GENERIC_WRITE, 0, NULL, OPEN_ALWAYS, FILE_ATTRIBUTE_NORMAL, NULL);
    if (lock == INVALID_HANDLE_VALUE)
        return fail(GetLastError() == ERROR_SHARING_VIOLATION ?
                    L"Phantasy Star Nova is already running from this folder." :
                    L"Unable to open the player folder for writing.");

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
        return fail(L"Unable to create the session log in NovaData\\Player.");
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
        wchar_t message[320];
        swprintf(message, sizeof message / sizeof *message,
                 L"Windows could not start the installed game (error %lu). Run setup to repair it, and check whether Windows blocked the locally built executable.",
                 error);
        return fail(message);
    }
    CloseHandle(process.hThread);
    WaitForSingleObject(process.hProcess, INFINITE);
    DWORD status = 1;
    GetExitCodeProcess(process.hProcess, &status);
    CloseHandle(process.hProcess);
    CloseHandle(lock);
    return (int)status;
}

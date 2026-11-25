/* Done by Codex. Native entry point for Phantasy Star Nova Recomp setup.
 *
 * No arguments: the setup window (pythonw). Arguments: a console run for scripts (python). The exception is --export-report when
 * nothing in front of it is a console (the game launcher's "Create a support report" button): that runs without a console window
 * and ends in a message box that shows where the report was written. */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <wchar.h>

#define PATH_CAP 32768

static int fail(const wchar_t *text) {
    MessageBoxW(NULL, text, L"Phantasy Star Nova Recomp Setup", MB_OK | MB_ICONERROR);
    return 1;
}

int WINAPI wWinMain(HINSTANCE instance, HINSTANCE previous, PWSTR arguments, int show) {
    (void)instance;
    (void)previous;
    (void)show;
    static wchar_t root[PATH_CAP], python[PATH_CAP], script[PATH_CAP], command[PATH_CAP];
    DWORD length = GetModuleFileNameW(NULL, root, PATH_CAP);
    if (length == 0 || length >= PATH_CAP) return fail(L"Cannot find the setup folder.");
    wchar_t *separator = wcsrchr(root, L'\\');
    if (!separator) return fail(L"Cannot find the setup folder.");
    *separator = L'\0';

    BOOL has_arguments = arguments && *arguments;
    BOOL attached = has_arguments && AttachConsole(ATTACH_PARENT_PROCESS);
    BOOL cli = has_arguments;
    if (has_arguments && !attached && wcsncmp(arguments, L"--export-report", 15) == 0) cli = FALSE;   /* a windowed export */
    if (swprintf(python, PATH_CAP, L"%ls\\engine\\python\\%ls", root,
                 cli ? L"python.exe" : L"pythonw.exe") < 0 ||
        swprintf(script, PATH_CAP, L"%ls\\setup.py", root) < 0 ||
        swprintf(command, PATH_CAP, L"\"%ls\" -E -s -B -X utf8 \"%ls\" %ls", python, script,
                 has_arguments ? arguments : L"") < 0)
        return fail(L"Move the extracted release to a shorter folder path and run setup again.");
    if (GetFileAttributesW(python) == INVALID_FILE_ATTRIBUTES || GetFileAttributesW(script) == INVALID_FILE_ATTRIBUTES)
        return fail(L"The setup files are missing. Extract the entire Windows release before running setup.");

    HANDLE job = CreateJobObjectW(NULL, NULL);
    JOBOBJECT_EXTENDED_LIMIT_INFORMATION limits = {0};
    limits.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE | JOB_OBJECT_LIMIT_BREAKAWAY_OK;
    if (!job || !SetInformationJobObject(job, JobObjectExtendedLimitInformation, &limits, sizeof limits)) {
        if (job) CloseHandle(job);
        return fail(L"Windows could not create the setup process group.");
    }

    STARTUPINFOW startup = {0};
    startup.cb = sizeof startup;
    PROCESS_INFORMATION process;
    if (cli) {
        startup.hStdInput = GetStdHandle(STD_INPUT_HANDLE);
        startup.hStdOutput = GetStdHandle(STD_OUTPUT_HANDLE);
        startup.hStdError = GetStdHandle(STD_ERROR_HANDLE);
        if (startup.hStdOutput && startup.hStdOutput != INVALID_HANDLE_VALUE)
            startup.dwFlags = STARTF_USESTDHANDLES;
    }
    if (!CreateProcessW(python, command, NULL, NULL, cli, CREATE_SUSPENDED, NULL, root, &startup, &process)) {
        CloseHandle(job);
        return fail(L"Windows could not start the bundled Python. Extract the complete 64-bit Windows release and try again.");
    }
    if (!AssignProcessToJobObject(job, process.hProcess) || ResumeThread(process.hThread) == (DWORD)-1) {
        TerminateProcess(process.hProcess, 1);
        CloseHandle(process.hThread);
        CloseHandle(process.hProcess);
        CloseHandle(job);
        return fail(L"Windows could not start setup in its process group.");
    }
    CloseHandle(process.hThread);
    WaitForSingleObject(process.hProcess, INFINITE);
    DWORD code = 1;
    GetExitCodeProcess(process.hProcess, &code);
    CloseHandle(process.hProcess);
    CloseHandle(job);
    if (code && !cli) return fail(L"Setup exited early. Check that the entire release was extracted.");
    return (int)code;
}

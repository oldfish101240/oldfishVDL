#define _CRT_SECURE_NO_WARNINGS
#include <stdio.h>
#include <stdlib.h>
#include <windows.h>
#include <string.h>
#include <stdarg.h>
#include <time.h>
#include <shlwapi.h>
#pragma comment(lib, "Shlwapi.lib")

#define LAUNCHER_VERSION "2.0.0-beta"
#define MUTEX_NAME L"Local\\OldFishVideoDownloaderLauncherSingleton"

static FILE* g_log_file = NULL;
static HANDLE g_singleton_mutex = NULL;

int file_exists(const char* path) {
    DWORD attributes = GetFileAttributesA(path);
    return (attributes != INVALID_FILE_ATTRIBUTES && !(attributes & FILE_ATTRIBUTE_DIRECTORY));
}

int wide_to_utf8(const wchar_t* src, char* dest, size_t dest_size) {
    if (!src || !dest || dest_size == 0) {
        return 0;
    }
    int converted = WideCharToMultiByte(CP_UTF8, 0, src, -1, dest, (int)dest_size, NULL, NULL);
    return converted > 0;
}

int utf8_to_wide(const char* src, wchar_t* dest, size_t dest_size) {
    if (!src || !dest || dest_size == 0) {
        return 0;
    }
    int converted = MultiByteToWideChar(CP_UTF8, 0, src, -1, dest, (int)dest_size);
    return converted > 0;
}

void close_log_file() {
    if (g_log_file) {
        fclose(g_log_file);
        g_log_file = NULL;
    }
}

void log_message(const char* level, const char* fmt, ...) {
    if (!g_log_file) {
        return;
    }

    time_t now = time(NULL);
    struct tm time_info;
    localtime_s(&time_info, &now);

    char timestamp[32];
    strftime(timestamp, sizeof(timestamp), "%Y-%m-%d %H:%M:%S", &time_info);

    fprintf(g_log_file, "[%s] [%s] ", timestamp, level);
    va_list args;
    va_start(args, fmt);
    vfprintf(g_log_file, fmt, args);
    va_end(args);
    fprintf(g_log_file, "\n");
    fflush(g_log_file);
}

void init_log_file(const char* app_path) {
    char log_path[MAX_PATH] = {0};
    char log_dir[MAX_PATH] = {0};
    char local_appdata[MAX_PATH] = {0};

    PathCombineA(log_dir, app_path, "main");
    CreateDirectoryA(log_dir, NULL);
    PathCombineA(log_path, log_dir, "launcher.log");

    g_log_file = fopen(log_path, "a");
    if (g_log_file) {
        log_message("INFO", "launcher start version=%s", LAUNCHER_VERSION);
        log_message("INFO", "log path=%s", log_path);
        return;
    }

    DWORD got = GetEnvironmentVariableA("LOCALAPPDATA", local_appdata, MAX_PATH);
    if (got > 0 && got < MAX_PATH) {
        PathCombineA(log_dir, local_appdata, "oldFishVDL");
        CreateDirectoryA(log_dir, NULL);
        PathCombineA(log_path, log_dir, "launcher.log");
        g_log_file = fopen(log_path, "a");
        if (g_log_file) {
            log_message("INFO", "launcher start version=%s", LAUNCHER_VERSION);
            log_message("INFO", "fallback log path=%s", log_path);
        }
    }
}

void show_error(const char* message) {
    wchar_t wmessage[2048];
    if (utf8_to_wide(message, wmessage, sizeof(wmessage) / sizeof(wmessage[0]))) {
        MessageBoxW(NULL, wmessage, L"OldFish Video Downloader 啟動器", MB_ICONERROR | MB_OK);
    } else {
        MessageBoxA(NULL, message, "OldFish Video Downloader 啟動器", MB_ICONERROR | MB_OK);
    }
}

void show_info(const wchar_t* message) {
    MessageBoxW(NULL, message, L"OldFish Video Downloader 啟動器", MB_ICONINFORMATION | MB_OK);
}

int contains_flag_w(const wchar_t* cmd_line, const wchar_t* flag) {
    if (!cmd_line || !flag) {
        return 0;
    }
    return wcsstr(cmd_line, flag) != NULL;
}

int is_running_as_admin() {
    BOOL is_admin = FALSE;
    SID_IDENTIFIER_AUTHORITY nt_authority = SECURITY_NT_AUTHORITY;
    PSID admin_group = NULL;

    if (AllocateAndInitializeSid(
            &nt_authority, 2,
            SECURITY_BUILTIN_DOMAIN_RID,
            DOMAIN_ALIAS_RID_ADMINS,
            0, 0, 0, 0, 0, 0,
            &admin_group)) {
        CheckTokenMembership(NULL, admin_group, &is_admin);
        FreeSid(admin_group);
    }
    return is_admin ? 1 : 0;
}

int ensure_single_instance(const wchar_t* cmd_line) {
    int is_restart = contains_flag_w(cmd_line, L"--restart");

    if (is_restart) {
        log_message("INFO", "restart mode: waiting for previous instance to exit");
        for (int attempt = 0; attempt < 30; attempt++) {
            g_singleton_mutex = CreateMutexW(NULL, FALSE, MUTEX_NAME);
            if (!g_singleton_mutex) {
                return 0;
            }
            if (GetLastError() != ERROR_ALREADY_EXISTS) {
                log_message("INFO", "restart mode: acquired singleton mutex");
                return 1;
            }
            CloseHandle(g_singleton_mutex);
            g_singleton_mutex = NULL;
            Sleep(500);
        }
        show_info(L"無法完成重啟，請稍後再試或手動啟動程式。");
        log_message("WARN", "restart mode: timed out waiting for singleton mutex");
        return 0;
    }

    g_singleton_mutex = CreateMutexW(NULL, FALSE, MUTEX_NAME);
    if (!g_singleton_mutex) {
        return 0;
    }
    if (GetLastError() == ERROR_ALREADY_EXISTS) {
        show_info(L"程式已在執行中，不會重複啟動。");
        return 0;
    }
    return 1;
}

void release_singleton() {
    if (g_singleton_mutex) {
        CloseHandle(g_singleton_mutex);
        g_singleton_mutex = NULL;
    }
}

void get_app_path(char* path, size_t size) {
    if (GetModuleFileNameA(NULL, path, (DWORD)size) == 0) {
        GetCurrentDirectoryA((DWORD)size, path);
    } else {
        char* last_slash = strrchr(path, '\\');
        if (last_slash) {
            *last_slash = '\0';
        }
    }

    size_t len = strlen(path);
    if (len > 0 && path[len - 1] == '\\') {
        path[len - 1] = '\0';
    }
}

int is_vsredist_installed() {
    HKEY hKey;
    if (RegOpenKeyExA(HKEY_LOCAL_MACHINE, "SOFTWARE\\Microsoft\\VisualStudio\\14.0\\VC\\Runtimes\\x64", 0, KEY_READ, &hKey) == ERROR_SUCCESS) {
        DWORD value = 0;
        DWORD size = sizeof(DWORD);
        if (RegQueryValueExA(hKey, "Installed", NULL, NULL, (LPBYTE)&value, &size) == ERROR_SUCCESS) {
            RegCloseKey(hKey);
            return value == 1;
        }
        RegCloseKey(hKey);
    }

    char sysdir[MAX_PATH];
    char vcruntime_path[MAX_PATH];
    GetSystemDirectoryA(sysdir, MAX_PATH);
    snprintf(vcruntime_path, MAX_PATH, "%s\\vcruntime140.dll", sysdir);
    return file_exists(vcruntime_path);
}

void prompt_and_install(const wchar_t* title, const wchar_t* msg, const wchar_t* url) {
    int res = MessageBoxW(NULL, msg, title, MB_ICONQUESTION | MB_YESNO);
    if (res == IDYES) {
        ShellExecuteW(NULL, L"open", url, NULL, NULL, SW_SHOWNORMAL);
    }
}

int maybe_relaunch_as_admin(const wchar_t* cmd_line) {
    if (!contains_flag_w(cmd_line, L"--require-admin")) {
        return 0;
    }
    if (is_running_as_admin()) {
        return 0;
    }
    if (contains_flag_w(cmd_line, L"--launcher-elevated")) {
        return 0;
    }

    wchar_t exe_path[MAX_PATH] = {0};
    wchar_t elevated_args[4096] = {0};
    if (GetModuleFileNameW(NULL, exe_path, MAX_PATH) == 0) {
        return 0;
    }

    if (cmd_line && cmd_line[0] != L'\0') {
        swprintf_s(elevated_args, sizeof(elevated_args) / sizeof(elevated_args[0]), L"%s --launcher-elevated", cmd_line);
    } else {
        swprintf_s(elevated_args, sizeof(elevated_args) / sizeof(elevated_args[0]), L"--launcher-elevated");
    }

    HINSTANCE result = ShellExecuteW(NULL, L"runas", exe_path, elevated_args, NULL, SW_SHOWNORMAL);
    if ((INT_PTR)result <= 32) {
        DWORD code = (DWORD)(INT_PTR)result;
        char msg[512];
        snprintf(msg, sizeof(msg), "需要管理員權限，但提權失敗或被取消（代碼: %lu）。程式將結束。", code);
        show_error(msg);
        log_message("WARN", "elevation denied or failed code=%lu", code);
        return -1;
    }

    log_message("INFO", "elevation requested successfully, exiting current process");
    return 1;
}

void filter_internal_launcher_args(const char* src, char* dest, size_t dest_size) {
    char buffer[1024];
    char* token = NULL;
    char* context = NULL;

    if (!dest || dest_size == 0) {
        return;
    }
    dest[0] = '\0';
    if (!src || src[0] == '\0') {
        return;
    }

    strncpy_s(buffer, sizeof(buffer), src, _TRUNCATE);
    token = strtok_s(buffer, " \t", &context);
    while (token) {
        if (strcmp(token, "--restart") != 0) {
            if (dest[0] != '\0') {
                strncat_s(dest, dest_size, " ", _TRUNCATE);
            }
            strncat_s(dest, dest_size, token, _TRUNCATE);
        }
        token = strtok_s(NULL, " \t", &context);
    }
}

int check_critical_paths(const char* pythonw_path, const char* script_path) {
    if (!file_exists(pythonw_path)) {
        char error_msg[1024];
        snprintf(error_msg, sizeof(error_msg), "錯誤：找不到 pythonw.exe\n\n預期路徑：%s\n\n請確認檔案是否存在。", pythonw_path);
        show_error(error_msg);
        log_message("ERROR", "missing file path=%s", pythonw_path);
        return 0;
    }

    if (!file_exists(script_path)) {
        char error_msg[1024];
        snprintf(error_msg, sizeof(error_msg), "錯誤：找不到 main.pyw\n\n預期路徑：%s\n\n請確認檔案是否存在。", script_path);
        show_error(error_msg);
        log_message("ERROR", "missing file path=%s", script_path);
        return 0;
    }

    return 1;
}

void run_non_blocking_checks() {
    if (!is_vsredist_installed()) {
        log_message("WARN", "vs redist check failed");
    } else {
        log_message("INFO", "vs redist check passed");
    }
}

int APIENTRY wWinMain(HINSTANCE hInstance, HINSTANCE hPrevInstance, LPWSTR lpCmdLine, int nCmdShow) {
    UNREFERENCED_PARAMETER(hInstance);
    UNREFERENCED_PARAMETER(hPrevInstance);
    UNREFERENCED_PARAMETER(nCmdShow);

    char app_path[MAX_PATH] = {0};
    char pythonw_path[MAX_PATH] = {0};
    char script_path[MAX_PATH] = {0};
    char temp_path[MAX_PATH] = {0};
    char forwarded_args[1024] = {0};
    char command[3072] = {0};
    STARTUPINFOA si;
    PROCESS_INFORMATION pi;
    DWORD start_tick = GetTickCount();

    get_app_path(app_path, sizeof(app_path));
    init_log_file(app_path);
    log_message("INFO", "app path=%s", app_path);

    if (!ensure_single_instance(lpCmdLine)) {
        log_message("INFO", "blocked by singleton mutex");
        close_log_file();
        release_singleton();
        return 2;
    }

    int elevate_result = maybe_relaunch_as_admin(lpCmdLine);
    if (elevate_result != 0) {
        close_log_file();
        release_singleton();
        return elevate_result > 0 ? 0 : 1;
    }

    if (!is_vsredist_installed()) {
        const wchar_t* msg = L"您的系統未安裝 Visual C++ Redistributable (x64)！\n\n是否要自動下載安裝？\n\n按 [是] 會開啟官方下載頁面，安裝完成後請重新啟動本程式。";
        prompt_and_install(L"缺少 Visual C++ Redistributable (x64)", msg, L"https://aka.ms/vs/17/release/vc_redist.x64.exe");
        log_message("ERROR", "blocking check failed: missing VS redist");
        close_log_file();
        release_singleton();
        return 1;
    }

    PathCombineA(temp_path, app_path, "main");
    PathCombineA(temp_path, temp_path, "lib");
    PathCombineA(temp_path, temp_path, "python_embed");
    PathCombineA(pythonw_path, temp_path, "pythonw.exe");
    PathCombineA(temp_path, app_path, "main");
    PathCombineA(script_path, temp_path, "main.pyw");
    log_message("INFO", "pythonw path=%s", pythonw_path);
    log_message("INFO", "script path=%s", script_path);

    if (!check_critical_paths(pythonw_path, script_path)) {
        close_log_file();
        release_singleton();
        return 1;
    }

    if (lpCmdLine && lpCmdLine[0] != L'\0') {
        if (!wide_to_utf8(lpCmdLine, forwarded_args, sizeof(forwarded_args))) {
            show_error("錯誤：無法解析啟動參數。");
            log_message("ERROR", "failed to parse launcher args");
            close_log_file();
            release_singleton();
            return 1;
        }
    }

    {
        char filtered_args[1024] = {0};
        filter_internal_launcher_args(forwarded_args, filtered_args, sizeof(filtered_args));
        strncpy_s(forwarded_args, sizeof(forwarded_args), filtered_args, _TRUNCATE);
    }

    if (forwarded_args[0] != '\0') {
        snprintf(command, sizeof(command), "\"%s\" \"%s\" %s", pythonw_path, script_path, forwarded_args);
    } else {
        snprintf(command, sizeof(command), "\"%s\" \"%s\"", pythonw_path, script_path);
    }
    log_message("INFO", "create process command=%s", command);

    ZeroMemory(&si, sizeof(si));
    si.cb = sizeof(si);
    si.dwFlags = STARTF_USESHOWWINDOW;
    si.wShowWindow = SW_SHOW;
    ZeroMemory(&pi, sizeof(pi));

    if (!CreateProcessA(NULL, command, NULL, NULL, FALSE, 0, NULL, app_path, &si, &pi)) {
        DWORD error = GetLastError();
        char error_reason[256] = {0};
        char error_msg[1024] = {0};

        switch (error) {
            case ERROR_FILE_NOT_FOUND:
                strcpy_s(error_reason, sizeof(error_reason), "找不到指定的檔案");
                break;
            case ERROR_PATH_NOT_FOUND:
                strcpy_s(error_reason, sizeof(error_reason), "找不到指定的路徑");
                break;
            case ERROR_ACCESS_DENIED:
                strcpy_s(error_reason, sizeof(error_reason), "存取被拒絕");
                break;
            case ERROR_INVALID_PARAMETER:
                strcpy_s(error_reason, sizeof(error_reason), "無效的參數");
                break;
            case ERROR_BAD_EXE_FORMAT:
                strcpy_s(error_reason, sizeof(error_reason), "可執行檔案格式錯誤");
                break;
            default:
                snprintf(error_reason, sizeof(error_reason), "未知錯誤 (代碼: %lu)", error);
                break;
        }

        snprintf(error_msg, sizeof(error_msg), "錯誤：無法啟動程式。\n\n錯誤代碼：%lu\n錯誤原因：%s\n\n請檢查檔案權限和路徑是否正確。", error, error_reason);
        show_error(error_msg);
        log_message("ERROR", "create process failed code=%lu reason=%s cwd=%s", error, error_reason, app_path);

        if (pi.hProcess) CloseHandle(pi.hProcess);
        if (pi.hThread) CloseHandle(pi.hThread);
        close_log_file();
        release_singleton();
        return 1;
    }

    run_non_blocking_checks();

    WaitForSingleObject(pi.hProcess, INFINITE);
    DWORD child_exit_code = 0;
    GetExitCodeProcess(pi.hProcess, &child_exit_code);
    log_message("INFO", "python process exited code=%lu elapsed_ms=%lu", child_exit_code, GetTickCount() - start_tick);

    if (pi.hProcess) CloseHandle(pi.hProcess);
    if (pi.hThread) CloseHandle(pi.hThread);
    close_log_file();
    release_singleton();
    return (int)child_exit_code;
}
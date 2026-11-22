/* Done by Codex: display-only translations for Nova's saved slot words.
 * Sheet: psnova_text_v7, classes 10201-10204 and chapter names 810400-810413.
 * Never changes the game's save data. Unknown fields pass through unchanged. */
#ifndef NOVA_SAVE_DISPLAY_H
#define NOVA_SAVE_DISPLAY_H
#include <cstring>
#include <string>

extern "C" const char *host_lang(void);
inline bool nova_save_english() { return std::strcmp(host_lang(), "en") == 0; }

inline std::string nova_save_subtitle(const char *text, bool english) {
    std::string s = text ? text : "";
    if (!english) return s;
    struct Word { const char *jp, *en; };
    static const Word classes[] = {
        {u8"ハンター", "Hunter"}, {u8"レンジャー", "Ranger"},
        {u8"フォース", "Force"}, {u8"バスター", "Buster"}
    };
    // Parse from the right, so slashes and class names in the player's name survive.
    const size_t slash = s.rfind('/');
    if (slash == std::string::npos || slash + 1 == s.size()) return s;
    const size_t prev = slash ? s.rfind('/', slash - 1) : std::string::npos;
    if (prev == std::string::npos) return s;
    for (const auto &w : classes) {
        const size_t start = prev + 1, n = std::strlen(w.jp);
        if (s.compare(start, n, w.jp) != 0 || s.compare(start + n, 2, "Lv") != 0) continue;
        size_t p = start + n + 2;
        if (p == slash) continue;
        while (p < slash && s[p] >= '0' && s[p] <= '9') ++p;
        if (p != slash) continue;
        s.replace(start, n, w.en);
        break;
    }
    return s;
}

inline std::string nova_save_detail(const char *text, bool english) {
    const char *s = text ? text : "";
    if (!english) return s;
    struct Word { const char *jp, *en; };
    static const Word chapters[] = {
        {u8"惑星の洗礼", "Planet's Baptism"}, {u8"鋼焔の巨獣", "Steel Giants"},
        {u8"生存への挑戦　Ⅰ", "Subsistence I"}, {u8"生存への挑戦　Ⅱ", "Subsistence II"},
        {u8"生存への挑戦　Ⅲ", "Subsistence III"}, {u8"生存への挑戦　Ⅳ", "Subsistence IV"},
        {u8"生存への挑戦　Ⅴ", "Subsistence V"}, {u8"脱出", "Escape"},
        {u8"惑星の真実　Ⅰ", "Planet's Truth I"}, {u8"惑星の真実　Ⅱ", "Planet's Truth II"},
        {u8"惑星の真実　Ⅲ", "Planet's Truth III"}, {u8"惑星の真実　Ⅳ", "Planet's Truth IV"},
        {u8"ほんとうの約束", "Real Promise"}, {u8"惑星より永遠に", "Eternal Than the Planet"}
    };
    for (const auto &w : chapters) if (std::strcmp(s, w.jp) == 0) return w.en;
    return s;
}
#endif

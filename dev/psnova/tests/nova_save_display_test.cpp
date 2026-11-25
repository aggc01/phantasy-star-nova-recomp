
#include "../../../runtime/ui/nova_save_display.h"
#include <cassert>
extern "C" const char *host_lang(void) { return "en"; }
int main() {
    assert(nova_save_english());
    assert(nova_save_subtitle(u8"Nova/ハンターLv1/0:02", true) == "Nova/HunterLv1/0:02");
    assert(nova_save_subtitle(u8"A/ハンター/レンジャーLv25/4:00", true) == u8"A/ハンター/RangerLv25/4:00");
    assert(nova_save_subtitle(u8"Nova/フォースLv9/0:02", true) == "Nova/ForceLv9/0:02");
    assert(nova_save_subtitle(u8"Nova/バスターLv99/0:02", true) == "Nova/BusterLv99/0:02");
    assert(nova_save_subtitle(u8"Nova/ハンターLv1/0:02", false) == u8"Nova/ハンターLv1/0:02");
    assert(nova_save_subtitle(u8"Nova/ハンターLvX/0:02", true) == u8"Nova/ハンターLvX/0:02");
    assert(nova_save_detail(u8"惑星の洗礼", true) == "Planet's Baptism");
    assert(nova_save_detail(u8"惑星の真実　Ⅳ", true) == "Planet's Truth IV");
    assert(nova_save_detail(u8"未知", true) == u8"未知");
    assert(nova_save_detail(u8"惑星の洗礼", false) == u8"惑星の洗礼");
}


"""Pin reviewed V17 production deltas before executing older baseline assertions.

The hash gate rejects any extra change; the historical tests then compare the
V16 parent against their older checkpoints. V17 behavior has separate executable
storage/factory tests and mechanical rendering-body equivalence checks.
"""
import hashlib
from pathlib import Path
import subprocess
from v18_source_contract import without_v18

BASELINE = "d830338e418530b9c68cd77dfcee60ef47978894"
REVIEWED = {'src/activities/home/HomeActivity.cpp': 'd8f6ed46cf7854d08265842bd365a06ac4191fb832edd4368a39e46144da62e9',
 'src/activities/home/HomeActivity.h': '8467c20e828b48859d7735a607f38e56a2a09bd4a1a252861ad1e92f902bff29',
 'src/components/CoverGridHomeUi.cpp': '9007570a632f32755239d4875da4fe7e1d79502f3d3476bf881f5c0f649d7f2b',
 'src/components/CoverGridHomeUi.h': '6152e93c112f1b0be0ef007ef68b4cda6317a9544b2536895a396f89ca7cdb91',
 'src/components/themes/BaseTheme.cpp': '6df3f903202d65d0a615049eeafe0aa1278936c40199805dbcf3d0d8c2393f7c',
 'src/components/themes/BaseTheme.h': '37041c0b89a3e6104a1f5283d7b55335c70a3e4907063fe7a30239010cffbc26',
 'src/components/themes/dashboard/DashboardTheme.cpp': 'aa1f134d7530c4afb1cc11cf6019778fd74178725427ba439ec4d25e513cc4c6',
 'src/components/themes/dashboard/DashboardTheme.h': 'e4681c7348cb78b45cb606cd7cd42a9536cd6ea9a2cb33bd200e365a2e517f10',
 'src/components/themes/lyra/Lyra3CoversTheme.cpp': 'ffb17d7454627db7f862a311442548b5aad19af13b75417cd4ca3c74149638ae',
 'src/components/themes/lyra/Lyra3CoversTheme.h': '9b6b68a7b7f2621bfb44ca6a03a73fb90471401f579391d7db45eb5d5cc4db80',
 'src/components/themes/lyra/LyraCarouselTheme.cpp': '386356acf6acdee55ada1ca77a402bf9b523ebd37b297faff421dc11103ca639',
 'src/components/themes/lyra/LyraCarouselTheme.h': 'ab984e2d11f0073f4818795d03cada44c59acd344c7b1256d189bfd8bec43c83',
 'src/components/themes/lyra/LyraTheme.cpp': '1d6321c58e10ef434f38d7d014a1c6862863725d4fed2b6e5ee44694537e8de8',
 'src/components/themes/lyra/LyraTheme.h': '4e6067f6fe8e9a9128a74b1bb9816f3b4e017186cf1206dea79fca6a0dc8edd1',
 'src/components/themes/minimal/MinimalTheme.cpp': '3154822068c33bb66bf7e90ad2e6ecd66d0fed984b0bee4d5e7b154b95dcae40',
 'src/components/themes/minimal/MinimalTheme.h': '367eb5bf87269ba069ff7f091612765b158470fe0de432aceb18ecff8bccc55d',
 'src/components/themes/roundedraff/RoundedRaffTheme.cpp': '3cbf1271ee4e0cce612c8ed38026e76d322e77a4c45c2fc3ee510a3a45078ec4',
 'src/components/themes/roundedraff/RoundedRaffTheme.h': 'd659b586c674a714ced6e3ad9e720390d5bf8ed8d3e8e465f0786bf1c3207a16'}

def without_v17(name, text):
    text = without_v18(name, text)
    if name not in REVIEWED:
        return text
    if hashlib.sha256(text.encode()).hexdigest() != REVIEWED[name]:
        raise AssertionError("Unreviewed V17 source delta: " + name)
    return subprocess.check_output(["git", "show", f"{BASELINE}:{name}"],
                                   cwd=Path(__file__).resolve().parents[1]).decode()

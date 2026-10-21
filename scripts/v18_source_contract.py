"""Remove only the explicit V18 diagnostic gate for historical source assertions.

The V17 hash gate still rejects every other production delta. Independent V18
tests execute the actual onEnter method and compare its full file with V17.
"""

BASELINE = "a65801555dc210e443e317e0909420933404fd28"
HOME = "src/activities/home/HomeActivity.cpp"
ORIGINAL = "  loadRecentBooks(recentBooksToLoad);"
EXPERIMENT = """  // V18 diagnostic: only root Settings-return Home owns external record storage.
  // Keep its preflighted slots empty; do not create even temporary private copies.
  if (!externalRecentBooks) loadRecentBooks(recentBooksToLoad);"""


def without_v18(name, text):
    if name == HOME and EXPERIMENT in text:
        assert text.count(EXPERIMENT) == 1
        return text.replace(EXPERIMENT, ORIGINAL)
    return text

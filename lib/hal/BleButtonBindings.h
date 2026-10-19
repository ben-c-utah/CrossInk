#pragma once

#include <array>
#include <cstddef>
#include <cstdint>

// CrossPoint BleKeyBinding's raw fingerprint and bounded per-peer lookup,
// reduced to two press actions. No profile dependency or global Up/Down map.
namespace BleBindings {
constexpr size_t MaxPeers = 4;
enum class Action : uint8_t { Next, Previous };
enum class Result : uint8_t { Saved, Unchanged, Duplicate, Full, Invalid };
struct Peer {
  char address[18]{};
  uint8_t type = 0;
};
constexpr char lower(char c) { return c >= 'A' && c <= 'F' ? c + ('a' - 'A') : c; }
constexpr bool valid(const Peer& p) {
  if (p.type > 3 || p.address[17] != '\0') return false;
  for (size_t i = 0; i < 17; ++i) {
    const char c = lower(p.address[i]);
    if (i % 3 == 2 ? c != ':' : !((c >= '0' && c <= '9') || (c >= 'a' && c <= 'f'))) return false;
  }
  return true;
}
constexpr bool same(const Peer& a, const Peer& b) {
  if (a.type != b.type) return false;
  for (size_t i = 0; i < 18; ++i) if (lower(a.address[i]) != lower(b.address[i])) return false;
  return true;
}
constexpr bool validCode(uint32_t code) { return (code & 0xffu) != 0 && (code & 0xff000000u) == 0; }
struct Table {
  Peer peer{};
  uint32_t codes[2]{};
};
struct Store {
  std::array<Table, MaxPeers> tables{};
  constexpr uint32_t get(const Peer& peer, Action action) const {
    if (static_cast<unsigned>(action) > 1) return 0;
    for (const auto& t : tables) if (same(t.peer, peer)) return t.codes[static_cast<unsigned>(action)];
    return 0;
  }
  constexpr Result assign(const Peer& peer, Action action, uint32_t code) {
    if (!valid(peer) || !validCode(code) || static_cast<unsigned>(action) > 1) return Result::Invalid;
    Table* slot = nullptr;
    for (auto& t : tables) if (same(t.peer, peer)) { slot = &t; break; }
    if (!slot) for (auto& t : tables) if (!t.peer.address[0]) { slot = &t; break; }
    if (!slot) return Result::Full;
    const unsigned index = static_cast<unsigned>(action);
    if (slot->codes[1 - index] == code) return Result::Duplicate;
    if (slot->codes[index] == code) return Result::Unchanged;
    slot->peer = peer;
    for (char& c : slot->peer.address) c = lower(c);
    slot->codes[index] = code;
    return Result::Saved;
  }
  constexpr bool reset(const Peer& peer) {
    for (auto& t : tables) if (same(t.peer, peer)) { t = {}; return true; }
    return false;
  }
};

// Explicit little-endian, fixed-size, versioned NVS blob; no struct padding.
using Blob = std::array<uint8_t, 4 + MaxPeers * 27 + 4>;
constexpr uint32_t checksum(const Blob& blob) {
  uint32_t value = 2166136261u;
  for (size_t i = 0; i < blob.size() - 4; ++i) value = (value ^ blob[i]) * 16777619u;
  return value;
}
constexpr void put32(Blob& blob, size_t pos, uint32_t n) {
  for (unsigned i = 0; i < 4; ++i) blob[pos + i] = static_cast<uint8_t>(n >> (8 * i));
}
constexpr uint32_t get32(const Blob& blob, size_t pos) {
  uint32_t n = 0;
  for (unsigned i = 0; i < 4; ++i) n |= uint32_t{blob[pos + i]} << (8 * i);
  return n;
}
constexpr Blob encode(const Store& store) {
  Blob blob{};
  blob[0] = 'B'; blob[1] = 'M'; blob[2] = 1; blob[3] = MaxPeers;
  size_t pos = 4;
  for (const auto& t : store.tables) {
    for (char c : t.peer.address) blob[pos++] = static_cast<uint8_t>(c);
    blob[pos++] = t.peer.type;
    for (uint32_t code : t.codes) { put32(blob, pos, code); pos += 4; }
  }
  put32(blob, pos, checksum(blob));
  return blob;
}
constexpr bool decode(const Blob& blob, Store& store) {
  if (blob[0] != 'B' || blob[1] != 'M' || blob[2] != 1 || blob[3] != MaxPeers ||
      get32(blob, blob.size() - 4) != checksum(blob)) return false;
  Store next{};
  size_t pos = 4;
  for (size_t i = 0; i < MaxPeers; ++i) {
    auto& t = next.tables[i];
    for (char& c : t.peer.address) c = static_cast<char>(blob[pos++]);
    t.peer.type = blob[pos++];
    for (auto& code : t.codes) { code = get32(blob, pos); pos += 4; }
    if (!t.peer.address[0]) {
      for (char c : t.peer.address) if (c) return false;
      if (t.peer.type || t.codes[0] || t.codes[1]) return false;
      continue;
    }
    if (!valid(t.peer) || (t.codes[0] && !validCode(t.codes[0])) || (t.codes[1] && !validCode(t.codes[1])) ||
        (t.codes[0] && t.codes[0] == t.codes[1])) return false;
    for (size_t j = 0; j < i; ++j) if (same(t.peer, next.tables[j].peer)) return false;
  }
  store = next;
  return true;
}

struct Router {
  uint8_t held = 0;
  constexpr void reset() { held = 0; }
  constexpr int8_t accept(const Store& store, const Peer& peer, uint32_t code, bool pressed,
                          bool wasRest, uint8_t mods, int8_t fallback) {
    for (unsigned i = 0; i < 2; ++i) {
      if (!code || store.get(peer, static_cast<Action>(i)) != code) continue;
      const uint8_t bit = 1u << i;
      if (!pressed) { held &= ~bit; return 0; }
      const bool repeated = held & bit;
      held |= bit;
      return repeated || wasRest || mods ? 0 : i == 0 ? 1 : -1;
    }
    return pressed ? fallback : 0;
  }
};

enum class Learning : uint8_t { Idle, Waiting, Captured, Saved, Duplicate, Timeout, Disconnected, StorageError, Full };
struct Learner {
  static constexpr uint32_t TimeoutMs = 15000;
  Learning state = Learning::Idle;
  Action action = Action::Next;
  Peer peer{};
  uint32_t started = 0;
  uint32_t candidate = 0;
  constexpr void start(const Peer& p, Action a, uint32_t now) {
    peer = p; action = a; started = now; candidate = 0; state = Learning::Waiting;
  }
  constexpr void cancel() { state = Learning::Idle; candidate = 0; }
  constexpr void tick(uint32_t now, bool connected) {
    if (state != Learning::Waiting) return;
    if (!connected) state = Learning::Disconnected;
    else if (now - started >= TimeoutMs) state = Learning::Timeout;
  }
  constexpr bool feed(uint32_t code, bool pressed, bool wasRest, uint8_t mods, uint32_t atMs, uint32_t now) {
    tick(now, true);
    if (state != Learning::Waiting || static_cast<int32_t>(atMs - started) < 0 || mods || !validCode(code)) return false;
    if (pressed) { if (!candidate) candidate = code; return false; }
    if (candidate != code) return false;
    if (wasRest) { candidate = 0; return false; }
    state = Learning::Captured;
    return true;
  }
};
}  // namespace BleBindings

#pragma once

// Host command reader. Pure C++11: no Arduino dependency and no dynamic
// allocation. Reads the lines the host sends to the board:
//   "ALARM,<0|1|2>"         set the local alarm level (see alarm_command.h)
//   "BSEC_STATE,<hex>"      the saved BSEC state, 1 to 238 bytes as hex
//   "BSEC_STATE,NONE"       the host has no saved BSEC state
// Also holds the rule for when the board sends its BSEC state to the host.

#include <cstddef>
#include <cstdint>

enum {
  ROOM_HOST_NONE = 0,        // No complete line yet, or an empty line.
  ROOM_HOST_ALARM = 1,       // level holds 0, 1 or 2.
  ROOM_HOST_BSEC_STATE = 2,  // state holds stateLength bytes.
  ROOM_HOST_BSEC_NONE = 3,   // The host has no saved state.
  ROOM_HOST_INVALID = 4,     // A complete line that is not a valid command.
  ROOM_HOST_LINE_MAX = 511,  // Longest line kept; longer lines are discarded.
  ROOM_HOST_STATE_MAX = 238  // Largest BSEC state in bytes.
};

struct HostCommand {
  int kind;
  int level;
  std::uint8_t state[ROOM_HOST_STATE_MAX];
  std::size_t stateLength;
};

inline HostCommand hostCommandOf(int kind) {
  HostCommand command;
  command.kind = kind;
  command.level = -1;
  command.stateLength = 0;
  return command;
}

inline int hostHexValue(char c) {
  if (c >= '0' && c <= '9') return c - '0';
  if (c >= 'a' && c <= 'f') return c - 'a' + 10;
  if (c >= 'A' && c <= 'F') return c - 'A' + 10;
  return -1;
}

inline bool hostStartsWith(const char* line, std::size_t length, const char* prefix,
                           std::size_t prefixLength) {
  if (length < prefixLength) return false;
  for (std::size_t i = 0; i < prefixLength; ++i) {
    if (line[i] != prefix[i]) return false;
  }
  return true;
}

// Parse one line (length excludes the newline). Anything that is not exactly
// one of the commands above is ROOM_HOST_INVALID.
inline HostCommand parseHostCommand(const char* line, std::size_t length) {
  static const char alarmPrefix[] = "ALARM,";
  static const char statePrefix[] = "BSEC_STATE,";
  static const char noState[] = "NONE";
  const std::size_t alarmPrefixLength = sizeof(alarmPrefix) - 1;
  const std::size_t statePrefixLength = sizeof(statePrefix) - 1;
  const std::size_t noStateLength = sizeof(noState) - 1;
  if (line == nullptr) return hostCommandOf(ROOM_HOST_INVALID);

  if (hostStartsWith(line, length, alarmPrefix, alarmPrefixLength)) {
    if (length != alarmPrefixLength + 1) return hostCommandOf(ROOM_HOST_INVALID);
    const char digit = line[alarmPrefixLength];
    if (digit < '0' || digit > '2') return hostCommandOf(ROOM_HOST_INVALID);
    HostCommand command = hostCommandOf(ROOM_HOST_ALARM);
    command.level = digit - '0';
    return command;
  }

  if (!hostStartsWith(line, length, statePrefix, statePrefixLength)) {
    return hostCommandOf(ROOM_HOST_INVALID);
  }
  const char* payload = line + statePrefixLength;
  const std::size_t payloadLength = length - statePrefixLength;
  if (payloadLength == noStateLength &&
      hostStartsWith(payload, payloadLength, noState, noStateLength)) {
    return hostCommandOf(ROOM_HOST_BSEC_NONE);
  }
  if (payloadLength == 0 || payloadLength % 2 != 0 ||
      payloadLength > 2 * static_cast<std::size_t>(ROOM_HOST_STATE_MAX)) {
    return hostCommandOf(ROOM_HOST_INVALID);
  }
  HostCommand command = hostCommandOf(ROOM_HOST_BSEC_STATE);
  for (std::size_t i = 0; i < payloadLength; i += 2) {
    const int high = hostHexValue(payload[i]);
    const int low = hostHexValue(payload[i + 1]);
    if (high < 0 || low < 0) return hostCommandOf(ROOM_HOST_INVALID);
    command.state[i / 2] = static_cast<std::uint8_t>(high * 16 + low);
  }
  command.stateLength = payloadLength / 2;
  return command;
}

// Collect serial bytes into a fixed buffer. feed() returns the parsed command
// for a complete line and ROOM_HOST_NONE otherwise. A trailing '\r' is
// ignored. A line longer than ROOM_HOST_LINE_MAX is discarded up to its
// newline and reported as ROOM_HOST_INVALID.
struct HostLineReader {
  char buffer[ROOM_HOST_LINE_MAX + 1];
  std::size_t length;
  bool overflow;

  HostLineReader() : length(0), overflow(false) { buffer[0] = '\0'; }

  HostCommand feed(char c) {
    if (c == '\n') {
      std::size_t end = length;
      const bool discarded = overflow;
      length = 0;
      overflow = false;
      if (discarded) return hostCommandOf(ROOM_HOST_INVALID);
      if (end > 0 && buffer[end - 1] == '\r') --end;
      if (end == 0) return hostCommandOf(ROOM_HOST_NONE);
      return parseHostCommand(buffer, end);
    }
    if (overflow) return hostCommandOf(ROOM_HOST_NONE);
    if (length >= ROOM_HOST_LINE_MAX) {
      overflow = true;
      length = 0;
      return hostCommandOf(ROOM_HOST_NONE);
    }
    buffer[length++] = c;
    return hostCommandOf(ROOM_HOST_NONE);
  }
};

// Write state as lowercase hex with a terminating '\0'. False, with out set
// to "" when it has room, if out cannot hold 2 * length + 1 characters.
inline bool formatStateHex(const std::uint8_t* state, std::size_t length, char* out,
                           std::size_t capacity) {
  static const char digits[] = "0123456789abcdef";
  if (out == nullptr || capacity == 0) return false;
  out[0] = '\0';
  if ((state == nullptr && length > 0) || length > (capacity - 1) / 2) return false;
  for (std::size_t i = 0; i < length; ++i) {
    out[2 * i] = digits[state[i] >> 4];
    out[2 * i + 1] = digits[state[i] & 0x0F];
  }
  out[2 * length] = '\0';
  return true;
}

// True when the board should send its BSEC state to the host: only at IAQ
// accuracy 3, at once if it has not saved yet, otherwise once periodMs has
// passed since the last save. Unsigned subtraction keeps the result right
// across the millis() wrap.
inline bool bsecShouldSave(std::uint8_t accuracy, bool savedOnce, std::uint32_t nowMs,
                           std::uint32_t lastSaveMs, std::uint32_t periodMs) {
  if (accuracy < 3) return false;
  if (!savedOnce) return true;
  return static_cast<std::uint32_t>(nowMs - lastSaveMs) >= periodMs;
}

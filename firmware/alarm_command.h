#pragma once

// Local alarm command core. Pure C++11: no Arduino dependency and no dynamic
// allocation. The sketch feeds it from Serial and drives the alarm LED and the
// buzzer module (pins in bsec_board_config.h) from alarmOutputs.
//
// Host to board: "ALARM,<0|1|2>\n". Board to host: {"type":"alarm","state":<n>}.
// Level 0: LED off, buzzer off. 1: LED on, buzzer off. 2: LED on, buzzer on.

#include <cstddef>
#include <cstdio>

enum {
  ROOM_ALARM_NO_LINE = -2,  // No complete line yet, or an empty line.
  ROOM_ALARM_INVALID = -1,  // A complete line that is not a valid command.
  ROOM_ALARM_LINE_MAX = 31  // Longest line kept; longer lines are discarded.
};

struct AlarmOutputs {
  bool led;
  bool buzzer;
};

// Accept exactly "ALARM,0", "ALARM,1" or "ALARM,2" (length excludes the newline).
inline int parseAlarmCommand(const char* line, std::size_t length) {
  static const char prefix[] = "ALARM,";
  const std::size_t prefixLength = sizeof(prefix) - 1;
  if (line == nullptr || length != prefixLength + 1) return ROOM_ALARM_INVALID;
  for (std::size_t i = 0; i < prefixLength; ++i) {
    if (line[i] != prefix[i]) return ROOM_ALARM_INVALID;
  }
  const char digit = line[prefixLength];
  if (digit < '0' || digit > '2') return ROOM_ALARM_INVALID;
  return digit - '0';
}

// The buzzer is on only at level 2, and the LED is on whenever the buzzer is.
// Any other value turns both off; callers apply only parsed levels.
inline AlarmOutputs alarmOutputs(int level) {
  AlarmOutputs outputs;
  outputs.led = level == 1 || level == 2;
  outputs.buzzer = level == 2;
  return outputs;
}

// Collect serial bytes into a fixed buffer. feed() returns a level for a
// valid command line, ROOM_ALARM_INVALID for any other complete line, and
// ROOM_ALARM_NO_LINE otherwise. A trailing '\r' is ignored.
struct AlarmLineReader {
  char buffer[ROOM_ALARM_LINE_MAX + 1];
  std::size_t length;
  bool overflow;

  AlarmLineReader() : length(0), overflow(false) { buffer[0] = '\0'; }

  int feed(char c) {
    if (c == '\n') {
      std::size_t end = length;
      const bool discarded = overflow;
      length = 0;
      overflow = false;
      if (discarded) return ROOM_ALARM_INVALID;
      if (end > 0 && buffer[end - 1] == '\r') --end;
      if (end == 0) return ROOM_ALARM_NO_LINE;
      return parseAlarmCommand(buffer, end);
    }
    if (overflow) return ROOM_ALARM_NO_LINE;
    if (length >= ROOM_ALARM_LINE_MAX) {
      overflow = true;
      length = 0;
      return ROOM_ALARM_NO_LINE;
    }
    buffer[length++] = c;
    return ROOM_ALARM_NO_LINE;
  }
};

// Pin level for an output that should be on or off. activeHigh is false for a
// module that triggers on LOW.
inline bool alarmDriveLevel(bool on, bool activeHigh) { return on == activeHigh; }

// Feed at most maxBytes bytes from source into reader and call apply(level)
// for each valid command line. Source needs Arduino-style available() and
// read(); neither may wait. Bytes beyond maxBytes stay in the source for the
// next call. Returns the number of bytes read.
template <typename Source, typename Apply>
std::size_t pumpAlarmInput(Source& source, AlarmLineReader& reader,
                           std::size_t maxBytes, Apply apply) {
  std::size_t used = 0;
  while (used < maxBytes && source.available() > 0) {
    const int c = source.read();
    if (c < 0) break;
    ++used;
    const int level = reader.feed(static_cast<char>(c));
    if (level >= 0) apply(level);
  }
  return used;
}

inline bool formatAlarmReply(char* output, std::size_t capacity, int level) {
  if (output == nullptr || capacity == 0) return false;
  output[0] = '\0';
  if (level < 0 || level > 2) return false;
  const int length = std::snprintf(output, capacity, "{\"type\":\"alarm\",\"state\":%d}", level);
  if (length < 0 || static_cast<std::size_t>(length) >= capacity) {
    output[0] = '\0';
    return false;
  }
  return true;
}

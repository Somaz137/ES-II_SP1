#pragma once

// Local alarm command core. Pure C++11: no Arduino dependency and no dynamic
// allocation. The sketch feeds it from Serial and drives the alarm LED and the
// buzzer module (pins in bsec_board_config.h) from alarmOutputsAt.
//
// Host to board: "ALARM,<0|1|2>\n". Board to host: {"type":"alarm","state":<n>}.
// Level 0: LED off, buzzer off. 1: LED on, buzzer off. 2: LED on, buzzer on.
// With no valid command for the link timeout, the LED blinks and the buzzer
// keeps the last level's state.

#include <cstddef>
#include <cstdint>
#include <cstdio>

#include "host_command.h"

enum {
  ROOM_ALARM_NO_LINE = -2,  // No complete line yet, or an empty line.
  ROOM_ALARM_INVALID = -1,  // A complete line that is not a valid command.
  ROOM_ALARM_LINE_MAX = ROOM_HOST_LINE_MAX  // Longest line kept; longer lines are discarded.
};

struct AlarmOutputs {
  bool led;
  bool buzzer;
};

// Accept exactly "ALARM,0", "ALARM,1" or "ALARM,2" (length excludes the newline).
inline int parseAlarmCommand(const char* line, std::size_t length) {
  const HostCommand command = parseHostCommand(line, length);
  return command.kind == ROOM_HOST_ALARM ? command.level : ROOM_ALARM_INVALID;
}

// The buzzer is on only at level 2, and the LED is on whenever the buzzer is.
// Any other value turns both off; callers apply only parsed levels.
inline AlarmOutputs alarmOutputs(int level) {
  AlarmOutputs outputs;
  outputs.led = level == 1 || level == 2;
  outputs.buzzer = level == 2;
  return outputs;
}

// True when no valid command arrived for timeoutMs. Unsigned subtraction keeps
// the result right across the millis() wrap.
inline bool alarmLinkLost(uint32_t nowMs, uint32_t lastCommandMs, uint32_t timeoutMs) {
  return static_cast<uint32_t>(nowMs - lastCommandMs) >= timeoutMs;
}

// Outputs at time nowMs. With the link lost the LED blinks (on for the first
// halfPeriodMs, off for the next); the buzzer always keeps the level's state.
inline AlarmOutputs alarmOutputsAt(int level, bool linkLost, uint32_t nowMs,
                                   uint32_t halfPeriodMs) {
  AlarmOutputs outputs = alarmOutputs(level);
  if (linkLost) outputs.led = (nowMs / halfPeriodMs) % 2 == 0;
  return outputs;
}

// Collect serial bytes through a HostLineReader. feed() returns a level for a
// valid ALARM line, ROOM_ALARM_INVALID for any other complete line (BSEC_STATE
// lines included), and ROOM_ALARM_NO_LINE otherwise. A trailing '\r' is ignored.
struct AlarmLineReader {
  HostLineReader host;

  int feed(char c) {
    const HostCommand command = host.feed(c);
    if (command.kind == ROOM_HOST_NONE) return ROOM_ALARM_NO_LINE;
    if (command.kind == ROOM_HOST_ALARM) return command.level;
    return ROOM_ALARM_INVALID;
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

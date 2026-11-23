// Host test for the host-command reader and the BSEC state-save rule. Build on
// Linux with
// g++ -std=c++11 -Wall -Wextra -pedantic firmware/tests/test_host_command.cpp
#include "../host_command.h"
#include <cassert>
#include <cstring>
#include <string>

static HostCommand parse(const std::string& line) {
  return parseHostCommand(line.c_str(), line.size());
}

// Feed every character; only the last may end a line.
static HostCommand feedLine(HostLineReader& reader, const std::string& text) {
  HostCommand result = HostCommand();
  for (std::size_t i = 0; i < text.size(); ++i) {
    result = reader.feed(text[i]);
    if (i + 1 < text.size()) assert(result.kind == ROOM_HOST_NONE);
  }
  return result;
}

// 238 bytes 0x00, 0x01, ... as lowercase hex: 476 characters.
static std::string stateHex() {
  static const char digits[] = "0123456789abcdef";
  std::string hex;
  for (int i = 0; i < ROOM_HOST_STATE_MAX; ++i) {
    const unsigned value = static_cast<unsigned>(i * 7 + 3) & 0xFFu;
    hex += digits[value >> 4];
    hex += digits[value & 0x0Fu];
  }
  return hex;
}

int main() {
  // ALARM lines.
  for (int level = 0; level <= 2; ++level) {
    const std::string line = std::string("ALARM,") + static_cast<char>('0' + level);
    const HostCommand command = parse(line);
    assert(command.kind == ROOM_HOST_ALARM);
    assert(command.level == level);
  }
  assert(parse("ALARM,9").kind == ROOM_HOST_INVALID);
  assert(parse("ALARM,").kind == ROOM_HOST_INVALID);
  assert(parse("ALARM,22").kind == ROOM_HOST_INVALID);
  assert(parse("HELLO").kind == ROOM_HOST_INVALID);
  assert(parseHostCommand(nullptr, 0).kind == ROOM_HOST_INVALID);

  // No saved state.
  assert(parse("BSEC_STATE,NONE").kind == ROOM_HOST_BSEC_NONE);

  // A full 238-byte state round-trips through formatStateHex.
  const std::string hex = stateHex();
  assert(hex.size() == 476);
  const HostCommand state = parse("BSEC_STATE," + hex);
  assert(state.kind == ROOM_HOST_BSEC_STATE);
  assert(state.stateLength == 238);
  assert(state.state[0] == 3 && state.state[1] == 10 && state.state[237] == ((237 * 7 + 3) & 0xFF));
  char formatted[2 * ROOM_HOST_STATE_MAX + 1];
  assert(formatStateHex(state.state, state.stateLength, formatted, sizeof(formatted)));
  assert(hex == formatted);

  // Uppercase hex is accepted.
  const HostCommand upper = parse("BSEC_STATE,0A1bFF");
  assert(upper.kind == ROOM_HOST_BSEC_STATE && upper.stateLength == 3);
  assert(upper.state[0] == 0x0A && upper.state[1] == 0x1B && upper.state[2] == 0xFF);
  const HostCommand single = parse("BSEC_STATE,7f");
  assert(single.kind == ROOM_HOST_BSEC_STATE && single.stateLength == 1 && single.state[0] == 0x7F);

  // Odd length, a non-hex character, 478 characters, an empty payload.
  assert(parse("BSEC_STATE," + hex.substr(0, 475)).kind == ROOM_HOST_INVALID);
  // The odd-length check must not rely on a byte after the line.
  assert(parseHostCommand("BSEC_STATE,abcd", 14).kind == ROOM_HOST_INVALID);
  std::string bad = hex;
  bad[100] = 'g';
  assert(parse("BSEC_STATE," + bad).kind == ROOM_HOST_INVALID);
  assert(parse("BSEC_STATE," + hex + "00").kind == ROOM_HOST_INVALID);
  assert(parse("BSEC_STATE,").kind == ROOM_HOST_INVALID);
  assert(parse("BSEC_STATE").kind == ROOM_HOST_INVALID);
  assert(parse("BSEC_STATE,none").kind == ROOM_HOST_INVALID);
  assert(parse("BSEC_STATE,NONE ").kind == ROOM_HOST_INVALID);

  // formatStateHex needs room for the terminator.
  char tight[7];
  const uint8_t bytes[3] = {0x00, 0xAB, 0x10};
  assert(formatStateHex(bytes, 3, tight, sizeof(tight)));
  assert(std::strcmp(tight, "00ab10") == 0);
  assert(!formatStateHex(bytes, 3, tight, 6));
  assert(tight[0] == '\0');
  assert(!formatStateHex(bytes, 3, nullptr, 0));

  // The reader: lines, '\r', empty lines.
  HostLineReader reader;
  HostCommand got = feedLine(reader, "ALARM,2\n");
  assert(got.kind == ROOM_HOST_ALARM && got.level == 2);
  got = feedLine(reader, "ALARM,1\r\n");
  assert(got.kind == ROOM_HOST_ALARM && got.level == 1);
  assert(feedLine(reader, "\n").kind == ROOM_HOST_NONE);
  assert(feedLine(reader, "BSEC_STATE,NONE\r\n").kind == ROOM_HOST_BSEC_NONE);
  got = feedLine(reader, "BSEC_STATE," + hex + "\n");
  assert(got.kind == ROOM_HOST_BSEC_STATE && got.stateLength == 238);
  // A shorter odd line after a longer one: old bytes stay in the buffer.
  assert(feedLine(reader, "BSEC_STATE,abc\n").kind == ROOM_HOST_INVALID);

  // A 600-character line overflows and is invalid; the next line works.
  assert(feedLine(reader, std::string(600, 'A') + "\n").kind == ROOM_HOST_INVALID);
  got = feedLine(reader, "ALARM,0\n");
  assert(got.kind == ROOM_HOST_ALARM && got.level == 0);
  // A line of exactly ROOM_HOST_LINE_MAX characters fits.
  const std::string longest = "BSEC_STATE," + hex + std::string(ROOM_HOST_LINE_MAX - 11 - 476, 'A');
  assert(longest.size() == ROOM_HOST_LINE_MAX);
  assert(feedLine(reader, longest + "\n").kind == ROOM_HOST_INVALID);
  assert(feedLine(reader, "BSEC_STATE,NONE\n").kind == ROOM_HOST_BSEC_NONE);

  // Save rule: only at accuracy 3, at once the first time, then every period.
  const uint32_t sixHours = 6u * 60u * 60u * 1000u;
  assert(!bsecShouldSave(2, false, 1000u, 0u, sixHours));
  assert(!bsecShouldSave(0, false, 1000u, 0u, sixHours));
  assert(bsecShouldSave(3, false, 1000u, 0u, sixHours));
  assert(!bsecShouldSave(3, true, 5000u + sixHours - 1u, 5000u, sixHours));
  assert(bsecShouldSave(3, true, 5000u + sixHours, 5000u, sixHours));
  assert(!bsecShouldSave(2, true, 5000u + sixHours, 5000u, sixHours));
  // millis() wraps: saved at 0xFFFF0000, one period later is past zero.
  const uint32_t lastSave = 0xFFFF0000u;
  assert(!bsecShouldSave(3, true, lastSave + sixHours - 1u, lastSave, sixHours));
  assert(bsecShouldSave(3, true, lastSave + sixHours, lastSave, sixHours));
  assert(!bsecShouldSave(3, true, 0x00000010u, lastSave, sixHours));

  // Retry gate: after a failed getState, wait retryMs before the next try.
  const uint32_t minute = 60000u;
  assert(bsecRetryAllowed(false, 1000u, 0u, minute));
  assert(!bsecRetryAllowed(true, 5000u, 5000u, minute));
  assert(!bsecRetryAllowed(true, 5000u + minute - 1u, 5000u, minute));
  assert(bsecRetryAllowed(true, 5000u + minute, 5000u, minute));
  // millis() wraps between the failure and the retry.
  const uint32_t failedAt = 0xFFFFF000u;
  assert(!bsecRetryAllowed(true, 0x00000010u, failedAt, minute));
  assert(bsecRetryAllowed(true, failedAt + minute, failedAt, minute));
  return 0;
}

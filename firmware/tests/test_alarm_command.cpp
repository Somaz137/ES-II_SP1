// Host test for the alarm command core. Build on Linux with
// g++ -std=c++11 -Wall -Wextra -pedantic firmware/tests/test_alarm_command.cpp
#include "../alarm_command.h"
#include <cassert>
#include <cstring>
#include <string>

// Minimal stand-in for Arduino Serial: available() and read().
struct FakeSerial {
  std::string data;
  std::size_t position;
  explicit FakeSerial(const char* text) : data(text), position(0) {}
  void load(const char* text) { data = text; position = 0; }
  std::size_t remaining() const { return data.size() - position; }
  int available() { return static_cast<int>(remaining()); }
  int read() { return position < data.size() ? static_cast<unsigned char>(data[position++]) : -1; }
};

struct BrokenSerial {
  int available() { return 1; }
  int read() { return -1; }
};

static int applied[8];
static int appliedCount = 0;
static void recordLevel(int level) {
  if (appliedCount < 8) applied[appliedCount] = level;
  ++appliedCount;
}

static int feedLine(AlarmLineReader& reader, const char* text) {
  int result = ROOM_ALARM_NO_LINE;
  for (const char* c = text; *c != '\0'; ++c) {
    result = reader.feed(*c);
    if (*(c + 1) != '\0') assert(result == ROOM_ALARM_NO_LINE);
  }
  return result;
}

int main() {
  assert(parseAlarmCommand("ALARM,0", 7) == 0);
  assert(parseAlarmCommand("ALARM,1", 7) == 1);
  assert(parseAlarmCommand("ALARM,2", 7) == 2);
  const char* invalid[] = {"", "ALARM", "ALARM,", "ALARM,3", "ALARM,-1", "ALARM,22",
                           "alarm,2", " ALARM,2", "ALARM,2 ", "ALARM;2", "XALARM,2"};
  for (const char* line : invalid) {
    assert(parseAlarmCommand(line, std::strlen(line)) == ROOM_ALARM_INVALID);
  }
  assert(parseAlarmCommand(nullptr, 0) == ROOM_ALARM_INVALID);

  AlarmLineReader reader;
  assert(feedLine(reader, "ALARM,2\n") == 2);
  assert(feedLine(reader, "ALARM,1\r\n") == 1);
  assert(feedLine(reader, "ALARM,9\n") == ROOM_ALARM_INVALID);
  assert(feedLine(reader, "\n") == ROOM_ALARM_NO_LINE);
  // A fragment left by a failed host write, ended by the host's resync newline.
  assert(feedLine(reader, "ALA\n") == ROOM_ALARM_INVALID);
  assert(feedLine(reader, "ALARM,0\n") == 0);
  // Over-long lines are discarded up to the newline; the next line works.
  for (int i = 0; i < ROOM_ALARM_LINE_MAX + 100; ++i) assert(reader.feed('A') == ROOM_ALARM_NO_LINE);
  assert(feedLine(reader, "ALARM,2\n") == ROOM_ALARM_INVALID);
  assert(feedLine(reader, "ALARM,2\n") == 2);
  // A line at the buffer limit is rejected and the reader recovers.
  char longLine[ROOM_ALARM_LINE_MAX + 2];
  std::memset(longLine, 'A', ROOM_ALARM_LINE_MAX);
  longLine[ROOM_ALARM_LINE_MAX] = '\n';
  longLine[ROOM_ALARM_LINE_MAX + 1] = '\0';
  assert(feedLine(reader, longLine) == ROOM_ALARM_INVALID);
  assert(feedLine(reader, "ALARM,1\n") == 1);

  AlarmOutputs off = alarmOutputs(0), led = alarmOutputs(1), both = alarmOutputs(2);
  assert(!off.led && !off.buzzer);
  assert(led.led && !led.buzzer);
  assert(both.led && both.buzzer);
  for (int level = -3; level < 6; ++level) {
    AlarmOutputs outputs = alarmOutputs(level);
    assert(!outputs.buzzer || outputs.led);
  }
  assert(!alarmOutputs(3).led && !alarmOutputs(ROOM_ALARM_INVALID).led);

  char reply[32];
  assert(formatAlarmReply(reply, sizeof(reply), 2));
  assert(std::strcmp(reply, "{\"type\":\"alarm\",\"state\":2}") == 0);
  assert(formatAlarmReply(reply, sizeof(reply), 0));
  assert(std::strcmp(reply, "{\"type\":\"alarm\",\"state\":0}") == 0);
  assert(!formatAlarmReply(reply, sizeof(reply), 3));
  assert(reply[0] == '\0');
  char shortBuffer[10];
  assert(!formatAlarmReply(shortBuffer, sizeof(shortBuffer), 1));
  assert(shortBuffer[0] == '\0');
  assert(!formatAlarmReply(nullptr, 0, 1));

  // Polarity: an active-low module is driven LOW to sound.
  assert(alarmDriveLevel(true, true) && !alarmDriveLevel(false, true));
  assert(!alarmDriveLevel(true, false) && alarmDriveLevel(false, false));

  // The pump reads at most maxBytes per pass and applies every valid line.
  FakeSerial serial("ALARM,1\nALARM,9\nALARM,2\r\nALA");
  AlarmLineReader pumpReader;
  appliedCount = 0;
  assert(pumpAlarmInput(serial, pumpReader, 5, recordLevel) == 5);
  assert(appliedCount == 0 && serial.remaining() > 0);
  assert(pumpAlarmInput(serial, pumpReader, 64, recordLevel) == 23);
  assert(appliedCount == 2 && applied[0] == 1 && applied[1] == 2);
  assert(serial.remaining() == 0);
  // An empty source returns at once; the partial "ALA" is kept for later.
  assert(pumpAlarmInput(serial, pumpReader, 64, recordLevel) == 0);
  serial.load("RM,0\n");
  assert(pumpAlarmInput(serial, pumpReader, 64, recordLevel) == 5);
  assert(appliedCount == 3 && applied[2] == 0);
  // A flood is bounded per pass.
  std::string flood(1000, 'X');
  serial.load(flood.c_str());
  assert(pumpAlarmInput(serial, pumpReader, 64, recordLevel) == 64);
  assert(serial.remaining() == 1000 - 64);
  // A source that reports data but returns -1 ends the pass.
  BrokenSerial broken;
  assert(pumpAlarmInput(broken, pumpReader, 64, recordLevel) == 0);

  // Link timeout: lost at exactly the timeout, in unsigned arithmetic.
  assert(!alarmLinkLost(29999u, 0u, 30000u));
  assert(alarmLinkLost(30000u, 0u, 30000u));
  assert(!alarmLinkLost(130000u, 100001u, 30000u));
  assert(alarmLinkLost(130001u, 100001u, 30000u));
  // millis() wraps: 0xFFFFF000 to 0x00000FFF is 8191 ms, not lost.
  assert(!alarmLinkLost(0x00000FFFu, 0xFFFFF000u, 30000u));
  assert(alarmLinkLost(0xFFFFF000u + 30000u, 0xFFFFF000u, 30000u));

  // Link lost, level 0: LED on 0-999 ms, off 1000-1999 ms, buzzer off.
  for (uint32_t t = 0; t < 4000u; t += 250u) {
    AlarmOutputs lost0 = alarmOutputsAt(0, true, t, 1000u);
    assert(lost0.led == ((t / 1000u) % 2u == 0u));
    assert(!lost0.buzzer);
  }
  assert(alarmOutputsAt(0, true, 999u, 1000u).led);
  assert(!alarmOutputsAt(0, true, 1000u, 1000u).led);
  assert(!alarmOutputsAt(0, true, 1999u, 1000u).led);
  assert(alarmOutputsAt(0, true, 2000u, 1000u).led);
  // Link lost, level 2: the LED blinks, the buzzer stays on.
  assert(alarmOutputsAt(2, true, 500u, 1000u).led);
  assert(!alarmOutputsAt(2, true, 1500u, 1000u).led);
  assert(alarmOutputsAt(2, true, 500u, 1000u).buzzer);
  assert(alarmOutputsAt(2, true, 1500u, 1000u).buzzer);
  // Link lost, level 1: the LED blinks, the buzzer stays off.
  assert(!alarmOutputsAt(1, true, 1500u, 1000u).led);
  assert(!alarmOutputsAt(1, true, 1500u, 1000u).buzzer);
  // Link up: outputs follow the level and ignore the time.
  for (uint32_t t = 0; t < 4000u; t += 250u) {
    AlarmOutputs steady1 = alarmOutputsAt(1, false, t, 1000u);
    assert(steady1.led && !steady1.buzzer);
    AlarmOutputs steady0 = alarmOutputsAt(0, false, t, 1000u);
    assert(!steady0.led && !steady0.buzzer);
    AlarmOutputs steady2 = alarmOutputsAt(2, false, t, 1000u);
    assert(steady2.led && steady2.buzzer);
  }

  // Only valid commands reach the apply callback, which resets the link
  // timer in the sketch. Malformed and overflowed lines never reach it.
  AlarmLineReader linkReader;
  assert(feedLine(linkReader, "ALARM,7\n") == ROOM_ALARM_INVALID);
  assert(feedLine(linkReader, "HELLO\n") == ROOM_ALARM_INVALID);
  FakeSerial noise("ALARM,7\nHELLO\nALARM,\r\n");
  appliedCount = 0;
  assert(pumpAlarmInput(noise, linkReader, 64, recordLevel) == 22);
  assert(appliedCount == 0);
  std::string overflowed(ROOM_ALARM_LINE_MAX + 5, 'A');
  overflowed += "ALARM,2\n";
  noise.load(overflowed.c_str());
  // Each pass reads at most 64 bytes; no pass applies anything.
  std::size_t pumped = 0;
  while (noise.remaining() > 0) {
    const std::size_t used = pumpAlarmInput(noise, linkReader, 64, recordLevel);
    assert(used > 0 && used <= 64);
    pumped += used;
    assert(appliedCount == 0);
  }
  assert(pumped == overflowed.size());
  noise.load("ALARM,1\n");
  assert(pumpAlarmInput(noise, linkReader, 64, recordLevel) == 8);
  assert(appliedCount == 1 && applied[0] == 1);
  return 0;
}

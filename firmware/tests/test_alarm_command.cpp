// Host test for the alarm command core. Build on Linux with
// g++ -std=c++11 -Wall -Wextra -pedantic firmware/tests/test_alarm_command.cpp
#include "../alarm_command.h"
#include <cassert>
#include <cstring>

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
  for (int i = 0; i < 100; ++i) assert(reader.feed('A') == ROOM_ALARM_NO_LINE);
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
  return 0;
}

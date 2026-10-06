// Zippy's motor watchdog, simulated in Wokwi (Manual 0.6, 5 Oct 2026)
//
// The real ESP32-S3 will sit between Zippy's brain (the Jetson) and the motor driver.
// It lets the motors run ONLY while
//   1. the brain is alive: a heartbeat at least every 200 ms (on the robot: /zippy/heartbeat), and
//   2. no bumper has been hit since the last reset.
// A bumper hit latches: the motors stay off until both bumpers are free, the brain is alive,
// and someone presses RESET.
//
// In Wokwi:  slide switch = the brain (left = running)    keys 1 / 2 = bumpers    key r = RESET
//            green LED = motors allowed                    red LED = bumper fault latched

const int BUMP_L = 4, BUMP_R = 5, RESET_BTN = 6, BRAIN_SWITCH = 7;
const int MOTOR_ENABLE = 15, FAULT_LED = 16;

const unsigned long HEARTBEAT_EVERY_MS = 100;   // the brain sends 10 a second
const unsigned long WATCHDOG_MS = 200;          // two missed heartbeats and the motors stop

unsigned long lastBeat = 0;       // when the last heartbeat arrived
bool gotBeat = false;             // no heartbeat yet = brain not alive yet
unsigned long lastSent = 0;       // pretend brain - when it last sent one
bool fault = false;               // bumper hit, waiting for RESET
bool motorsOn = false;
String why = "starting";

void setup() {
  Serial.begin(115200);
  pinMode(BUMP_L, INPUT_PULLUP);        // buttons connect the pin to GND when pressed
  pinMode(BUMP_R, INPUT_PULLUP);
  pinMode(RESET_BTN, INPUT_PULLUP);
  pinMode(BRAIN_SWITCH, INPUT_PULLUP);  // switch left = pin to GND = brain running
  pinMode(MOTOR_ENABLE, OUTPUT);
  pinMode(FAULT_LED, OUTPUT);
  digitalWrite(MOTOR_ENABLE, LOW);      // safe until proven otherwise
  Serial.println("Zippy watchdog ready. Switch = brain, keys 1/2 = bumpers, r = reset.");
}

// ---------------------------------------------------------------- the pretend brain
// On the real robot this part is gone: heartbeats arrive over micro-ROS from the Jetson.
void pretendBrain(unsigned long now) {
  bool brainRunning = digitalRead(BRAIN_SWITCH) == LOW;
  if (brainRunning && now - lastSent >= HEARTBEAT_EVERY_MS) {
    lastSent = now;
    lastBeat = now;                     // "heartbeat received"
    gotBeat = true;
  }
}

// ---------------------------------------------------------------- the watchdog itself
void loop() {
  unsigned long now = millis();
  pretendBrain(now);

  bool brainAlive = gotBeat && now - lastBeat < WATCHDOG_MS;
  bool bumped = digitalRead(BUMP_L) == LOW || digitalRead(BUMP_R) == LOW;

  if (bumped && !fault) {
    fault = true;
    Serial.printf("%7lu ms  BUMPER hit (%s)\n", now, digitalRead(BUMP_L) == LOW ? "left" : "right");
  }
  if (fault && !bumped && brainAlive && digitalRead(RESET_BTN) == LOW) {
    fault = false;
    Serial.printf("%7lu ms  fault cleared by RESET\n", now);
  }

  bool allow = brainAlive && !fault;
  String reason = fault ? "bumper fault, press RESET" : (brainAlive ? "brain alive" : "brain silent");
  if (allow != motorsOn || reason != why) {
    motorsOn = allow;
    why = reason;
    if (!brainAlive) {
      Serial.printf("%7lu ms  motors %s (%s, last heartbeat %lu ms ago)\n",
                    now, allow ? "ON " : "OFF", reason.c_str(), now - lastBeat);
    } else {
      Serial.printf("%7lu ms  motors %s (%s)\n", now, allow ? "ON " : "OFF", reason.c_str());
    }
  }
  digitalWrite(MOTOR_ENABLE, motorsOn ? HIGH : LOW);
  digitalWrite(FAULT_LED, fault ? HIGH : LOW);
  delay(5);                             // check 200 times a second
}
